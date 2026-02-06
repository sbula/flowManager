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

import os
import re
import sys
from datetime import datetime


def harvest_proposals(report_path, backlog_path):
    if not os.path.exists(report_path):
        print(f"[FAIL] Report not found: {report_path}")
        return 0

    with open(report_path, "r", encoding="utf-8") as f:
        content = f.read()

    # extract Task ID from report filename (e.g. 4_1_11_Review.Code.md -> 4.1.11)
    filename = os.path.basename(report_path)
    task_match = re.search(r"(\d+_\d+_\d+)", filename)
    task_id = task_match.group(1).replace("_", ".") if task_match else "UNKNOWN_TASK"

    harvested_count = 0
    new_entries = []

    # Split by reviewers
    reviewer_blocks = content.split("### Reviewer:")[1:]

    for block in reviewer_blocks:
        lines = block.split("\n")
        role = lines[0].strip().replace("**", "")

        proposal_text = ""
        for line in lines:
            if "| **Proposal** |" in line:
                # Format: | **Proposal** | The Text |
                parts = line.split("|")
                if len(parts) > 2:
                    proposal_text = parts[2].strip()
                    break

        # Filter junk
        if not proposal_text:
            continue
        if "PENDING PROPOSAL" in proposal_text:
            continue
        if "No action required" in proposal_text:
            continue
        if "None" == proposal_text:
            continue

        # Format Entry
        date_str = datetime.now().strftime("%Y-%m-%d")
        entry = f"- [ ] **{task_id}** ({role}): {proposal_text} (Captured: {date_str})"
        new_entries.append(entry)
        harvested_count += 1

    if harvested_count > 0:
        # Append to Backlog
        # ensure dir exists
        os.makedirs(os.path.dirname(backlog_path), exist_ok=True)

        header = "# Phase 5 Backlog\n\n"
        if not os.path.exists(backlog_path):
            with open(backlog_path, "w", encoding="utf-8") as f:
                f.write(header)

        with open(backlog_path, "a", encoding="utf-8") as f:
            for entry in new_entries:
                f.write(entry + "\n")

    print(f"Captured {harvested_count} proposals.")
    return harvested_count


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python proposal_harvester.py <report_path> <backlog_path>")
        sys.exit(1)

    harvest_proposals(sys.argv[1], sys.argv[2])
