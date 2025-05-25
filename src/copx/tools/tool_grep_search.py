from .use_tools import TOOL_FUNC_MAP, TOOL_NAME_LIST
import asyncio
import json

async def grep_search(
    project_path: str,  # 新增的必选参数
    pattern: str,
    file_path: str = None,
    case_sensitive: str = "false"
) -> dict:
    """
    使用 ripgrep (rg) 在指定的项目路径中搜索文件内容。

    Args:
        project_path: 要搜索的项目根目录的绝对路径。
        pattern: 用于搜索的正则表达式模式。
        file_path: (可选) 相对于 project_path 的特定文件或子目录路径。
                   如果为 None，则搜索整个 project_path。
        case_sensitive: (可选) 是否区分大小写。
                        "true" 表示区分大小写，"false" (默认) 表示不区分。

    Returns:
        一个字典，包含搜索结果或错误信息。
        成功时: {"result": [{"file": "path/to/file", "matches": [{"line": N, "span": [start_byte, end_byte], "match": "text"}]}]}
        错误时: {"error": "error message", "details": "optional details", "result": []}
    """
    is_case_sensitive = isinstance(case_sensitive, str) and case_sensitive.lower() == "true"

    cmd = ["rg", "--json"]
    if is_case_sensitive:
        cmd.append("--case-sensitive")
    else:
        cmd.append("--ignore-case")  

    cmd.append("--")  # 确保 pattern 被视为模式，即使它以 '-' 开头
    cmd.append(pattern)

    if file_path:
        cmd.append(file_path)

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
            "error": "执行 ripgrep 失败。请确保 'rg' 已安装并在 PATH 中，且 project_path 有效。",
            "result": []
        }
    except Exception as e:
        return {
            "error": f"执行 ripgrep 时发生意外错误: {e}",
            "result": []
        }

    if process.returncode == 2:
        return {
            "error": "ripgrep 执行错误。",
            "details": stderr.decode().strip() if stderr else "No stderr output.",
            "result": []
        }

    results_by_file = {}

    if stdout:
        for line in stdout.decode().strip().split('\n'):
            if not line:
                continue
            try:
                message = json.loads(line)
                data = message.get("data", {})
                msg_type = message.get("type")

                if msg_type == "begin":
                    f_path_data = data.get("path", {})
                    f_path = f_path_data if isinstance(f_path_data, str) else f_path_data.get("text")
                    if f_path and f_path not in results_by_file:
                        results_by_file[f_path] = []
                
                elif msg_type == "match":
                    f_path_data = data.get("path", {})
                    f_path = f_path_data if isinstance(f_path_data, str) else f_path_data.get("text")
                    if not f_path:
                        continue

                    if f_path not in results_by_file:
                        results_by_file[f_path] = []
                    
                    line_num = data.get("line_number")
                    submatches = data.get("submatches")
                    if not submatches:
                        continue
                    
                    primary_submatch = submatches[0]
                    match_text_data = primary_submatch.get("match", {})
                    match_text = match_text_data if isinstance(match_text_data, str) else match_text_data.get("text")
                    
                    abs_offset_line = data.get("absolute_offset", 0)
                    match_start_in_line = primary_submatch.get("start", 0)
                    match_end_in_line = primary_submatch.get("end", 0)

                    span_start_file_bytes = abs_offset_line + match_start_in_line
                    span_end_file_bytes = abs_offset_line + match_end_in_line

                    if line_num is not None and match_text is not None:
                        results_by_file[f_path].append({
                            "line": line_num,
                            "span": [span_start_file_bytes, span_end_file_bytes],
                            "match": match_text,
                        })
            except json.JSONDecodeError:
                continue
            except Exception:
                continue

    output_list = []
    for f_path, matches_list in results_by_file.items():
        output_list.append({
            "file": f_path,
            "matches": matches_list
        })
    
    return {"result": output_list}


TOOL_NAME_LIST.append("grep_search")
TOOL_FUNC_MAP["grep_search"] = grep_search
