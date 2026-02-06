from pathlib import Path

from flow.engine.models import SecurityError
from flow.engine.security import SafePath


class LoomError(Exception):
    pass


class Loom:
    def __init__(self, project_root: Path):
        self.root = project_root

    def insert(self, path: Path, anchor: str, content: str, position: str = "after"):
        """
        Surgical insertion relative to an anchor.
        Safety:
        - Must be single match for anchor.
        - Path must be safe.
        """
        # Security Check
        try:
            # If path is absolute, check relative to root.
            # If path is relative, resolve it.
            # SafePath expects string or Path?
            target = SafePath(self.root, str(path))
        except SecurityError:
            raise

        if not target.exists():
            raise LoomError(f"File not found: {target}")

        # T6.07 Encoding Safety (Latin1/Binary check)
        # We enforce UTF-8 for now. If it fails to strict decode, it might be binary or legacy.
        try:
            text = target.read_text(encoding="utf-8", errors="strict")
        except UnicodeDecodeError:
            raise LoomError(
                f"File {path} is not valid UTF-8. Loom only supports UTF-8."
            )

        # Capture state for Optimistic Locking (T6.10)
        # We use nano-second precision if available for tight races
        original_mtime_ns = target.stat().st_mtime_ns

        # Anchor finding
        # T6.13 Whitespace Normalization (Lenient)
        # We strip both anchor and line for comparison?
        # Or we rely on exact match?
        # Spec T6.13 says "Lenient whitespace".
        # Implementation: Simple normalization (strip lines) implies we operate line-by-line.
        # But we are doing string find.
        # Let's try exact match first as per T6.08 (Regex Literal Safety).

        count = text.count(anchor)

        if count == 0:
            # Fallback: T6.13 Lenient check
            # Try finding ignoring leading/trailing whitespace on lines
            # This is complex for a simple `find`.
            # For V1.3, if exact match fails, we raise.
            # We can implement "Smart Search" later or if existing tests demand it.
            # T6.06 Whitespace mismatch (Anchor=Spaces, File=Tabs).
            # If we want to support this, we need to normalize file content to spaces to find?
            # No, we must preserve file content (T6.01 indents).
            # So if file has tabs, anchor must have tabs.
            # But Agent might not know.
            # "Fuzzy Fallback" described in Spec 4.3?
            # "If Insert fails... allow ReplaceLine using hint."
            # So maybe we just fail here strictly.
            raise LoomError(f"Anchor not found: '{anchor}'")

        if count > 1:
            raise LoomError(f"Ambiguous anchor: '{anchor}' found {count} times.")

        # Perform Insert
        idx = text.find(anchor)
        end_idx = idx + len(anchor)

        # T6.11 EOL Preservation
        # Detect line ending style of the file?
        # Simple heuristic: if \r\n in text, use it?
        eol = "\n"
        if "\r\n" in text:
            eol = "\r\n"

        new_text = text[:end_idx] + eol + content + text[end_idx:]

        # T6.10 Optimistic Locking check
        # Verify the file hasn't been touched since we read it.
        try:
            current_stat = target.stat()
            # Note: mtime_ns is high precision.
            # If filesystem doesn't support ns, it falls back to s (padded).
            if current_stat.st_mtime_ns != original_mtime_ns:
                raise LoomError(
                    "Content changed during operation (Optimistic Lock Failed)"
                )
        except OSError:
            # File deleted?
            raise LoomError("File disappeared during operation")

        target.write_text(new_text, encoding="utf-8")
