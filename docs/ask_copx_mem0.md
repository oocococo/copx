`mem0` 项目通过一个复杂的多层系统来组织记忆。其核心是使用向量数据库进行记忆的存储和语义搜索，并通过 LLM 驱动的推理管道进行智能处理和生命周期管理。此外，可以选择使用图数据库进行结构化知识表示，并使用 SQLite 数据库跟踪记忆操作历史。

以下是记忆组织方式的详细说明：

1.  **核心存储：向量数据库**
    *   记忆主要存储在可配置的向量数据库（例如 FAISS、Qdrant、Chroma、Pinecone）中。这由 `mem0/memory/main.py` 中的 `Memory` 和 `AsyncMemory` 类管理。各种向量数据库的特定客户端实现在 `mem0/vector_stores/` 中。
    *   每个记忆项通常包括：
        *   **文本内容**：正在存储的实际信息。
        *   **嵌入（Embedding）**：表示文本内容的数字向量，由可配置的嵌入模型（提供者在 `mem0/embeddings/` 中）生成。这对于语义搜索至关重要。
        *   **唯一 ID**：记忆项的 UUID。
        *   **元数据**：与每个记忆项关联的字典，包含 `user_id`、`agent_id`、`run_id`（用于范围界定）、`role`、`actor_id`、`created_at`、`updated_at` 时间戳、数据的 `hash` 以及任何自定义元数据。这在 `mem0/memory/main.py` 中的 `_add_to_vector_store` 方法（第 292-301、787-790 行）中很明显，该方法在存储前准备元数据。

2.  **LLM 驱动的推理管道（用于 `infer=True` 模式）**
    *   当使用 `infer=True` 标志添加记忆时（`Memory.add` 方法中的默认设置，`mem0/memory/main.py` 第 178-275 行），LLM 会处理输入：
        *   **事实提取**：使用 `mem0/configs/prompts.py` 中的 `FACT_RETRIEVAL_PROMPT` 和 LLM 从输入消息中提取关键“事实”。`mem0/memory/main.py` 中的 `_add_to_vector_store` 方法（第 314-335 行）显示了此过程。
        *   **记忆更新逻辑**：将这些新事实与现有记忆（从向量存储中检索）进行比较。`DEFAULT_UPDATE_MEMORY_PROMPT`（或 `mem0/configs/prompts.py` 中的自定义变体）指导 LLM 决定是 `ADD`（添加）事实作为新记忆、`UPDATE`（更新）现有记忆、`DELETE`（删除）旧记忆，还是 `NONE`（无更改）。`mem0/memory/main.py` 中的 `_add_to_vector_store` 方法（第 367-422 行）详细说明了此决策过程以及对 `_create_memory`、`_update_memory` 或 `_delete_memory` 的后续调用。
    *   该管道允许对信息进行智能提炼和管理。

3.  **原始存储（用于 `infer=False` 模式）**
    *   如果在 `add` 方法中指定 `infer=False`，则绕过 LLM 处理管道。消息直接被嵌入并存储为新的记忆项。这在 `mem0/memory/main.py` 中 `_add_to_vector_store` 方法的初始部分（第 278-312 行）处理。

4.  **基于图的记忆（可选）**
    *   系统支持可选的图数据库（例如 Memgraph、Neo4j）将记忆存储为结构化知识图。这通过配置启用，如 `Memory` 类的 `__init__` 方法所示（`mem0/memory/main.py`，第 131-142 行）。
    *   `MemoryGraph` 类（在 `mem0/memory/graph_memory.py` 或 `mem0/memory/memgraph_memory.py` 中）使用带有专门工具（例如 `mem0/graphs/tools.py` 中的 `NodesMemoryTool`、`RelationsMemoryTool`）的 LLM 从文本中提取实体（节点）及其关系。
    *   然后将这些实体和关系持久化到图数据库中。`mem0/memory/graph_memory.py` 中的 `add` 方法（第 68-86 行）调用诸如 `_retrieve_nodes_from_data` 和 `_establish_nodes_relations_from_data` 之类的辅助函数进行提取，并调用 `_add_entities` 进行存储。

5.  **程序记忆**
    *   支持特殊的 `memory_type="procedural_memory"`。在 `add` 方法中指定时（`mem0/memory/main.py`，第 242-244 行），它使用 `mem0/configs/prompts.py` 中的 `PROCEDURAL_MEMORY_SYSTEM_PROMPT`。
    *   此提示指导 LLM 创建一个详细的、逐字记录的代理操作及其结果的日志，并将其构造成一个包含概述和编号步骤的摘要。然后存储此结构化摘要。

6.  **历史跟踪**
    *   记忆操作（创建、更新、删除）记录到本地 SQLite 数据库中。这由 `SQLiteManager`（可能在 `mem0/memory/storage.py` 中）管理，并在 `Memory` 类中初始化为 `self.db`（`mem0/memory/main.py`，第 127 行）。诸如 `_create_memory`、`_update_memory` 和 `_delete_memory` 之类的方法显示了对 `self.db.insert_memory_history()` 的调用。

7.  **检索**
    *   使用 `mem0/memory/main.py` 中的 `search` 方法（第 601-665 行）检索记忆。
    *   查询字符串被嵌入，向量存储（在 `_search_vector_store` 内调用的 `self.vector_store.search()`，第 667-702 行）执行相似性搜索。
    *   可以应用基于元数据（例如 `user_id`、`agent_id`）的过滤器来缩小搜索范围。`_build_filters_and_metadata`（`mem0/memory/main.py`，第 36-105 行）用于准备这些过滤器。
    *   如果启用了图数据库，也会查询它（例如 `self.graph.search`）。
    *   结果被格式化，将一些元数据键提升到返回记忆项的顶层，其他键则嵌套在“metadata”键下。

总而言之，mem0 采用混合策略：用于稳健语义搜索的向量嵌入，用于智能事实提取和记忆生命周期管理的 LLM，用于互连结构化知识的可选图数据库，以及用于操作历史的 SQLite 数据库。元数据对于过滤、范围界定和情境化记忆至关重要。