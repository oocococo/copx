import re
from typing import Dict, List, Any, Optional, Awaitable # Awaitable kept for consistency if other tools need it

from .use_tools import TOOL_FUNC_MAP, TOOL_NAME_LIST

async def grep_declaration_map(
    declaration_map: Dict[str, List[Dict[str, Any]]],
    search_pattern: str,
    is_regex: bool = False,
    target_declaration_types: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Performs a search (literal string or regular expression) across all identifiers 
    and types in the pre-computed Declaration Map for the entire codebase.

    Args:
        declaration_map (Dict[str, List[Dict[str, Any]]]): The pre-computed declaration map.
            Example: {"module/file.py": [{"name": "my_func", "type": "function", 
                                          "start_point": (0,0), "end_point": (1,10)}, ...]}
        search_pattern (str): The string or regular expression pattern to search for in
                              the declaration identifiers or types.
        is_regex (bool, optional): Set to true if search_pattern is a regular expression.
                                   Defaults to False.
        target_declaration_types (Optional[List[str]], optional): A list of declaration types
                                   to filter the search by (e.g., ["function", "class"]).
                                   If None, searches all types. If an empty list is provided,
                                   it effectively matches no types. Defaults to None.

    Returns:
        Dict[str, Any]: A dictionary containing a list of matches or an error message.
                        Each match includes file path, identifier, type, and code location.
                        Structure: {"results": [
                            {"file_path": str, "identifier": str, "type": str, 
                             "location": {"start_line": int, "start_column": int, 
                                          "end_line": int, "end_column": int}}, ...
                        ]}
                        or {"error": "message"}.
    """
    if not isinstance(declaration_map, dict):
        return {
            "error": "Declaration map is not available or is not a dictionary.",
            "results": []
        }

    results: List[Dict[str, Any]] = []
    compiled_regex = None

    if is_regex:
        try:
            # For regex search, case sensitivity is controlled by the pattern itself (e.g. (?i) for ignore case)
            compiled_regex = re.compile(search_pattern)
        except re.error as e:
            return {"error": f"Invalid regular expression pattern: {e}", "results": []}

    for file_path, symbols_list in declaration_map.items():
        if not isinstance(symbols_list, list):
            # Skip malformed entries in the declaration_map
            continue

        for symbol_info in symbols_list:
            if not isinstance(symbol_info, dict):
                continue

            identifier = symbol_info.get("name")
            symbol_actual_type = symbol_info.get("type") # e.g., "function", "class", "variable"

            # Ensure identifier and symbol_actual_type are strings for searching
            if not isinstance(identifier, str) or not isinstance(symbol_actual_type, str):
                continue

            # 1. Filter by target_declaration_types
            if target_declaration_types is not None:  # If None, this filter is skipped (all types pass)
                if not target_declaration_types:  # Empty list provided (e.g. [])
                    continue  # Effectively matches no types through this filter
                if symbol_actual_type not in target_declaration_types:
                    continue
            
            # 2. Perform search on identifier or symbol_actual_type
            match_found = False
            if is_regex and compiled_regex:
                # Search in identifier OR type
                if compiled_regex.search(identifier) or compiled_regex.search(symbol_actual_type):
                    match_found = True
            elif not is_regex: # Literal string search (case-sensitive substring search)
                if search_pattern in identifier or search_pattern in symbol_actual_type:
                    match_found = True
            
            if match_found:
                location: Dict[str, int] = {}
                start_point = symbol_info.get("start_point")
                end_point = symbol_info.get("end_point")

                if isinstance(start_point, (list, tuple)) and len(start_point) >= 1 and isinstance(start_point[0], int):
                    location["start_line"] = start_point[0] + 1  # 0-indexed to 1-indexed
                if isinstance(start_point, (list, tuple)) and len(start_point) >= 2 and isinstance(start_point[1], int):
                    location["start_column"] = start_point[1] + 1 # 0-indexed to 1-indexed
                
                if isinstance(end_point, (list, tuple)) and len(end_point) >= 1 and isinstance(end_point[0], int):
                    location["end_line"] = end_point[0] + 1
                if isinstance(end_point, (list, tuple)) and len(end_point) >= 2 and isinstance(end_point[1], int):
                    location["end_column"] = end_point[1] + 1

                results.append({
                    "file_path": file_path,
                    "identifier": identifier,
                    "type": symbol_actual_type,
                    "location": location
                })

    return {"results": results}


# Register the tool (ensure this matches how tools are registered in your project)
# The tool name in the prompt is 'grep_declaration_map'.
# If the key in TOOL_FUNC_MAP or entry in TOOL_NAME_LIST was different, it has been standardized here.
if "grep_declaration_map" not in TOOL_NAME_LIST: # Avoid duplicate entries if script re-run
    TOOL_NAME_LIST.append("grep_declaration_map")
TOOL_FUNC_MAP["grep_declaration_map"] = grep_declaration_map
