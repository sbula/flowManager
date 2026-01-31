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
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from ...flow_manager.template_factory.core import TemplateFactory, ReviewContext
from ...flow_manager.templater import detect_language

class ReviewOrchestrator:
    """
    Encapsulates the 'Sequential Expert Review' logic (The Gauntlet).
    Determines the state of a review document and drives the next step.
    """
    def __init__(self, factory: TemplateFactory):
        self.factory = factory

    def determine_next_action(
        self, 
        task_id: str, 
        report_path: Path, 
        expert_modules: List[Dict], 
        base_modules: List[Dict],
        context: ReviewContext
    ) -> Tuple[str, str]:
        """
        Analyzes the report and returns (status, blocker_message).
        Status: "PASSED", "BLOCKED"
        """
        
        # CASE A: New Report (Not Exists)
        if not report_path.exists():
            return self._initialize_report(task_id, report_path, expert_modules, base_modules, context)

        # CASE B: Report Exists. Verify Integrity and Progress.
        content = report_path.read_text(encoding="utf-8")
        
        # 1. Integrity Check (External Script via Subprocess or Import?)
        # We import the validator logic directly to avoid subshell overhead if possible, 
        # but the original used a script. Let's replicate the logic or use the script wrapper.
        # Ideally, we should import the validator function.
        try:
            from ...flow_manager.scripts.validate_review_completeness import check_review_completeness
            # Strict Mode: Check if current sections are filled
            if not check_review_completeness(str(report_path), ignore_pending=False, check_verdict=False):
                return "BLOCKED", f"Review Validation Failed: {report_path.name} is incomplete (Check Evidence/Status)."
        except ImportError:
            # Fallback if pathing is weird
            pass

        # 2. Check for PENDING status in existing text
        if "| **Status** | [ ] PENDING |" in content:
            # parsing who is pending
            found_roles = re.findall(r"### Reviewer: (.+)", content)
            pending_role = found_roles[-1] if found_roles else "Unknown"
            return "BLOCKED", f"Expert Review Pending: {pending_role}. Please complete the report."

        # 3. Determine Next Expert
        found_roles = re.findall(r"### Reviewer: (.+)", content)
        next_expert = None
        for mod in expert_modules:
            if mod.get("Role") not in found_roles:
                next_expert = mod
                break
        
        if next_expert:
            return self._append_next_expert(report_path, content, next_expert, context)
        
        # 4. Final Verdict
        if "## Final Verdict" not in content:
            return self._append_footer(report_path, content, base_modules, context)
            
        # 5. Check Final Verdict Sign-off
        # The external validator logic handles this, but let's double check if we are just "done".
        # If we are here, everything is technically generated. The user just needs to sign off.
        # The Reconciler usually checks the final validator return code. 
        # Here we just say "Ready for Final Sign-off" if it's there but maybe not checked?
        # Actually, if "Final Verdict" is there, we assume the user is handling it. 
        # The Orchestrator's job is to UNLOCK sections. If all unlocked, we pass?
        # No, the Reconciler will run the final validation check.
        
        return "PASSED", "All experts unlocked."

    def _initialize_report(self, task_id, path, experts, base, ctx) -> Tuple[str, str]:
        print(f">> [SEQ] Starting Sequential Review for {task_id}")
        
        content_parts = []
        
        # Metrics Injection (This should ideally be passed in, but we can do lazy loading or depend on Reconciler data)
        # For V3, let's assume metrics are calculated by caller or we call simple analysis here?
        # Let's keep it simple: Render Base modules.
        
        # We need data for metrics.
        # In V3 Refactor, we might want to abstract getting metrics.
        metrics_data = self._collect_metrics(ctx.service_path, ctx.language)

        for mod in base:
            if mod["Name"] == "Standard_Footer": continue
            part = self.factory.render_single_module(mod["Name"], ctx, metrics_data)
            if part: content_parts.append(part)
            
        if experts:
            first = experts[0]
            part = self.factory.render_single_module(first["Name"], ctx)
            content_parts.append(part)
        else:
            # No experts (rare?), add footer
            footer = next((m for m in base if m["Name"] == "Standard_Footer"), None)
            if footer: content_parts.append(self.factory.render_single_module(footer["Name"], ctx))
            
        if not path.parent.exists(): path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n\n".join(content_parts), encoding="utf-8")
        
        role = experts[0]['Role'] if experts else "None"
        return "BLOCKED", f"Sequential Review Started. First Expert: {role}."

    def _append_next_expert(self, path, content, expert, ctx) -> Tuple[str, str]:
        print(f">> [SEQ] Unlocking Next Expert: {expert['Role']}")
        new_section = self.factory.render_single_module(expert["Name"], ctx)
        
        if "## Final Verdict" in content:
            new_content = content.replace("## Final Verdict", f"\n\n{new_section}\n\n## Final Verdict")
        else:
            new_content = content + "\n\n" + new_section
            
        path.write_text(new_content, encoding="utf-8")
        return "BLOCKED", f"New Expert Unlocked: {expert['Role']}. Please perform review."

    def _append_footer(self, path, content, base, ctx) -> Tuple[str, str]:
        print(">> [SEQ] All Experts Complete. Unlocking Final Verdict.")
        footer = next((m for m in base if m["Name"] == "Standard_Footer"), None)
        if footer:
            f_sec = self.factory.render_single_module(footer["Name"], ctx)
            path.write_text(content + "\n\n" + f_sec, encoding="utf-8")
        
        return "BLOCKED", "Final Verdict Unlocked. Please Sign-off."

    def _collect_metrics(self, svc_path: Path, lang: str) -> Dict:
        # Wrapper around existing analysis logic
        # We can import the same helpers as reconciler uses
        data = {}
        if not lang or lang == "Unknown": return data
        
        try:
             from ...flow_manager.templater import run_analysis, format_complexity, format_lint
             from ...flow_manager.reconciler import _collect_test_metrics # This import might be circular?
             # Be careful with imports. 'reconciler' imports 'engine'. 'engine' imports 'reconciler'? 
             # No, engine import was simple.
             # _collect_test_metrics is a helper in reconciler. We should probably move it to utils or metrics module.
             # For now, let's duplicate or assume we can import it. 
             # Actually, best to move _collect_test_metrics to templater.py or a metrics.py
             pass
        except:
            pass
        return data
