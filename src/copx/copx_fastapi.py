import fastapi
import os # Added import for os module
from pydantic import BaseModel
from copx.project_declaration_map import update_project_declaration_map
from copx.flow import run_agent
from copx.utils import LLMClient, setup_logging  # 添加setup_logging导入


class CodeQuery(BaseModel):
    project_path: str
    question: str
    model: str = ""
    base_url: str = ""
    api_key: str = ""
    git_path: str = ""
    log_path: str = ""  # 添加日志文件路径参数


app = fastapi.FastAPI()
# 设置默认日志记录器
logger = setup_logging()


@app.post("/query")
async def query(query: CodeQuery):
        
    # 如果提供了自定义日志路径，则重新配置日志系统
    if query.log_path:
        if not os.path.isabs(query.log_path):
            return "must provide absolute log path"
        global logger
        logger = setup_logging(query.log_path)
 
    if not os.path.isabs(query.project_path):
        logger.error(f"Invalid project path: {query.project_path}")
        return "must provide absolute project path"
    
    if not os.path.isabs(query.git_path):
        logger.error(f"Invalid git path: {query.git_path}")
        return "must provide absolute git path"
    
    proj_path = query.project_path
    git_path = query.git_path

    # Ensure query.git_path exists, if not, create it
    if not os.path.exists(git_path):
        os.makedirs(git_path)
        logger.info(f"Reindexed files: {git_path}")

    decl_map, changed = await update_project_declaration_map(proj_path, git_path)
    logger.info(f"Modified files: {changed}")
    llm_client = LLMClient(
        model_id=query.model, base_url=query.base_url, api_key=query.api_key
    )
    shared = await run_agent(proj_path, query.question, decl_map, llm_client)
    logger.info(f"Token usage: {llm_client.get_token_usage()}")
    return shared["answer"]

