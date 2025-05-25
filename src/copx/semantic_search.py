import os
from tree_sitter import Language, Parser
import tree_sitter_go
import pathspec
import lancedb
from lancedb.pydantic import LanceModel, Vector
from lancedb.embeddings import EmbeddingFunctionRegistry, EmbeddingFunction
import numpy as np


GO_LANGUAGE = Language(tree_sitter_go.language())


def load_gitignore_patterns(dir_path):
    gitignore_path = os.path.join(dir_path, ".gitignore")
    if not os.path.isfile(gitignore_path):
        return pathspec.PathSpec.from_lines("gitwildmatch", [])
    with open(gitignore_path, "r") as f:
        lines = f.readlines()
    return pathspec.PathSpec.from_lines("gitwildmatch", lines)


def is_ignored(root, rel_path, spec):
    rel_path_posix = rel_path.replace(os.sep, "/")
    return spec.match_file(rel_path_posix)


def get_go_functions_and_methods_from_file(filepath):
    with open(filepath, "rb") as f:
        code = f.read()
    parser = Parser(GO_LANGUAGE)
    tree = parser.parse(code)
    root_node = tree.root_node
    result = []

    def traverse(node):
        if node.type == "function_declaration":
            name_node = next((c for c in node.children if c.type == "identifier"), None)
            if name_node:
                func_name = code[name_node.start_byte : name_node.end_byte].decode(
                    "utf-8"
                )
                result.append((filepath, func_name))
        elif node.type == "method_declaration":
            receiver_type = None
            for child in node.children:
                if child.type == "parameter_list":
                    params = [
                        c for c in child.children if c.type != "," and c.type != ")"
                    ]
                    if params:
                        param = params[0]
                        for part in param.children[::-1]:
                            if part.type == "type_identifier":
                                receiver_type = code[
                                    part.start_byte : part.end_byte
                                ].decode("utf-8")
                                break
                            elif part.type == "pointer_type":
                                for p in part.children:
                                    if p.type == "type_identifier":
                                        receiver_type = code[
                                            p.start_byte : p.end_byte
                                        ].decode("utf-8")
                                        break
                                break
                    break
            name_node = next((c for c in node.children if c.type == "identifier"), None)
            if receiver_type and name_node:
                method_name = code[name_node.start_byte : name_node.end_byte].decode(
                    "utf-8"
                )
                result.append((filepath, receiver_type + method_name))
        for child in node.children:
            traverse(child)

    traverse(root_node)
    return result


def collect_go_functions_methods_from_dir(root_dir):
    spec = load_gitignore_patterns(root_dir)
    results = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = [
            d
            for d in dirnames
            if not is_ignored(
                root_dir, os.path.relpath(os.path.join(dirpath, d), root_dir), spec
            )
        ]
        for filename in filenames:
            rel_file = os.path.relpath(os.path.join(dirpath, filename), root_dir)
            if is_ignored(root_dir, rel_file, spec):
                continue
            if filename.endswith(".go"):
                file_path = os.path.join(dirpath, filename)
                names = get_go_functions_and_methods_from_file(
                    file_path,
                )
                results.extend(names)
    return results


# 初始化 embedding 模型（可根据需求更换模型）
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

# LanceDB 数据库地址 & 表名
DB_URI = "./lancedb_dir"
TABLE_NAME = "code_methods"


MODEL_NAME = "nomic-embed-text"
registry = EmbeddingFunctionRegistry.get_instance()
model = registry.get("ollama").create(name=MODEL_NAME, host="http://100.68.29.74:11434")
EMBEDDING_DIM = 768
MAX_TOKENS = 8192


class Method(LanceModel):
    path: str
    method: str = model.SourceField()
    embeddings: Vector(EMBEDDING_DIM) = model.VectorField()


# 1. 初始化数据库与表格
def init_table():
    db = lancedb.connect(DB_URI)
    if TABLE_NAME not in db.table_names():
        table = db.create_table(
            TABLE_NAME, schema=Method, mode="overwrite", on_bad_vectors="drop"
        )
    return db.open_table(TABLE_NAME)


# 2. 方法：插入数据
def insert_methods(method_tuples):
    """
    method_tuples: List of (path, method_name)
    """
    table = init_table()
    records = []
    for i, (path, method) in enumerate(method_tuples):
        records.append({"path": path, "method": method})
    table.add(records)


# 3. 基于语义的搜索
def search_methods(query, top_k=5):
    """
    query: 输入查询字符串
    top_k: 返回最相似的数量
    """
    table = init_table()

    results = table.search(query=query).limit(top_k).to_list()
    return [
        {"path": r["path"], "method": r["method"], "score": float(r["_distance"])}
        for r in results
    ]


# DEMO 示例：初始化和搜索
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python script.py <目录路径>")
        exit(1)

    # 首次插入数据
    # 这里假设你已经有函数列表: method_tuples = [(path1, method1), (path2, method2), ...]
    # 比如: method_tuples = [("foo/bar.go", "AddUser"), ("foo/bar.go", "DeleteUser")]
    method_tuples = collect_go_functions_methods_from_dir(sys.argv[1])

    for filepath, method_name in method_tuples:
        print(method_name)
    exit(0)
    insert_methods(method_tuples)

    # 搜索接口
    q = input("输入要查找的描述(如 '添加用户'): ")
    candidates = search_methods(q, top_k=3)
    print("Top results:")
    for item in candidates:
        print(
            f"路径: {item['path']} 方法: {item['method']} 相似度: {item['score']:.4f}"
        )
