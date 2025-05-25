import re
import os
from typing import Dict, List, Any, Awaitable

from .use_tools import TOOL_FUNC_MAP, TOOL_NAME_LIST

async def grep_declaration_map(
    declaration_map: Dict[str, List[Dict[str, Any]]],
    pattern: str, 
    file_path: str = None, 
    case_sensitive: str = "false"
) -> Dict[str, Any]:
    """
    在 declaration_map 中的符号名称内搜索正则表达式模式。

    Args:
        declaration_map (Dict[str, List[Dict[str, Any]]]): 要搜索的声明映射。
        pattern (str): 要在符号名称中搜索的正则表达式模式。
        file_path (str, optional): 如果提供，则仅在此文件的声明中搜索。
                                   路径应相对于项目根目录，与 declaration_map 中的键匹配。
                                   默认为 None (搜索所有文件)。
        case_sensitive (str, optional): "true" 表示区分大小写的搜索，
                                        "false" 表示不区分大小写。默认为 "false"。

    Returns:
        Dict[str, Any]: 包含搜索结果的字典。
                        结构: {"results": [{"file": "path", "matching_symbols": [...]}]}
                        或 {"error": "message"} 如果发生全局错误。
    """
    is_case_sensitive = isinstance(case_sensitive, str) and case_sensitive.lower() == "true"
    regex_flags = 0 if is_case_sensitive else re.IGNORECASE

    current_decl_map = declaration_map

    if not isinstance(current_decl_map, dict):
        return {
            "error": "global_decl_map 不可用、不是字典，或者 app 模块未正确加载。",
            "results": []
        }

    if not current_decl_map and not file_path: # Map 为空且搜索所有文件
         return {"results": []} # 没有错误，只是没有符号可供搜索

    search_results = []
    files_to_process = []

    if file_path:
        if not isinstance(file_path, str):
            return {"error": "file_path 参数必须是字符串。", "results": []}
        
        if file_path in current_decl_map:
            symbols_list = current_decl_map.get(file_path)
            if isinstance(symbols_list, list):
                files_to_process.append((file_path, symbols_list))
            else:
                return {
                    "error": f"文件 '{file_path}' 在声明映射中的数据格式错误 (不是列表)。",
                    "results": []
                }
        else:
            # 提供了文件路径但在声明映射中未找到
            return {"results": []} # 没有错误，只是此文件没有结果，与 grep 行为一致
    else:
        # 搜索所有文件
        for f_path, symbols_list in current_decl_map.items():
            if isinstance(symbols_list, list): # 检查每个条目
                files_to_process.append((f_path, symbols_list))
            # else: 可以选择跳过格式错误的条目或记录警告

    if not files_to_process: # 如果没有文件可处理 (例如，map 为空或所有条目均格式错误)
        return {"results": []}

    for f_path, symbols_list_for_file in files_to_process:
        matching_symbols_for_file = []
        for symbol_info in symbols_list_for_file:
            if not isinstance(symbol_info, dict) or "name" not in symbol_info:
                # 跳过格式错误的符号条目
                continue

            symbol_name = symbol_info.get("name")
            if not isinstance(symbol_name, str):
                # 跳过名称非字符串的符号
                continue

            try:
                if re.search(pattern, symbol_name, regex_flags):
                    matching_symbols_for_file.append(symbol_info)
            except re.error as e:
                # 此错误适用于整个操作（如果正则表达式无效）
                return {"error": f"无效的正则表达式模式: {e}", "results": []}
            except TypeError:
                # 如果 pattern 或 symbol_name 不是字符串/字节/None，则可能发生
                return {"error": "正则表达式搜索因类型错误失败 (例如 pattern 或 symbol name)。", "results": []}

        if matching_symbols_for_file:
            search_results.append({
                "file": f_path,
                "matching_symbols": matching_symbols_for_file
            })

    return {"results": search_results}


TOOL_NAME_LIST.append("grep_declaration_map")
TOOL_FUNC_MAP["grep_declaration_map"] = grep_declaration_map