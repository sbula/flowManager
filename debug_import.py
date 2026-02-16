import sys
import os
# Add current directory to sys.path
sys.path.append(os.getcwd())

print(f"CWD: {os.getcwd()}")
print(f"Sys Path: {sys.path}")

try:
    from workflow_core.knowledge.llm.gateway import LLMGateway
    print("Import successful")
except Exception as e:
    print(f"Import failed: {e}")
    import traceback
    traceback.print_exc()
