import importlib
import json
import os
import signal
import sys
import time
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional

from flow.atoms import Atom, AtomResult, ManualInterventionAtom
from flow.engine.models import RegistryError, RootNotFoundError

if TYPE_CHECKING:
    from flow.domain.models import StatusTree, Task


class Engine:
    def __init__(self) -> None:
        self.root: Optional[Path] = None
        self.flow_dir: Optional[Path] = None
        self.registry_map: Dict[str, str] = {}
        self.persister: Any = None
        self.context: Dict[str, Any] = {}
        self.expected_version: Optional[str] = None

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
            # T7.03 implies empty config handling if empty file,
            # but if missing? Start with empty.
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
        from flow.atoms import Atom

        for atom_name, class_path in self.registry_map.items():
            try:
                module_name, class_name = class_path.rsplit(".", 1)
                module = importlib.import_module(module_name)
                atom_class = getattr(module, class_name)

                if not issubclass(atom_class, Atom):
                    # It's importable but not an Atom
                    raise RegistryError(
                        f"Atom '{atom_name}' ({class_path}) "
                        f"is not a subclass of Atom."
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
        """
        import re

        # T2.01 Explicit Metadata Match
        # Policy: Must be distinct tag.
        # Regex: Start/Space + Tag + Space/End
        if re.search(r"(?:^|\s)<!-- type: flow -->(?:$|\s)", task.name):
            from flow.atoms import FlowEngineAtom

            return FlowEngineAtom()

        # 2. Registry Match (T2.02)
        # Regex to find [AtomName] at start of string
        # T2.08: Case Sensitivity? Registry keys are usually PascalCase.
        # T2.10: Invisible Character Dispatch (Normalization)
        # Remove zero-width spaces (\u200b) etc.
        clean_name = task.name.replace("\u200b", "").strip()

        # Let's extract the tag content first.
        atom_tag_re = re.compile(r"^\[([a-zA-Z0-9_]+)\]")
        match = atom_tag_re.match(clean_name)

        if match:
            atom_key = match.group(1)

            # Strict Lookup in registry (Case-Sensitive T2.08)
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

                    sys.stderr.write(f"DEBUG: Import Failed for {atom_key}: {e}\\n")
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

            if (
                self.expected_version
                and tree.headers.get("Version")
                and tree.headers.get("Version") != self.expected_version
            ):
                from flow.domain.models import ConfigVersionMismatchError

                raise ConfigVersionMismatchError(
                    f"Version drifted! Expected {self.expected_version}, got {tree.headers.get('Version')}"
                )

            return tree
        except Exception as e:
            # Check for backup recovery (T2.06)
            from flow.domain.models import (
                ConfigVersionMismatchError,
                IntegrityError,
                StatusParsingError,
            )

            if isinstance(e, (StatusParsingError, IntegrityError)):
                try:
                    parser.decline_changes()
                    tree = parser.load()
                    tree._reindex()
                    return tree
                except Exception:
                    raise e
            raise

    def find_active_task(self) -> Optional["Task"]:
        """
        Finds the 'active' task.
        Recursive Logic for Fractal Zoom (T7.07).
        """
        tree = self.load_status()
        return self._recursive_find_active(tree, self.root)

    def _recursive_find_active(
        self, tree: "StatusTree", current_root: Optional[Path]
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
                    if self.flow_dir is not None and self.root is not None:
                        sub_path = SafePath(self.flow_dir, active.ref)
                        if sub_path.exists():
                            sub_parser = StatusParser(
                                self.root
                            )  # Parser needs project root to find .flow
                            # Manually load specific file?
                            sub_tree = sub_parser.load(active.ref)
                            sub_tree._reindex()

                        # Recurse
                        deep_active = self._recursive_find_active(sub_tree, self.root)
                        if deep_active:
                            return deep_active

                        # If sub-flow has no active task, but parent is active?
                        # Fallback to smart resume in sub-flow?

                        # If sub-flow is DONE, then we shouldn't be here
                        # (Parent should be done).
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
                    # Return proxy task so we can maybe run it
                    pass

            return active

        # 2. Smart Resume (First Pending) in CURRENT tree
        # Only if we are at the ROOT level
        # (recursion depth 0, or caller handles it?)
        # Logic: If no active task in Root, start first pending.
        return self._find_first_pending(tree.root_tasks)

    def _find_first_pending(self, tasks: List["Task"]) -> Optional["Task"]:
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
        if task.status in ("done", "skipped"):
            print(f"Idempotent skip: task {task.name} is already {task.status}")
            return

        has_lock = False
        self._validate_hydration()

        try:
            # 1. Register Signals (T7.06)
            self._register_signal_handlers(task)

            # 2. Acquire Lock & Check Circuit Breaker
            self._handle_lock_acquisition_safely(task)
            has_lock = True

            # 2. Execute Task
            self._execute_task_lifecycle(task)

        except Exception as e:
            self._handle_crash(task, e)
        finally:
            # Restore signal handlers? (For now, process exits anyway)
            if has_lock:
                self._release_intent_lock()

    def _register_signal_handlers(self, task: "Task") -> None:
        # T7.06 SIGINT Handling
        def handler(signum: int, frame: Any) -> None:
            print(f"Caught signal {signum}. Saving state and exiting...")
            try:
                if task:
                    self._handle_crash(
                        task, InterruptedError("Process Interrupted by User")
                    )
                    sys.exit(1)
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
        print(f"FATAL: Circuit Breaker Triggered for Task {task.id}", file=sys.stderr)
        tree = self.load_status()
        tree.update_task(task.id, status="error")
        self.persister.save(tree)
        self._release_intent_lock()
        raise SystemExit(1)

    def _run_atom_isolated(
        self, atom: "Atom", read_only_context: MappingProxyType
    ) -> "AtomResult":
        import concurrent.futures

        # T9 DAU Defenses
        orig_stdout = sys.stdout
        orig_environ = os.environ.copy()

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(atom.run, read_only_context)  # type: ignore
        timeout_val = getattr(atom.config, "timeout", None)
        try:
            result = future.result(timeout=timeout_val)
        except concurrent.futures.TimeoutError:
            raise TimeoutError(
                f"Atom '{atom.__class__.__name__}' execution timed out after {timeout_val} seconds"
            )
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        # T9.01 sys.stdout Hijacking Defense
        if sys.stdout is not orig_stdout:
            sys.stdout = orig_stdout
            raise RuntimeError("EnvironmentPollutionError: sys.stdout was hijacked!")

        # T9.02 Dynamic os.environ Mutation Defense
        if os.environ != orig_environ:
            os.environ.clear()
            os.environ.update(orig_environ)
            raise RuntimeError("EnvironmentPollutionError: os.environ was mutated!")

        from flow.atoms import AtomResult

        if not isinstance(result, AtomResult):
            raise TypeError("Atom did not return an AtomResult")

        return result

    def _handle_retry_status(
        self, task: "Task", result: "AtomResult"
    ) -> Literal["pending", "error"]:
        import sys
        import time

        # T8.06 Maximum Retry Circuit Breaker
        retry_key = f"__retry_count_{task.id}__"
        current_retries = self.context.get(retry_key, 0) + 1
        self.context[retry_key] = current_retries

        if current_retries > 3:
            print(
                f"FATAL_LOOP: Max retries exceeded for {task.id}",
                file=sys.stderr,
            )
            return "error"
        else:
            if (
                hasattr(result, "retry_strategy")
                and result.retry_strategy
                and result.retry_strategy.name == "BACKOFF"
            ):
                now = time.time()
                mono = time.monotonic()
                # Detect temporal drift on a retry loop
                last_mono = self.context.get(f"__last_mono_{task.id}__")
                last_time = self.context.get(f"__last_time_{task.id}__")
                if last_mono and last_time:
                    mono_diff = mono - last_mono
                    time_diff = now - last_time
                    # If time.time() drifts more than 5 seconds from time.monotonic()
                    if abs(time_diff - mono_diff) > 5.0:
                        raise RuntimeError(
                            "NTP Clock Leap / Temporal Drift detected between retries. Safely freezing."
                        )
                self.context[f"__last_mono_{task.id}__"] = mono
                self.context[f"__last_time_{task.id}__"] = now
                self.context[f"__next_retry_at_{task.id}__"] = now + (
                    2**current_retries
                )  # exponential backoff
            return "pending"

    def _merge_exports(
        self, result: "AtomResult"
    ) -> None:
        """Validate and merge exports into context."""
        self._validate_exports_security(result.exports)
        for k, v in result.exports.items():
            if k in self.context:
                old_val = self.context[k]
                if old_val is not None and not isinstance(v, type(old_val)):
                    raise TypeError(
                        f"Type shadowing detected for key '{k}': "
                        f"expected {type(old_val).__name__}, got {type(v).__name__}"
                    )
        self.context.update(result.exports)

    def _process_atom_result(
        self, task: "Task", result: "AtomResult"
    ) -> Literal["pending", "active", "done", "skipped", "error", "RETRY"]:
        if result and result.success and result.exports:
            self._merge_exports(result)

        _STATUS_MAP = {
            "SUCCESS": "done",
            "FAILED": "error",
            "SKIPPED": "skipped",
        }

        if hasattr(result.status, "name"):
            name = result.status.name.upper()
            if name == "RETRY":
                return self._handle_retry_status(task, result)
            return _STATUS_MAP.get(name, "done")
        return "done"

    def _execute_task_lifecycle(self, task: "Task") -> None:

        # Update State -> Active
        self.context["__task_id__"] = task.id
        self.context["__task_name__"] = task.name
        self.context["__task_ref__"] = task.ref
        tree = self.load_status()
        tree.update_task(task.id, status="active")
        self.persister.save(tree)

        # Dispatch
        atom = self.dispatch(task)

        try:
            read_only_context = MappingProxyType(self.context)
            result = self._run_atom_isolated(atom, read_only_context)
            final_status = self._process_atom_result(task, result)

            # T3.07 Phantom Lock Deletion Defense
            if self.flow_dir:
                lock_file = self.flow_dir / "intent.lock"
                if not lock_file.exists():
                    from flow.domain.models import LostLockError

                    raise LostLockError(
                        "Phantom Lock Deletion! Intent.lock is missing during execution!"
                    )

            tree = self.load_status()
            tree.update_task(task.id, status=final_status)
            self.persister.save(tree)
        finally:
            if not getattr(atom, "_cleanup_called", False):
                import concurrent.futures

                executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                cleanup_future = executor.submit(atom.cleanup)
                try:
                    cleanup_future.result(
                        timeout=2.0
                    )  # T8.13 Hanging Isolation Timeout
                except concurrent.futures.TimeoutError:
                    print(
                        f"CLEANUP TIMEOUT: atom {task.id} exceeded teardown budget",
                        file=sys.stderr,
                    )
                except Exception as e:
                    import traceback

                    print(f"CLEANUP ERROR: {e}", file=sys.stderr)
                    traceback.print_exc()
                finally:
                    executor.shutdown(wait=False, cancel_futures=True)

    def _handle_crash(self, task: "Task", e: Exception) -> None:
        """Handles unhandled Atom exceptions and updates state gracefully."""
        import sys

        try:
            import traceback

            print(f"CRASH: {e}", file=sys.stderr)
            traceback.print_exc()

            tree = self.load_status()
            # Depending on V1.2 specifications, failed states map to specific statuses.
            # Usually we use 'error', but map to 'skipped' / 'failed' based on requirements.
            tree.update_task(task.id, status="error")
            self.persister.save(tree)
        except Exception as meta_e:
            import sys

            print(
                f"DOUBLE FAULT in crash handler: {type(meta_e).__name__}",
                file=sys.stderr,
            )
            try:
                # Secondary fallback: attempt minimal safe state update without relying on str(e)
                tree = self.load_status()
                tree.update_task(task.id, status="error")  # 'FAILED_CRITICAL' mapping
                self.persister.save(tree)
            except Exception:
                pass  # Last resort, prevent global thread crash

        sys.exit(1)

    def _validate_exports_security(self, exports: Dict[str, Any]) -> None:
        import re

        try:
            payload = json.dumps(exports, allow_nan=False)
            if len(payload) > 500 * 1024:
                from flow.domain.models import PayloadTooLargeError
                raise PayloadTooLargeError(
                    "OOM Defense (T7.01): Exports size limit exceeded"
                )
        except (TypeError, OverflowError, ValueError) as e:
            raise RuntimeError(f"Atom returned non-serializable exports: {e}")

        if re.search(r"(\\u001b|\x1b|\\\\x1b)\[", payload):
            raise ValueError("ANSI_Escape_Sequence_Detected")

        self._validate_export_node(exports)

    def _validate_export_node(self, obj: Any, depth: int = 0) -> None:
        """Recursively validate nesting, types, and reserved keys."""
        if depth > 500:
            raise ValueError("Max_Nesting_Exceeded")

        if type(obj) is dict:
            for k, v in obj.items():
                if not isinstance(k, str):
                    raise TypeError(
                        "Export dict keys must be strict strings (T6.11)"
                    )
                if k.startswith("__") or k in ["run_id", "status"]:
                    raise ValueError(
                        f"Reserved or Dunder key injection restricted: {k}"
                    )
                self._validate_export_node(v, depth + 1)
        elif type(obj) is list:
            for v in obj:
                self._validate_export_node(v, depth + 1)
        elif type(obj) in (int, float, str, bool, type(None)):
            pass
        else:
            raise TypeError(
                f"Strict validation requires exact types, rejected: {type(obj)}"
            )

    def _check_stale_lock(self, lock_file: Path, lock_data: dict) -> None:
        """Check if existing lock is stale. Removes it if > 30s old, otherwise raises."""
        probe_file = lock_file.with_name("time.probe")
        try:
            probe_file.touch()
            current_fs_time = probe_file.stat().st_mtime
            probe_file.unlink()
        except OSError:
            current_fs_time = time.time()

        lock_fs_time = lock_file.stat().st_mtime
        if current_fs_time - lock_fs_time > 30:
            try:
                lock_file.unlink()
            except FileNotFoundError:
                pass
        else:
            raise RuntimeError(
                f"Engine Locked by {lock_data.get('task_id')}"
            )

    def _check_existing_lock(self, lock_file: Path, task_id: str) -> int:
        """Handle existing lock file. Returns retry_count."""
        try:
            content = lock_file.read_text(encoding="utf-8")
            if not content:
                return 0
            lock_data = json.loads(content)

            if lock_data.get("pid") == os.getpid():
                return -1  # sentinel: we own this lock, skip

            if lock_data.get("task_id") == task_id:
                retry_count = lock_data.get("retry_count", 0) + 1
                if retry_count > 3:
                    from flow.engine.models import CircuitBreakerError
                    raise CircuitBreakerError(
                        f"Task {task_id} failed {retry_count} times. Giving up."
                    )
                return retry_count

            self._check_stale_lock(lock_file, lock_data)
        except (json.JSONDecodeError, OSError):
            pass  # Corrupt lock - Steal it
        return 0

    def _acquire_intent_lock(self, task_id: str):
        flow_dir = self.flow_dir
        if not flow_dir:
            return

        lock_file = flow_dir / "intent.lock"
        retry_count = 0

        if lock_file.exists():
            retry_count = self._check_existing_lock(lock_file, task_id)
            if retry_count == -1:
                return  # We already own the lock

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


def fan_in_reducer(
    base_snapshot: Dict[str, Any], *branch_contexts: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Merges multiple branch contexts (or exports) back into a base snapshot.
    Raises SchemaCollisionError if multiple branches modified or exported the same key.
    """
    merged = dict(base_snapshot)
    modifications = {}  # key -> branch_index

    # Identify changes per branch
    for i, branch in enumerate(branch_contexts):
        for k, v in branch.items():
            # If the key is new or the value differs from base
            if k not in base_snapshot or base_snapshot[k] != v:
                if k in modifications and modifications[k] != i:
                    from flow.domain.models import SchemaCollisionError

                    raise SchemaCollisionError(
                        f"Topological Merge Conflict: Key '{k}' modified by multiple parallel branches."
                    )
                modifications[k] = i
                merged[k] = v

    return merged
