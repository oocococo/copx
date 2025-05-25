# ✨ CopX - Your **Co**de **P**roject E**x**pert ✨

[中文](docs/README_zh.md)

🚀 **Co**de **P**roject E**x**pert (CopX) is a system designed to answer questions about any codebase.
- Explore, search your codebase agentically (like a human expoert).
- No embedding needed.

## Core Features

*   **Declaration-Based Context**: Understands code structure by parsing source files and building a "declaration map" of symbols (functions, classes, variables, etc.). This allows for precise, non-embedding-based retrieval of relevant code context.
*   **Incremental Updates**: Utilizes a hidden Git repository to track file changes and incrementally updates the declaration map, ensuring efficiency for large codebases.
*   **Hybrid Retrieval (Optional)**: Can integrate with semantic search (e.g., using LanceDB and embedding models) for queries that benefit from semantic understanding, complementing the primary declaration-based retrieval.
*   **LLM-Powered Q&A**: Leverages Large Language Models (LLMs) to understand questions and formulate answers based on the retrieved context.
*   **Multi-Language Support**: Easily extensible to support various programming languages through Tree-sitter configurations. Currently supports Python, Golang, TypeScript, and JavaScript out-of-the-box.
*   **Flexible Deployment**: Can be run as a FastAPI service or an MCP (Model Context Protocol) server.

## Workflow Diagram

Here's a simplified diagram of the agent's workflow:

```mermaid
graph TD
    A[User Question] --> B{CopX Agent};

    subgraph "CopX Core Processing Pipeline"
        B --> D[1 Update/Load Declaration Map];
        D --> E["Symbol Extractor (Tree-sitter) + Git Manager"];
        E --> F[(Declaration Map <br/> .pkl + .git Store)];
        
        D --> G["2 Agentic Code Retrieval <br/> Tools: <br/> - view_file_declaration_map <br/> - view_file_content <br/> - grep_declaration_map <br/> - grep_search <br/> - semantic_search_declaration_map"];
        G -- Uses --> F;
        G -- Optional: Semantic Search --> H[(LanceDB)];
        
        G --> I["3 Formulate Answer (LLM)"];
    end
    
    I --> J[Return Answer];
    J --> A;
```

## Usage Guide

CopX can be run in two modes: as an MCP server or as a FastAPI service.

### 1. MCP (Model Context Protocol) Server

The MCP server exposes CopX's capabilities as a tool that can be used by MCP-compatible clients (e.g., AI IDEs).

**Prerequisites:**
*   Ensure you have `uv` installed. You can install it by following the instructions at [https://github.com/astral-sh/uv](https://github.com/astral-sh/uv).

**To run:**
Execute the following command in your terminal:
```bash
uvx --from copx copx-mcp
```
This will start the MCP server, registering a tool named "Ask Expert".

**Recommended AI IDE Configuration:**
You can integrate CopX MCP server into your AI IDE (like those supporting MCP) using a configuration similar to this:

```json
{
  "copx": {
    "command": "uvx",
    "args": [
      "--from",
      "copx",
      "copx-mcp"
    ],
    "env": {
      "COPX_MODEL": "ollama/devstral",
      "COPX_DATA_PATH": "~/Documents/Copx",
      "COPX_API_KEY": "YOUR_KEY_HERE",
      "COPX_BASE_URL": "YOUR_LLM_BASE_URL_HERE"
    },
    "disabled": false,
    "autoApprove": [
      "Ask Expert"
    ],
    "timeout": 1800
  }
}
```
**Parameter Explanations:**
*   `COPX_MODEL`: Specifies litellm style model name for CopX (e.g., `"ollama/devstral"`, `"openai/gpt-4"`).
*   `COPX_DATA_PATH`: The directory where CopX stores its internal data, such as declaration maps and Git snapshots for projects (e.g., `"~/Documents/Copx"`). It's recommended to use a persistent path.
*   `COPX_API_KEY`: Your API key for the selected LLM service.
*   `COPX_BASE_URL`: The base URL for your LLM API endpoint.

**MCP Tool: `Ask Expert`**
*   **Description**: Get expert answer about project's codebase.
*   **Arguments**:
    *   `project_path` (string, required): The absolute path to the project codebase.
    *   `question` (string, required): The question about the codebase.

### 2. FastAPI Service

The FastAPI service provides an HTTP endpoint for querying.

**Configuration:**
The query endpoint accepts LLM configuration parameters directly in the request body.

**To run:**
Use Uvicorn (or any ASGI server):
```bash
uvicorn copx.copx_fastapi:app --reload --host 0.0.0.0 --port 8000
```

**API Endpoint: `POST /query`**

Request Body (`application/json`):
```json
{
  "project_path": "/path/to/your/codebase",
  "question": "How does the user authentication work?",
  "model": "openai/gpt-4", // litellm format                
  "base_url": "https://api.example.com/v1", 
  "api_key": "your_llm_api_key",    
  "git_path": "~/.copx_data"        
}
```
*   `project_path`: Absolute path to the codebase you want to query.
*   `question`: Your question about the codebase.
*   `model`, `base_url`, `api_key`: LLM provider details.
*   `git_path`: Directory where CopX will store its cache (declaration maps and git snapshots). It's recommended to use a persistent path like `~/.copx_data` or `./.copx_data` in your project. If the directory doesn't exist, CopX will create it.

## How It Works

CopX processes user queries about a codebase through a multi-stage pipeline:

1.  **Declaration Map Update/Load**:
    *   When a query is received for a project, CopX first ensures its declaration map is up-to-date.
    *   It uses a `ProjectGitManager` to track file changes since the last run.
    *   A `SymbolExtractor` (powered by Tree-sitter) parses modified or new files according to language-specific rules.
    *   The extracted symbols (functions, classes, variables, with their locations) are stored in the `declaration_map`. This map is persisted as a `.pkl` file, and the file versions are tracked in a hidden `.git` repository within a specified data directory.

2.  **Code Retrieval**:
    *   The `CodeRetriever` node uses the `declaration_map` to find code segments directly relevant to the user's query based on symbol names and code structure.
    *   Optionally, for broader or more abstract queries, it can utilize semantic search (if configured) on a LanceDB index of code (e.g., function bodies).

3.  **Answer Formulation**:
    *   The `AnswerFormulator` node takes the retrieved context (from the declaration map and/or semantic search) and the original question.
    *   It then interacts with an LLM to generate a comprehensive answer.

## Supported Languages

CopX uses Tree-sitter for code parsing and supports languages via configuration files found in `src/copx/symbal_extractor/configs/`.
Currently supported:

*   Python (`.py`)
*   Golang (`.go`)
*   JavaScript (`.js`, `.jsx`)
*   TypeScript (`.ts`, `.tsx`)

## Adding Support for a New Language

To add support for a new programming language:

1.  **Install Tree-sitter grammar**:
    Find the Python binding for the Tree-sitter grammar (e.g., `tree-sitter-ruby`) and install it:
    ```bash
    pip install tree-sitter-newlanguage
    ```

2.  **Create a configuration file**:
    In the `src/copx/symbal_extractor/configs/` directory, create a new JSON file (e.g., `newlanguage.json`).
    This file needs to specify:
    *   `tree_sitter_module`: The name of the installed Python module for the language (e.g., `tree_sitter_newlanguage`).
    *   `language_accessor_name` (optional): If the language object in the module is not accessed by `module.language`, specify the correct accessor (e.g., `get_language`).
    *   `extraction_rules`: An array of rules defining which AST node types correspond to which symbols (function, class, variable, etc.) and how to extract their names. Refer to existing config files (e.g., `py.json`, `go.json`) for examples.

    Example `newlanguage.json`:
    ```json
    {
      "tree_sitter_module": "tree_sitter_newlanguage",
      "extraction_rules": [
        {
          "node_type": "function_definition",
          "name_field": "name",
          "symbol_type": "Function"
        },
        {
          "node_type": "class_definition",
          "name_field": "name",
          "symbol_type": "Class"
        }
        // ... more rules
      ]
    }
    ```

## Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd copx
    ```

2.  **Install dependencies:**
    It's recommended to use a virtual environment.
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    pip install -r requirements.txt # Or: uv pip install -r requirements.txt
    ```
    You'll need to install Tree-sitter language bindings for the languages you intend to support, for example:
    ```bash
    pip install tree-sitter-python tree-sitter-go tree-sitter-javascript tree-sitter-typescript
    ```
