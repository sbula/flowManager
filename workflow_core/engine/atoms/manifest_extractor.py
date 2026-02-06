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

import json
import logging
import re
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ManifestExtractor")


def extract_feature_info(project_map_path: str, feature_seq: str):
    """
    Parses project_map.md to find a feature by its Sequence ID (e.g. "0", "1").
    Returns a dict with: feature_name, feature_goal, feature_context, complexity.
    """
    path = Path(project_map_path)
    if not path.exists():
        logger.error(f"Project Map not found at: {path}")
        sys.exit(1)

    content = path.read_text("utf-8")

    # Regex to find the header: "## 1. Feature Name" or "## 0. Feature Name"
    # Matches: ## <Seq>. <Name>
    header_pattern = re.compile(
        r"^##\s+" + re.escape(feature_seq) + r"\.\s+(.*?)\s*$", re.MULTILINE
    )
    match = header_pattern.search(content)

    if not match:
        logger.error(f"Feature Sequence '{feature_seq}' not found in Project Map.")
        sys.exit(2)

    feature_title = match.group(1).strip()

    # Extract the block until the next "## " or end of file
    start_idx = match.end()
    rest_of_file = content[start_idx:]
    next_header_match = re.search(r"^##\s+\d+\.", rest_of_file, re.MULTILINE)

    if next_header_match:
        block_content = rest_of_file[: next_header_match.start()]
    else:
        block_content = rest_of_file

    # Extract key fields from the block
    # **Complexity**: ...
    # **Feature**: ... (This is the Goal)
    # **Customer Benefit**: ... (This is the Context)

    complexity_match = re.search(r"\*\*Complexity\*\*:\s*(.*)", block_content)
    feature_def_match = re.search(r"\*\*Feature\*\*:\s*(.*)", block_content)
    benefit_match = re.search(r"\*\*Customer Benefit\*\*:\s*(.*)", block_content)
    scope_in_match = re.search(r"\*\*Scope \(In\)\*\*:\s*(.*)", block_content)

    info = {
        "feature_seq": feature_seq,
        "feature_name": feature_title.lower()
        .replace(" ", "_")
        .replace(":", "")
        .replace("__", "_"),
        "feature_title": feature_title,
        "complexity": (
            complexity_match.group(1).strip() if complexity_match else "Unknown"
        ),
        "feature_goal": (
            feature_def_match.group(1).strip()
            if feature_def_match
            else "Defined in Project Map"
        ),
        "feature_context": (
            benefit_match.group(1).strip() if benefit_match else "See Project Map"
        ),
        "scope_in": scope_in_match.group(1).strip() if scope_in_match else "",
    }

    return info


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python manifest_extractor.py <project_map_path> <feature_seq>")
        sys.exit(1)

    pmap_path = sys.argv[1]
    seq_id = sys.argv[2]

    data = extract_feature_info(pmap_path, seq_id)

    # Output metrics for Flow Manager to capture
    print(f"::set-output name=feature_name::{data['feature_name']}")
    print(f"::set-output name=feature_title::{data['feature_title']}")
    print(f"::set-output name=feature_goal::{data['feature_goal']}")
    print(f"::set-output name=feature_context::{data['feature_context']}")
    print(f"::set-output name=complexity::{data['complexity']}")

    # Also dump json for debug
    logger.info(json.dumps(data, indent=2))
