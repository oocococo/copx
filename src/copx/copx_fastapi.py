import fastapi
import os # Added import for os module
from pydantic import BaseModel
from copx.project_declaration_map import update_project_declaration_map
from copx.flow import run_agent
from copx.utils import LLMClient  # Add LLMClient import


class CodeQuery(BaseModel):
    project_path: str
    question: str
    model: str = ""
    base_url: str = ""
    api_key: str = ""
    git_path: str = ""


app = fastapi.FastAPI()


@app.post("/query")
async def query(query: CodeQuery):
    proj_path = query.project_path
    git_path = os.path.expanduser(query.git_path) # Expand user for git_path

    # Ensure query.git_path exists, if not, create it
    if not os.path.exists(git_path):
        os.makedirs(git_path)
        print(f"Reindexed files: {git_path}")

    decl_map, changed = await update_project_declaration_map(proj_path, git_path)
    print("Modified files:", changed)
    llm_client = LLMClient(
        model_id=query.model, base_url=query.base_url, api_key=query.api_key
    )
    shared = await run_agent(proj_path, query.question, decl_map, llm_client)
    print(f"Token usage: {llm_client.get_token_usage()}")
    return shared["answer"]
