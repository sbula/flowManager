import json
from pathlib import Path
from typing import List, Dict, Any

class RulesEngine:
    def __init__(self, config_root: Path):
        self.config_path = config_root / "rules.json"
        self.rules = self._load_rules()

    def _load_rules(self) -> Dict[str, List[Dict]]:
        if not self.config_path.exists():
            return {}
        try:
            data = json.loads(self.config_path.read_text(encoding="utf-8"))
            return data.get("Rules", {})
        except Exception as e:
            print(f">> [RULES] Error loading rules.json: {e}")
            return {}

    def resolve(self, rule_type: str, context: Dict[str, Any]) -> str:
        """
        Resolves a rule type (AuthorRole, CouncilSet) based on context.
        Context expected keys: 'ServiceType' (str), 'Tags' (list of str)
        """
        if rule_type not in self.rules:
            return "Unknown"

        candidates = self.rules[rule_type]
        service_type = context.get("ServiceType", "")
        tags = set(context.get("Tags", []))

        # 1. Tags (Priority)
        # Check rules that have Tags defined
        for rule in candidates:
            if "Tags" in rule:
                rule_tags = set(rule["Tags"])
                # If ANY tag matches (Intersection)
                if tags.intersection(rule_tags):
                    return rule["Result"]

        # 2. Service Type
        for rule in candidates:
            if "ServiceType" in rule:
                # Direct match or partial match?
                # Configuration assumes exact strings usually, but let's stick to exact for now as per JSON.
                if rule["ServiceType"] == service_type:
                    return rule["Result"]
                # Heuristic: If ServiceType in rules is "Engine" but context is "ExecutionEngine" -> maybe?
                # For now, strict.

        # 3. Default
        for rule in candidates:
            if rule.get("Default"):
                return rule["Result"]

        return "Unknown"

    def resolve_author_role(self, service_type: str, tags: List[str]) -> str:
        return self.resolve("AuthorRole", {"ServiceType": service_type, "Tags": tags})

    def resolve_council_set(self, service_type: str, tags: List[str]) -> str:
        return self.resolve("CouncilSet", {"ServiceType": service_type, "Tags": tags})
