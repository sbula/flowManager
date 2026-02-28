from typing import Any, Dict, List, Optional

from flow.tools.base import Tool, ToolContext, ToolError, ToolResult


def get_rag_client():
    # Factory for RAG Client (Stub for now)
    return RagClientStub()


class RagClientStub:
    def get_status(self) -> Dict[str, Any]:
        return {"status": "ready"}

    def get_related_tests(self, file_path: str) -> List[str]:
        return []

    def generate_map(self, root_dir: Optional[str] = None) -> Dict[str, Any]:
        return {"services": [], "infrastructure": []}

    def get_task_context(self, task_id: str) -> Dict[str, Any]:
        return {"phase": "Unknown", "task": task_id}

    def find_usage(self, symbol: str) -> List[Dict[str, Any]]:
        return []


class KnowledgeTool(Tool):
    name = "knowledge_tool"
    description = "Interact with project knowledge base (RAG)."
    input_schema = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": [
                    "search_knowledge",
                    "check_status",
                    "find_usage",
                    "get_related_tests",
                    "get_system_map",
                    "get_task_context",
                ],
            },
            "query": {"type": "string"},
            "limit": {"type": "integer"},
            "symbol": {"type": "string"},
            "file_path": {"type": "string"},
            "root_dir": {"type": "string"},
            "task_id": {"type": "string"},
        },
        "required": ["operation"],
    }

    def __init__(self):
        self._client = get_rag_client()

    def run(self, args: Dict[str, Any], context: ToolContext) -> ToolResult:
        operation = args.get("operation")

        try:
            if operation == "check_status":
                status = self._client.get_status()
                return ToolResult(status="success", data=status)
            elif operation == "search_knowledge":
                query = args.get("query")
                if not query:
                    raise ToolError("Query required for search", code="ValidationError")
                results = self._client.search(query, args.get("limit", 5))
                return ToolResult(status="success", data={"results": results})
            elif operation == "find_usage":
                symbol = args.get("symbol")
                if not symbol:
                    raise ToolError("Symbol name required", code="ValidationError")
                usages = self._client.find_usage(symbol)
                return ToolResult(status="success", data={"usages": usages})
            elif operation == "get_related_tests":
                file_path = args.get("file_path")
                if not file_path:
                    raise ToolError("File path required", code="ValidationError")
                tests = self._client.get_related_tests(file_path)
                return ToolResult(status="success", data={"tests": tests})
            elif operation == "get_system_map":
                sys_map = self._client.generate_map(args.get("root_dir"))
                return ToolResult(status="success", data={"map": sys_map})
            elif operation == "get_task_context":
                task_id = args.get("task_id")
                if not task_id:
                    raise ToolError("Task ID required", code="ValidationError")
                ctx = self._client.get_task_context(task_id)
                return ToolResult(status="success", data={"context": ctx})
            else:
                return ToolResult(
                    status="error",
                    error={
                        "code": "UnknownOperation",
                        "message": f"Unknown operation: {operation}",
                    },
                )

        except ToolError as e:
            return ToolResult(status="error", error={"code": e.code, "message": str(e)})
        except Exception as e:
            return ToolResult(
                status="error", error={"code": "InternalError", "message": str(e)}
            )
