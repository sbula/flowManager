import os
from pathlib import Path

from flow.engine.models import SecurityError


def SafePath(root: Path, path: str) -> Path:
    """
    Resolves a path relative to root with strict security checks.

    Security Rules:
    1. Must be relative (no absolute paths).
    2. Must be within root (no .. traversal).
    3. Must not be a reserved device name (Windows).
    4. Must not use unsafe protocols (handled by parser, but good double check).
    5. Symlinks must resolve to within root.
    """

    # rule 0: Null bytes
    if "\0" in path:
        raise SecurityError("Null byte in path")

    # Rule 0.5: Length Limit (T7.04)
    # Enforce basic sanity limit to prevent DOS/Buffer issues
    if len(path) > 4096:  # Linux max
        raise SecurityError("Path too long")
    if os.name == "nt" and len(path) > 255:  # Windows classic max for component/path
        raise SecurityError("Path too long for Windows portability")

    # Rule 1: No Absolute Paths
    if Path(path).is_absolute():
        raise SecurityError(f"Absolute paths are forbidden: {path}")

    # Rule 3: Windows Reserved Names
    _check_reserved_names(path)

    # Resolve
    try:
        resolved_root = root.resolve()
        target = (root / path).resolve()
    except OSError as e:
        # Handle "File name too long" etc
        raise SecurityError(f"OS Error resolving path: {e}")

    # Rule 2: Jailbreak (Common Prefix Check)
    # On Windows, resolve() lowercases strict comparisons sometimes? No, Python 3 Path implementation is good.
    # But strict containment check:
    try:
        target.relative_to(resolved_root)
    except ValueError:
        raise SecurityError(
            f"Path traversal detected. {target} is outside {resolved_root}"
        )

    # Rule 5: Symlink Escape check
    # resolve() follows symlinks. If the FINAL target is outside, checks above catch it.
    # But what if intermediate is a symlink to outside?
    # e.g. root/link_to_etc -> /etc. Link is inside, target is outside.
    # .resolve() handles this by resolving the final path.
    # So `target.relative_to(root)` checks if the *result* is inside. Correct.

    return target


def _check_reserved_names(path: str):
    """Check for DOS legacy device names."""
    reserved = {"CON", "PRN", "AUX", "NUL"}
    for i in range(1, 10):
        reserved.add(f"COM{i}")
        reserved.add(f"LPT{i}")

    parts = Path(path).parts
    for part in parts:
        stem = Path(part).stem.upper()
        if stem in reserved:
            raise SecurityError(f"Reserved device name forbidden: {part}")
