# Copyright 2026 Steve Bula @ pitBula
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
from pathlib import Path

# Add root to sys.path to simulate running from root
root_dir = Path(__file__).parent.parent.parent
sys.path.append(str(root_dir))

def verify():
    print(">> Verifying V3 Refactor...")
    
    # 1. Check Imports
    try:
        from workflow_core.engine.core.rules_engine import RulesEngine
        print("   [x] RulesEngine Imported")
        
        from workflow_core.engine.core.review_orchestrator import ReviewOrchestrator
        print("   [x] ReviewOrchestrator Imported")
        
        # Check reconciler import (ensure no syntax errors)
        from workflow_core.flow_manager import reconciler
        print("   [x] Reconciler Imported")
        
    except ImportError as e:
        print(f"   [!] Import Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"   [!] Syntax/Runtime Error: {e}")
        sys.exit(1)

    # 2. Check Rules Engine Logic
    try:
        config_path = root_dir / "workflow_core" / "config"
        engine = RulesEngine(config_path)
        
        # Test Case 1: #ML Tag
        role = engine.resolve_author_role("Service", ["ML"])
        print(f"   [x] Rule Check (#ML -> {role})")
        if role != "ML Engineer":
            print(f"       [!] Expected 'ML Engineer', got '{role}'")
            sys.exit(1)
            
        # Test Case 2: Signal Service
        council = engine.resolve_council_set("Signal", [])
        print(f"   [x] Rule Check (Signal -> {council})")
        if council != "AlphaSquad":
            print(f"       [!] Expected 'AlphaSquad', got '{council}'")
            sys.exit(1)
            
    except Exception as e:
        print(f"   [!] Rules Engine Logic Error: {e}")
        sys.exit(1)
        
    print(">> Verification Successful.")

if __name__ == "__main__":
    verify()
