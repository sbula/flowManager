import argparse
import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.append(str(Path(__file__).resolve().parents[3]))

try:
    from flow.domain.models import Task
    from flow.engine.core import Engine
except ImportError:
    # Fallback for direct execution
    sys.path.append(str(Path(__file__).resolve().parents[3]))
    from flow.domain.models import Task
    from flow.engine.core import Engine


def run_ask_codebase(query: str, profile: str = "default"):
    """
    Executes the Ask Codebase workflow using the Engine and RagRetrievalAtom.
    """
    engine = Engine()
    try:
        engine.hydrate()
    except Exception as e:
        print(f"Error hydrating engine: {e}")
        return

    # Create a transient task
    task = Task(
        id="manual-query",
        parent=None,
        name=f"[RagRetrievalAtom] Query: {query}",
        status="pending",
        indent_level=0,
    )

    # Inject parameters into context
    engine.context["query"] = query
    engine.context["profile"] = profile

    # Execute
    print(f"Executing [RagRetrievalAtom] with profile '{profile}'...")
    try:
        # Dispatch and Run manually since run_task persists to
        # status.md which we might not want for temporary queries?
        # But run_task encapsulates lifecycle.
        # If we use run_task, it will look for status.md.

        atom = engine.dispatch(task)
        result = atom.run(engine.context)

        if result.success:
            print("\n=== Answer ===")
            print(result.exports.get("answer", "No answer returned."))
            print("==============")
        else:
            print(f"Error: {result.message}")

    except Exception as e:
        print(f"Workflow Failed: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ask Codebase Workflow")
    parser.add_argument("query", help="The question to ask")
    parser.add_argument("--profile", default="default", help="Model profile to use")

    args = parser.parse_args()

    run_ask_codebase(args.query, args.profile)
