# 01_07 Test Specification: Skills & Personas
> **Status**: DRAFT (Paranoid QA V-Next Validations)
> **Owner**: Senior QA Architecture Team
> **Target**: `src/flow/skills/`, `src/flow/config/skills.registry.json`, `src/flow/config/expert_personas.json`

## 1. Goal & QA Philosophy
This document defines the strict, DAU-resistant (Dumbest Available User) test inventory for all `Skill` and `Persona` implementations, covering the complete lifecycle from startup validation through execution, hot-reloading, graceful teardown, and crash recovery.

All tests follow the dual-path calling model defined in the specification:
*   **Path 1 (Engine Step)**: The Engine invokes a Skill directly via `engine.dispatch(skill_name, **kwargs)`.
*   **Path 2 (LLM Function-Call)**: The AgentAtom exposes Skills to the LLM via `as_tool()`, and the LLM invokes them during the ReAct loop.

Our core philosophy: **"There is no happy path; there are only tolerated fault states."**

> [!IMPORTANT]
> **Timeout Tier Contract**: Tests MUST verify both timeout tiers during teardown: the **Skill's cleanup()** gets a **5-second** budget (01_07 §8.3), and the **AgentAtom's cleanup()** gets its own **5-second** budget (01_07 §8.3 — "each invocation in the chain gets its own 5-second budget"). The total theoretical cleanup window for a single AgentAtom containing one active Skill is **10 seconds** (5s Skill + 5s AgentAtom) before the outer SIGKILL watchdog fires at **13 seconds** (10s + 3s safety margin for signal propagation and stack unwinding). Tests MUST verify SIGKILL fires at the correct accumulated budget, not just the individual tier.

---

## 2. Persona Startup Validation
These tests ensure Personas are correctly validated during Engine startup.

*   **T2.01 Valid Persona Loads Successfully**: Load `expert_personas.json` with valid schema, valid Skill references, valid tool references. Expect successful startup with no warnings.
*   **T2.02 Missing `schema_version` Field**: Remove `schema_version` entirely from `expert_personas.json`. Expect `SchemaVersionError` with message containing `"missing 'schema_version'"`. Engine MUST NOT start.
*   **T2.03 Wrong `schema_version` Value**: Set `schema_version: "99"`. Expect `SchemaVersionError` with message containing expected and actual versions. Engine MUST NOT start.
*   **T2.04 Valid `AllowedSkills` Reference**: Persona references a Skill that exists in `skills.registry.json` with matching version. Expect successful load.
*   **T2.05 Unknown Skill in `AllowedSkills`**: Persona references `"name": "nonexistent_skill"`. Expect `RegistryError` with message containing `"Unknown skill: 'nonexistent_skill'"` (U1 — error messages must be substring-verifiable for disambiguation). Engine MUST NOT start.
*   **T2.06 Version Mismatch — Single Persona**: Persona references `"version": "1"` but registry has `"version": "2"`. Expect `RegistryError` with mismatch details.
*   **T2.07 Version Mismatch — Multiple Personas (Aggregate Report)**: Three Personas reference the same Skill with wrong versions. Expect a SINGLE `RegistryError` listing ALL three mismatches (not just the first one). Operator can fix all references in one pass.
*   **T2.08 Unknown Tool in `AllowedTools`**: Persona references `"nonexistent_tool"` in `AllowedTools`. Expect `RegistryError`.
*   **T2.09 Duplicate Tool in `AllowedTools`**: Persona lists `"read_file"` twice. Expect `RegistryError` (§2.3 step 3 mandates hard error, not WARNING).
*   **T2.10 Tool Count > 20 Warning**: Persona declares 25 tools. Expect `WARNING` logged but startup succeeds.
*   **T2.11 Tool Count > `max_tools_per_persona` Error**: Persona exceeds the hard limit from `.flow/config.json`. Expect `RegistryError`.
*   **T2.12 Empty Skills + Empty Tools**: Persona with `AllowedSkills: []` and `AllowedTools: []`. Expect `WARNING` logged, but startup succeeds (valid configuration).
*   **T2.13 Unrecognized `model_params` Key**: Persona specifies `"beam_width": 5` (not a standard LLM parameter). Expect `WARNING` logged with unrecognized key name.
*   **T2.14 `SystemPrompt` Exceeds 8192 Characters**: Persona has a 10,000-char system prompt. Expect `RegistryError`.
*   **T2.15 Persona Version Format Validation**: Persona has `"version": "1.1"` (float string). Expect `RegistryError`: version must be an integer string. Also test `"version": "02"` (leading zero) — must fail if integer-string validation is strict.
*   **T2.16 Persona File is Array Not Object**: `expert_personas.json` contains `[]` instead of `{}`. Expect `ConfigParseError`.
*   **T2.17 Persona JSON `personas` Key is Null**: `"personas": null`. Expect `ConfigParseError`.
*   **T2.18 Missing Required Field `Description`**: Persona entry omits `Description` entirely. Expect `ConfigParseError`.
*   **T2.19 Missing Required Field `SystemPrompt`**: Persona entry omits `SystemPrompt`. Expect `ConfigParseError`.
*   **T2.20 Missing Required Field `Focus`**: Persona entry omits `Focus`. Expect `ConfigParseError`.
*   **T2.21 Missing Required Field `AllowedSkills`**: Persona entry omits `AllowedSkills`. Expect `ConfigParseError`.
*   **T2.22 Missing Required Field `AllowedTools`**: Persona entry omits `AllowedTools`. Expect `ConfigParseError`.
*   **T2.23 Missing Required Field `version`**: Persona entry omits `version`. Expect `ConfigParseError`.
*   **T2.24 `AllowedSkills` is String Not List**: Value is `"code_review"` instead of `["code_review"]`. Expect `ConfigParseError`.
*   **T2.25 `AllowedTools` is Number Not List**: Value is `42` instead of a list. Expect `ConfigParseError`.
*   **T2.26 `Focus` is String Not List**: Value is `"testing"` instead of `["testing"]`. Expect `ConfigParseError`.
*   **T2.27 `SystemPrompt` is Empty String**: Valid (short prompt) but expect `WARNING` logged.
*   **T2.28 `SystemPrompt` is Exactly 8192 Characters**: Boundary — expect SUCCESS, no warning.
*   **T2.29 `SystemPrompt` is 8193 Characters**: Boundary — expect `RegistryError`.
*   **T2.30 `model_params` Contains `temperature: "not_a_number"` (String)**: Key is recognized, value type mismatch. Expect `WARNING` (spec §2.3 step 6 only validates key names).
*   **T2.31 AllowedSkill Entry Missing `name` Key**: Skill reference object has no `name`. Expect `ConfigParseError`.
*   **T2.32 AllowedSkill Entry Missing `version` Key**: Skill reference object has no `version`. Expect `ConfigParseError`.
*   **T2.33 Persona Name is Empty String**: JSON key is `""`. Expect `ConfigParseError` or `RegistryError`.
*   **T2.34 Persona Name Contains Unicode/Emoji** (`"🔥 QA Engineer"`): Expect success or explicit rejection per naming policy.
*   **T2.35 Tool Count Exactly 20 (Skills + Tools)**: Boundary — no warning expected.
*   **T2.36 Tool Count Exactly 21**: Boundary — `WARNING` expected.
*   **T2.37 Tool Count Exactly `max_tools_per_persona`** (default 30): Boundary — success.
*   **T2.38 Tool Count is `max_tools_per_persona + 1`** (default 31): Boundary — `RegistryError`.
*   **T2.39 `AllowedTools` Contains Empty String Entry**: `[""]`. Expect `RegistryError`.
*   **T2.40 `AllowedTools` Contains Whitespace-Only Entry**: `["  "]`. Expect `RegistryError`.
*   **T2.41 Multiple Personas — One Invalid, Rest Valid**: Expect full startup failure (not partial load).
*   **T2.42 `schema_version` is Integer (1) Not String ("1")**: Expect `SchemaVersionError` (strict type check).
*   **T2.43 Persona References Skill That Exists But Is DEGRADED**: Expect startup success — degradation is a runtime state, not startup (§5.3 pt 7).
*   **T2.44 `Checklist` Field Present in Persona (Removed Anti-Pattern)**: Expect field silently ignored or `WARNING`. Must NOT crash (§2.5).
*   **T2.45 Malformed JSON in Persona File (Trailing Comma)**: `expert_personas.json` contains valid JSON structure but with a trailing comma — a common editor accident. Expect `ConfigParseError` with line/column number identifying the syntax error (§2.3 step 0).
*   **T2.46 Persona File is Empty (0 Bytes)**: File exists but is entirely empty. Expect `ConfigParseError` with descriptive message.
*   **T2.47 Persona File Contains Only Whitespace**: File has spaces/newlines but no JSON content. Expect `ConfigParseError`.
*   **T2.48 Persona File Encoding is UTF-16**: JSON spec requires UTF-8. Expect `ConfigParseError` or `UnicodeDecodeError` handled gracefully.
*   **T2.49 Persona File is Binary Data** (e.g., PNG header bytes): Expect `ConfigParseError`.
*   **T2.50 Persona File Missing Entirely (FileNotFoundError)**: `expert_personas.json` does not exist on disk. Expect `ConfigParseError` with "file not found" detail.
*   **T2.51 `model_params` Has Recognized Key with Null Value** (`"temperature": null`): Key is valid, value is null. Expect `WARNING` logged (§2.3 step 6 validates keys only).
*   **T2.52 `model_params` Has Negative Temperature** (`"temperature": -0.5`): Valid key, semantically invalid value. Expect `WARNING` logged.
*   **T2.53 `model_params` Has Absurd Temperature** (`"temperature": 99`): Valid JSON number, absurd LLM value. Expect `WARNING` logged.
*   **T2.54 Two Personas with Identical Names (Duplicate JSON Keys)**: JSON has two `"architect"` top-level keys. Expect `ConfigParseError` via duplicate-key-detecting decoder (§5.2 step 5 pattern).
*   **T2.55 AllowedSkills Entry Has Extra Unexpected Keys**: `{"name":"x","version":"1","color":"red"}`. Extra key `color` should be ignored with `WARNING`.
*   **T2.56 AllowedSkill Entry `name` is Empty String**: `{"name":"","version":"1"}`. Expect `RegistryError`.
*   **T2.57 AllowedSkill Entry `version` is Empty String**: `{"name":"x","version":""}`. Expect `RegistryError` (§9.6).
*   **T2.58 `AllowedSkills` is Null (Not Empty List)**: `"AllowedSkills": null`. Expect `ConfigParseError`.
*   **T2.59 `AllowedTools` is Null (Not Empty List)**: `"AllowedTools": null`. Expect `ConfigParseError`.
*   **T2.60 `Focus` is Null (Not Empty List)**: `"Focus": null`. Expect `ConfigParseError`.
*   **T2.61 `schema_version` is Empty String** `""`: Expect `SchemaVersionError`.
*   **T2.62 `schema_version` is Null**: `"schema_version": null`. Expect `SchemaVersionError`.
*   **T2.63 100 Personas — All Valid (Stress Test)**: Expect successful load within reasonable time. No performance degradation.
*   **T2.64 Persona `Description` is 1MB String**: Valid JSON but excessively long. Expect success or explicit size limit.
*   **T2.65 AllowedSkills + AllowedTools Combined Count at Warning Threshold**: 20 total (combined) → no warning. 21 total → `WARNING`. Verify combined count, not separate.
*   **T2.66 `model_params` is a List Not Object**: `"model_params": [0.2]`. Expect `ConfigParseError`.
*   **T2.67 `model_params` is Null (Optional Field)**: `"model_params": null`. Expect success — field is optional.
*   **T2.68 AllowedSkill Entry `version` is Integer Not String**: `{"name":"x","version":1}`. Expect `ConfigParseError` (§9.6 — version must be string).
*   **T2.69 `AllowedTools` Contains Integer Entry**: `[1, "read_file"]`. Expect `ConfigParseError`.
*   **T2.70 Persona `version` is Negative String**: `"version": "-1"`. Expect `RegistryError`.
*   **T2.71 Persona References Skill with `version: "0"`**: Zero is a valid integer string per §9.6. Expect SUCCESS — version `"0"` is not explicitly forbidden.
*   **T2.72 `model_params` with `stop_sequences` as String Not List**: `"stop_sequences": "\n"` instead of `["\n"]`. Expect `WARNING` logged (§2.3 step 6 validates key names; type mismatch within recognized keys is a warning).
*   **T2.73 Two Personas Reference Same Skill, Both with Wrong Versions**: Persona A has `version: "3"`, Persona B has `version: "5"`, registry has `version: "2"`. Expect aggregate error listing both mismatches with their respective expected/actual versions.
*   **T2.74 AllowedSkill Entry `version` is Null**: `{"name":"x","version":null}`. Expect `ConfigParseError`.
*   **T2.75 Duplicate Skill Reference in `AllowedSkills`**: Same Skill listed twice: `[{"name":"code_review","version":"1"},{"name":"code_review","version":"1"}]`. Expect `RegistryError` (dedup enforcement, same pattern as T2.09 duplicate tool).
*   **T2.76 Tool Count Semantics — Skill Expansion**: Persona has 5 `AllowedSkills` (each requiring 3 internal tools) + 5 `AllowedTools` = 10 entries in AllowedSkills + AllowedTools arrays. Verify: combined count counts **list entries** (5 + 5 = 10), NOT the Skills' internal `required_tools` expansion (15 + 5 = 20). The `required_tools` count is a Skill-internal concern, not a Persona projection concern.

---

## 3. Skill Registry Startup Validation
Validating the Skill Registry's startup checks.

*   **T3.01 Valid Registry Loads and Imports All Skills**: All modules importable, all metadata matches. Expect clean startup.
*   **T3.02 Malformed JSON in Registry**: `skills.registry.json` has trailing comma. Expect `ConfigParseError` with line number.
*   **T3.03 Registry File Missing**: File does not exist. Expect `ConfigParseError` with "file not found".
*   **T3.04 `schema_version` Mismatch**: Registry has `"schema_version": "99"`. Expect `SchemaVersionError`.
*   **T3.05 Module Import Failure (SyntaxError)**: Registry points to a module with a Python syntax error. Expect `RegistryError` with message containing `"ImportError"` and the module path (U1 — distinct from T3.06 class-subclass check and T3.14 tool-import check). Engine MUST NOT start.
*   **T3.06 Class Not Subclass of `Skill`**: Module exists, class exists, but does not inherit from `Skill`. Expect `RegistryError` with message containing `"is not a subclass of Skill"` (U1 — distinct error code from import failure T3.05).
*   **T3.07 Metadata Mismatch — Name**: Class `name` property returns `"code_review"`, registry key says `"code_review_v2"`. Expect `RegistryError`.
*   **T3.08 Metadata Mismatch — Version**: Class `version` returns `"2"`, registry says `"1"`. Expect `RegistryError`.
*   **T3.09 Invalid `parameters_schema` (Not Valid JSON Schema)**: Schema has invalid ref. Expect `RegistryError`.
*   **T3.10 `parameters_schema` with `type: "array"`**: Top-level type is not `object`. Expect `RegistryError`.
*   **T3.11 `parameters_schema` Missing `additionalProperties: false`**: Expect `RegistryError` (§9.7).
*   **T3.12 Duplicate Skill Name in Registry**: Two entries with key `"refactor_code"`. Expect `RegistryError` via duplicate-key-detecting decoder.
*   **T3.13 `required_tools` References Non-Existent Tool**: Skill requires `"deploy_to_prod"` which is not in Tool Registry. Expect `RegistryError` with message containing `"Unknown tool: 'deploy_to_prod'"` (U1 — distinct from T3.14 tool-import failure).
*   **T3.14 `required_tools` References Tool That Fails Import (Not Skill Import)**: Tool exists in Tool Registry but the **Tool's** module crashes on import (distinct from T3.05 which tests the **Skill's** module import failure). Expect `RegistryError` with message identifying the failing tool name and the import traceback (§5.2 step 6 — tool dependency validation MUST verify import success).
*   **T3.15 `expected_duration_ms` = 0 or Negative**: Expect `RegistryError`.
*   **T3.16 Skill Version Float String (`"1.1"`)**: Expect `RegistryError` (§9.6).
*   **T3.17 `parameters_schema` with `$ref` External URL**: Expect `RegistryError` — external references are a security risk.
*   **T3.18 `required_tools` Has Duplicate Entries**: Expect `RegistryError`.
*   **T3.19 Skill `name` Contains Spaces or Special Characters**: Expect `RegistryError`.
*   **T3.20 Empty `parameters_schema` (`{}`)**: Expect `RegistryError` — must have `type: "object"`.
*   **T3.21 Empty `description` in Skill**: Valid — no error, but `WARNING` recommended.
*   **T3.22 Registry `skills` Key is Missing**: JSON is valid but has no `skills` key. Expect `ConfigParseError`.
*   **T3.23 Registry `skills` Value is Null**: `"skills": null`. Expect `ConfigParseError`.
*   **T3.24 Registry `skills` Value is a List Not Object**: `"skills": []`. Expect `ConfigParseError`.
*   **T3.25 Skill Entry Missing `module` Field**: Skill object has no `module`. Expect `RegistryError`.
*   **T3.26 Skill Entry Missing `category` Field**: Skill object has no `category`. Expect `RegistryError`.
*   **T3.27 Skill `category` is Invalid Value (`"magic"`)**: Not one of `reasoning`, `action`, `rag`. Expect `RegistryError`.
*   **T3.28 Skill `module` Path Points to Non-Existent Package**: `"flow.skills.does_not_exist"`. Expect `RegistryError` (ImportError).
*   **T3.29 Skill `module` Points to Module Without Expected Class**: Module exists but has no `Skill` subclass. Expect `RegistryError`.
*   **T3.30 `parameters_schema` with `type: "string"`**: Top-level type is not `object`. Expect `RegistryError`.
*   **T3.31 `parameters_schema` with `type: "integer"`**: Top-level type is not `object`. Expect `RegistryError`.
*   **T3.32 `parameters_schema` with `additionalProperties: true`**: Explicit true. Expect `RegistryError` (§9.7).
*   **T3.33 `parameters_schema` Missing `additionalProperties` Key Entirely**: Expect `RegistryError` (§9.7 — implicit true is same as explicit true).
*   **T3.34 `schema_version` is Integer (1) Not String ("1")**: Expect `SchemaVersionError`.
*   **T3.35 Metadata Mismatch — `description`**: Class description differs from registry. Expect `RegistryError`.
*   **T3.36 Metadata Mismatch — `required_tools`**: Class declares `["read_file"]`, registry says `["write_file"]`. Expect `RegistryError`.
*   **T3.37 Skill Version is Empty String** (`"version": ""`): Expect `RegistryError`.
*   **T3.38 `expected_duration_ms` is Float** (e.g., `30000.5`): Expect `RegistryError` (must be integer).
*   **T3.39 Multiple Skills — One Has Invalid Schema, Rest Valid**: Expect full startup failure (not partial registry load).
*   **T3.40 Registry File is Empty (0 Bytes)**: File exists but content is empty. Expect `ConfigParseError`.
*   **T3.41 Registry File Contains Only Whitespace**: Spaces/newlines, no JSON. Expect `ConfigParseError`.
*   **T3.42 Skill `module` Path Uses OS Path Separators** (`flow\\skills\\code`): Must be dotted Python path. Expect `RegistryError`.
*   **T3.43 Skill Class `name` Property Raises Exception**: Property getter throws `RuntimeError`. Expect `RegistryError` at startup — not an unhandled crash.
*   **T3.44 Skill Class `parameters_schema` Property Returns `None`**: Not a dict. Expect `RegistryError`.
*   **T3.45 `parameters_schema` with Internal `$ref` (Not External URL)**: Schema uses `"$ref": "#/$defs/TargetFile"`. Expect SUCCESS (internal refs are valid).
*   **T3.46 `required_tools` is Null (Not Empty List)**: `"required_tools": null`. Expect `RegistryError`.
*   **T3.47 `required_tools` Contains Empty String**: `["", "read_file"]`. Expect `RegistryError`.
*   **T3.48 100 Skills — All Valid (Stress Test)**: Expect successful load. No performance degradation.
*   **T3.49 Skill `module` is Empty String**: `"module": ""`. Expect `RegistryError`.
*   **T3.50 Skill `description` is Null**: `"description": null`. Expect `RegistryError`.
*   **T3.51 Skill `category` is Null**: `"category": null`. Expect `RegistryError`.
*   **T3.52 Skill `version` is Null**: `"version": null`. Expect `RegistryError`.
*   **T3.53 Skill `version` is Integer (Not String)**: `"version": 2`. Expect `RegistryError` (§9.6).
*   **T3.54 Multiple Registry Errors Reported Together**: 3 skills with different issues. Expect ALL errors collected and reported, not just the first (aggregate error pattern from §2.3 step 2).
*   **T3.55 Skill `name` Has Leading/Trailing Whitespace**: `" refactor_code "`. Expect `RegistryError`.
*   **T3.56 Skill `category` Valid Value But Wrong Case**: `"Action"` instead of `"action"`. Expect `RegistryError` (enum values are case-sensitive).
*   **T3.57 `required_tools` Order Differs From Class Declaration**: Registry says `["write_file", "read_file"]`, class property returns `["read_file", "write_file"]`. Expect SUCCESS — comparison should be set-based, not ordered.
*   **T3.58 Skill Class `__init__` Raises Exception During Import**: Module imports successfully but class `__init__()` raises `RuntimeError` during instantiation. Expect `RegistryError` at startup — distinct from T3.05 (module-level import failure).
*   **T3.59 Two Skills with Different Names But Same `module` Path**: Two registry entries point to the same Python module (different classes). Expect SUCCESS if both classes exist and are distinct `Skill` subclasses.
*   **T3.60 Startup Load Order — Persona Loaded Before Skill Registry (Race Simulation)**: Mock the loader to process `expert_personas.json` BEFORE `skills.registry.json` has been fully loaded. Verify: Engine either enforces sequential load (Skills first, then Personas) or handles the "not-yet-loaded" case gracefully by deferring Persona validation until both files are loaded. No crash due to ordering assumptions.

---

## 4. SkillResult Contract Enforcement
Validating the `SkillResult` return value and Engine processing.

*   **T4.01 `status=SUCCESS` with No Error**: Standard success. Exports merged per context policy.
*   **T4.02 `status=SUCCESS` with Error Present**: `WARNING` logged, error stripped. Exports processed.
*   **T4.03 `status=FAILED` with Structured Error**: Error processed per Flow `on_failure` policy.
*   **T4.04 `status=RETRY` with `error.code=RATE_LIMITED`**: Engine applies exponential backoff.
*   **T4.05 `status=RETRY` with `error.code=TRANSIENT_ERROR`**: Engine applies immediate retry.
*   **T4.06 `status=RETRY` with Unknown `error.code`**: Engine applies default retry policy.
*   **T4.07 `status=PAUSED_FOR_EXPANSION`**: Flow transitions to named pause state. TTL timer starts.
*   **T4.08 `execute()` Returns `None`**: Engine safety wrapper catches `TypeError`, step fails with descriptive error (§9.13).
*   **T4.09 `execute()` Returns Unknown Status String**: Engine rejects with `ValueError` (§9.13).
*   **T4.10 `execute()` Raises Unhandled `ValueError`**: Engine wraps as `FAILED` with traceback in error field.
*   **T4.11 `execute()` Raises `SystemExit`**: Engine handles at higher level (01_05 §6.1). Skill MUST NOT catch this.
*   **T4.12 `exports` Exceeds 128KB Aggregate**: Engine rejects result, step fails (01_05 §2 limit).
*   **T4.13 `exports` Contains Un-Namespaced Key Shadowing Reserved Engine Key**: Engine rejects with `ReservedKeyCollisionError` (§9.10).
*   **T4.14 `status=FAILED` with Non-Empty `exports` (Partial Results)**: Engine processes per `on_failure` policy — `halt` discards, `ignore` merges (§9.14).
*   **T4.15 `status=RETRY` with `error` = None**: Retry without structured error info. Engine applies default retry policy but logs `WARNING` (no strategy hint from Skill).
*   **T4.16 `status=RETRY` with `error.code=TIMEOUT`**: Engine retries with same timeout budget.
*   **T4.17 `status=FAILED` with `error` = None**: Valid — no structured error for debugging. Engine still processes step failure correctly.
*   **T4.18 `exports` Contains Non-JSON-Serializable Value** (`set()`, `datetime`): Engine catches `TypeError` during serialization, step fails.
*   **T4.19 `exports` Key Not Using Namespace Convention**: Key is `"result"` instead of `"skill:name:result"`. Engine validates and logs `WARNING` or rejects.
*   **T4.20 Minimum Valid `SkillResult`**: `status=SUCCESS, message="", exports={}, error=None`. Must be accepted.
*   **T4.21 `message` Field is 1MB String**: Not in exports (not serialized to context), only logged. Verify no OOM in logging subsystem.
*   **T4.22 `skill_name` and `skill_version` Metadata on Result**: Verify Engine populates observability metadata fields correctly.
*   **T4.23 `duration_ms` is Negative**: Engine ignores or logs `WARNING` (observability field only, not contract).
*   **T4.24 `SkillResult.error` is a String Not a Dict**: Engine wraps as `{"message": error_string}` and logs `WARNING` about format violation.
*   **T4.25 `status=FAILED` with `error.code` = Empty String**: Structured error with empty code. Engine processes failure normally, logs `WARNING` about empty code.
*   **T4.26 `status=RETRY` with `error.code=RATE_LIMITED` — Max Retries Exceeded**: After configured max retries (e.g., 3), Engine stops. Expect `FATAL` status and Flow halt.
*   **T4.27 `status=RETRY` with `error.code=RATE_LIMITED` — Exponential Backoff Timing**: Verify delays are approximately 1s, 2s, 4s (or per config). Must write absolute `next_retry_at` timestamp.
*   **T4.28 `status=PAUSED_FOR_EXPANSION` with Non-Null `exports`**: Partial exports on pause. Expect Engine **preserves** exports in the paused step's state snapshot for diagnostic purposes (operators may need them to decide the DAG modification). Exports are NOT merged into the live `context_cache` until the flow resumes and the step completes with a terminal status.
*   **T4.29 `status=PAUSED_FOR_EXPANSION` with Non-Standard `error.code`**: `error.code` is not `COMPLEXITY_EXCEEDED`. Expect Engine still processes the pause correctly.
*   **T4.30 `status=SUCCESS` with `exports` Containing Exactly 128KB**: Boundary — expect success (at limit, not over).
*   **T4.31 `status=SUCCESS` with `exports` Containing 128KB + 1 Byte**: Boundary — expect rejection.
*   **T4.32 `execute()` Raises `MemoryError`**: Engine wraps as FAILED. Verify Engine itself doesn't OOM.
*   **T4.33 `execute()` Raises `RecursionError`**: Engine wraps as FAILED with traceback in error field.
*   **T4.34 `SkillResult` with `status` as Integer (Not String/Enum)**: `status=1`. Expect Engine rejects with `ValueError`.
*   **T4.35 `SkillResult.error` Dict Missing `code` Key**: `{"message": "x"}`. Expect Engine processes failure but logs `WARNING` about missing code.
*   **T4.36 `SkillResult.error` Dict Missing `message` Key**: `{"code": "X"}`. Expect Engine processes failure but logs `WARNING`.
*   **T4.37 `exports` Value is `None`**: Key exists with `None` value. Expect success (None is JSON-serializable).
*   **T4.38 Rapid Succession of RETRY Results**: Skill returns RETRY 100 times in 1 second. Expect circuit breaker trips per 01_03 §3.1.
*   **T4.39 `status=RETRY` at Exact Circuit Breaker Threshold**: Skill returns RETRY exactly `max_retries` times (e.g., 3). Expect `FATAL` status on the 3rd RETRY (threshold is inclusive). Verify off-by-one: 2 retries = continue, 3 retries = FATAL.
*   **T4.40 `skill_name` Observability Mismatch**: `SkillResult` metadata has `skill_name` that doesn't match the executing Skill's `name` property. Expect Engine overrides with the correct name and logs `WARNING` about the mismatch.
*   **T4.41 `exports` with Wrongly Formatted Namespace Key**: Key is `"skill:wrong:extra:colons:key"` (4 colons instead of expected 3-segment format). Expect `WARNING` logged about malformed namespace, but exports still processed (namespace format is advisory in V1). **V1: `WARNING` only. V2: upgrade to `RegistryError`.**
*   **T4.42 `PAUSED_FOR_EXPANSION` TTL Expires with `on_failure: ignore` Policy**: Skill returns `PAUSED_FOR_EXPANSION`. TTL expires → `TIMED_OUT`. Flow step has `on_failure: ignore`. Verify: `TIMED_OUT` is treated as a FAILURE status, and the `ignore` policy allows the Flow to continue past the step. Exports from the paused step are discarded (no partial data merged into live context).
*   **T4.43 `SkillResult` with Extra Custom Attributes (DAU Subclass)**: DAU subclasses `SkillResult` and adds `result.custom_field = "leak"`. Verify Engine processes ONLY the documented fields (`status`, `message`, `exports`, `error`, `metadata`). Extra attributes are silently dropped, NOT serialized to state or context. No crash.

---

## 5. Skill Execution — Path 1 (Engine Step)
Testing direct Engine invocation of Skills.

*   **T5.01 Happy Path**: Valid kwargs, Skill executes, returns SUCCESS with exports.
*   **T5.02 Schema Validation Failure on `kwargs`**: Args fail JSON Schema. Expect `ValueError`, `execute()` never called.
*   **T5.03 Idempotent Action Skill (Check-Then-Act)**: First run creates file. Second run detects file exists, returns SUCCESS without mutation.
*   **T5.04 Action Skill Uses Loom for File Write**: Verify atomic write-replace (tmp → fsync → rename).
*   **T5.05 Action Skill Uses Raw `open()` (Forbidden)**: Engine startup validator detects and raises `RegistryError`.
*   **T5.06 Skill Timeout via Engine Step Timeout**: `execute()` takes too long. Engine sends SIGTERM → `cleanup()` → `FAILED`.
*   **T5.07 Context is Read-Only (`MappingProxyType`)**: Mutation attempt raises `TypeError`.
*   **T5.08 `ToolContext` Correctly Injected**: Skill accesses `tool_context.service_root` and `tool_context.isolation_level`.
*   **T5.09 Exports Key Namespacing Verification**: Exports use `skill:<name>:<key>` format.
*   **T5.10 Parallel Fan-Out — Same Skill, Different `kwargs`**: Run IDs are distinct. No state bleeding.
*   **T5.11 `expected_duration_ms` Is a Hint Not Enforcement**: Skill runs longer than hint but within step timeout. Expect SUCCESS.
*   **T5.12 Empty `kwargs` When Schema Has No Required Fields**: Valid `execute()` call with `kwargs={}`. Expect SUCCESS.
*   **T5.13 Extra `kwargs` Not In Schema** (`additionalProperties: false`): `ValueError` raised before `execute()`.
*   **T5.14 `execute()` Returns Wrong Type** (e.g., `dict` not `SkillResult`): Engine catches `TypeError`.
*   **T5.15 `execute()` Raises `KeyboardInterrupt`**: Engine does NOT catch (BaseException). Process-level handling required.
*   **T5.16 Action Skill Check-Then-Act — State Already Exists On First Run**: External target already exists. Returns SUCCESS without mutation (idempotent from run 1).
*   **T5.17 Reasoning Skill Re-Execution After Crash**: No side effects — safe to re-run without Check-Then-Act.
*   **T5.18 RAG Skill Re-Execution After Crash**: Read-only query — safe to re-run without Check-Then-Act.
*   **T5.19 Skill `required_tools` Tool Fails At Runtime**: Tool was working at startup but crashes during Skill execution. Skill catches `ToolError` gracefully.
*   **T5.20 Context Contains `idempotency_token`**: Verify token is accessible to Skill via `context["idempotency_token"]`.
*   **T5.21 Context Contains `abort_event`**: Verify `abort_event` is accessible to Skill via `context["abort_event"]`.
*   **T5.22 Skill Uses `abort_event.is_set()` In Long Loop**: Abort fires mid-loop, Skill checks and exits early returning `FAILED`.
*   **T5.23 Parallel Fan-Out — Abort Event Shared Across Branches**: One branch fails → `abort_event.set()` → other branches check and exit.
*   **T5.24 `ToolContext` is Immutable**: Skill cannot modify `service_root`, `isolation_level`, etc. `AttributeError` raised.
*   **T5.25 Skill `execute()` Mutates Instance Attributes (Statelessness Violation)**: A Skill sets `self._cache = result` during `execute()`. On next invocation (same Engine instance), the stale attribute leaks state. Verify Engine either isolates instances or Skill contract mandates statelessness (§4.3).
*   **T5.26 Timeout Boundary — Skill Takes Exactly Step Timeout**: Skill completes at the exact timeout boundary. Expect SUCCESS (timeout is strict `>`, not `>=`).
*   **T5.27 Timeout Boundary — Skill Takes Step Timeout + 1ms**: Skill exceeds by 1ms. Expect SIGTERM → cleanup → FAILED.
*   **T5.28 Idempotency Token is Deterministic Across Identical Invocations**: Same `run_id`, same skill, same step → identical token. Verify exact reproducibility.
*   **T5.29 Action Skill Deliberately Ignores `idempotency_token`**: Valid behavior if documented. Verify no Engine error — Skill-level decision.
*   **T5.30 Skill Calls `abort_event.set()` (Forbidden / Accepted Risk)**: No runtime enforcement, but verify other Fan-Out branches DO abort.
*   **T5.31 Skill Calls `abort_event.wait()` (Blocks Forever)**: Engine's step timeout eventually kills it. Verify FAILED status.
*   **T5.32 Skill Calls `abort_event.clear()` After Engine Sets It**: Fan-Out siblings stop seeing abort signal. Verify documented risk with test evidence.
*   **T5.33 Context Missing `idempotency_token` Key (Engine Bug Simulation)**: Skill accesses `context["idempotency_token"]` → `KeyError`. Verify Skill catches gracefully or Engine guarantees presence.
*   **T5.34 Context Missing `abort_event` Key (Engine Bug Simulation)**: Skill accesses `context["abort_event"]` → `KeyError`. Verify gracefully handled.
*   **T5.35 Parallel Fan-Out — 10 Branches, All Same Skill**: Verify all 10 get distinct Run IDs and no state bleeding across any combination.
*   **T5.36 Skill Calls Tool That Returns Error**: Skill catches `ToolError`, returns `SkillResult(status=FAILED)`. Verify Engine processes the Skill-returned failure, not the raw ToolError.
*   **T5.37 Skill Receives Context with Blob Pointer from Previous Step**: Verify Skill can dereference blob pointer `{"ref": ".flow/artifacts/blob_X.txt"}` correctly.
*   **T5.38 `expected_duration_ms` Hint Does Not Override Step Timeout**: Hint is 2000ms, step timeout is 30s. Skill runs 5s. Expect SUCCESS (hint is advisory only).
*   **T5.39 Skill Exports with Correct Namespace vs Without Namespace**: With namespace `skill:refactor_code:result` → merged. Without namespace `result` → `WARNING` or rejection.
*   **T5.40 Skill `execute()` Uses `threading.local()` for Scratch State**: Valid alternative to local vars. Verify no cross-thread leakage in parallel Fan-Out.
*   **T5.41 Skill `execute()` Takes 0ms (Instant Return)**: Degenerate case. Verify `duration_ms` is recorded as 0 (not negative). No timing error.
*   **T5.42 Context `abort_event` Already Set Before Skill Starts**: Skill should check `.is_set()` at entry and return `FAILED` immediately. Verify no partial execution occurs.
*   **T5.43 Context `idempotency_token` is Empty String (Engine Bug)**: Token key exists but value is `""`. Skill's Check-Then-Act should treat empty token as invalid and log `WARNING` or fall back to non-idempotent execution.
*   **T5.44 Action Skill Check-Then-Act — External Process Modifies State During Pause**: Flow pauses (§8.5). Operator manually edits the file the Action Skill created. On resume, Check-Then-Act detects existing state (modified by external), returns SUCCESS without mutation. Verify the externally-modified content is preserved, not overwritten.

---

## 6. Skill Execution — Path 2 (LLM Function-Call)
Testing Skills invoked via AgentAtom's ReAct loop.

*   **T6.01 AgentAtom Exposes Skill via `as_tool()`**: LLM sees Skill in toolset with correct schema.
*   **T6.02 LLM Invokes Skill with Valid Args**: `execute()` called, result returned to LLM context.
*   **T6.03 LLM Passes Invalid Args (Schema Failure)**: Error returned to LLM, ReAct loop continues.
*   **T6.04 LLM Fails Schema Correction (`max_schema_retries` = 3, Total Attempts Semantics)**: LLM sends invalid args 3 times total (initial attempt + 2 retries). On the 3rd failure, `LLM_SCHEMA_CORRECTION_EXHAUSTED` returned. `max_schema_retries` uses **total-attempts** semantics: value of 3 means 3 total chances, NOT "3 retries after the first attempt".

    > [!IMPORTANT]
    > **Definitive `max_schema_retries` Semantics Table** (resolves ambiguity across T6.04, T6.13, T6.35):
    >
    > | Config Value | Total Attempts | Behavior |
    > |---|---|---|
    > | `0` | 1 | LLM gets exactly 1 attempt. First schema failure → `EXHAUSTED`. (Zero **retries**, not zero attempts.) |
    > | `1` | 2 | LLM gets initial attempt + 1 retry = 2 total chances. |
    > | `3` | 4 | LLM gets initial attempt + 3 retries = 4 total chances. |
    >
    > The name `max_schema_retries` uses **retry semantics** (not total-attempts). Value N = N retries after the initial attempt. A value of 0 means the LLM gets **one** attempt with zero retries.
*   **T6.05 LLM Hallucinates Unknown Skill Name**: Tool error with available skills list returned.
*   **T6.06 LLM Passes Valid-Schema but Semantically Invalid Args**: Skill's business-rule validation catches. `INVALID_ARGUMENT` returned.
*   **T6.07 `_active_skill` Tracking**: Set before `execute()`, cleared immediately after (normal return AND exception).
*   **T6.08 SIGTERM During Skill Execute in ReAct Loop**: AgentAtom.cleanup() → Skill.cleanup() chain verified.
*   **T6.09 Two Sequential Skill Invocations — Different Idempotency Tokens**: Same Skill called twice in one loop. Tokens differ by `tool_call_index` (U3).
*   **T6.10 Engine Crash Mid-ReAct Loop — Restart Rehydrates History**: `tool_call_index` initialized from `len(rehydrated_history)`, not 0.
*   **T6.11 Per-Skill Timeout Within ReAct Loop**: AgentAtom enforces `expected_duration_ms` or global default.
*   **T6.12 Persona with Zero `AllowedSkills`, Non-Empty `AllowedTools`**: ReAct loop works with tools directly, no crash (§9.9).
*   **T6.13 `max_schema_retries = 0` Boundary (Retry Semantics)**: Value 0 means zero retries = 1 total attempt. LLM gets exactly one chance. First schema failure → `LLM_SCHEMA_CORRECTION_EXHAUSTED`. No division-by-zero or off-by-one (§9.16). See semantics table in T6.04.
*   **T6.14 DEGRADED Skill Self-Correction via ReAct Loop**: Skill degrades mid-loop. AgentAtom returns descriptive tool error (not `RegistryError`). LLM self-corrects. Wasted iteration does NOT count against `max_schema_retries` (§9.15). 
*   **T6.15 Same Skill Invoked 5 Times in One Loop**: Each invocation has unique `tool_call_index`. All idempotency tokens are distinct.
*   **T6.16 AgentAtom Exposes Only Persona's AllowedSkills**: Registry has 10 skills, Persona allows 3. LLM sees exactly 3.
*   **T6.17 `as_tool()` Descriptor Matches Skill Properties Exactly**: Cross-validate `name`, `description`, `parameters_schema` in generated descriptor.
*   **T6.18 `as_tool()` with `strict_schema=False`**: Descriptor has `"strict": false` (or omits strict field per provider).
*   **T6.19 LLM Invokes Skill A (Fails Schema), Then Skill B (Succeeds)**: Skill A's schema retry counter does NOT affect Skill B.
*   **T6.20 LLM Schema Correction Counter Resets Between Different Skills**: Counter is per-skill per-invocation, not global.
*   **T6.21 LLM Invokes Skill That Requires Unavailable Tool Mid-Loop**: Live registry check catches tool removal → DEGRADED error returned to LLM.
*   **T6.22 AgentAtom Frozen Snapshot vs Live Registry Divergence**: Frozen snapshot shows skill available, live registry has removed it. Skill invocation still works (frozen).
*   **T6.23 Persona Has Only Reasoning Skills (No Action)**: ReAct loop works. Idempotency tokens ARE generated by Engine but correctly ignored by Reasoning skills (§8.1 — "MAY ignore").
*   **T6.24 Persona Has Mixed Action + Reasoning Skills**: Both types correctly projected. Idempotency tokens generated for ALL invocations; Action skills use them for Check-Then-Act, Reasoning skills ignore them.
*   **T6.25 LLM Passes Args With Extra Fields** (not in schema): `SCHEMA_VALIDATION_FAILED` returned to LLM context.
*   **T6.26 LLM Returns Empty Arguments `{}` When Schema Requires Fields**: Schema validation fails, error returned to LLM.
*   **T6.27 Skill `execute()` Hangs Indefinitely in ReAct Loop**: Per-skill timeout fires within AgentAtom. Skill killed, `FAILED` returned to LLM.
*   **T6.28 Multiple Concurrent AgentAtom Instances — Different Personas**: No cross-contamination of skill sets or context.
*   **T6.29 ReAct Loop Reaches `max_loops` Without Schema Failures**: Normal loop exhaustion handling per 01_05 §3.2.
*   **T6.30 Skill Invoked via Path 2 Receives Same `tool_context` as AgentAtom**: RBAC applies identically to both paths.
*   **T6.31 Crash Mid-Tool in ReAct Loop**: A crash occurs exactly after a Skill executes a Tool but *before* the Skill processes the Tool's output within the AgentAtom's ReAct loop. On restart, verify deterministic `Sub-Run ID` recovery prevents duplicate Tool invocation.
*   **T6.32 `as_tool()` Called 100 Times — Deterministic Output**: Verify identical descriptor every time (§9.5). Regression guard for caching issues.
*   **T6.33 LLM Invokes Skill That Returns RETRY**: AgentAtom passes RETRY as tool error to LLM. LLM can try again or use a different Skill.
*   **T6.34 LLM Invokes Skill That Returns `PAUSED_FOR_EXPANSION`**: In Path 2, AgentAtom detects the pause status. AgentAtom returns the status to the Engine. Engine transitions Flow to pause state.
*   **T6.35 `max_schema_retries = 1` Boundary (Retry Semantics)**: `max_schema_retries=1` means 1 retry after initial attempt = 2 total chances. LLM sends invalid args on attempt 1 → error returned → LLM retries → fails again on attempt 2 → `LLM_SCHEMA_CORRECTION_EXHAUSTED`. Verify exactly 2 schema validation attempts occur (not 1, not 3). See semantics table in T6.04.
*   **T6.36 LLM Invokes Two Different Skills in Sequence**: Verify idempotency tokens are distinct (different `skill_name` in the formula).
*   **T6.37 LLM Invokes Skill A, Then A Again, Then B**: Token for A(idx=0), A(idx=1), B(idx=0) — all three are distinct.
*   **T6.38 `_active_skill` is None Between Invocations — SIGTERM Arrives**: SIGTERM during LLM reasoning phase (`_active_skill = None`). Only AgentAtom.cleanup() runs, no Skill cleanup. No crash (01_05 §3.3.1).
*   **T6.39 `_active_skill` Set Correctly During `execute()` — SIGTERM Arrives**: SIGTERM during `skill.execute()`. Verify AgentAtom.cleanup() → `self._active_skill.cleanup()` chain fires correctly.
*   **T6.40 `_active_skill` Cleared on Exception from `execute()`**: Skill raises `ValueError`. `_active_skill` set to `None` immediately after exception — NOT left dangling.
*   **T6.41 Frozen Snapshot Contains Skill A, Live Registry Removes A**: LLM can still invoke A via frozen snapshot. Dispatch passes because frozen is authoritative during loop.
*   **T6.42 Frozen Snapshot Contains Skill A, Live Registry Marks A DEGRADED**: LLM can still invoke A via frozen snapshot. BUT live registry check at dispatch-time returns DEGRADED error to LLM (§5.3 pt 5, §9.1).
*   **T6.43 ReAct Loop Reaches `max_loops` WITH Schema Failures Included**: Schema failures consume loop iterations. Verify correct counting: 3 schema failures + 2 successful calls = 5 iterations against `max_loops=5`.
*   **T6.44 LLM Passes Args That Pass Schema But Fail Business Rules, Then Self-Corrects**: Skill returns `INVALID_ARGUMENT`. LLM sees error and sends corrected args on retry. Verify self-correction works.
*   **T6.45 Per-Skill Timeout: Skill Takes 10s, Timeout is 5s**: AgentAtom enforces per-skill timeout. `FAILED` result returned to LLM.
*   **T6.46 AgentAtom Total Timeout Fires During Skill Execution**: Outer timeout kills AgentAtom mid-Skill. Verify `Skill.cleanup()` called via `_active_skill`.
*   **T6.47 ReAct Loop: LLM Keeps Calling Non-Existent Skills**: Each call returns tool error. Loop eventually terminates via `max_loops`.
*   **T6.48 LLM Sends `null` as Skill Arguments**: JSON `null` instead of object. Schema validation rejects. Error returned to LLM.
*   **T6.49 Two AgentAtoms with Same Persona, One Hot-Reloads Mid-Loop**: Each keeps its own frozen snapshot. Verify no cross-contamination between the two loops.
*   **T6.50 Path 2: Skill Returns Exports with Blob Reference**: AgentAtom passes blob ref to LLM. Verify LLM receives pointer, not the raw blob data.
*   **T6.51 LLM Invokes Skill with Valid JSON but Semantically Contradictory Args**: `{"refactoring_type": "rename", "new_name": null}` — required field `new_name` is null. Schema validation passes (nullable), but Skill's business-rule validation catches. Expect `INVALID_ARGUMENT` error to LLM.
*   **T6.52 Frozen Snapshot vs Live Registry — Skill Version Change (Not Removal)**: Frozen shows Skill A v1, live has Skill A v2. Dispatch uses **frozen** snapshot (v1). Verify the LLM gets v1's schema, not v2's.
*   **T6.53 Same Skill Invoked 100 Times in One ReAct Loop (Stress)**: Each invocation has unique `tool_call_index` (0–99). All 100 idempotency tokens are distinct. No integer overflow or string-length issues.
*   **T6.54 SIGTERM Arrives During `as_tool()` Cache Rebuild After Hot-Reload**: Race between cache invalidation and teardown. Verify cleanup proceeds without crash (cache in inconsistent state is acceptable during teardown).
*   **T6.55 Buggy AgentAtom Fails to Increment `tool_call_index` (U3)**: Simulate a bug where `tool_call_index` stays at 0 for two sequential Skill invocations. Two different Skill calls receive the **same** idempotency token. Verify: (1) Action Skill's Check-Then-Act incorrectly deduplicates (demonstrates the danger), (2) Engine SHOULD log `WARNING` if two sequential tool calls produce identical tokens.
*   **T6.56 `strict_schema=False` Runtime Behavior (U6)**: Set `strict_schema=False` in Skill config. LLM sends response with extra fields not in the schema. Verify the extra fields are **tolerated** (not rejected) during dispatch — the descriptor allows it, and the runtime dispatch must not apply strict validation that contradicts the descriptor.

---

## 7. Hot-Reload & Registry Lifecycle
Testing dynamic registry updates without Engine restart.

*   **T7.01 Successful Hot-Reload — New Skill Added**: Next ReAct loop sees the new Skill.
*   **T7.02 Hot-Reload Validation Failure**: Bad JSON in new registry → no-op, old registry stays, ERROR logged.
*   **T7.03 Hot-Reload with `schema_version` Bump**: Rejected. Old registry stays. ERROR logged (§5.3 point 4).
*   **T7.04 JSON Parse Error During Hot-Reload**: Syntax error → no-op, old registry stays, ERROR logged.
*   **T7.05 In-Flight ReAct Loop Unaffected**: AgentAtom keeps its frozen snapshot for the duration of its loop.
*   **T7.06 `as_tool()` Cache Invalidated After Successful Hot-Reload**: Next invocation rebuilds descriptors.
*   **T7.07 Hot-Reload Removes a Tool → Dependent Skill Marked DEGRADED**: Skill's `required_tools` references removed tool.
*   **T7.08 DEGRADED Skill Excluded from `as_tool()` Projection**: LLM does not see the DEGRADED Skill.
*   **T7.09 Capability Collapse Guard — All Skills DEGRADED**: `PreconditionFailed` raised, zero-capability Persona detected.
*   **T7.10 Debounce — Rapid File Changes Within 2000ms**: Multiple edits → single reload triggered.
*   **T7.11 Python Source Changes NOT Picked Up**: Hot-reload only watches JSON. Python `.py` changes require Engine restart.
*   **T7.12 Two Concurrent AgentAtoms Same Persona During Hot-Reload**: Each keeps its own frozen snapshot.
*   **T7.13 Hot-Reload During Engine Startup Validation**: Reload is no-op until startup completes (§9.17).
*   **T7.14 Hot-Reload with Partial File Save (Transactional Tear)**: Debounce coalesces both files (§9.18).
*   **T7.15 Hot-Reload Adds New Persona Referencing Existing Skill**: Next invocation sees new Persona with correct Skill set.
*   **T7.16 Hot-Reload Removes a Skill Entry**: Dependent Personas lose the Skill. Persona validation re-runs.
*   **T7.17 Hot-Reload Changes Skill Version**: Personas pinned to old version → version mismatch → Skill becomes DEGRADED or reload fails.
*   **T7.18 Hot-Reload Changes `model_params` for a Persona**: Next invocation uses new params.
*   **T7.19 Hot-Reload While No ReAct Loops Active**: Immediate swap, next invocation uses new registry.
*   **T7.20 Concurrent Hot-Reload Events** (two rapid file saves within 100ms): Debounce coalesces — only one validation triggered after 2000ms window.
*   **T7.21 Hot-Reload Restores Previously Removed Tool**: DEGRADED skill becomes active again.
*   **T7.22 Hot-Reload with Registry File Locked** (e.g., Windows editor lock): Expect graceful retry or skip. No crash.
*   **T7.23 Hot-Reload Changes `additionalProperties` in Schema**: New schema enforced for next invocation.
*   **T7.24 Hot-Reload with Empty Registry** (`"skills": {}`): All existing skills become unregistered. Log `WARNING`.
*   **T7.25 Hot-Reload Changes Skill `required_tools`**: Old version required `[read_file]`, new requires `[read_file, write_file]`. If `write_file` absent in Tool Registry → Skill becomes DEGRADED.
*   **T7.26 Hot-Reload Adds New Skill with Invalid `parameters_schema`**: Existing skills unaffected. New skill rejected. Old registry stays active.
*   **T7.27 Hot-Reload with Persona + Skill Both Updated Simultaneously**: Both `expert_personas.json` and `skills.registry.json` saved within debounce window. Expect single atomic validation after debounce, not two sequential validations.
*   **T7.28 Hot-Reload Stress — 50 Saves in 2 Seconds**: Debounce coalesces all into one reload. No intermediate invalid states observable.
*   **T7.29 Hot-Reload During Active Path 1 Skill Execution**: Currently executing Skill unaffected. Next invocation uses new registry.
*   **T7.30 Hot-Reload Removes Persona That Is Currently In-Flight**: AgentAtom keeps frozen snapshot. No crash. Loop completes normally.
*   **T7.31 Hot-Reload Changes `model_params.temperature` While AgentAtom Running**: In-flight loop uses old params. Next loop launch uses new params.
*   **T7.32 Hot-Reload with Skill `schema_version` Bump**: Requires Engine restart (§5.3 pt 4). Hot-reload MUST reject this change. Old registry stays.
*   **T7.33 Hot-Reload Restores DEGRADED Skill (Tool Re-Added)**: Tool dependency added back to Tool Registry. Skill transitions from DEGRADED to active. `as_tool()` cache force-rebuilt.
*   **T7.34 Hot-Reload with Persona `schema_version` Bump**: Rejected (§5.3 pt 4). Old persona config stays.
*   **T7.35 Hot-Reload Thread Safety**: Two hot-reload file change events trigger simultaneously from two file watchers. No race condition on internal registry atomic swap.
*   **T7.36 Hot-Reload Validation Timeout**: Validation of new registry takes > 10s (100 skills with complex schemas). Verify main Engine execution loop is NOT blocked during validation.
*   **T7.37 Capability Collapse Guard — Mixed DEGRADED/Active Skills**: Persona has 5 skills, 3 become DEGRADED, 2 remain active. Guard does NOT trigger (still has active capabilities).
*   **T7.38 Capability Collapse Guard — Persona with `AllowedSkills: []`**: Zero skills by design (tools-only agent). Guard does NOT trigger — this is intentional, not a collapse.
*   **T7.39 Hot-Reload File Watcher on Non-Target File**: Change to `.flow/config.json` (NOT registry/persona files). No reload triggered.
*   **T7.40 Hot-Reload Adds Skill Whose `required_tools` Includes Newly Removed Tool**: Within same debounce window: new Skill added + its dependency Tool removed from Tool Registry. New Skill should be DEGRADED immediately after reload. Existing Skills unaffected.
*   **T7.41 Hot-Reload with Persona File Having Different `schema_version` Than Skill Registry**: Mixed version scenario: personas file has `schema_version: "2"`, skills registry has `schema_version: "1"`. Expect reload rejects with `SchemaVersionError` listing both files.
*   **T7.42 Hot-Reload While Engine Is Performing Blob Garbage Collection**: Concurrent GC + reload. Verify no resource contention — GC operates on `.flow/artifacts/` while reload operates on registry JSON. Both complete without deadlock.
*   **T7.43 Hot-Reload Removes the ONLY Persona**: All Personas removed from `expert_personas.json`. Engine continues running (Path 1 still works). Any Path 2 invocation fails with `NoPersonaAvailableError`. `WARNING` logged.
*   **T7.44 Hot-Reload `schema_version` Downgrade (Not Just Bump)**: Current live registry has `schema_version: "2"`. Hot-reload file has `schema_version: "1"` (downgrade). Verify: same behavior as a version bump — rejected, old registry stays, `ERROR` logged. Downgrades are as dangerous as upgrades because they can remove fields or change semantics.
*   **T7.45 Hot-Reload Changes `parameters_schema` During Active Path 1 Execution**: Path 1 Skill is mid-`execute()`. Hot-reload changes the Skill's `parameters_schema` (new required field added). Skill completes with exports matching the OLD schema. Verify: Engine uses the schema that was active at **dispatch time** (snapshot), NOT the hot-reloaded schema. Exports from the in-flight execution are accepted without re-validation against the new schema.

---

## 8. LLM Projection & Provider Binding
Validating `as_tool()` → provider-specific format translation.

*   **T8.01 Gemini Projection**: `parameters_schema` → `FunctionDeclaration`. `strict_schema=True` maps to declaration-level validation.
*   **T8.02 OpenAI Projection**: `parameters_schema` → `tools[].function.parameters`. `strict_schema=True` → `strict: true`.
*   **T8.03 Anthropic Projection**: `parameters_schema` → `tools[].input_schema`. `strict_schema=True` → `strict: true`.
*   **T8.04 Ollama Projection**: `strict_schema` silently ignored (Ollama lacks strict mode).
*   **T8.05 Unsupported JSON Schema Feature**: `oneOf` on Ollama → `ProviderProjectionError`.
*   **T8.06 Provider Strips Unsupported `model_params`**: `top_k` on OpenAI → DEBUG log, no error.
*   **T8.07 Projection with `strict_schema=False`**: `strict` flag omitted or set to false per provider convention.
*   **T8.08 Provider Rejects Schema at Runtime** (Gemini strict mode rejects certain patterns): Engine wraps as `PROVIDER_SCHEMA_REJECTION`.
*   **T8.09 Projection with Empty `parameters_schema`** (no properties, just `type: object`): Valid minimal schema. LLM sees function with no arguments.
*   **T8.10 Provider Switch Mid-Session** (reconfigure LLMGateway): Same skill correctly projected to new provider format.
*   **T8.11 Tool Package Projection**: Multiple micro-tools wrapped in one Skill (§6.3). LLM sees unified interface.
*   **T8.12 Projection with `parameters_schema` Containing `oneOf`**: Verify Gemini/OpenAI handle it correctly. Ollama rejects with `ProviderProjectionError`.
*   **T8.13 Projection with Deeply Nested `parameters_schema` (5 Levels)**: All providers handle the depth correctly without truncation.
*   **T8.14 Projection with Invalid `required` List**: `required` contains field names not in `properties`. Expect `RegistryError` at startup, not at projection time.
*   **T8.15 `model_params` with ALL 5 Recognized Keys Set**: `temperature`, `top_p`, `top_k`, `max_tokens`, `stop_sequences` — all forwarded correctly to provider.
*   **T8.16 Projection After Provider Reconfiguration Mid-Session**: Same Skill projected to new provider. Verify schema re-projection uses new provider's format.
*   **T8.17 `strict_schema=True` on Ollama**: Silently ignored (Ollama has no strict mode). No error thrown. DESC log note.
*   **T8.18 Provider Rejects Entire API Call Due to Schema (Not Just Strict Mode)**: Full API rejection — wraps as `PROVIDER_SCHEMA_REJECTION`. Non-retryable.
*   **T8.19 Projection with `parameters_schema` Containing `default` Values**: Some providers strip defaults, others enforce them. Verify: (1) descriptor includes defaults if provider supports them, (2) descriptor omits defaults if provider strips them. No crash in either case.
*   **T8.20 Projection with Large `parameters_schema` (100 Properties)**: Verify descriptor doesn't exceed provider-specific payload size limits. If exceeded, expect `ProviderProjectionError` before API call.
*   **T8.21 Provider Returns Tool Call Response with `null` for Required Field**: Strict schema says field is required, but provider sent `null`. Schema validation at dispatch catches the violation. Error returned to LLM context for self-correction.
*   **T8.22 Projection with `parameters_schema` Containing `allOf`**: Schema uses `allOf` to compose multiple sub-schemas. Verify: (1) Gemini handles it (supported), (2) OpenAI handles it (supported in strict mode with restrictions), (3) Ollama rejects with `ProviderProjectionError` (unsupported composition keyword).
*   **T8.23 Projection with `parameters_schema` Containing `anyOf`**: Schema uses `anyOf` for union types. Verify: (1) Gemini supports it natively, (2) OpenAI supports it in strict mode as of 2025, (3) Ollama rejects with `ProviderProjectionError`. Provider-specific capability matrix applies.
*   **T8.24 Projection with `parameters_schema` Containing `not`**: Schema uses `not` keyword. Verify: Most providers reject — `ProviderProjectionError` expected for Ollama, `WARNING` + best-effort for others.
*   **T8.25 `model_params` with Value Exceeding Provider Limits at Runtime**: Persona has `model_params.max_tokens: 999999` (exceeds model context window). Projection succeeds (projection doesn't validate value ranges). Provider rejects at API call time. Verify: error wraps as `LLM_CALL_FAILED` with provider-specific error details, NOT a crash.

---

## 9. Graceful Teardown & Cleanup
Validating signal reactions, cleanup chains, and resource release.

> [!IMPORTANT]
> **Cleanup Budget Model** — The budget depends on the execution path:
>
> | Scenario | Budget | SIGKILL Watchdog | Notes |
> |---|---|---|---|
> | **Path 1 — Single Skill step** | 5s (Skill.cleanup()) | N/A (Engine handles) | Step-level timeout governs |
> | **Path 1 — N Sequential Skill Steps** | 5s × N (each gets own budget) | N/A | Each step's cleanup independent |
> | **Path 2 — AgentAtom + 1 Active Skill** | 5s (Skill) + 5s (AgentAtom) = **10s** | **13s** (10s + 3s margin) | §8.3 "each invocation in chain" |
> | **Path 2 — AgentAtom, no active Skill** | 5s (AgentAtom only) | **8s** (5s + 3s margin) | SIGTERM between invocations |

*   **T9.01 `cleanup()` Default No-Op**: No crash, no resource leak.
*   **T9.02 `cleanup()` Raises `AttributeError` (Typo)**: Engine catches, logs, continues teardown chain.
*   **T9.03 `cleanup()` Raises `SystemExit` (Forbidden)**: Engine handles; teardown chain continues for other atoms.
*   **T9.04 `cleanup()` Exceeds 5-Second Budget**: SIGKILL fires at budget exhaustion.
*   **T9.05 `cleanup()` Called Twice Concurrently (Idempotent)**: SIGTERM handler + AgentAtom watchdog fire simultaneously. No `FileNotFoundError`, no crash (§9.11).
*   **T9.06 `cleanup()` Attempts Blocking Network I/O**: Times out within 5s budget. SIGKILL fires.
*   **T9.07 Nested Teardown Chain**: Engine → AgentAtom.cleanup() → Skill.cleanup(). All complete within total budget.
*   **T9.08 SIGTERM Between Two Skill Invocations**: `_active_skill = None`. No Skill cleanup called; only AgentAtom cleanup runs.
*   **T9.09 Fan-Out Abort — One Branch Fails**: `abort_event.set()` → other branches check `.is_set()` and exit.
*   **T9.10 `abort_event` Violation — Skill Calls `.set()`**: No runtime enforcement (documented accepted risk). Verify siblings actually abort.
*   **T9.11 Nested Cleanup Budget Accounting**: Skill.cleanup() = **5s** budget, AgentAtom.cleanup() = **5s** budget = **10s** of individual cleanup time (§8.3 — each invocation in the chain gets its own 5-second budget). The outer SIGKILL watchdog fires at **13s** total (10s + 3s safety margin for signal propagation and stack unwinding). Verify individual tier budgets AND the outer SIGKILL timing.
*   **T9.12 `cleanup()` Deletes Temp File Already Deleted**: `missing_ok=True` pattern. No `FileNotFoundError`.
*   **T9.13 `cleanup()` Has Infinite Loop**: 5s budget exceeded → SIGKILL fires. Process terminates.
*   **T9.14 SIGTERM Arrives During `cleanup()` Itself**: Re-entrant signal handling. No double teardown.
*   **T9.15 Multiple Skills In Sequence — First `cleanup()` Hangs**: Second skill's `cleanup()` still called after first is killed at budget.
*   **T9.16 `cleanup()` Accesses `self._tmp` Never Set** (Skill never reached file creation stage): `AttributeError` caught by wrapper.
*   **T9.17 Skill `cleanup()` Called When `execute()` Was Never Called**: Timeout hit before execution started. No crash.
*   **T9.18 Fan-Out: 5 Branches, 3 Complete, 2 Running — Abort Fires**: 2 running branches get abort. 3 completed branches NOT re-cleaned.
*   **T9.19 SIGINT (Ctrl+C) During Skill Execution**: Same cleanup chain as SIGTERM. Signal handler sets event, cooperative exit.
*   **T9.20 Budget Inheritance Chains**: Skill declares `expected_duration_ms=2000` (advisory hint per §4.3). Skill calls a Tool with a default 10s timeout. The Engine Step has a 30s timeout. Verify: (1) `expected_duration_ms` does NOT override the Tool's own timeout (it is a hint for the Engine scheduler, not an enforcement mechanism), (2) the Tool's execution IS bounded by the **Engine Step timeout** (30s), which is the authoritative ceiling. The full three-layer chain is: **Engine Step Timeout → Skill → Tool** (01_04 T7.25 cross-ref).
*   **T9.21 `cleanup()` Raises `KeyboardInterrupt` (BaseException)**: Engine handles at higher level. Teardown chain continues for remaining atoms/skills.
*   **T9.22 `cleanup()` Takes Exactly 5 Seconds (Boundary)**: Expect SUCCESS — 5s is the budget limit, not exceeded.
*   **T9.23 `cleanup()` Takes 5001ms (Boundary)**: Budget exceeded by 1ms. Expect SIGKILL fires.
*   **T9.24 Three Skills Executed in Sequence — All `cleanup()` Called**: SIGTERM arrives. Each Skill gets its own 5s budget. Total budget = 3 × 5s. Verify all three receive cleanup calls.
*   **T9.25 Cleanup Called on Skill Mid-Execution (Never Returned)**: Skill was mid-`execute()` when SIGTERM arrived. `cleanup()` must handle the partial state (e.g., temp file created but not finalized).
*   **T9.26 Nested Cleanup Exception Chain**: AgentAtom.cleanup() → Skill.cleanup() → Skill.cleanup() raises `RuntimeError`. Inner exception caught by AgentAtom wrapper. AgentAtom.cleanup() returns normally.
*   **T9.27 SIGTERM During Hot-Reload Debounce Window**: Hot-reload validation is in progress (debounce timer expired, validation started). SIGTERM arrives. Hot-reload aborted. Cleanup proceeds normally. No race condition.
*   **T9.28 Fan-Out: All 5 Branches Complete BEFORE Abort Fires**: No cleanup needed on any branch. Verify completed branches are not re-cleaned unnecessarily.
*   **T9.29 Cleanup — Skill Deletes Temp File In Use By Another Thread (Windows)**: `PermissionError` on Windows. Verify `missing_ok` pattern with exception suppression handles this gracefully.
*   **T9.30 SIGKILL Arrives (Uncatchable)**: No cleanup at all. Verify state on disk is consistent due to Loom write-replace guarantee (01_05 §6.2).
*   **T9.31 Skill Cleanup Attempts to Call a Tool** (e.g., `delete_file`): `ToolContext` may no longer be valid during SIGTERM teardown. Verify graceful failure.
*   **T9.32 Cleanup Budget in Nested Sub-Workflow Fan-Out**: Multi-level nesting: Flow → Sub-Workflow → Fan-Out → Skill. Verify total budget accumulates correctly across levels.
*   **T9.33 SIGINT Followed by SIGTERM 100ms Later**: Only one cleanup run. No double teardown. Signal latch prevents re-entry.
*   **T9.34 `cleanup()` Deletes File Being Written by Parallel Fan-Out Branch (Cross-Branch Conflict)**: Branch A's cleanup runs while Branch B's Skill is mid-write via Loom. Verify: (1) Loom advisory lock prevents Branch A's cleanup from deleting the file, OR (2) Branch B's write completes atomically before Branch A's delete succeeds. No partial-write corruption.
*   **T9.35 SIGTERM During Skill `execute()` While Skill Holds Loom Advisory Lock**: Skill acquired Loom lock for file editing. SIGTERM arrives. Verify: (1) `cleanup()` releases the Loom lock, (2) lock is not left dangling for other processes to contend with.
*   **T9.36 Four-Layer Cleanup Chain: Flow → AgentAtom → Skill → Tool**: SIGTERM arrives while Tool is executing within a Skill within an AgentAtom. Verify full 4-layer propagation: Tool.cancel() → Skill.cleanup() → AgentAtom.cleanup() → Engine teardown.
*   **T9.37 `cleanup()` Called on Skill That Already Returned SUCCESS (Late SIGTERM)**: Skill completed normally. SIGTERM arrives during Engine state checkpoint write. `cleanup()` called on already-completed Skill. Must be a no-op — no crash.
*   **T9.38 `cleanup()` Called Twice Sequentially (U5 — Sequential Double-Call)**: Engine erroneously calls `cleanup()` once (completes successfully), then calls it again sequentially due to a teardown state machine bug. Second call MUST be a no-op. No crash, no resource double-release.

---

## 10. Idempotency & Crash Recovery
Validating deterministic restart behavior and idempotency guarantees.

*   **T10.01 Idempotency Token Formula Verification**: Token matches `base64url(sha256(run_id + ":" + skill_name + ":" + step_index + ":" + tool_call_index))`.
*   **T10.02 Token Differs for Different `tool_call_index` Values**: Same Skill, indices 0 and 1 → different tokens.
*   **T10.03 Token Stable Across Retry Attempts (Path 1)**: Same token on retry (run_id excludes retry count).
*   **T10.04 Token Rehydration After Crash**: `tool_call_index = len(rehydrated_history)`, NOT reset to 0.
*   **T10.05 Action Skill with External API — Same Token = Idempotent**: API deduplicates. No double-fire.
*   **T10.06 Reasoning Skill Ignores Token**: Valid — no side-effects to duplicate.
*   **T10.07 Crash Mid-File-Write (Loom)**: Old file intact on restart (Write-Replace guarantee).
*   **T10.08 Crash Mid-File-Write (Raw IO, Forbidden)**: File may be corrupted — test detection mechanism.
*   **T10.09 Crash Between `execute()` Return and State Checkpoint**: Action Skill re-executes, Check-Then-Act skips. Reasoning/RAG re-execute safely (§9.19).
*   **T10.10 Token Contains Only URL-Safe Characters**: Verify base64url encoding (no `+`, `/`, `=` padding).
*   **T10.11 Different `run_id` Produces Different Token**: Same skill, same step. Tokens differ.
*   **T10.12 Different `skill_name` Produces Different Token**: Same run_id, same step. Tokens differ.
*   **T10.13 Different `step_index` Produces Different Token**: Same run_id, same skill. Tokens differ.
*   **T10.14 Agent Crash After Skill SUCCESS But Before Checkpoint — Action Skill**: Re-execute → Check-Then-Act → no duplication.
*   **T10.15 Agent Crash After Skill SUCCESS But Before Checkpoint — Reasoning Skill**: Re-execute safely (no side effects).
*   **T10.16 Token Rehydration — `tool_call_index` Based on History of SPECIFIC Skill**: Not total history count.
*   **T10.17 Skill Returns RETRY — Engine Uses Same Token on Retry**: Idempotency preserved across retry attempts.
*   **T10.18 Idempotency Token State Drift**: A Skill executes successfully and mutates external state, but Orchestrator crashes before saving the `SkillResult`. On restart, the same `idempotency_token` is generated. Verification that the Check-Then-Act pattern prevents duplicate mutation.
*   **T10.19 Token Formula with Unicode `skill_name`**: Skill named `"レビュー"`. Verify token is valid base64url with no encoding errors.
*   **T10.20 Token with `step_index = 0` and `tool_call_index = 0`**: Minimum inputs. Verify valid, non-empty token generated.
*   **T10.21 Token with Very Long `run_id` (1000 Characters)**: Verify SHA256 handles gracefully. No truncation of inputs.
*   **T10.22 Crash Mid-`cleanup()`**: Engine crashes during `Skill.cleanup()` execution. On restart, Engine re-executes Skill (cleanup state is unknown — must be treated as incomplete).
*   **T10.23 Crash During Blob Write**: Skill writing large exports to blob file. Crash leaves partial blob. On restart, deterministic blob path allows clean overwrite (01_05 §2 implicit GC).
*   **T10.24 Action Skill Check-Then-Act — State Modified By Another Parallel Branch**: Branch A creates file. Branch B (same Skill, different run_id) checks for file → finds it → returns SUCCESS without mutation. Idempotency works across branches.
*   **T10.25 Crash Between Skill SUCCESS and Engine Event Emission**: Event missed. On restart, Skill re-executes (idempotent). Engine re-emits event. Verify no duplicate user-facing side-effects.
*   **T10.26 Reasoning Skill Re-Execution Produces Different Result After Crash**: Inherent LLM non-determinism. Verify Engine accepts different exports on re-run (Reasoning Skills have no Check-Then-Act obligation).
*   **T10.27 Crash During State Checkpoint Write**: File half-written. Verify Engine's atomic write pattern (tmp → fsync → rename) prevents corruption. Old valid state remains intact.
*   **T10.28 Crash During Hot-Reload Atomic Swap**: Engine crashes while replacing the in-memory registry reference during hot-reload. On restart, Engine re-reads both JSON files from disk and performs full startup validation. Verify: (1) no partially-swapped registry state persists in memory, (2) the on-disk files are the authoritative source after crash.
*   **T10.29 Action Skill API Accepts Idempotency Token But Returns Different Result on Retry**: External API accepted the token for deduplication but returned a different response body on retry. Engine MUST use the **live API response** (not a cached one) since the API itself chose to return a different result despite dedup. Verify: (1) exports reflect the retry response, (2) no stale cache overrides live data.
*   **T10.30 Dual Crash: Engine Crashes During `execute()`, Restarts, Skill Re-Executes But Crashes at Different Point**: Multi-crash sequence. First crash: during Skill's file write. Second crash: during Skill's API call. On third restart, state must be consistent — Check-Then-Act pattern handles the partial-write from crash 1, and fresh API call handles crash 2.

---

## 11. Edge Cases & DAU Defenses
Testing resilience against developer mistakes and framework abuse.

*   **T11.01 Skill Module Has `@lru_cache` on Property**: `RegistryError` at startup (§8.2).
*   **T11.02 Skill Module Has `global` Variable**: `RegistryError` at startup if validator checks.
*   **T11.03 Blob Pointer Path Traversal**: `{"ref": "/etc/passwd"}` → `INVALID_BLOB_REF` (§8.4).
*   **T11.04 Blob Pointer to Non-Existent File**: → `INVALID_BLOB_REF`.
*   **T11.05 Persona Version `"02"` vs Registry Skill Version `"2"`**: Mismatch (exact string match). `RegistryError`.
*   **T11.06 Persona File Valid JSON but `personas` Key Missing**: `ConfigParseError`.
*   **T11.07 `as_tool()` Returns Different Values on Repeated Calls**: Violation of determinism invariant. Test 100 calls → identical output (§9.5).
*   **T11.08 Skill `execute()` Calls `sys.exit(0)`**: Engine does NOT catch (BaseException). Process-level handling.
*   **T11.09 Skill `execute()` Calls `os._exit(1)`**: Uncatchable. Container-level recovery required.
*   **T11.10 Skill Module Imports `requests` Without Timeout**: Static analysis flag or runtime enforcement of network safety rule.
*   **T11.11 Skill Uses Raw `open(path, 'w')` For File Writing**: Startup validator detects and raises `RegistryError`.
*   **T11.12 Skill Writes to Path Outside `service_root` via Tool**: `SecurityError` from ToolContext (§4.3, 01_04 §3.3).
*   **T11.13 Skill Returns `exports` with Reserved Key `"status"`**: `ReservedKeyCollisionError` (§9.10).
*   **T11.14 Skill Returns `exports` with Reserved Key `"current_step"`**: `ReservedKeyCollisionError` (§9.10).
*   **T11.15 Skill Returns `exports` with Reserved Key `"idempotency_token"`**: `ReservedKeyCollisionError` (§9.10).
*   **T11.16 Blob Pointer References Symlink Outside `.flow/artifacts/`**: `INVALID_BLOB_REF` (§8.4).
*   **T11.17 Skill Property `name` Returns Different Value Each Call**: Non-deterministic property. `RegistryError` at startup (§9.5).
*   **T11.18 `parameters_schema` Has Deeply Nested Internal `$ref`**: Valid if resolvable within schema. No external URLs.
*   **T11.19 Skill `execute()` Returns `SkillResult` With Status `None`**: Engine rejects with `ValueError` (§9.13).
*   **T11.20 Uncatchable C-Extension Crash in Skill**: A Skill uses a bad compiled dependency (e.g., malformed tree-sitter parse) causing a segfault. Ensure the Engine supervisor isolates the crash without corrupting `.flow_state/` or killing the main Orchestrator.
*   **T11.21 Skill `execute()` Forks a Subprocess** (`os.fork()` / `subprocess.Popen`): Against statelessness principle. Verify subprocess cleaned up by Engine supervisor at step completion or SIGTERM.
*   **T11.22 Skill `execute()` Spawns Daemon Thread** (`threading.Thread(daemon=True)`): Thread survives Skill return but should die with Engine process. Verify no side-effects leak.
*   **T11.23 Skill `execute()` Opens File Handle Without Closing**: Resource leak. Verify Engine's step-level wrapper or GC-based cleanup handles eventual release.
*   **T11.24 Skill `execute()` Writes to `sys.stderr` Directly**: Should not affect Engine's structured logging stream. Verify no interleaving or corruption.
*   **T11.25 Skill `name` Property Returns Value with Path Separators**: `"../../etc"`. Expect `RegistryError` (name must be sanitized — alphanumerics, underscores, hyphens only).
*   **T11.26 Skill `name` Property Returns Value with Null Bytes**: `"skill\x00"`. Expect `RegistryError` at startup.
*   **T11.27 Skill `description` Contains Terminal Control Characters**: `"Skill\x1b[2J"`. Expect sanitization or `WARNING` logged (01_05 §6.08 cross-ref pattern).
*   **T11.28 Skill Exports Key with Very Long Name (10,000 Characters)**: Expect SUCCESS or explicit key-length limit enforcement.
*   **T11.29 Skill Exports Deeply Nested Dict (1,000 Levels)**: Expect serialization limit or `RecursionError` caught by Engine (01_05 §6.07 cross-ref).
*   **T11.30 Skill `parameters_schema` Uses `format` Keyword** (e.g., `"format": "email"`): Valid JSON Schema, but not enforced by all LLM providers. Expect SUCCESS at registration; runtime validation depends on provider.
*   **T11.31 Skill Uses `@functools.cached_property`** on `parameters_schema`: Similar caching issue as `@lru_cache`. Verify startup validator catches (§8.2, §9.5).
*   **T11.32 Skill `as_tool()` Overridden by Subclass**: Subclass returns different keys or structure. Engine should validate descriptor structure before using.
*   **T11.33 Skill Has `__del__` Destructor for Cleanup**: Not reliably called in Python. Verify Engine doesn't rely on destructors — uses `cleanup()` instead.
*   **T11.34 Skill `execute()` Calls `importlib.import_module()`**: Dynamic import at runtime. Verify no security escalation beyond Skill's existing permissions.
*   **T11.35 Skill `required_tools` Property Raises Exception**: Property getter throws `RuntimeError`. Expect `RegistryError` at startup.
*   **T11.36 Skill `version` Property Returns Different Values on Consecutive Calls**: Non-deterministic. Expect `RegistryError` at startup (§9.5).
*   **T11.37 Skill Creates Files Outside `.flow/artifacts/`**: Should be caught by ToolContext `service_root` check when using Tools (§4.3, 01_04 §3.3).
*   **T11.38 Skill `execute()` Calls `gc.disable()`**: Disabling garbage collection affects the entire process. Verify: (1) Engine does not crash due to memory pressure, (2) Engine's step-level wrapper re-enables GC after Skill returns if possible, (3) `WARNING` logged about GC manipulation.
*   **T11.39 Skill `execute()` Modifies `sys.path`**: Path injection allows loading arbitrary code on subsequent imports. Verify: (1) Engine executes Skill in context where `sys.path` modifications don't affect subsequent Skills (subprocess isolation or deep-copy), (2) if in-process, `sys.path` is restored after Skill returns.
*   **T11.40 Skill `parameters_schema` Uses `patternProperties`**: Valid JSON Schema keyword, but unusual. Verify: (1) registration succeeds (valid JSON Schema), (2) `WARNING` logged noting some providers may not support `patternProperties`, (3) projection to Ollama produces `ProviderProjectionError` (unsupported feature).

---

## 12. Security & Isolation
Validating architectural boundaries and access control.

*   **T12.01 Skill Attempts to Import and Invoke Atoms Directly**: No import path exists (architectural boundary enforced by module structure).
*   **T12.02 Skill Exports Key Shadowing `run_id`**: Rejected by Engine (`ReservedKeyCollisionError`).
*   **T12.03 Skill Exports Key Shadowing `abort_event`**: Rejected by Engine.
*   **T12.04 Skill Reads `context["abort_event"]` and Calls `.wait()`**: Blocks forever. Documented risk. Test that Engine's step timeout eventually kills it.
*   **T12.05 Context Window Exhaustion — 1MB String in `exports`**: 128KB limit enforced.
*   **T12.06 `ToolContext` Forwarded Unchanged from AgentAtom to Skill**: Same RBAC applies. Skill cannot escalate.
*   **T12.07 Skill Modifies `ToolContext` Before Passing to Tool**: Expect failure or no effect — `ToolContext` is immutable.
*   **T12.08 Skill Attempts to Read and Modify `context["run_id"]`**: `TypeError` from `MappingProxyType`.
*   **T12.09 Skill Creates `threading.Thread` With `daemon=False`**: Engine's cleanup must handle leaked non-daemon threads (01_05 §8.14 cross-ref).
*   **T12.10 Skill Monkey-Patches `SkillResult` Class**: No effect on Engine's processing — separate import (01_05 §9.03 cross-ref).
*   **T12.11 Skill Calls `signal.signal(SIGTERM, SIG_IGN)`**: `RuntimeError` (not main thread), or container SIGKILL watchdog (01_05 §9.05 cross-ref).
*   **T12.12 Skill Writes to `sys.stdout` Directly**: No effect on Engine's structured logging stream (01_05 §9.01 cross-ref).
*   **T12.13 Skill Accesses `os.environ`**: Should receive sanitized copy, not real environment (01_05 §9.02 cross-ref).
*   **T12.14 Path 2: AgentAtom Cannot Escalate Skill's RBAC**: Modifying `ToolContext` has no effect. RBAC check uses Engine-injected context.
*   **T12.15 Skill Exports Contain Pickle-Encoded Data**: JSON serializer rejects non-standard types (01_04 T7.26 cross-ref).
*   **T12.16 Skill Attempts `import flow.atoms`**: Import succeeds (Python doesn't prevent it), but Skill MUST NOT directly invoke Atom classes. Verify architectural note or runtime guard.
*   **T12.17 Skill Attempts to Escalate Tool Permissions**: Skill modifies `tool_context.role` before passing to Tool. `ToolContext` is immutable — `AttributeError` raised.
*   **T12.18 Skill Reads `tool_context.access_token`**: Should be available (needed for RAG/API access). Verify token is not leaked to exports or logs.
*   **T12.19 Skill Passes `tool_context.access_token` as Export**: Token in exports → persisted to disk. Expect `ReservedKeyCollisionError` or secret-detection redactor catches it.
*   **T12.20 Path 2: LLM Attempts SQL Injection via Skill Args**: `"target_file": "'; DROP TABLE skills; --"`. Schema validation passes (it's a string). Skill's business-rule validation MUST catch.
*   **T12.21 Skill Exports Contain Sensitive-Looking Strings** (`sk-*` pattern): Redactor should flag API key patterns in exports. `WARNING` logged.
*   **T12.22 Two Skills in Same Flow Share Python Global State**: Module-level dict used as cache. Verify Engine's statelessness enforcement prevents cross-Skill contamination.
*   **T12.23 Skill Calls `multiprocessing.Process()`**: Spawns child process. Verify Engine's process supervisor tracks and cleans it up on SIGTERM.
*   **T12.24 Skill Monkeypatches `json.loads` to Bypass Schema Validation**: Verify Engine uses its own isolated import chain. Monkeypatch has no effect on Engine's validation (01_05 §9.03 cross-ref).
*   **T12.25 Skill Reads `/proc/self/environ` (Linux) or `os.environ` (Windows)**: Should receive sanitized environment, not real secrets (01_05 §9.02 cross-ref).
*   **T12.26 Blob Pointer TOCTOU Vulnerability**: Skill exports blob reference pointing to a path that was safe during `execute()`. Between export creation and Engine resolution, an external process replaces the file with a symlink to `/etc/passwd`. Verify: (1) Engine resolves blob using `SafePath` (§8.4), (2) symlink detected and rejected with `INVALID_BLOB_REF` + `SecurityError`.
*   **T12.27 Skill Receives `tool_context` with `isolation_level = "STRICT"` But Accesses Shared Tool**: ToolContext has `isolation_level: STRICT`, restricting Loom access. Skill calls `read_file` (shared tool). Verify: (1) `read_file` is allowed (read access respects scope), (2) `edit_file` via Loom is DENIED (`STRICT` mode blocks Loom writes).
*   **T12.28 Path 2: LLM Encodes Args Bypassing Schema (Nested Objects Where Strings Expected)**: LLM sends `{"target_file": {"path": "../../etc/passwd"}}` where schema expects a string. Schema validation catches type mismatch. Error returned to LLM. Verify no object-to-string coercion that would bypass validation.

---

## 13. Sub-Workflow & Cross-Module Interaction

> [!NOTE]
> These tests overlap with 01_03 and 01_05. They are included here because the Skill-specific behavior (e.g., `PAUSED_FOR_EXPANSION` propagation, Loom locking) must be verified from the Skill's perspective.

*   **T13.01 `PAUSED_FOR_EXPANSION` in Sub-Workflow**: Innermost Flow pauses. Parent transitions to waiting. TTL applies to inner. (§9.20).
*   **T13.02 Resume After `PAUSED_FOR_EXPANSION` — DAG Changed**: `ConfigVersionMismatchError` raised (§8.5 step pointer safety).
*   **T13.03 Resume After `PAUSED_FOR_EXPANSION` — DAG Unchanged**: Flow resumes at exact paused step.
*   **T13.04 Concurrent Sub-Workflows Write Same File (Loom Lock)**: One succeeds, other gets `ResourceBusy`. No corruption.
*   **T13.05 `PAUSED_FOR_EXPANSION` TTL Expires**: Flow transitions to `TIMED_OUT`. Admin notified.
*   **T13.06 `PAUSED_FOR_EXPANSION` — Engine Emits Structured Event**: Dashboard receives `flow_paused_for_expansion` event payload.
*   **T13.07 Nested Sub-Workflow — Parent and Child Both Pause**: Both TTL timers run independently. Parent TTL kills child if child TTL hasn't fired.
*   **T13.08 Logical Cycle via `PAUSED_FOR_EXPANSION`**: Flow A → Skill X → PAUSED suggesting Flow B → Skill X → PAUSED suggesting Flow A. TTL prevents infinite loop (01_03 T7.09 cross-ref).
*   **T13.09 Concurrent Sub-Workflows Read Same File** (no Loom lock needed): Both succeed — reads are non-exclusive.
*   **T13.10 Sub-Workflow Skill `exports` Collide With Parent Context Keys**: Namespace enforcement prevents collision (§9.10).
*   **T13.11 Sub-Workflow Pause vs Skill Pause**: An active Skill returns `PAUSED_FOR_EXPANSION` while executing *inside* an L2 Sub-Workflow. Expect: (1) L2 child Flow transitions to `PAUSED_FOR_EXPANSION` state, (2) L1 parent Flow transitions to `WAITING` state, (3) `flow_paused_for_expansion` event payload contains the full ancestry chain (`L1_flow_id → L2_flow_id → skill_name`), (4) L2 child's `context.json` snapshot is consistent with the last completed step (no partial exports from the paused Skill), (5) TTL timer starts on L2 (inner), NOT on L1.
*   **T13.12 Parallel Export Collisions (Fan-Out)**: Two parallel skills in a Flow export identically named, un-namespaced keys simultaneously. Expect Engine Fan-In Reducer to reject the ambiguous dict-merge and fail the parent Flow with `SchemaCollisionError`.
*   **T13.13 Three Levels of Nesting: Flow → Sub-Workflow → Skill Returns `PAUSED_FOR_EXPANSION`**: Pause propagates L3 → L2 → L1. All three Flows have correct states (L3=PAUSED, L2=WAITING, L1=WAITING).
*   **T13.14 Resume After `PAUSED_FOR_EXPANSION` with Same DAG**: Resume succeeds at exact step where pause occurred. No duplicate Skill execution.
*   **T13.15 Sub-Workflow Skill Exports Don't Leak to Parent's Global Context**: Namespace isolation enforced. Parent sees only `skill:name:key` format, not raw keys from child.
*   **T13.16 Two Parallel Sub-Workflows Both Return `PAUSED_FOR_EXPANSION`**: Parent handles both pauses. Both TTL timers are independent.
*   **T13.17 `PAUSED_FOR_EXPANSION` TTL Expires While Operator Modifies DAG**: Flow transitions to `TIMED_OUT`. DAG modifications are discarded (not applied to timed-out flow).
*   **T13.18 Concurrent Sub-Workflows: One Succeeds, One PAUSEs**: Parent must handle mixed results correctly — SUCCESS branch exports merged, PAUSED branch awaits intervention.
*   **T13.19 Sub-Workflow Crash During Skill Execution**: Parent detects child failure. Propagates to parent's `on_failure` policy (halt or ignore).
*   **T13.20 Sub-Workflow Skill Uses Loom Lock Conflicting with Parent's Lock**: Parent holds file lock. Sub-Workflow Skill tries same file. Expect `ResourceBusy` (file-level concurrency control).
*   **T13.21 Sequential Sub-Workflows: Child A Exports, Child B Needs Them**: Sequential sub-workflow execution. Child B sees Child A's exports in merged context.
*   **T13.22 `PAUSED_FOR_EXPANSION` — Engine Restart During Pause**: Pause state persisted to disk. On restart, pause is preserved, TTL continues from where it left off.
*   **T13.23 `PAUSED_FOR_EXPANSION` at L3 + Hot-Reload + Resume (U7)**: Flow is at L3 depth in `PAUSED_FOR_EXPANSION`. Hot-reload fires, changing Skill versions in the registry. Operator resumes. Verify: (1) `ConfigVersionMismatchError` is checked against the **sub-workflow's** DAG (not parent's), (2) Skill version changes in registry do NOT affect the frozen snapshot's validity check (frozen snapshot was from before the pause), (3) if DAG is unchanged, resume succeeds despite registry changes.
*   **T13.24 Sub-Workflow Skill Exports Blob Reference — Parent Resolution**: Sub-workflow's Skill exports `{"ref": ".flow/artifacts/blob_child_123.txt"}`. Parent Flow tries to resolve this blob in its own context. Verify: (1) path is relative to the **common** `.flow/` root, not the sub-workflow's isolated state, (2) blob is accessible from parent's context.
*   **T13.25 Parallel Sub-Workflows — Sequential Loom Lock Acquisition**: Parallel sub-workflows: Skill A and Skill B both need Loom lock on `src/main.py`. Skill A completes first, releases lock. Skill B acquires lock and proceeds. Verify: (1) no `ResourceBusy` when locks are sequential (not concurrent), (2) Loom advisory lock correctly released by Skill A's normal completion.
*   **T13.26 Parallel Fan-Out — Same Skill, Different Inputs, Namespace Collision (U4)**: Two parallel branches both run `refactor_code` Skill with different inputs. Both export `skill:refactor_code:diff_path`. Expect: (1) since both use the correct namespace AND the same Skill name, the keys collide, (2) Engine's Fan-In Reducer detects the collision and fails with `SchemaCollisionError`, OR (3) Fan-Out branch indexing disambiguates the keys (e.g., `branch_0:skill:refactor_code:diff_path`). Define and test the actual policy.
*   **T13.27 Sub-Workflow Skill Returns RETRY — Circuit Breaker Interaction**: Skill inside L2 sub-workflow returns `RETRY` 4 times. Circuit breaker configured at `max_retries=3`. Verify: (1) L2 sub-workflow's circuit breaker trips on the 4th RETRY, (2) L2 transitions to `FATAL`, (3) L1 parent handles L2's failure per its `on_failure` policy, (4) the sub-workflow's retry counter is **independent** of the parent's — parent circuit breaker is unaffected.

---

## 14. Future Proposals (V-Next+1)
Features not in V1 scope but documented for future planning.

*   **P14.01 Read-Only Proxy for `abort_event`**: Wrap in proxy exposing only `.is_set()`.
*   **P14.02 `flow_hot_reload_rejected` Dashboard Event**: Structured event for schema version bumps.
*   **P14.03 Fuzz Testing for `parameters_schema` Validation**: Python Hypothesis → random schemas.
*   **P14.04 Execution Trajectory Logging (Google ADK Pattern)**: Log Skill call sequence for replay.

---

## 15. Statistical Repeat Testing & Non-Determinism Quantification

> [!NOTE]
> These tests address the BP-4 gap ("run evaluations multiple times, measure variance") identified in the industry best-practices audit. They target the inherent non-determinism of LLM-based Skill execution and provide statistical confidence that the system produces acceptable results under real-world conditions. All tests use the `N_RUNS` parameter (default: 10, configurable via `FLOW_STAT_RUNS` env var) and report pass/fail against a configured threshold.

### 15.1 Output Consistency & Variance

*   **T15.01 Reasoning Skill — Output Variance Across N Runs**: Execute the same Reasoning Skill with identical context and kwargs `N_RUNS` times. Collect all `SkillResult.exports`. Measure: (1) structural consistency — all runs produce exports with the same key set (100% required), (2) semantic consistency — exports values are the "same answer" within acceptable bounds. Report: key-set match rate (MUST be 100%), value variance metric (informational, not gating for V1).
*   **T15.02 Action Skill — Idempotency Token Stability Across N Runs**: Execute the same Action Skill with identical `run_id`, `skill_name`, `step_index`, `tool_call_index` across `N_RUNS` runs. Verify: 100% of runs produce the **identical** idempotency token (deterministic formula). If any run produces a different token, this is a CRITICAL regression — the formula is broken.
*   **T15.03 LLM Tool Selection Consistency (Path 2)**: Present AgentAtom with a scenario that has ONE optimal Skill to call. Run `N_RUNS` times. Measure: tool selection accuracy rate. Threshold: ≥ 80% of runs select the correct Skill. Below threshold → `WARNING` (LLM model quality issue, not system bug).
*   **T15.04 LLM Argument Accuracy Across N Runs (Path 2)**: LLM invokes a Skill with required args. Run `N_RUNS` times. Measure: (1) schema validation pass rate (MUST be ≥ 90%), (2) semantic correctness of args (measured by string similarity or exact-match for constrained fields). Report: per-field accuracy rates.
*   **T15.05 Schema Self-Correction Success Rate**: LLM sends invalid args on first attempt. Measure: self-correction success rate across `N_RUNS` flows (each allowing `max_schema_retries=2`). Threshold: ≥ 60% of runs self-correct within allowed retries. Below threshold → `WARNING` (schema complexity issue or model quality issue).
*   **T15.06 ReAct Loop Iteration Count Variance**: Same task, `N_RUNS` times. Measure: mean and standard deviation of loop iterations to completion. Threshold: coefficient of variation (CV) ≤ 0.5. CV > 0.5 → `WARNING` (high non-determinism indicates unstable task decomposition).
*   **T15.07 Execution Time Variance**: Same Skill, same kwargs, `N_RUNS` times. Measure: mean and p95 of `duration_ms`. Threshold: p95 ≤ 3× mean (detect outlier runs that indicate resource contention or LLM latency spikes). Report: histogram of durations.

### 15.2 Determinism Gates (Hard Requirements)

*   **T15.08 `as_tool()` Determinism Gate**: Call `as_tool()` `N_RUNS` times on the same Skill instance. Verify: 100% identical output (§9.5). This is NOT statistical — it's a determinism regression gate. Any deviation is a CRITICAL failure.
*   **T15.09 Idempotency Token Determinism Gate**: Generate idempotency tokens with identical inputs `N_RUNS` times. Verify: 100% identical output. Any deviation is a CRITICAL failure (hash function regression).
*   **T15.10 State Checkpoint Determinism Gate**: Serialize `WorkflowState` to JSON `N_RUNS` times from the same in-memory state. Verify: 100% byte-identical output. Any deviation indicates non-deterministic serialization (dict ordering, float precision).
*   **T15.11 Namespace Key Generation Determinism Gate**: Generate `skill:<name>:<key>` namespace keys `N_RUNS` times for the same Skill/export combination. Verify: 100% identical. Tests string construction stability.

### 15.3 Regression Detection via Statistical Baselines

*   **T15.12 Baseline Capture — Tool Selection Accuracy**: Run the T15.03 scenario `N_RUNS` times. Store the accuracy rate as a **baseline** in `.flow/test_baselines/tool_selection.json`. On subsequent CI runs, compare current accuracy against baseline. Fail if current accuracy drops by > 10 percentage points (indicates model degradation or system regression).
*   **T15.13 Baseline Capture — Self-Correction Rate**: Run T15.05 scenario. Store baseline. Fail if rate drops by > 15 percentage points.
*   **T15.14 Baseline Capture — Loop Iteration Count**: Run T15.06 scenario. Store mean + stddev as baseline. Fail if current mean exceeds baseline mean + 2σ (statistically significant increase in iterations → potential prompt degradation).
*   **T15.15 Baseline Drift Alert — No Baseline Exists**: First run, no baseline file. Expect: test passes but logs `INFO: "Baseline captured for {test_name}. Subsequent runs will compare against this."` No failure on first run.

### 15.4 Flaky Test Detection & Quarantine

*   **T15.16 Flaky Detection — Same Test Passes and Fails Within N Runs**: Run a Skill execution scenario `N_RUNS` times. If ≥ 1 run fails and ≥ 1 passes (not 0% or 100% pass rate), mark the test as `FLAKY`. Report: exact pass rate and failure reasons. Flaky tests are quarantined (not counted as failures in CI gate, but tracked in flaky dashboard).
*   **T15.17 Flaky Detection — LLM Timeout Variance**: Skill execution times out on 2 of 10 runs. Verify: (1) test is tagged `FLAKY`, (2) timeout failures are logged with individual `duration_ms` for each run, (3) flaky dashboard updated.
*   **T15.18 Statistical Test with `temperature=0` — High Determinism Expected**: Set `model_params.temperature: 0`. Run `N_RUNS` times. Measure: output variance should be near-zero. Threshold: ≥ 95% of runs produce byte-identical exports. Below threshold → `WARNING` (provider's temperature=0 is not truly deterministic, which is a known industry issue).

### 15.5 Multi-Provider Statistical Comparison

*   **T15.19 Cross-Provider Consistency — Same Skill, Same Prompt**: Run identical Skill scenario against Gemini, OpenAI, and Anthropic (where configured). Measure: (1) all three produce structurally identical exports (same keys), (2) semantic similarity of values across providers. Report: per-provider accuracy and agreement matrix. No hard failure — informational only (providers are expected to differ).
*   **T15.20 Provider Failover — Statistical Reliability**: Configure primary provider (Gemini) + fallback (OpenAI). Run `N_RUNS` times with primary intermittently failing (mock 30% failure rate). Verify: (1) overall success rate ≥ 90% (failover compensates), (2) failover latency is logged per run, (3) no runs produce inconsistent state due to provider switch mid-execution.

---

## Appendix A: Industry Best Practices Coverage Matrix

> [!NOTE]
> Cross-reference with published evaluation patterns from Anthropic, Google Cloud, OpenAI, and the Berkeley Function Calling Leaderboard (BFCL). This matrix tracks which best practices are covered by the test spec and where gaps remain.

| # | Best Practice | Status | Covering Tests | Notes |
|---|:---|:---:|:---|:---|
| BP-1 | **Schema-driven tool contracts with strict validation** | ✅ Covered | T3.09–T3.33, T6.03, T6.25, T8.01–T8.18 | JSON Schema `type: object`, `additionalProperties: false`, strict mode projection |
| BP-2 | **Multi-turn evaluation with grader functions** | ⚠️ Partial | T6.43, T6.44 | Self-correction loops tested, but no LLM-as-Judge or external grader pattern. **V2 candidate**: add autorater-based grading. |
| BP-3 | **Tool usage accuracy metrics (correct tool, correct args, correct order)** | ✅ Covered | T6.01–T6.06, T6.36–T6.37 | Correct tool selection, correct argument validation, and multi-tool sequencing tested. |
| BP-4 | **Non-determinism handling (run evaluations multiple times)** | ✅ Covered | T10.26, T15.01–T15.20 | Statistical repeat tests (Ch. 15): output variance, determinism gates, baseline regression detection, flaky test quarantine, cross-provider comparison. |
| BP-5 | **Fail-safe over fail-fast design** | ✅ Covered | T9.01–T9.38, T10.01–T10.30 | Pervasive: cleanup chains, circuit breakers, idempotent teardown, SIGKILL watchdogs. |
| BP-6 | **Clear tool input/output contracts** | ✅ Covered | T4.01–T4.41, T5.09 | `SkillResult` contract, `parameters_schema`, namespace enforcement. |
| BP-7 | **Versioned tool definitions linked to evaluations** | ✅ Covered | T2.06–T2.07, T3.07–T3.08, T7.17, T11.05 | Version pinning, version mismatch detection, hot-reload version changes. |
| BP-8 | **Security: hallucinated params, unauthorized access** | ✅ Covered | T6.05–T6.06, T12.01–T12.28, T11.03, T11.12 | Hallucination defense, RBAC, blob traversal, TOCTOU, ToolContext immutability. |
| BP-9 | **Context engineering / "just-in-time" context** | ⚠️ Partial | T5.37, T6.50, T13.24 | Blob pointer pattern covers deferred data loading. Missing: dynamic tool filtering (deferred to V2, spec §10.8). |
| BP-10 | **Continuous self-correction via LLM autoraters** | ❌ Not in V1 | — | Correctly deferred to V2+. No testing needed. |
| BP-11 | **Relevance detection (knowing when NOT to call a function)** | ✅ Covered | T6.05, T6.47 | LLM calling non-existent skills, repeated invalid calls. |
| BP-12 | **Parallel function calls** | ✅ Covered | T5.10, T5.23, T5.35, T13.12, T13.26 | Fan-Out with same/different skills, export collision detection. |
| BP-13 | **Component and end-to-end testing separation** | ✅ Covered | Ch. 2–4 (schema), Ch. 5–6 (execution), Ch. 13 (integration) | Schema validation at startup (component), full execution paths (E2E). |
| BP-14 | **Cost/token usage awareness** | ⚠️ Partial | T6.43 (loop iteration counting) | ReAct loop iteration counting serves as proxy for token cost. No explicit token budget enforcement in V1. |

**Legend**: ✅ = Fully covered | ⚠️ = Partially covered (V2 candidate noted) | ❌ = Explicitly out of scope for V1
