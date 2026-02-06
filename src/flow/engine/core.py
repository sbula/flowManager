import importlib
import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

from flow.engine.atoms import Atom, FlowEngineAtom, ManualInterventionAtom
from flow.engine.models import RegistryError, RootNotFoundError

if TYPE_CHECKING:
    from flow.domain.models import StatusTree, Task


class Engine:
    def __init__(self):
        self.root: Optional[Path] = None
        self.flow_dir: Optional[Path] = None
        self.registry_map: Dict[str, str] = {}
        self.persister = None
        self.context: Dict[str, Any] = {}

    def hydrate(self):
        """
        Discovers the project root by looking for .flow/ folder.
        Scanning upwards from CWD.
        """
        cwd = Path(os.getcwd()).resolve()

        current = cwd
        found = False

        # Scan upwards (root of drive logic handled by checks)
        while True:
            candidate = current / ".flow"

            # T1.08: Strict Resolution (Detect Symlink Loops)
            try:
                if candidate.exists():
                    candidate = candidate.resolve(strict=True)
            except (RuntimeError, OSError):
                # RecursionError or Loop
                raise RootNotFoundError("Symlink loop detected during hydration.")

            # T1.09: If .flow exists but is a file -> CRASH.
            if candidate.exists() and not candidate.is_dir():
                raise RootNotFoundError(
                    f"Found .flow at {candidate} but it is not a directory."
                )

            if candidate.exists() and candidate.is_dir():
                self.root = current
                self.flow_dir = candidate
                found = True
                break

            parent = current.parent
            if parent == current:  # Reached root of filesystem
                break
            current = parent

        if not found:
            raise RootNotFoundError(f"No .flow/ directory found starting from {cwd}")

        # Load Registry
        self._load_registry()

        # Init components
        from flow.domain.persister import StatusPersister

        self.persister = StatusPersister(self.flow_dir)
        self.context: Dict[str, Any] = {"__root__": self.root}

    def _load_registry(self):
        reg_file = self.flow_dir / "flow.registry.json"
        if not reg_file.exists():
            # T7.03 implies empty config handling if empty file, but if missing?
            # Start with empty.
            self.registry_map = {}
            return

        try:
            data = json.loads(reg_file.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise RegistryError("Invalid Registry: Root must be a dictionary.")
            self.registry_map = data
            self._validate_registry_integrity()
        except json.JSONDecodeError:
            raise RegistryError("Invalid JSON in flow.registry.json")

    def _validate_registry_integrity(self):
        """Paranoid check: Ensure all registered atoms are importable."""
        from flow.engine.atoms import Atom

        for atom_name, class_path in self.registry_map.items():
            try:
                module_name, class_name = class_path.rsplit(".", 1)
                module = importlib.import_module(module_name)
                atom_class = getattr(module, class_name)

                if not issubclass(atom_class, Atom):
                    # It's importable but not an Atom
                    raise RegistryError(
                        f"Atom '{atom_name}' ({class_path}) is not a subclass of Atom."
                    )

            except (ImportError, AttributeError, ValueError) as e:
                # Catch ValueError if rsplit fails (bad format)
                raise RegistryError(f"Registry Integrity Failed for '{atom_name}': {e}")

    def get_atom_class(self, atom_name: str) -> str:
        """
        Returns class path for an atom.
        Does NOT import it yet (that's Execution phase).
        """
        if atom_name not in self.registry_map:
            raise RegistryError(f"Atom '{atom_name}' not found in registry.")
        return self.registry_map[atom_name]

    def dispatch(self, task) -> "Atom":
        """
        Determines the correct Atom for a Task.
        Priority:
        1. Metadata <!-- type: flow -->
        2. Registry Match [AtomName]
        3. Fallback -> ManualInterventionAtom

        Logic:
        - Parse name for [Atom] tag using regex.
        - Look up class in registry.
        - Import class.
        - Verify subclass Atom.
        - Instantiate.
        """
        import re

        # T2.01 Explicit Metadata Match
        # Policy: Must be distinct tag.
        # Regex: Start/Space + Tag + Space/End
        if re.search(r"(?:^|\s)<!-- type: flow -->(?:$|\s)", task.name):
            from flow.engine.atoms import FlowEngineAtom

            return FlowEngineAtom()

        # 2. Registry Match (T2.02)
        # Regex to find [AtomName] at start of string
        # T2.08: Case Sensitivity? Registry keys are usually PascalCase or specific.
        # T2.10: Invisible Character Dispatch (Normalization)
        # Remove zero-width spaces (\u200b) etc.
        clean_name = task.name.replace("\u200b", "").strip()

        # Let's extract the tag content first.
        atom_tag_re = re.compile(r"^\[([a-zA-Z0-9_]+)\]")
        match = atom_tag_re.match(clean_name)

        if match:
            atom_key = match.group(1)

            # Lookup in registry
            if atom_key in self.registry_map:
                class_path = self.registry_map[atom_key]
                try:
                    # Import Logic
                    module_name, class_name = class_path.rsplit(".", 1)
                    module = importlib.import_module(module_name)
                    atom_class = getattr(module, class_name)

                    # Verify Subclass (T2.05)
                    if not issubclass(atom_class, Atom):
                        # Log error? Return Manual?
                        # Spec says "Safety check". Fallback is safe.
                        return ManualInterventionAtom()

                    return atom_class()
                except Exception as e:
                    # T1.18 Atom Import/Init Crash -> Manual/Broken
                    # Catch everything to ensure Dispatch Safety (T2.04/T2.05)
                    import sys

                    sys.stderr.write(f"DEBUG: Import Failed for {atom_key}: {e}\n")
                    import traceback

                    traceback.print_exc(file=sys.stderr)
                    return ManualInterventionAtom()

        # 3. Fallback
        return ManualInterventionAtom()

    def load_status(self) -> "StatusTree":
        """Delegate to StatusParser."""
        from flow.domain.parser import StatusParser

        if not self.root:
            raise RootNotFoundError("Root not set.")

        root = self.root
        parser = StatusParser(root)
        try:
            tree = parser.load()
            tree._reindex()
            return tree
        except Exception:
            # If load fails, what? Return empty? Or raise?
            # T3.02 Crash handling might catch this at higher level
            raise

    def find_active_task(self) -> Optional["Task"]:
        """
        Finds the 'active' task.
        Recursive Logic for Fractal Zoom (T7.07).
        """
        tree = self.load_status()
        return self._recursive_find_active(tree, self.root)

    def _recursive_find_active(
        self, tree: "StatusTree", current_root: Path
    ) -> Optional["Task"]:
        """
        Helper that traverses sub-flows (Fractal Zoom).
        """
        # 1. Check current tree for active
        active = tree.find_active_task()
        if active:
            # Check if this active task is a Proxy for a Sub-Flow
            if active.ref and active.ref.endswith(".md"):
                # Load Sub-Flow
                # T1.03 Path Resolution Safety
                from flow.domain.parser import StatusParser
                from flow.engine.security import SafePath

                try:
                    # Path is relative to .flow root of current context?
                    # Actually refs are relative to .flow/
                    # If we are in root/.flow/status.md, ref="sub.md" -> root/.flow/sub.md

                    # But if we are in a sub-flow?
                    # Standard: All refs relative to project .flow/ root?
                    # OR relative to the file defining them?
                    # Spec V1.2. Says "Anchor Rule: All paths relative to .flow/"

                    sub_path = SafePath(self.flow_dir, active.ref)
                    if sub_path.exists():
                        sub_parser = StatusParser(
                            self.root
                        )  # Parser needs project root to find .flow
                        # Manually load specific file? StatusParser.load() takes filename.
                        # active.ref is filename relative to .flow/
                        sub_tree = sub_parser.load(active.ref)
                        sub_tree._reindex()

                        # Recurse
                        deep_active = self._recursive_find_active(sub_tree, self.root)
                        if deep_active:
                            return deep_active

                        # If sub-flow has no active task, but parent is active?
                        # Fallback to smart resume in sub-flow?

                        # If sub-flow is DONE, then we shouldn't be here (Parent should be done).
                        # If sub-flow is PENDING, we should start it.

                        first_pending = self._find_first_pending(sub_tree.root_tasks)
                        if first_pending:
                            return first_pending

                        # If no pending in sub-flow? Then it's done?
                        # Then Parent should move to Done?
                        # Manual intervention needed if state mismatch.
                        return active

                except Exception:
                    # If sub-flow fails load, return the proxy task itself?
                    # Or crash?
                    # Return proxy task so we can maybe run it (or fail running it)
                    pass

            return active

        # 2. Smart Resume (First Pending) in CURRENT tree
        # Only if we are at the ROOT level (recursion depth 0, or caller handles it?)
        # Logic: If no active task in Root, start first pending.
        return self._find_first_pending(tree.root_tasks)

    def _find_first_pending(self, tasks):
        for t in tasks:
            if t.status == "pending":
                return t
            res = self._find_first_pending(t.children)
            if res:
                return res
        return None

    def run_task(self, task: "Task"):
        """
        Executes a task.
        1. Validates State (Pending -> Active)
        2. Dispatches
        3. Updates State (Active/Done)
        4. Persist
        """
        self._validate_hydration()

        try:
            # 1. Register Signals (T7.06)
            self._register_signal_handlers(task)

            # 2. Acquire Lock & Check Circuit Breaker
            self._handle_lock_acquisition_safely(task)

            # 2. Execute Task
            self._execute_task_lifecycle(task)

        except Exception as e:
            self._handle_crash(task, e)
        finally:
            # Restore signal handlers? (For now, process exits anyway)
            self._release_intent_lock()

    def _register_signal_handlers(self, task):
        # T7.06 SIGINT Handling
        def handler(signum, frame):
            print(f"\nCaught signal {signum}. Saving state and exiting...")
            try:
                if task:
                    self._handle_crash(
                        task, InterruptedError("Process Interrupted by User")
                    )
                else:
                    sys.exit(1)
            except Exception:
                sys.exit(1)

        signal.signal(signal.SIGINT, handler)
        # Also handle SIGTERM?
        signal.signal(signal.SIGTERM, handler)

    def _validate_hydration(self):
        if not self.root:
            from flow.engine.models import RootNotFoundError

            raise RootNotFoundError("Root not set.")
        if not self.flow_dir:
            from flow.engine.models import RootNotFoundError

            raise RootNotFoundError("Engine not hydrated.")

    def _handle_lock_acquisition_safely(self, task):
        try:
            self._acquire_intent_lock(task.id)
        except Exception as e:
            from flow.engine.models import CircuitBreakerError

            if isinstance(e, CircuitBreakerError):
                self._handle_circuit_breaker(task)
            raise

    def _handle_circuit_breaker(self, task):
        tree = self.load_status()
        tree.update_task(task.id, status="error")
        self.persister.save(tree)
        self._release_intent_lock()
        raise SystemExit(1)

    def _execute_task_lifecycle(self, task):
        import types

        # Update State -> Active
        self.context["__task_id__"] = task.id
        self.context["__task_name__"] = task.name
        self.context["__task_ref__"] = task.ref
        tree = self.load_status()
        tree.update_task(task.id, status="active")
        self.persister.save(tree)

        # Dispatch
        atom = self.dispatch(task)

        # Run with Immutable Context (T3.12)
        # Atoms receive a Read-Only view to prevent side-channel corruption.
        read_only_context = types.MappingProxyType(self.context)
        result = atom.run(read_only_context)

        # Merge Context
        if result and result.success and result.exports:
            # T3.10: Validate Serialization Safety
            # Ensure exports don't contain non-serializable objects (sockets, files)
            # that would crash the persistence layer later.
            try:
                json.dumps(result.exports)
            except (TypeError, OverflowError) as e:
                # If non-serializable, we treat this as a Safety Violation (Error)
                # We do NOT merge the exports.
                raise RuntimeError(f"Atom returned non-serializable exports: {e}")

            self.context.update(result.exports)

        # Update State -> Done
        tree.update_task(task.id, status="done")
        self.persister.save(tree)

    def _handle_crash(self, task, e):
        print(f"CRASH: {e}")
        try:
            tree = self.load_status()
            tree.update_task(task.id, status="error")
            self.persister.save(tree)
        except Exception:
            pass
        raise SystemExit(1)

    def _acquire_intent_lock(self, task_id: str):
        flow_dir = self.flow_dir
        if not flow_dir:
            return

        lock_file = flow_dir / "intent.lock"
        retry_count = 0

        if lock_file.exists():
            try:
                content = lock_file.read_text(encoding="utf-8")
                if content:
                    lock_data = json.loads(content)

                    # 1. Check PID Ownership (Recursion/Re-entry)
                    if lock_data.get("pid") == os.getpid():
                        return

                    # 2. Check WAL Recovery (Same Task, Crashed)
                    # If task_id matches, we assume we are retrying a crashed task
                    if lock_data.get("task_id") == task_id:
                        retry_count = lock_data.get("retry_count", 0) + 1

                        # T3.02 Circuit Breaker
                        if retry_count > 3:
                            from flow.engine.models import CircuitBreakerError

                            raise CircuitBreakerError(
                                f"Task {task_id} failed {retry_count} times. Giving up."
                            )

                    # 3. Check Stale Lock (Zombie Stealing T3.11)
                    else:
                        # Different task is locked. Is it alive?
                        timestamp = lock_data.get("timestamp", 0)
                        if time.time() - timestamp > 30:  # 30s timeout
                            # Steal it
                            pass
                        else:
                            raise RuntimeError(
                                f"Engine Locked by {lock_data.get('task_id')}"
                            )

            except (json.JSONDecodeError, OSError):
                # Corrupt lock - Steal it
                pass

        # Write Lock (Update or Create)
        lock_data = {
            "pid": os.getpid(),
            "timestamp": time.time(),
            "task_id": task_id,
            "retry_count": retry_count,
        }
        lock_file.write_text(json.dumps(lock_data), encoding="utf-8")

    def _release_intent_lock(self):
        if self.flow_dir:
            lock_file = self.flow_dir / "intent.lock"
            if lock_file.exists():
                # Only unlink if WE own it?
                # For V1.3 simple unlink
                try:
                    lock_file.unlink()
                except OSError:
                    pass
