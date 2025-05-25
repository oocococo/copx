# /Users/bytedance/Projects/Hobby/CodeQA/tools/__init__.py

"""
这个 __init__.py 文件确保当 'tools' 包或其任何子模块
（如 use_tools）首次被导入时，所有的工具模块都会被导入。
这将触发每个工具模块内的注册逻辑。
"""

# 首先导入定义了 TOOL_NAME_LIST 和 TOOL_FUNC_MAP 的模块。
# 这使得这些变量在 'use_tools' 模块的命名空间中存在。
# 注意这里使用相对导入。
from . import use_tools

# 现在，导入所有单独的工具模块。
# 导入这些模块的行为会执行它们顶层的代码，
# 这些代码应该会向 'use_tools' 中定义的 TOOL_NAME_LIST 和 TOOL_FUNC_MAP 添加工具。
# 这些导入也必须使用相对路径。
from . import tool_grep_declaration_map
from . import tool_grep_search
from . import tool_view_file_content
from . import tool_view_file_declaration_map

# 为了方便 'tools' 包的用户，您可以在包级别暴露关键的变量和函数。
# 这意味着用户可以执行 'from tools import TOOL_NAME_LIST'
# 而不是 'from tools.use_tools import TOOL_NAME_LIST'。
TOOL_NAME_LIST = use_tools.TOOL_NAME_LIST
TOOL_FUNC_MAP = use_tools.TOOL_FUNC_MAP
process_text_with_tools = use_tools.process_text_with_tools
ToolCall = use_tools.ToolCall
invoke_tool = use_tools.invoke_tool
extract_tool_calls = use_tools.extract_tool_calls

# 定义 __all__ 来指定 'from tools import *' 应该导入哪些名称。
# 这是包接口的良好实践。
__all__ = [
    "TOOL_NAME_LIST",
    "TOOL_FUNC_MAP",
    "process_text_with_tools",
    "ToolCall",
    "invoke_tool",
    "extract_tool_calls",
    # 如果子模块也是公共 API 的一部分，您可能也想暴露它们
    # "use_tools",
    # "tool_grep_declaration_map",
    # "tool_grep_search",
    # "tool_view_file_content",
    # "tool_view_file_declaration_map",
]