import asyncio
import logging
from .project_declaration_map import update_project_declaration_map

# 获取logger
logger = logging.getLogger("copx.test")

async def main():
    logger.info("test")
    decl_map, changed = await update_project_declaration_map("/home/liam/NonProject/mindsdb","~/Documents/Copx")
    logger.info(f"{decl_map}")

if __name__ == "__main__":
    # 设置基本的日志配置
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        filename='/tmp/copx/copx.log'
    )
    asyncio.run(main())
