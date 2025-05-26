import os
import logging
from pathspec import PathSpec
from pathspec.patterns.gitwildmatch import GitWildMatchPattern
import litellm


def setup_logging(log_path=None):
    """
    设置日志系统
    - log_path: 日志文件路径，如果为None则使用默认路径 /tmp/copx/copx.log
    """
    if log_path is None:
        log_path = "/tmp/copx/copx.log"
    
    # 确保日志目录存在
    log_dir = os.path.dirname(log_path)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 配置日志格式
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.FileHandler(log_path),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger("copx")


class LLMClient:
    def __init__(self, model_id: str, base_url: str = None, api_key: str = None):
        self.model_id = model_id
        self.base_url = base_url
        self.api_key = api_key
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.logger = logging.getLogger("copx.llm")

    async def call_llm(self, messages):
        # self.logger.debug(f"Sending messages to LLM: {messages}")
        response = await litellm.acompletion(
            model=self.model_id,
            messages=messages,
            api_base=self.base_url,
            api_key=self.api_key,
        )
        response_content = response.choices[0].message.content
        # self.logger.debug(f"Received response from LLM: {response_content}")

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
    logger = logging.getLogger("copx.files")
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
            logger.warning(f"警告：无法读取 .gitignore 文件 '{gitignore_path}': {e}")

    spec = PathSpec.from_lines(GitWildMatchPattern, ignore_patterns)

    def _walk(dir_path):
        try:
            entries = os.listdir(dir_path)
        except Exception as e:
            logger.warning(f"无法列举目录 {dir_path}: {e}")
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
#     logger.debug(f"目录: {dirpath}")
#     logger.debug(f"子目录: {dirnames}")
#     logger.debug(f"文件: {filenames}")
