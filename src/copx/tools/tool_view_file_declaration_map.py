from .use_tools import TOOL_FUNC_MAP, TOOL_NAME_LIST
from typing import Dict, List, Any, Awaitable # Added Any for declaration_map type hint
from copx.symbal_extractor.symbol_extractor import extract_symbols_from_file # Assuming this can be awaited or is already async
import asyncio

async def view_file_declaration_map(declaration_map: Dict[str, List[Dict[str, Any]]], file_path: str) -> Any:
    declarations = declaration_map.get(file_path)
    if declarations is None:
        print("File not found in global_decl_map. Extracting symbols from file...")
        return await extract_symbols_from_file(file_path)
    return declarations


TOOL_NAME_LIST.append("view_file_declaration_map")
TOOL_FUNC_MAP["view_file_declaration_map"] = view_file_declaration_map
