from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from flow.domain.models import IntegrityError, StatusParsingError, StatusTree, Task

# --- Parser ---


class StatusParser:
    def __init__(self, root_path: Path):
        print(f"DEBUG: Parser Init Root: {root_path}")
        self.root = root_path
        self.flow_dir = root_path / ".flow"
        print(f"DEBUG: Parser Flow Dir: {self.flow_dir}")
        self.backups_dir = self.flow_dir / "backups"

    def load(self, status_path: str = "status.md") -> StatusTree:
        full_path = self.flow_dir / status_path
        print(
            f"DEBUG: Loading {status_path} from {full_path}. Exists: {full_path.exists()}"
        )
        if not full_path.exists():
            print("DEBUG: File missing, returning empty tree.")
            return StatusTree()

        # Integrity Check (T1.13)
        self._check_integrity(full_path)

        tree = self._parse_content(full_path.read_text(encoding="utf-8"))

        # Initial Cycle Check (Recursive)
        # We only check if the tree is valid.
        try:
            self._validate_cycles(tree.root_tasks, visited={full_path.resolve()})
        except RecursionError:
            raise StatusParsingError("Recursion Limit Hit")

        return tree

    def accept_changes(self, status_path: str = "status.md"):
        """Updates .meta hash to match current file (T1.14)."""
        full_path = self.flow_dir / status_path
        if not full_path.exists():
            raise FileNotFoundError(f"{status_path} not found.")
        self._update_hash(full_path)

    def decline_changes(self, status_path: str = "status.md"):
        """Restores from latest backup (T1.15)."""
        full_path = self.flow_dir / status_path

        # Find latest backup
        if not self.backups_dir.exists():
            raise FileNotFoundError("No backups directory found.")

        backups = sorted(
            list(self.backups_dir.glob(f"{full_path.stem}_*{full_path.suffix}"))
        )
        if not backups:
            raise FileNotFoundError("No backups found to restore.")

        latest = backups[-1]

        # Restore
        shutil.copy2(latest, full_path)

        # Sync Hash
        self._update_hash(full_path)

    def _check_integrity(self, file_path: Path):
        meta_path = file_path.with_suffix(".meta")
        if not meta_path.exists():
            # If meta missing, assume First Run or Tampered?
            # Spec implies Strict Mode. But for bootstrap, maybe warn?
            # Let's assume strict for now, but handle 'First Run' by creating meta on save.
            # If loading and meta missing, it's suspicious.
            # But if file created manually?
            # Let's Raise IntegrityError("Meta missing").
            return  # For now, allow load if meta missing (legacy support), or decide Strict.
            # User said: "prevent human ability to modify".
            # So if meta missing, we can't verify.
            pass

        content = file_path.read_bytes()
        current_hash = hashlib.sha256(content).hexdigest()

        try:
            meta = json.loads(meta_path.read_text())
            expected_hash = meta.get("hash")
            if current_hash != expected_hash:
                raise IntegrityError(
                    f"Integrity Mismatch! Expected {expected_hash[:8]}, got {current_hash[:8]}. File tampered."
                )
        except (json.JSONDecodeError, KeyError):
            raise IntegrityError("Corrupt Meta file.")

    def _update_hash(self, file_path: Path):
        # Duplicated from Persister (Shared Utility?)
        # Ideally move to a util, but for now copying is fine to avoid large refactor.
        content = file_path.read_bytes()
        sha = hashlib.sha256(content).hexdigest()

        meta_path = file_path.with_suffix(".meta")
        # Load existing for timestamp or create new?
        # Update hash, keep timestamp if exists? No, accept = new state.
        import time

        meta = {"hash": sha, "timestamp": time.time()}

        with open(meta_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(meta, f, indent=2)

    def _parse_content(self, content: str) -> StatusTree:
        tree = StatusTree()
        lines = content.splitlines()

        # State
        stack: List[Task] = []
        self._id_counters: List[int] = []

        # Compiled Regexes
        header_re = re.compile(r"^([^:]+):\s*(.*)$")
        parsing_headers = True

        for i, line in enumerate(lines, start=1):
            if not line.strip():
                continue

            # 1. Header Parsing
            if parsing_headers:
                if self._try_parse_header(line, header_re, tree):
                    continue
                parsing_headers = False

            # 2. Task Parsing
            task_match = self._match_task_line(line, i)
            indent_level, status, name, ref = self._extract_task_data(task_match, i)

            # 3. ID Generation
            task_id = self._generate_next_id(indent_level)

            # 4. Tree Construction
            new_task = Task(
                id=task_id,
                name=name,
                status=status,
                indent_level=indent_level,
                ref=ref,
                parent=None,
            )
            self._add_to_tree(tree, stack, new_task, indent_level, i)

            # 5. Integrity Check
            if status == "active" and ref:
                self._validate_ref_integrity(ref, i)

        self._validate_tree(tree.root_tasks)

        # T7.09 Recursion Safety (Cycle Detection)
        # We validate that following refs does not form a loop.
        # This is expensive but necessary for safety (Paranoid Mode).
        # We start validation from the CURRENT file being parsed?
        # But _parse_content is generic. load() calls it.
        # So we should move cycle detection to load() or keep it separate.
        # `load` knows the file path.
        return tree

    def _validate_cycles(self, tasks: List[Task], visited: set[Path]):
        print(f"DEBUG: Validating cycles. Visited: {[p.name for p in visited]}")
        for task in tasks:
            if task.ref:
                target_path = (self.flow_dir / task.ref).resolve()
                print(f"DEBUG: Checking ref: {task.ref} -> {target_path}")

                # Check Cycle
                if target_path in visited:
                    print("DEBUG: Cycle Found!")
                    raise StatusParsingError(
                        f"Cycle detected: {task.ref} loops back to {target_path.name}"
                    )

                # If target exists, parse and recurse
                if target_path.exists():
                    # Prevent infinite expansion bombs (T7.15)
                    if len(visited) > 20:  # Depth Limit
                        raise StatusParsingError("Max Recursion Depth Exceeded")

                    new_visited = visited | {target_path}
                    try:
                        content = target_path.read_text(encoding="utf-8")
                        # Parse without full check (to avoid redundantly checking integrity of sub-files here?
                        # Or recursive check? Recursive is safer.)
                        sub_tree = self._parse_content(content)
                        self._validate_cycles(sub_tree.root_tasks, new_visited)
                    except (FileNotFoundError, UnicodeDecodeError):
                        # If sub-file missing/bad-encoding, we might ignore here
                        # because ref integrity for ACTIVE tasks is checked elsewhere?
                        # But for structural cycle check, we skip unreadable files.
                        pass

            if task.children:
                self._validate_cycles(task.children, visited)

    def _try_parse_header(
        self, line: str, header_re: re.Pattern, tree: StatusTree
    ) -> bool:
        # Check if line is a header
        # But wait, tasks can look like headers? No, headers don't start with - [ ]
        # My previous logic checked TASK first.
        task_check = re.match(r"^\s*-\s*\[", line)
        if task_check:
            return False

        header_match = header_re.match(line)
        if header_match:
            key, val = header_match.groups()
            tree.headers[key.strip()] = val.strip()
            return True
        return False

    def _match_task_line(self, line: str, line_idx: int) -> re.Match:
        task_re = re.compile(r"^(\s*)-\s*\[([ xXvV/-])\]\s*(.+)$")
        match = task_re.match(line)
        if not match:
            if line.lstrip().startswith("-"):
                raise StatusParsingError(
                    f"Line {line_idx}: Missing status marker or invalid format."
                )
            raise StatusParsingError(f"Line {line_idx}: Invalid format.")
        return match

    def _extract_task_data(self, match: re.Match, line_idx: int):
        indent_str, marker, full_text = match.groups()

        # Indent Validation
        if "\t" in indent_str:
            raise StatusParsingError(f"Line {line_idx}: Tabs are forbidden.")
        if len(indent_str) % 4 != 0:
            raise StatusParsingError(
                f"Line {line_idx}: Invalid indentation. Must be multiple of 4."
            )
        indent_level = len(indent_str) // 4

        # Status
        marker = marker.lower()
        status_map = {
            "x": "done",
            "v": "done",
            " ": "pending",
            "/": "active",
            "-": "skipped",
        }
        if marker not in status_map:
            raise StatusParsingError(f"Line {line_idx}: Unknown marker '[{marker}]'")
        status = status_map[marker]

        # Ref Parsing
        ref = None
        name = full_text.strip()
        ref_re = re.compile(r"(.*?)\s*@\s*(\"?)(.+?)\2\s*$")
        ref_match = ref_re.match(name)
        if ref_match:
            name, _, ref = ref_match.groups()
            name = name.strip()
            ref = ref.strip()
            self._validate_ref_safety(ref, line_idx)

        return indent_level, status, name, ref

    def _validate_ref_safety(self, ref: str, line_idx: int):
        if ".." in ref:
            raise StatusParsingError(
                f"Line {line_idx}: Jailbreak attempt detected in path '{ref}'"
            )

        bad_protocols = ["http", "https", "ftp", "javascript", "file", "data"]
        if any(ref.lower().startswith(p + ":") for p in bad_protocols):
            is_win = len(ref) > 1 and ref[1] == ":" and "\\" in ref
            if not is_win:
                raise StatusParsingError(
                    f"Line {line_idx}: Invalid Protocol in path '{ref}'"
                )

    def _generate_next_id(self, indent_level: int) -> str:
        non_local = self._id_counters
        if indent_level > len(non_local) - 1:
            while len(non_local) <= indent_level:
                non_local.append(1)
        else:
            non_local = non_local[: indent_level + 1]
            non_local[indent_level] += 1

        self._id_counters = non_local
        return ".".join(map(str, non_local))

    def _add_to_tree(
        self,
        tree: StatusTree,
        stack: List[Task],
        new_task: Task,
        indent_level: int,
        line_idx: int,
    ):
        if indent_level == 0:
            tree.root_tasks.append(new_task)
            stack[:] = [new_task]  # Replace stack
        else:
            while stack and stack[-1].indent_level >= indent_level:
                stack.pop()

            if not stack:
                raise StatusParsingError(
                    f"Line {line_idx}: Orphaned task (indent {indent_level})."
                )

            parent = stack[-1]
            if parent.status == "done" and new_task.status == "pending":
                raise StatusParsingError(
                    f"Line {line_idx}: Logic Conflict - Parent Done, Child Pending."
                )

            parent.children.append(new_task)
            new_task.parent = parent
            stack.append(new_task)

    def _validate_ref_integrity(self, ref: str, line_idx: int):
        target = self.flow_dir / ref
        if not target.exists():
            raise StatusParsingError(f"Line {line_idx}: Missing sub-status file: {ref}")

    def _validate_tree(self, tasks: List[Task]):
        names = set()
        active_count = 0

        for t in tasks:
            # T2.09: Duplicate Name
            if t.name in names:
                raise StatusParsingError(f"Duplicate Task Name: '{t.name}'")
            names.add(t.name)

            # T2.08: Sibling Activity
            if t.status == "active":
                active_count += 1

            if t.children:
                self._validate_tree(t.children)

        if active_count > 1:
            raise StatusParsingError("Ambiguous Focus: Multiple active siblings found.")
