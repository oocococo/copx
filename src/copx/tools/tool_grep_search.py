from .use_tools import TOOL_FUNC_MAP, TOOL_NAME_LIST
import asyncio
import json

async def grep_search(
    project_path: str,
    search_pattern: str,
    is_regex: bool = False,
    file_glob_pattern: str = None
) -> dict:
    """
    Performs a general-purpose text search (literal string or regular expression) 
    directly within the content of code files. This is useful for finding where an 
    identifier is used (references), locating specific comments, error messages, 
    or any arbitrary text strings within the codebase.

    Args:
        project_path: The absolute path to the root directory of the project to search.
        search_pattern: The string or regular expression pattern to search for.
        is_regex: (Optional) Set to true if the search_pattern is a regular expression. 
                  Defaults to false (literal string search).
        file_glob_pattern: (Optional) A glob pattern to restrict the search to specific 
                           files or directories (e.g., "*.py", "src/components/**/*.js", 
                           "**/tests/*"). If omitted, searches all files in the codebase.

    Returns:
        A dictionary containing the search results or an error message.
        On success: {"result": [{"file": "path/to/file", "line_number": N, "line_content": "content..."}]}
        On error: {"error": "error message", "details": "optional details", "result": []}
    """
    cmd = ["rg", "--json", "--ignore-case"]

    if not is_regex:
        cmd.append("-F")  # Treat search_pattern as a literal string

    # Glob pattern option must be applied BEFORE the -- separator
    if file_glob_pattern:
        cmd.extend(["-g", file_glob_pattern])

    cmd.extend(["--", search_pattern])
    # Always search in the current working directory (project_path),
    # rg will filter by glob if -g is provided.
    cmd.append(".")

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=project_path
        )
        stdout, stderr = await process.communicate()
    except FileNotFoundError:
        return {
            "error": "Failed to execute ripgrep. Ensure 'rg' is installed and in PATH, and project_path is valid.",
            "result": []
        }
    except Exception as e:
        return {
            "error": f"An unexpected error occurred while executing ripgrep: {e}",
            "result": []
        }

    if process.returncode == 2:  # ripgrep specific error code
        return {
            "error": "ripgrep execution error.",
            "details": stderr.decode('utf-8', errors='replace').strip() if stderr else "No stderr output.",
            "result": []
        }
    
    # process.returncode == 0 (matches found) or 1 (no matches found)
    # Both are non-error cases for the search operation itself.

    parsed_results = []

    if stdout:
        try:
            decoded_stdout = stdout.decode('utf-8', errors='replace')
            for line_str in decoded_stdout.strip().split('\n'):
                if not line_str:
                    continue
                try:
                    message = json.loads(line_str)
                    data = message.get("data", {})
                    msg_type = message.get("type")

                    if msg_type == "match":
                        path_obj = data.get("path")
                        f_path_text = path_obj.get("text") if path_obj else None
                        
                        if not f_path_text:
                            continue # Skip if path is missing
                        
                        line_num = data.get("line_number")
                        
                        lines_obj = data.get("lines")
                        line_content_text = None
                        if lines_obj:
                            line_content_text = lines_obj.get("text")
                            if line_content_text is None: # Try decoding from bytes if text is not present
                                lines_bytes_hex = lines_obj.get("bytes")
                                if lines_bytes_hex:
                                    try:
                                        line_content_text = bytes.fromhex(lines_bytes_hex).decode('utf-8', errors='replace')
                                    except ValueError:
                                        line_content_text = "[Binary content or decoding error]"
                                    except Exception:
                                        line_content_text = "[Line decoding error]"
                        
                        actual_line_content = None
                        if line_content_text:
                            actual_line_content = line_content_text.rstrip('\n')

                        if line_num is not None and actual_line_content is not None:
                            parsed_results.append({
                                "file": f_path_text,
                                "line_number": line_num,
                                "line_content": actual_line_content,
                            })
                except json.JSONDecodeError:
                    # Malformed JSON line from rg, log or skip
                    continue 
                except Exception:
                    # Unexpected error parsing a message, log or skip
                    continue
        except Exception as e:
             # Error decoding stdout itself or splitting lines
            return {
                "error": f"Error processing ripgrep output: {e}",
                "result": []
            }

    return {"result": parsed_results}


TOOL_NAME_LIST.append("grep_search")
TOOL_FUNC_MAP["grep_search"] = grep_search
