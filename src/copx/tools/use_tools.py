import asyncio
import re
from typing import List, Dict, Callable, Any, Awaitable

# 1. 工具名列表（可随时扩展）
TOOL_NAME_LIST = []

# 2. 工具名称->函数 的映射（业务层可用）
TOOL_FUNC_MAP: Dict[str, Callable[..., Awaitable[Any]]] = {}


# 3. 工具调用实体的类型
class ToolCall:
    def __init__(self, name: str, params: Dict[str, str]):
        self.name = name
        self.params = params

    def __repr__(self):
        return f"ToolCall(name={self.name}, params={self.params})"


# 4. 分析一段文本，提取所有工具调用的信息
def extract_tool_calls(text: str, tool_names: List[str]) -> List[ToolCall]:
    tool_calls = []
    # 为每个工具名编译正则
    patterns = {
        name: re.compile(
            rf"<{name}>(.*?)</{name}>",
            re.DOTALL,
        )
        for name in tool_names
    }

    idx = 0
    while idx < len(text):
        found = False
        for tool, pattern in patterns.items():
            match = pattern.search(text, idx)
            if match:
                found = True
                xml_str = match.group(1)
                params = _parse_params(xml_str)
                tool_calls.append(ToolCall(tool, params))
                idx = match.end()  # 下一轮从后面继续
                break
        if not found:
            break  # 没有更多标签了
    return tool_calls


# 5. 提取参数（内层 tag 及值）：支持任意参数名
def _parse_params(xml_fragment: str) -> Dict[str, str]:
    # 匹配 <tag>value</tag>
    pattern = re.compile(r"<(\w+)>(.*?)</\1>", re.DOTALL)
    params = {m.group(1): m.group(2).strip() for m in pattern.finditer(xml_fragment)}
    return params


# 6. 调用工具函数
async def invoke_tool(tool_call: ToolCall) -> Any:
    func = TOOL_FUNC_MAP.get(tool_call.name)
    if not func:
        raise ValueError(f"Unrecognized tool: {tool_call.name}")
    return await func(**tool_call.params)


# 7. 模块接口：完整流程
async def process_text_with_tools(text: str) -> List[Any]:
    tool_calls = extract_tool_calls(text, TOOL_NAME_LIST)
    results = []
    for call in tool_calls:
        try:
            res = await invoke_tool(call)
            results.append(res)
        except Exception as e:
            results.append(f"Tool {call.name} failed: {str(e)}")
    return results
