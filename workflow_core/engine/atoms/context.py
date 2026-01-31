from pathlib import Path
from typing import Dict, List, Optional
import fnmatch

def gather(root: Path, includes: List[str], excludes: Optional[List[str]] = None) -> Dict[str, str]:
    """
    Gathers file contents from root matching include/exclude patterns.
    Returns Dict[relative_path_str, content].
    """
    result = {}
    excludes = excludes or []
    
    # Simple strategy: Iterate all files in root (recursively is risky if huge, but okay for atoms)
    # Better: Use includes to drive the search if possible.
    # Pattern matching: glob doesn't support exclusions easily.
    # Strategy: Walk tree, check match.
    
    # If includes has "**" we must verify what user means. Assuming glob patterns.
    # To correspond to tests: includes=["src/*.py"]
    
    # Let's collect ALL candidates from includes first.
    candidates = set()
    for pattern in includes:
        # rglob if pattern starts with **/ or just glob?
        # Path.glob handles patterns.
        if "**" in pattern:
            # Recursive
             for p in root.rglob(pattern):
                 if p.is_file():
                     candidates.add(p)
        else:
             # Non-recursive (or recursive if glob has it)
             # actually Path.glob(pattern) works for most
             for p in root.glob(pattern):
                 if p.is_file():
                     candidates.add(p)

    # Now filter by excludes
    final_paths = []
    for p in candidates:
        rel_path = p.relative_to(root).as_posix()
        
        # Check exclusion
        is_excluded = False
        for ex in excludes:
            if fnmatch.fnmatch(rel_path, ex):
                is_excluded = True
                break
        
        if not is_excluded:
            try:
                content = p.read_text(encoding="utf-8", errors="ignore")
                result[rel_path] = content
            except Exception:
                pass # Binary or error
                
    return result
