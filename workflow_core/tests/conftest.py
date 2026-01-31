import sys
from pathlib import Path

# Add project root to sys.path
# workflow_core/tests -> workflow_core -> root
root = Path(__file__).parent.parent.parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))
