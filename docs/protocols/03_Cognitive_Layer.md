# 03. Cognitive Layer & Context Injection

## Overview
The "Intelligence" of the system is not magic; it is a pipeline of **File I/O** and **String Manipulation**. This layer (`atoms/prompt.py` and `atoms/agent.py`) handles the interface between the structured Engine and the unstructured LLM.

## 1. Context Construction
The "Context" passed to an LLM is built cumulatively.

### 1.1 The Context Cache
The Engine maintains a `context_cache` dictionary. This is populated by:
1.  **CLI Args**: Initial inputs (e.g., `task_id`, `service_type`).
2.  **Atom Exports**: Outputs from previous steps (e.g., `research_summary` from a research atom).
3.  **System Config**: Global paths (`config.root`, `project.root`).

### 1.2 Export Mechanism (`_export_context`)
To prevent context pollution (feeding too much data to the LLM), data must be *explicitly* exported.

*Definition*:
```json
{
    "id": "analyze_repo",
    "export": {
        "summary": "repo_analysis_summary" 
    }
}
```
*Effect*: The output `summary` from `analyze_repo` is saved to global context as `repo_analysis_summary`. Subsequent atoms can access it via `${repo_analysis_summary}`.

## 2. Prompt Templates
Templates are **Jinja2** files located in `workflow_core/config/prompts/`.

### 2.1 Structure
A standard template has three sections:
1.  **System Instructions**: Injected from Persona.
2.  **Task Context**: Injected from `context_cache` (e.g., file contents, previous analysis).
3.  **Output Schema**: Instructions on how to format the response (JSON/Markdown).

### 2.2 Template Inheritance**
We support Jinja2 inheritance (`{% extends "base.j2" %}`).
- `base.j2`: Contains standard headers (Safety warning, formatting rules).
- `specific.j2`: Injects the specific logic.

## 3. Token Management (The "Context Window")
To avoid exceeding token limits (`2M` for Gemini, but costly), we use **Just-In-Time Loading**.
- We do **NOT** dump the whole repo into context.
- We use `FileSystem` atoms to read *specific* files into variables immediately before the prompt step.
- These variables are often "Ephemeral"—used for one prompt and then discarded (unless exported).
