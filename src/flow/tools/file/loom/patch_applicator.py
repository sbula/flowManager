import re
import logging
from typing import List, Dict, Any
from src.flow.tools.base import ToolError

logger = logging.getLogger(__name__)

class PatchApplicator:
    """
    Applies surgical edits to text content.
    Enforces strict match counting and supports idempotency.
    """
    
    def apply(self, content: str, edits: List[Dict[str, Any]]) -> str:
        current_content = content
        
        for edit in edits:
            current_content = self._apply_single_edit(current_content, edit)
            
        return current_content

    def _apply_single_edit(self, content: str, edit: Dict[str, Any]) -> str:
        op = edit.get("operation", "replace")
        spec = edit.get("spec")
        replacement = edit.get("content", "")
        count = edit.get("count", 1)
        match_mode = edit.get("match_mode", "exact")

        if not spec:
            raise ToolError("Missing 'spec' in edit", code="ValidationError")

        if match_mode not in ["exact", "regex"]:
            raise ToolError(f"Unsupported match_mode: {match_mode}", 
                          code="ValidationError")

        # Check Matches
        if match_mode == "regex":
            try:
                # Compile regex with multiline flag? 
                # Usually code edits span lines.
                pattern = re.compile(spec, re.MULTILINE)
            except re.error as e:
                raise ToolError(f"Invalid regex: {e}", code="ValidationError")
            
            matches = len(pattern.findall(content))
        else:
            matches = content.count(spec)
        
        if matches != count:
            # Idempotency Check
            # If we expected N matches but found 0, maybe it's already done?
            # For distinctness: check if 'replacement' is in content? 
            # In regex mode, replacement might be dynamic \1, \2, so hard to check presence perfectly.
            # But simple check:
            
            # Simple Idempotency: If exact match failed (0), but content already contains replacement (literal).
            # This is heuristics. 
            
            if matches == 0 and op == "replace":
                 # If using regex, we can't easily valid replacement presence if it uses groups.
                 # But if standard string, we can try.
                 if match_mode == "exact" and replacement in content:
                     return content
                 
                 # Relaxed check for regex? 
                 # For now, strict failure if 0 matches unless exact replacement found.
            
            # If strictly 0 found, it's a "Not Found" error usually
            if matches == 0:
                 raise ToolError(f"Target text not found: '{spec}'", 
                               code="PatchError")
            
            # Ambiguity Error
            raise ToolError(
                f"Match count mismatch: Expected {count}, Found {matches}",
                code="PatchError"
            )

        # Apply
        if op == "replace":
            if match_mode == "regex":
                # re.sub replaces ALL occurrences by default
                # But we validated count == matches.
                # So we are replacing ALL matches.
                # If user meant "replace the first one", they should have crafted a more specific regex
                # or we should support 'count' arg in sub? 
                # re.sub(pattern, repl, string, count=0)
                # But we want to ensure we replace *exactly* N instances?
                # We already verified len(findall) == count. 
                # So re.sub will replace exactly count instances.
                return pattern.sub(replacement, content)
            else:
                return content.replace(spec, replacement)
                
        elif op == "delete":
            if match_mode == "regex":
                return pattern.sub("", content)
            else:
                return content.replace(spec, "")
                
        elif op == "append_after":
             if match_mode == "regex":
                 # Use backreference to keep match? 
                 # replacement = \g<0>\nNEW
                 return pattern.sub(r"\g<0>\n" + replacement, content)
             else:
                return content.replace(spec, spec + "\n" + replacement)
                
        elif op == "prepend_before":
            if match_mode == "regex":
                 # replacement = NEW\n\g<0>
                 return pattern.sub(replacement + r"\n\g<0>", content)
            else:
                return content.replace(spec, replacement + "\n" + spec)
        else:
            raise ToolError(f"Unknown edit operation: {op}", 
                          code="ValidationError")
