#!/usr/bin/env python3

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
import re
import sys
from pathlib import Path

# Config
HANDBOOK_DIR = Path("handbook")
ROUTER_FILE = HANDBOOK_DIR / "process_router.md"
CATALOG_FILE = HANDBOOK_DIR / "task_catalog.md"
WORKFLOWS_FILE = HANDBOOK_DIR / "workflows.md"


def get_anchors(file_path):
    """Extracts <!-- id: AnchorName --> tags from a file."""
    if not file_path.exists():
        print(f"!! Error: File {file_path} not found.")
        return set()

    content = file_path.read_text(encoding="utf-8")
    anchors = set(re.findall(r"<!-- id: ([a-zA-Z0-9_]+) -->", content))
    return anchors


def get_router_links():
    """Extracts links from process_router.md."""
    if not ROUTER_FILE.exists():
        return []

    content = ROUTER_FILE.read_text(encoding="utf-8")
    # Matches: `handbook/roles.md#Data_Scientist`
    links = re.findall(r"`handbook/([a-zA-Z0-9_]+\.md)#([a-zA-Z0-9_]+)`", content)
    return links


def get_catalog_keys():
    """Extracts task names from task_catalog.md."""
    if not CATALOG_FILE.exists():
        return set()
    content = CATALOG_FILE.read_text(encoding="utf-8")
    # Matches: ### `Analysis.Strategic`
    keys = set(re.findall(r"### `([a-zA-Z0-9_.]+)`", content))
    return keys


def get_workflow_tasks():
    """Extracts task references from workflows.md."""
    if not WORKFLOWS_FILE.exists():
        return []
    content = WORKFLOWS_FILE.read_text(encoding="utf-8")
    # Matches: - `Analysis.Strategic`
    tasks = re.findall(r"- `([a-zA-Z0-9_.]+)`", content)
    return tasks


def validate():
    print("=== Validating Knowledge Graph ===")
    errors = 0

    # 1. Validate Router Pointers -> Handbook Anchors
    print("\n[checking] Process Router Pointers...")
    links = get_router_links()
    for filename, anchor in links:
        target_file = HANDBOOK_DIR / filename
        if not target_file.exists():
            print(
                f"!! FAIL: Target file {target_file} not found (referenced in router)."
            )
            errors += 1
            continue

        defined_anchors = get_anchors(target_file)
        if anchor not in defined_anchors:
            print(f"!! FAIL: Anchor '{anchor}' not found in {filename}.")
            errors += 1
        else:
            # print(f"   OK: {filename}#{anchor}")
            pass

    # 2. Validate Workflow Tasks -> Catalog Definitions
    print("\n[checking] Workflow Task Composition...")
    catalog_keys = get_catalog_keys()
    workflow_tasks = get_workflow_tasks()

    for task in workflow_tasks:
        if task not in catalog_keys:
            print(f"!! FAIL: Workflow uses undefined task '{task}'.")
            errors += 1
        else:
            pass

    if errors == 0:
        print("\n>> SUCCESS: Knowledge Graph is Integrity Verified.")
        sys.exit(0)
    else:
        print(f"\n!! FAILURE: Found {errors} broken links/definitions.")
        sys.exit(1)


if __name__ == "__main__":
    validate()
