import os
from pathspec import PathSpec
from pathspec.patterns.gitwildmatch import GitWildMatchPattern


def format_size(size_bytes: int) -> str:
    """将字节大小格式化为人类可读的字符串 (KB, MB, GB)。"""
    if size_bytes == 0:
        return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = 0
    # 使用 1024 作为基数
    # int(math.log(size_bytes, 1024)) # 这是一个更直接的方法，但需要导入 math
    # 这里用循环代替
    size_val = float(size_bytes)
    while size_val >= 1024 and i < len(size_name) - 1:
        size_val /= 1024.0
        i += 1
    return f"{size_val:.1f}{size_name[i]}"


def get_directory_tree_for_llm(root_dir: str) -> str:
    """
    获取指定目录的文件目录树，过滤.gitignore和隐藏文件，包含文件大小，
    并输出为适合LLM上下文的字符串。

    Args:
        root_dir (str): 要扫描的根目录路径。

    Returns:
        str: 格式化后的目录树字符串，如果出错则返回错误信息。
    """
    abs_root_dir = os.path.abspath(root_dir)

    if not os.path.isdir(abs_root_dir):
        return f"错误：路径 '{root_dir}' 不是一个有效的目录。"

    # 1. 加载 .gitignore 文件
    gitignore_path = os.path.join(abs_root_dir, ".gitignore")
    ignore_patterns = [".git/"]  # 始终忽略 .git 目录

    if os.path.exists(gitignore_path) and os.path.isfile(gitignore_path):
        try:
            with open(gitignore_path, "r", encoding="utf-8") as f:
                for line in f:
                    stripped_line = line.strip()
                    if stripped_line and not stripped_line.startswith("#"):
                        ignore_patterns.append(stripped_line)
        except Exception as e:
            print(f"警告：无法读取 .gitignore 文件 '{gitignore_path}': {e}")

    spec = PathSpec.from_lines(GitWildMatchPattern, ignore_patterns)

    tree_lines = [os.path.basename(abs_root_dir) + "/"]

    def _generate_tree_recursive(current_dir_abs: str, prefix: str):
        try:
            entries = os.listdir(current_dir_abs)
        except OSError as e:
            tree_lines.append(
                f"{prefix}├── [错误: 无法访问 {os.path.basename(current_dir_abs)}/ ({e.strerror})]"
            )
            return

        filtered_entries = []
        for entry_name in entries:
            if entry_name.startswith("."):
                continue

            entry_abs_path = os.path.join(current_dir_abs, entry_name)
            relative_path_to_root = os.path.relpath(entry_abs_path, abs_root_dir)
            normalized_relative_path = relative_path_to_root.replace(os.sep, "/")

            is_dir = os.path.isdir(entry_abs_path)
            path_to_check = normalized_relative_path + ("/" if is_dir else "")

            if spec.match_file(path_to_check) or spec.match_file(
                normalized_relative_path
            ):
                continue

            filtered_entries.append(entry_name)

        filtered_entries.sort()

        dirs = [
            e
            for e in filtered_entries
            if os.path.isdir(os.path.join(current_dir_abs, e))
        ]
        files = [
            e
            for e in filtered_entries
            if not os.path.isdir(os.path.join(current_dir_abs, e))
        ]

        sorted_items = dirs + files

        for i, item_name in enumerate(sorted_items):
            is_last = i == len(sorted_items) - 1
            connector = "└── " if is_last else "├── "
            item_abs_path = os.path.join(current_dir_abs, item_name)

            if os.path.isdir(item_abs_path):
                tree_lines.append(f"{prefix}{connector}{item_name}/")
                new_prefix = prefix + ("    " if is_last else "│   ")
                _generate_tree_recursive(item_abs_path, new_prefix)
            else:  # 是文件
                try:
                    file_size = os.path.getsize(item_abs_path)
                    formatted_size = format_size(file_size)
                    tree_lines.append(
                        f"{prefix}{connector}{item_name} ({formatted_size})"
                    )
                except OSError:
                    # 如果无法获取文件大小（例如权限问题，虽然不常见）
                    tree_lines.append(f"{prefix}{connector}{item_name} [无法获取大小]")

    _generate_tree_recursive(abs_root_dir, "")

    return "\n".join(tree_lines)


if __name__ == "__main__":
    # 创建一个示例目录结构用于测试
    if not os.path.exists("test_project"):
        os.makedirs("test_project/src/utils")
        os.makedirs("test_project/data/raw")
        os.makedirs("test_project/.git")
        os.makedirs("test_project/ignored_folder")

        with open("test_project/main.py", "w") as f:
            f.write("# main script\n" * 50)  # 约 750B
        with open("test_project/README.md", "w") as f:
            f.write("Project Readme\n" * 10)  # 约 150B
        with open("test_project/src/app.py", "w") as f:
            f.write("# app script\n" * 200)  # 约 2.4KB
        with open("test_project/src/utils/helpers.py", "w") as f:
            f.write("# helper functions\n" * 5)  # 约 95B
        with open("test_project/data/raw/data.csv", "w") as f:
            f.write("col1,col2\n" * 1000)  # 约 9.8KB
        with open("test_project/data/processed.log", "w") as f:
            f.write("log data")
        with open("test_project/.hidden_file.txt", "w") as f:
            f.write("hidden")
        with open("test_project/specific_ignore.tmp", "w") as f:
            f.write("temp")
        with open("test_project/ignored_folder/content.txt", "w") as f:
            f.write("ignored content")

        with open("test_project/.gitignore", "w") as f:
            f.write("# Comments are allowed\n")
            f.write("*.log\n")
            f.write("ignored_folder/\n")
            f.write("specific_ignore.tmp\n")
            f.write("dist\n")
            f.write("*.pyc\n")
            f.write("__pycache__/\n")

    print("--- 目录树 (test_project) ---")
    tree_output = get_directory_tree_for_llm("test_project")
    print(tree_output)

    tree_output = get_directory_tree_for_llm("/Users/bytedance/Projects/DTS/dts-mgr")
    print(tree_output)

    # 清理测试目录 (可选)
    import shutil

    if os.path.exists("test_project"):
        shutil.rmtree("test_project")
