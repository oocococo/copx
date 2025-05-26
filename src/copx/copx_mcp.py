from mcp.server.fastmcp import FastMCP
import os 
from copx.copx_fastapi import query, CodeQuery
from copx.utils import setup_logging

# 设置默认日志记录器
_log_path = os.environ.get("COPX_LOG_PATH")
logger = setup_logging(_log_path)

_git_path = os.environ.get("COPX_DATA_PATH")
_model = os.environ.get("COPX_MODEL")
_api_key = os.environ.get("COPX_API_KEY")
_base_url = os.environ.get("COPX_BASE_URL")

mcp = FastMCP("CodeExpert", dependencies=["pocketflow","pydantic","tree_sitter","aiofiles","tree_sitter_go","pathspec"])

@mcp.tool(name="Ask Expert",description="Get expert answer about project's codebase")
async def mcp_query(question: str, project_path: str):
    logger.info(f"Received query for project: {project_path}")
    
    assert _git_path is not None
    assert _model is not None
    assert _api_key is not None
    assert _base_url is not None

    return await query(
        CodeQuery(
            project_path=project_path,
            question=question,
            model=_model,
            base_url=_base_url,
            api_key=_api_key,
            git_path=_git_path,
            log_path=_log_path))

def main():
    logger.info("Starting CopX MCP server")
    mcp.run()
