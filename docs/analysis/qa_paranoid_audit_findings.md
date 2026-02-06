# Paranoid QA Audit: Specs 01_02 & 01_03 vs Reality

**Date:** 2026-02-06
**Auditor:** Antigravity (Paranoid QA Mode)
**Status:** **CRITICAL GAPS DECTECTED**

You pay me to be paranoid. I found holes in your "strict" system.

## 1. The "Lossy Comments" Lie (Spec 01_02)
**Spec Claim:** "HTML Comments (`<!-- -->`) are **DELETED** on save (T3.05)."
**Reality:** The `StatusParser` **CRASHES** if it encounters a comment line. It raises `StatusParsingError("Invalid format")`.
**The Bug:** You cannot "strip" what you cannot "load". If a user (or agent) adds a comment, the entire project status becomes unreadable.
**Misleading Test (`test_persister_write.py::t3_05_comment_stripping`):**
- This test manually builds a `StatusTree` in memory (which supports no comments) and saves it.
- **Verdict:** It proves nothing about *file processing*. It's valid verification of `save()` but ignores the critical `load()` path failure.
**Missing Test Case:**
- Create file with `<!-- valid comment -->`.
- `load()` -> Expect Success (Tree loaded, comment ignored).
- `save()` -> Expect Success (File written without comment).

## 2. The Missing Enforcer: `LoomAtom` (Spec 01_03)
**Spec Claim:** "Agents ... MUST use the Loom Atom ... Agent Isolation: STRICT."
**Reality:** `LoomAtom` does not exist in `src/flow/engine/atoms.py` or seemingly anywhere in `src/flow`.
**The Bug:** The `Loom` logic exists (`flow.engine.loom`), but the **Security Boundary** (The AtomWrapper that checks "Is this agent allowed?") is missing.
**Implication:** If you don't have the Atom, you can't dispatch to it. If you can't dispatch to it, Agents can't edit files safely. Or worse, if you expose `Loom` class directly, there are no checks.
**Missing Test Case:**
- Attempt to dispatch `[Loom] Insert` from an unauthorized context.

## 3. The "Naive" Dispatcher Myth (Spec 01_03)
**Test Claim (`test_dispatch.py::t2_07_metadata_false_context`):**
- Comment says: `# Current implementation is NAIVE (checks substring).`
**Reality:** `src/flow/engine/core.py` Line 121 uses a strict Regex: `re.search(r"(?:^|\s)<!-- type: flow -->(?:$|\s)", task.name)`.
**The Issue:** Your test comments are lying to you. They degrade confidence in the codebase. The code is actually **Robust**, but the test implies it's broken/temporary.
**Action:** Update the test comment to reflect that Strict Boundaries are implemented and verified.

## 4. Registry Faith (Spec 01_03)
**Spec Claim:** "Anything NOT in the registry does not exist."
**Reality:** `Engine.hydrate()` loads the JSON but does not **Verify** that the targets exist.
**The Risk:** If `flow.registry.json` points to `flow.atoms.missing.GhostAtom`, the Engine starts happily. It only crashes at *Dispatch Time* (Runtime).
**Recommendation:** "Paranoid Mode" demands "Startup Consistency Check". `hydrate()` should import all defined atoms to ensure the environment is valid before accepting work.

## 5. Protocol Safety & Ambiguity (Spec 01_02)
**Status:**
- **Protocol Safety**: `tests/unit/domain/test_parser_read.py` has a comment questioning if the logic exists. **It Does.** Remove the doubt.
- **Ambiguity**: `StatusParser` assumes any line starting with `- ` MUST be a task. If I write `- Just a note`, it crashes.
- **Spec Question:** Should "Bullet Points that aren't tasks" be allowed as text? Spec says "Status Markers (`[ ]`, `[x]`) are ONLY recognized at the start... Markers inside text are treated as literal".
- **Ambiguity Gap:** It doesn't explicitly mention "Lines starting with `- ` but NO marker". Currently, strict crash. This is fragile for human editing.

## Summary
Score: **C-**
The Logic core (`Loom.insert`, `Validator`) is decent.
The Input/Output layer (`StatusParser`) is **Brittle** (Crashes on comments/formatting).
The Architecture (`LoomAtom`) has **Missing Components**.
The Tests have **Rotting Comments**.

Fix them.
