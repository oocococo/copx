根据我查阅的文档，这个项目 (Mem0) 通过以下方式组织记忆：

Mem0 区分短期记忆和长期记忆，但其核心实现侧重于长期记忆。

**长期记忆的组织方式：**

1.  **语义化存储**：
    *   当添加新的记忆时（例如，通过对话），大型语言模型 (LLM) 会从中提取相关信息、关键实体及其之间的关系。
    *   这些提取出的记忆信息会被转换成向量嵌入 (vector embeddings) 并存储在**向量数据库**中。这种方式使得系统可以理解和检索语义上相似的信息，而不仅仅是关键词匹配。

2.  **关系性存储**：
    *   实体之间的关系信息会存储在**图数据库** (graph database) 中。这有助于维护记忆之间的上下文联系和复杂关系。

3.  **多步骤处理流程**：
    *   **添加记忆 (`add` 操作)**：
        1.  **信息提取**：LLM 从输入（如对话）中提取记忆，并识别重要的实体及其关系。
        2.  **冲突解决**：系统将新信息与现有数据进行比较，以识别并解决任何矛盾。
        3.  **记忆存储**：实际的记忆内容存储在向量数据库中，关系信息存储在图数据库中。信息会随着每次交互不断更新。
    *   **搜索记忆 (`search` 操作)**：
        1.  **查询处理**：LLM 处理并优化搜索查询，系统准备过滤器以进行定向搜索。
        2.  **向量搜索**：使用优化后的查询执行语义搜索，并根据与查询的相关性对结果进行排序，同时应用指定的过滤器（如用户、代理、元数据等）。
        3.  **结果处理**：合并和排序搜索结果，返回带有相关性得分、关联元数据和时间戳的记忆。

总结来说，Mem0 项目通过结合使用向量数据库（用于语义理解和检索）和图数据库（用于关系映射），以一种结构化和上下文感知的方式组织记忆。这使得 AI 应用程序能够有效地存储、检索和利用过去的交互信息，以提供更智能和个性化的体验。