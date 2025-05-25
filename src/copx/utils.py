import os
from pathspec import PathSpec
from pathspec.patterns.gitwildmatch import GitWildMatchPattern
import litellm


class LLMClient:
    def __init__(self, model_id: str, base_url: str = None, api_key: str = None):
        self.model_id = model_id
        self.base_url = base_url
        self.api_key = api_key
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    async def call_llm(self, messages):
        # print(f"Sending messages to LLM: {messages}")
        response = await litellm.acompletion(
            model=self.model_id,
            messages=messages,
            api_base=self.base_url,
            api_key=self.api_key,
        )
        response_content = response.choices[0].message.content
        # print(f"Received response from LLM: {response_content}")

        # 统计 token 数量
        if response.usage:
            self.total_input_tokens += response.usage.prompt_tokens
            self.total_output_tokens += response.usage.completion_tokens
        
        return response_content

    def get_token_usage(self):
        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
        }


def iter_project_files(
    root_dir: str, include_hidden: bool = False, extra_ignore_patterns: list = None
):
    """
    遵循 .gitignore 的递归遍历生成器，等价 os.walk
    - 返回 (dirpath, dirnames, filenames)
    - 可指定是否包含隐藏文件（默认不包含）
    - 可额外附加ignore pattern
    """
    abs_root = os.path.abspath(root_dir)
    # 加载 .gitignore
    gitignore_path = os.path.join(abs_root, ".gitignore")
    ignore_patterns = [".git/"]  # 始终忽略 .git 目录

    if extra_ignore_patterns:
        ignore_patterns += extra_ignore_patterns

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

    def _walk(dir_path):
        try:
            entries = os.listdir(dir_path)
        except Exception as e:
            print(f"无法列举目录 {dir_path}: {e}")
            return

        dirs = []
        files = []
        for entry in entries:
            # 是否隐藏文件过滤
            if not include_hidden and entry.startswith("."):
                continue
            abs_entry = os.path.join(dir_path, entry)
            rel_entry = os.path.relpath(abs_entry, abs_root).replace(os.sep, "/")
            is_dir = os.path.isdir(abs_entry)
            matched = spec.match_file(rel_entry + ("/" if is_dir else ""))
            if matched:
                continue

            if is_dir:
                dirs.append(entry)
            else:
                files.append(entry)

        # sort：保证一致性
        dirs.sort()
        files.sort()

        yield dir_path, dirs.copy(), files.copy()

        for subdir in dirs:
            yield from _walk(os.path.join(dir_path, subdir))

    yield from _walk(abs_root)


# ========== 用法示例 ==========
# for dirpath, dirnames, filenames in iter_project_files("/path/to/project"):
#     print("目录:", dirpath)
#     print("子目录:", dirnames)
#     print("文件:", filenames)
