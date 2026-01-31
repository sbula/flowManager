# Incident Report: The "validate.sh" Bypass
**Date:** 2025-12-30
**Severity:** HIGH (Protocol Violation)

## Event
The Agent bypassed the `flow_manager.sh` protocol and executed `workflow_core/validate.sh` directly to verify a fix (CandlePublisher). 

## Why this is dangerous
1.  **Context Loss:** `validate.sh` is dumb. It does not know the Task ID, the Phase, or the Blocking Requirements managed by Flow Manager.
2.  **State Corruption:** Running validation outside the flow might produce artifacts (logs, files) that the Flow Manager doesn't track, or miss required pre-checks (like `status.md` validation).
3.  **Habit Formation:** It erodes the discipline of "Single Point of Entry" (Flow Manager).

## The Lesson
**"The Flow Manager is the Operating System. The Scripts are the Kernel."**
User code (Agent) calls the OS, never the Kernel directly. 

## Action Item
Permanently reinforced rule: **NEVER call `*.sh` scripts in `workflow_core/` directly.** ALWAYS use `flow_manager.sh`.
