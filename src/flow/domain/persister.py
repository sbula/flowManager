import hashlib
import json
import os
import shutil
import time
from pathlib import Path
from typing import Union

from flow.domain.models import IntegrityError, StatusTree, Task


class StatusPersister:
    def __init__(self, flow_dir: Union[str, Path]):
        self.flow_dir = Path(flow_dir)
        self.backups_dir = self.flow_dir / "backups"

    def save(self, tree: StatusTree, filename: str = "status.md") -> None:
        """
        Saves the StatusTree to disk with strict formatting and integrity protections.
        1. Backup existing file.
        2. Write new content (Deterministic).
        3. Update Integrity Hash.
        """
        full_path = self.flow_dir / filename

        # 1. Backup if exists
        if full_path.exists():
            self._create_backup(full_path)

        # 2. Serialize & Write Atomically
        content = self._serialize(tree)

        # Ensure parent exists
        full_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = full_path.with_suffix(".tmp")

        with open(tmp_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())

        # 3. Atomic Rename
        self._atomic_rename(tmp_path, full_path)

        # 4. Update Hash
        self._update_hash(full_path)

    def _atomic_rename(self, src: Path, dst: Path):
        """Robust atomic rename with retries for Windows."""
        max_retries = 5
        delay = 0.1

        for i in range(max_retries):
            try:
                os.replace(src, dst)
                return
            except OSError:
                if i == max_retries - 1:
                    src.unlink(missing_ok=True)  # Cleanup temp on final fail
                    raise
                time.sleep(delay)

    def _create_backup(self, file_path: Path):
        """Creates a timestamped copy in .flow/backups/"""
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        timestamp = int(time.time())
        backup_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
        backup_path = self.backups_dir / backup_name
        shutil.copy2(file_path, backup_path)

    def _update_hash(self, file_path: Path):
        """Calculates hash and updates .meta file."""
        content = file_path.read_bytes()
        sha = hashlib.sha256(content).hexdigest()

        meta_path = file_path.with_suffix(".meta")
        meta = {"hash": sha, "timestamp": time.time()}

        with open(meta_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(meta, f, indent=2)

    def _serialize(self, tree: StatusTree) -> str:
        """Converts Tree to Markdown String (Strict 4-space indent)."""
        lines = []

        # Headers
        for k, v in tree.headers.items():
            lines.append(f"{k}: {v}")
        if tree.headers:
            lines.append("")

        # Tasks
        self._serialize_tasks(tree.root_tasks, lines)

        return "\n".join(lines) + "\n"

    def _serialize_tasks(self, tasks: list[Task], lines: list[str]):
        for task in tasks:
            indent = "    " * task.indent_level

            # Marker Normalization
            marker_map = {"pending": " ", "active": "/", "done": "x", "skipped": "-"}
            marker_char = marker_map.get(task.status, " ")
            marker = f"[{marker_char}]"

            line = f"{indent}- {marker} {task.name}"

            # Reference
            if task.ref:
                # Quote if space
                ref_str = f'"{task.ref}"' if " " in task.ref else task.ref
                line += f" @ {ref_str}"

            lines.append(line)

            # Children
            if task.children:
                self._serialize_tasks(task.children, lines)
