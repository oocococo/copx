from mcp.server.fastmcp import FastMCP
import os 
from copx.copx_fastapi import query,CodeQuery

_git_path = os.environ.get("COPX_DATA_PATH")
_model = os.environ.get("COPX_MODEL")
_api_key = os.environ.get("COPX_API_KEY")
_base_url = os.environ.get("COPX_BASE_URL")

mcp = FastMCP("CodeExpert", dependencies=["pocketflow","pydantic","tree_sitter","aiofiles","tree_sitter_go","pathspec"])

@mcp.tool(name="Ask Expert",description="Get expert answer about project's codebase")
async def mcp_query(question: str,project_path: str):
    assert _git_path is not None
    assert _model is not None
    assert _api_key is not None
    assert _base_url is not None
 
    return await query(
        CodeQuery(
            project_path=project_path,
            question=question,
            model=_model,
            api_base=_base_url,
            api_key=_api_key,
            git_path=_git_path))

def main():
    mcp.run()
