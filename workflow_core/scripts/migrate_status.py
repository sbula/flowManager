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


def migrate_status(status_path):
    print(f">> Migrating {status_path} to Compact Gates...")
    content = Path(status_path).read_text(encoding="utf-8")
    lines = content.splitlines()
    new_lines = []

    skip_count = 0

    # Regex Patterns
    # - [x] 4.2.3. `Impl.Feature`: ...
    # - [ ] 4.2.7. `Valid.Unit`: ...
    # - [ ] 4.2.8. `Valid.Quality`: ...
    # - [ ] 4.2.9. `Review.Code`: ...

    # Strategy: Iterate and look ahead.
    i = 0
    while i < len(lines):
        line = lines[i]

        # Check if this is an Impl task that starts a chain
        impl_match = re.search(
            r"(- \[[ x/]\]) (\d+(\.\d+)+)\. `Impl\.(Feature|Code)`: (.*)", line
        )

        if impl_match:
            # Look ahead for Valid/Review chain
            # We expect: Valid.Unit -> Valid.Quality -> Review.Code
            # They might be separated by other lines? Assuming sequential for now based on standard template.

            # Check if next lines match the pattern
            # We want to keep the Impl line.
            new_lines.append(line)

            # Now look for the Verification Chain to Collapse
            # We consolidate 4.2.7, 4.2.8, 4.2.9 into ONE Gate.Feature task.
            # But the ID needs to be next in sequence.
            # Wait, if we collapse, we lose IDs?
            # Or we just replace the first Valid with Gate and delete the rest?

            # User wants:
            # - [x] Impl
            # - [ ] Gate

            # Let's peek ahead
            j = i + 1
            chain_found = False
            valid_lines = []

            while j < len(lines):
                next_line = lines[j]
                if "`Valid." in next_line or "`Review." in next_line:
                    valid_lines.append(next_line)
                    j += 1
                else:
                    break

            if len(valid_lines) >= 1:
                # We found a chain.
                # Determine Status of the Gate
                # If ALL valid_lines are [x], Gate is [x]. Else [ ].
                all_done = all("- [x]" in l for l in valid_lines)
                gate_status = "- [x]" if all_done else "- [ ]"

                # Determine ID
                # Taking the ID of the first Valid task
                first_valid = valid_lines[0]
                id_match = re.search(r"(\d+(\.\d+)+)\.", first_valid)
                gate_id = id_match.group(1) if id_match else "0.0.0"

                # Determine Gate Type
                # Default to Gate.Feature
                gate_type = "Gate.Feature"
                if "Refactor" in line:
                    gate_type = "Gate.Refactor"
                if "Fix" in line:
                    gate_type = "Gate.Fix"

                # Construct New Line
                gate_line = f"{first_valid[:first_valid.find('-')]} {gate_status} {gate_id}. `{gate_type}`: Verify & Review."
                # Indentation preservation
                indent = line[: line.find("-")]
                gate_line = (
                    f"{indent}{gate_status} {gate_id}. `{gate_type}`: Verify & Review."
                )

                new_lines.append(gate_line)

                # Skip the consumed lines
                i = j - 1  # Loop increment will add 1
            else:
                # No chain, just Impl
                pass

        elif "`Valid." in line or "`Review." in line:
            # If we hit a Valid/Review that wasn't consumed by an Impl lookahead,
            # it might be a standalone chain or we missed it.
            # For safety, blindly Replace Valid/Review with Gate?
            # No, that duplicates if we handled it above.
            # Actually, the lookahead strategy is safer.
            # But what if Impl was miles away?
            # Let's assumes strict adjacency for now as per `status.md` structure.
            # If we are here, it means it wasn't skipped. So keep it?
            # STARTUP Tasks (4.2.1) don't have this chain.
            new_lines.append(line)
        else:
            new_lines.append(line)

        i += 1

    # Write output
    output_path = Path(status_path)
    output_path.write_text("\n".join(new_lines), encoding="utf-8")
    print(">> Migration Done. Please reset hash.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python migrate_status.py <path_to_status.md>")
        sys.exit(1)
    migrate_status(sys.argv[1])
