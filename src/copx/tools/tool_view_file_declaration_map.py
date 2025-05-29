from .use_tools import TOOL_FUNC_MAP, TOOL_NAME_LIST
from typing import Dict, List, Any
from copx.symbal_extractor.symbol_extractor import extract_symbols_from_file # Assuming this can be awaited or is already async
import logging

# 获取logger
logger = logging.getLogger("copx.tools.tool_view_file_declaration_map")

async def view_file_declaration_map(declaration_map: Dict[str, List[Dict[str, Any]]], file_path: str) -> Any:
    normalized_file_path = file_path.lstrip('./')
    declarations = declaration_map.get(normalized_file_path)
    if declarations is None:
        logger.info("File not found in global_decl_map. Extracting symbols from file...")
        return await extract_symbols_from_file(file_path)
    return declarations


TOOL_NAME_LIST.append("view_file_declaration_map")
TOOL_FUNC_MAP["view_file_declaration_map"] = view_file_declaration_map
