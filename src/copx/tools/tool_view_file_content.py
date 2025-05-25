import os
import aiofiles
import asyncio
# from tools.use_tools import TOOL_FUNC_MAP, TOOL_NAME_LIST # 旧的导入方式
from .use_tools import TOOL_FUNC_MAP, TOOL_NAME_LIST # 新的相对导入方式

async def view_file_content(project_path: str, file_path: str, start_line: str = None, end_line: str = None) -> dict:
    """
    Views the actual content of a specific file within a project.
    Parameters:
    - project_path: (string, required) The absolute path to the project's root directory.
    - file_path: (string, required) The path to the code file, relative to project_path if not absolute.
    - start_line: (string, optional) The starting line number (1-indexed) to view.
                  If omitted and end_line is also omitted, the entire file is returned.
                  If end_line is omitted, content from start_line to the end of the file is returned.
    - end_line: (string, optional) The ending line number (1-indexed) to view.
                If omitted and start_line is also omitted, the entire file is returned.
                If start_line is omitted, content from the beginning of the file to end_line is returned.
    Returns:
    A dictionary containing the resolved file_path, content, error (if any), processed line numbers, and total lines.
    """
    if not os.path.isabs(file_path):
        actual_file_path = os.path.join(project_path, file_path)
    else:
        actual_file_path = file_path

    if not os.path.isfile(actual_file_path):
        return {
            "file_path": actual_file_path,
            "content": None,
            "error": "File not found.",
            "start_line_processed": None,
            "end_line_processed": None,
            "total_lines_in_file": None
        }

    s_line_int: int = None
    e_line_int: int = None

    try:
        if start_line is not None:
            s_line_int = int(start_line)
            if s_line_int <= 0:
                return {"file_path": actual_file_path, "content": None, "error": "start_line must be a positive integer.", "start_line_processed": start_line, "end_line_processed": end_line, "total_lines_in_file": None}
        if end_line is not None:
            e_line_int = int(end_line)
            if e_line_int <= 0:
                return {"file_path": actual_file_path, "content": None, "error": "end_line must be a positive integer.", "start_line_processed": start_line, "end_line_processed": end_line, "total_lines_in_file": None}
        
        if s_line_int is not None and e_line_int is not None and s_line_int > e_line_int:
            return {"file_path": actual_file_path, "content": None, "error": "start_line cannot be greater than end_line.", "start_line_processed": s_line_int, "end_line_processed": e_line_int, "total_lines_in_file": None}

    except ValueError:
        return {"file_path": actual_file_path, "content": None, "error": "Invalid line numbers. Must be integers.", "start_line_processed": start_line, "end_line_processed": end_line, "total_lines_in_file": None}

    try:
        async with aiofiles.open(actual_file_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = await f.readlines()
        
        total_lines = len(lines)

        # Determine effective start and end indices for slicing (0-based)
        # Default to full file if no line numbers are given
        start_index = (s_line_int - 1) if s_line_int is not None else 0
        end_index = e_line_int if e_line_int is not None else total_lines
        
        # Validate indices against actual file lines
        if start_index < 0: # Should have been caught by s_line_int <= 0
            start_index = 0 
        
        # If start_line is beyond the file, return empty
        if start_index >= total_lines and total_lines > 0 : # if total_lines is 0, start_index can be 0
             selected_lines = []
        elif start_index > end_index and e_line_int is not None : # only if end_line is specified and start is greater
             selected_lines = []
        else:
            # Ensure end_index does not exceed total_lines
            if end_index > total_lines:
                end_index = total_lines
            selected_lines = lines[start_index:end_index]
            
        return {
            "file_path": actual_file_path,
            "content": "".join(selected_lines),
            "error": None,
            "start_line_processed": s_line_int,
            "end_line_processed": e_line_int,
            "total_lines_in_file": total_lines
        }

    except Exception as e:
        return {
            "file_path": actual_file_path,
            "content": None,
            "error": f"Error reading file: {str(e)}",
            "start_line_processed": s_line_int,
            "end_line_processed": e_line_int,
            "total_lines_in_file": None 
        }

# Register the tool
TOOL_NAME_LIST.append("view_file_content")
TOOL_FUNC_MAP["view_file_content"] = view_file_content