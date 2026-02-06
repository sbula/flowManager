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

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


@dataclass
class ReviewContext:
    task_id: str
    task_type: str
    service_path: Path
    service_type: str
    language: str
    feature_name: str
    tags: Set[str] = field(default_factory=set)


class TemplateFactory:
    def __init__(self, config_root: Optional[Path] = None):
        self.modules = []
        if config_root:
            self.load_modules(config_root)
        else:
            # Heuristic to find config root if not provided
            # Assume we are in workflow_core/core/template_factory/core.py
            # Config is in ../../../config
            try:
                repo_root = Path(__file__).parent.parent.parent.parent
                # Check if repo_root has workflow_core
                if (repo_root / "workflow_core").exists():
                    config = repo_root / "workflow_core" / "config"
                    self.load_modules(config)
            except:
                pass

    def load_modules(self, config_root: Path):
        m_file = config_root / "modules.json"
        if m_file.exists():
            import json

            try:
                data = json.loads(m_file.read_text(encoding="utf-8"))
                self.modules = data.get("Modules", [])
            except Exception as e:
                print(f"Error loading modules.json: {e}")

    def get_active_modules(self, context: ReviewContext) -> List[Dict[str, Any]]:
        """
        Returns a list of modules that apply to the current context.
        """
        active = []
        for m in self.modules:
            # Check Triggers
            triggers = m.get("Trigger", {})

            # 1. Type Match
            if "Type" in triggers:
                # triggers["Type"] can be list or string
                types = (
                    triggers["Type"]
                    if isinstance(triggers["Type"], list)
                    else [triggers["Type"]]
                )
                if context.service_type not in types:
                    continue

            # 2. Tag Match
            if "Tags" in triggers:
                req_tags = set(triggers["Tags"])
                if not req_tags.intersection(context.tags):
                    continue

            # 3. Language Match
            if "Language" in triggers:
                if context.language != triggers["Language"]:
                    continue

            active.append(m)
        return active

    def generate_from_modules(
        self,
        modules: List[Dict[str, Any]],
        context: ReviewContext,
        data: Dict[str, Any],
    ) -> str:
        parts = []
        for m in modules:
            parts.append(self._render_module(m, context, data))
        return "\n\n".join(parts)

    def _render_module(
        self, module_def: Dict[str, Any], context: ReviewContext, data: Dict[str, Any]
    ) -> str:
        content = module_def.get("Content", "")

        # [V7 Fix] Default Content for Experts if missing
        if not content and module_def.get("Type") == "Expert":
            role = module_def.get("Role", "Expert")
            content = (
                f"### Reviewer: {role}\n\n"
                "> Focus: General\n\n"
                "#### Status\n"
                "- [ ] APPROVE\n"
                "- [ ] REQUEST_CHANGES\n\n"
                "#### Feedback\n"
                "(Add feedback here)\n\n"
                "#### Evidence\n"
                "| Check | Status | **Evidence** |\n"
                "|---|---|---|\n"
                "| Criteria 1 | PENDING | [LINK/CODE] (Mandatory) |\n"
            )

        # Dynamic Variable Substitution
        # Use all fields from ReviewContext (converted to string)
        import dataclasses

        context_vars = dataclasses.asdict(context)

        # [V7 Fix] Merge Extra Context (data)
        if data:
            context_vars.update(data)

        # Flatten paths to string
        replacements = {f"${{{k}}}": str(v) for k, v in context_vars.items()}

        # Add aliases for legacy or dot notation if needed (though ReviewContext is flat)
        # e.g. ${feature.name} -> ${feature_name}
        if "feature_name" in context_vars:
            replacements["${feature.name}"] = context_vars["feature_name"]

        for k, v in replacements.items():
            if k in content:
                content = content.replace(k, str(v))
        return content
