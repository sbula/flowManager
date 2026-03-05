import os
import sys

# Add src to path
sys.path.append(os.getcwd())

from flow.engine.core import Engine  # noqa: E402


def run_task(task_id):
    print(f"DEBUG: Hydrating Engine in {os.getcwd()}")
    engine = Engine()
    engine.hydrate()

    # We need to find the task object
    # Engine.find_active_task() logic might help, or load directly
    tree = engine.load_status()
    try:
        task = tree.find_task(task_id)
    except Exception:
        print(f"FATAL: Task {task_id} not found.")
        sys.exit(1)

    print(f"DEBUG: Running Task {task.name} ({task.id})")
    engine.run_task(task)
    print(f"DEBUG: Task Completed Successfully with status: {task.status}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_engine_task.py <task_id>")
        sys.exit(1)

    run_task(sys.argv[1])
