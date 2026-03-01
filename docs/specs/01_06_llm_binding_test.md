# 01_06 Test Specification: LLM Binding & Selection

> **Status**: DRAFT (Paranoid QA V-Next Validations)
> **Owner**: Senior QA Architecture Team
> **Target**: `src/flow/llm/`, `tests/unit/llm/`, `tests/integration/llm/`
> **Spec Reference**: [01_06_llm_binding_spec.md](01_06_llm_binding_spec.md)

## 1. Goal & QA Philosophy

This document defines the strict, DAU-resistant test inventory for the LLM Binding System (Provider Protocol, Factory, Authentication, Retry, and Adapter Contracts).

As Senior QA, we assume: providers **will** go down silently mid-stream, API keys **will** rotate without warning, junior developers **will** call `generate()` before `configure()`, tokens **will** run out at the worst possible moment, and someone **will** deploy with two conflicting provider SDKs. The DAU **will** store API keys in `flow_config.json`, pass `None` as messages, and call `reset()` mid-workflow.

**Core philosophy**: *"Every LLM call is a liability. Every provider is hostile. Every credential is ephemeral."*

---

## 2. Spec Audit: The Good, The Bad, The Ugly

### 2.1 The Good ✅

1.  **Lifecycle Contract is airtight**: The `configure()` → `generate()`/`embed()` → `close()` lifecycle with explicit error states (`ProviderNotConfiguredError`, `ProviderAlreadyConfiguredError`) prevents most state machine bugs.
2.  **Error hierarchy is well-stratified**: The distinction between `LLMConnectionError` (retryable), `LLMAuthError` (not retryable), `LLMRateLimitError` (retryable with backoff), and `LLMGenerationError` (conditional) is excellent. This prevents retry-loops on dead credentials.
3.  **Credential resolution chain** (§4.4) with layered fallback (env → keyring → ADC → fail fast) is production-grade.
4.  **Thread-safety requirement** is explicitly called out in the ABC docstring.
5.  **Contract Test Base Class** (§8.1) ensures all adapters share a common behavioral test suite.
6.  **`generate()` never returns empty/None** — this forces adapters to raise on empty responses, preventing silent downstream failures.
7.  **Lazy initialization** (no eager `validate()`) is pragmatic for local providers like Ollama.
8.  **`embed([])` returns `[]`** without API call — explicitly documented.

### 2.2 The Bad ⚠️ (Gaps to Close via Tests)

1.  **No startup validation hook**: The spec says validation is lazy (first use), but there's no `flow validate-llm` or startup health-check flow documented. If misconfig isn't detected until minutes into a workflow (after tokens are burned), the user experience is terrible. **Tests must cover this gap aggressively.**
2.  **`reset()` during active calls is "undefined behavior"** (§5.2 CAUTION box). This is honest but dangerous — we need tests that *prove* the system doesn't corrupt state when a DAU inevitably does this.
3.  **No explicit `embed()` timeout default** in the signature (the spec text says 60s but the ABC code shows `timeout_seconds: int = 60` — this is fine but should be tested).
4.  **`count_tokens()` approximation quality**: The spec allows `chars/4` as fallback. This could wildly miscount for CJK, emoji, or code-heavy prompts. Tests needed.
5.  **Missing: What happens if `configure()` partially succeeds?** E.g., SDK client created but credential validation fails mid-way. Is the adapter in "configured" state? Can you call `configure()` again? Tests must cover this.
6.  **No `embed()` dimension consistency guarantee**: The spec doesn't require adapters to declare or validate embedding dimensions. Different models return different dimensions — callers could get surprised.
7.  **`validate()` default costs tokens**: The default `validate()` implementation calls `generate()` with `max_tokens=1`. If an adapter author forgets to override, calling `validate()` silently burns tokens. Must test and document this cost.
8.  **Profile name case sensitivity undefined**: The spec does not state whether profile names are case-sensitive. `"Default"` vs `"default"` is a classic DAU trap.
9.  **SDK unexpected exceptions not mapped**: The spec §6.2 covers SDK-specific errors, but what about completely unexpected exceptions (`RuntimeError`, `KeyError`, `RecursionError`) from buggy SDKs? Must test they are caught and mapped.
10. **Retry-amplified timeout bound**: With Tenacity retries enabled, total wall-clock time for `generate(timeout_seconds=1)` could be 3× the timeout + backoff. No circuit breaker documented.
11. **Manual `adapter.close()` bypassing Factory**: If user holds a reference and calls `close()` directly (bypassing Factory), the Factory cache returns a dead instance on next `create()`. Must test.
12. **`close_all()` per-adapter timeout independence**: If one adapter's `close()` hangs, it must not block cleanup of other adapters in the `close_all()` loop.
13. **Credential sanitization incomplete character set**: Spec §4.4 covers ZWSP and BOM, but copy-paste from Outlook/Slack also introduces Non-Breaking Space (`\u00A0`), Em Space (`\u2003`), and Windows `\r\n`.

### 2.3 The Ugly 🔴 (Critical Gaps)

1.  **No test for `close()` idempotency**: The spec says `close()` is a no-op by default. But what if called twice? Three times? After a failed `configure()`? This MUST be tested.
2.  **Registry key mismatch attack surface**: The spec says `provider_name` must match the registry key (§5.1 #3). But there's no test for what happens if a malicious adapter lies about its `provider_name`. This is a supply-chain concern.
3.  **Missing: Factory behavior when `flow_config.json` has unknown profile name.** What error? When? This is a DAU classic.
4.  **Credential leakage via exception messages**: If `configure()` fails, does the exception message contain the API key? The spec says "No API keys in logs" (§8 checklist) but doesn't mention exception args.
5.  **Spec class diagram mismatch**: The Mermaid class diagram (§2) shows `close(profile_name: str)` on `LLMFactory`, but §5.2 only documents `reset(profile_name)` and `close_all()`. Either the diagram or the spec text is wrong — must be resolved before implementation.
6.  **`close()` on poisoned adapter — resource leak verification**: T3.3.05 says "verify close() releases resources" but doesn't specify **how** to verify. A silent no-op that leaks an HTTP pool would also pass. Must mock and assert `client.close()` was called on partially-initialized SDK.

---

## 3. LLMProvider Lifecycle Tests

These tests exercise the strict state machine: `Uninitialized → Configured → (Active use) → Closed`.

### 3.1 Basic Lifecycle (The Happy Path — Still Not Trusted)

*   **T3.1.01 Configure-Then-Generate**: Create adapter, call `configure()`, call `generate()` with valid messages. Expect success.
*   **T3.1.02 Configure-Then-Embed**: Create adapter, call `configure()`, call `embed()` with valid texts. Expect list of vectors with `len(result) == len(texts)`.
*   **T3.1.03 Configure-Then-CountTokens**: Create adapter, call `configure()`, call `count_tokens("hello world")`. Expect integer > 0.
*   **T3.1.04 Configure-Then-Validate**: Create adapter, call `configure()`, call `validate()`. Expect `True`.
*   **T3.1.05 Configure-Then-Close**: Create adapter, call `configure()`, call `close()`. Expect no exception.
*   **T3.1.06 Validate Default Costs Tokens**: Call `validate()` on an adapter that does NOT override the default implementation. Mock `generate()`. Verify `generate()` was called exactly once with `max_tokens=1` and `timeout_seconds=5`. Documents the token cost of unoverridden `validate()`.

### 3.2 Lifecycle Violations (State Machine Enforcement)

*   **T3.2.01 Generate Before Configure**: Call `generate()` without calling `configure()`. Expect `ProviderNotConfiguredError`.
*   **T3.2.02 Embed Before Configure**: Call `embed()` without calling `configure()`. Expect `ProviderNotConfiguredError`.
*   **T3.2.03 CountTokens Before Configure**: Call `count_tokens()` without `configure()`. Expect `ProviderNotConfiguredError`. Even local tokenizers (e.g., tiktoken) require `configure()` to determine which model's tokenizer to load (spec §3 Lifecycle #4).
*   **T3.2.04 Double Configure**: Call `configure()` twice. Expect `ProviderAlreadyConfiguredError` on second call.
*   **T3.2.05 Generate After Close**: Call `close()`, then `generate()`. Expect `ProviderNotConfiguredError`.
*   **T3.2.06 Embed After Close**: Call `close()`, then `embed()`. Expect `ProviderNotConfiguredError`.
*   **T3.2.07 CountTokens After Close**: Call `close()`, then `count_tokens()`. Expect `ProviderNotConfiguredError`. `close()` is permanent — all methods are dead (spec §3 Lifecycle #6, #7).
*   **T3.2.08 Close Without Configure**: Call `close()` without calling `configure()`. Expect no exception (no-op behavior).
*   **T3.2.09 Close Idempotency**: Call `close()` three times in a row. Expect no exception on any call.
*   **T3.2.10 Validate Before Configure**: Call `validate()` before `configure()`. Expect `ProviderNotConfiguredError` (since default implementation calls `generate()`).
*   **T3.2.11 Configure After Close**: Call `configure()`, `close()`, then `configure()` again. Expect `ProviderAlreadyConfiguredError`. The adapter is **permanently dead** after `close()`. To get a new instance, use `Factory.reset(profile)` + `Factory.create(profile)` (spec §3 Lifecycle #7).

### 3.3 Partial Configure Failure

*   **T3.3.01 Configure Fails Mid-Way (Auth Missing)**: `configure()` raises `LLMAuthError`. Subsequent `generate()` call: Expect `ProviderNotConfiguredError`. The adapter was never successfully configured. A failed `configure()` **poisons** the adapter — it is permanently unusable. The caller must discard it and obtain a fresh instance via `Factory.reset()` + `Factory.create()` (spec §3 Lifecycle #5).
*   **T3.3.02 Configure Fails Then Retry**: `configure()` fails with `LLMAuthError`. DAU calls `configure()` again with correct config. Expect `ProviderAlreadyConfiguredError`. A failed `configure()` poisons the adapter — even if the first call failed, a second call is rejected. This is intentional: it forces a full factory reset, which emits a warning/error message guiding the operator.
*   **T3.3.03 Configure SDK Import Failure**: The provider SDK is not installed. `configure()` should raise `MissingDependencyError` with install instructions. Expect the message to include the specific `poetry install -E` command.
*   **T3.3.04 Configure Fails After Partial SDK Init (Resource Leak)**: Mock `configure()` to create an SDK client (HTTP pool initialized) but fail during credential validation. Expect `LLMAuthError` raised AND verify that the partially-initialized SDK client's resources (HTTP pools, background threads) are properly cleaned up in the exception handler — no resource leak (spec §3 Lifecycle #5a).
*   **T3.3.05 Close On Poisoned Adapter Cleans Up**: `configure()` fails (adapter poisoned). Then call `close()`. Expect no exception. Verify that `close()` releases any partially-initialized SDK resources rather than silently no-opping — specifically, mock `httpx.Client()` creation to succeed and credential validation to fail, then after `close()` verify `httpx_client_mock.close()` was called. Then verify `generate()` still raises `ProviderNotConfiguredError` and `configure()` still raises `ProviderAlreadyConfiguredError`.

---

## 4. Input Validation Tests (The DAU Gauntlet)

### 4.1 `generate()` Message Validation

*   **T4.1.01 Empty Messages List**: `generate([])`. Expect `ValueError`.
*   **T4.1.02 None as Messages**: `generate(None)`. Expect `ValueError` or `TypeError`.
*   **T4.1.03 Missing Role Key**: `generate([{"content": "hello"}])`. Expect `ValueError`.
*   **T4.1.04 Missing Content Key**: `generate([{"role": "user"}])`. Expect `ValueError`.
*   **T4.1.05 Unknown Role**: `generate([{"role": "superadmin", "content": "hi"}])`. Expect `ValueError`.
*   **T4.1.06 Non-String Role**: `generate([{"role": 42, "content": "hi"}])`. Expect `ValueError`.
*   **T4.1.07 Non-String Content**: `generate([{"role": "user", "content": 42}])`. Expect `ValueError`.
*   **T4.1.08 None Content**: `generate([{"role": "user", "content": None}])`. Expect `ValueError`.
*   **T4.1.09 Extra Keys Tolerated**: `generate([{"role": "user", "content": "hi", "name": "bob"}])`. Should NOT raise — extra keys are ignored per standard LLM API conventions.
*   **T4.1.10 All Valid Roles**: Test `"system"`, `"user"`, `"assistant"` individually. All must succeed.
*   **T4.1.11 System-Only Messages**: `generate([{"role": "system", "content": "you are helpful"}])`. Valid per spec — no restriction on role ordering.
*   **T4.1.12 Empty String Content**: `generate([{"role": "user", "content": ""}])`. Adapters SHOULD reject with `ValueError` (RECOMMENDED, not mandatory). Most providers reject empty content, so this is a defensive measure (spec §3 generate() input validation).
*   **T4.1.13 Massive Message Count**: 10,000 messages. Expect either success or `LLMGenerationError` (context overflow), NOT a crash.
*   **T4.1.14 Unicode/Emoji Content**: `generate([{"role": "user", "content": "🔥🚀 café résumé 日本語"}])`. Expect success — UTF-8 is required by spec.
*   **T4.1.15 Null Bytes in Content**: `generate([{"role": "user", "content": "hello\x00world"}])`. Adapters SHOULD strip or reject null bytes (RECOMMENDED, not mandatory). Null bytes can cause truncation in C-based SDKs (spec §3 generate() input validation).
*   **T4.1.16 Messages is a Dict Not a List**: `generate({"role": "user", "content": "hi"})`. Expect `TypeError` or `ValueError`.
*   **T4.1.17 Messages Contains Non-Dict Item**: `generate(["hello"])`. Expect `ValueError`.
*   **T4.1.18 Binary/Garbage Payload Handling**: `generate([{"role": "user", "content": b"\xde\xad\xbe\xef\x00\x01\x02"}])`. Pass raw bytes or massive noise. Expect `TypeError` or `ValueError` catching bad types, or `LLMGenerationError` if provider kicks it back.
*   **T4.1.19 Gigantic Single Message (10MB)**: `generate([{"role": "user", "content": "x" * 10_000_000}])`. Expect either `LLMGenerationError` (context overflow) or a clean memory-related error. MUST NOT cause an unhandled OOM crash.
*   **T4.1.20 Invalid Kwarg Type (temperature)**: `generate([...], temperature="hot")`. Expect `ValueError` or provider-level rejection — NOT an unhandled `TypeError`.
*   **T4.1.21 Invalid Kwarg Type (stop_sequences)**: `generate([...], stop_sequences="stop")`. Expect `ValueError` or provider-level `TypeError` — NOT a crash.
*   **T4.1.22 Unknown Kwargs Pass-Through**: `generate([...], unknown_param=42)`. Expect unknown kwargs are silently passed through to the provider SDK. MUST NOT raise on the adapter side (spec §3 Kwargs Pass-Through).
*   **T4.1.23 Max Tokens Zero**: `generate([...], max_tokens=0)`. Expect either success or a clean error. If the provider returns empty, expect `LLMGenerationError` (since empty returns are forbidden by spec).
*   **T4.1.24 Duplicate Messages Not Deduplicated**: `generate([{"role": "user", "content": "test"}, {"role": "user", "content": "test"}])`. Expect success. Verify both messages are sent to the SDK (inspect mock call args) — the adapter MUST NOT deduplicate or collapse identical messages.
*   **T4.1.25 Negative Temperature**: `generate([...], temperature=-1)`. Expect `ValueError` or clean provider rejection — NOT an unhandled error.
*   **T4.1.26 Absurd Temperature**: `generate([...], temperature=999)`. Expect `ValueError` or clean provider rejection — NOT a silent clamp.

### 4.2 `embed()` Input Validation

*   **T4.2.01 Empty List**: `embed([])`. Expect `[]` returned, no API call.
*   **T4.2.02 None Input**: `embed(None)`. Expect `TypeError` or `ValueError`.
*   **T4.2.03 Single Text**: `embed(["hello"])`. Expect list with one vector.
*   **T4.2.04 Non-String Items**: `embed([42, None])`. Expect `ValueError` or `TypeError`.
*   **T4.2.05 Empty String Item**: `embed([""])`. Adapters SHOULD reject with `ValueError` (RECOMMENDED, consistent with generate() empty content policy).
*   **T4.2.06 Oversized Batch**: Exceed provider's batch limit. Expect `ValueError` with the limit in the message (per spec).
*   **T4.2.07 Not-Supported Provider**: Anthropic `embed()`. Expect `NotImplementedError`.
*   **T4.2.08 Result Dimension Consistency**: `embed(["hello", "world"])`. Expect both vectors to have the same length.
*   **T4.2.09 Unicode/CJK Text**: `embed(["日本語テスト"])`. Expect valid vector, not crash.
*   **T4.2.10 Duplicate Texts**: `embed(["hello", "hello"])`. Expect `len(result) == 2` and both vectors identical (or near-identical). Verify the adapter does NOT deduplicate and return only one vector — the output list length MUST match the input list length.
*   **T4.2.11 Cross-Call Dimension Consistency**: Two sequential `embed()` calls on the same adapter with different texts. Expect the embedding dimension is consistent across calls.
*   **T4.2.12 Inconsistent Dimensions Within Batch**: Mock a buggy provider that returns vectors with inconsistent dimensions within a single batch. Expect `LLMGenerationError` or at minimum a logged `WARNING` — NOT silent corruption.
*   **T4.2.13 Embedding Dimensions Property (Int)**: Adapter exposes `embedding_dimensions` property returning `int`. Call `embed(["hello"])`. Expect returned vector length matches `embedding_dimensions`. Cross-validates spec §4.8.
*   **T4.2.14 Embedding Dimensions Property (None)**: Adapter's `embedding_dimensions` returns `None` (cannot determine statically). Call `embed(["hello"])`. Expect success — caller must infer dimension from result.
*   **T4.2.15 Large Batch No OOM**: `embed()` with 1000 texts, each 10KB (~10MB total input). Expect success or clean `ValueError` (oversized batch). MUST NOT cause an unhandled OOM crash.

### 4.3 `count_tokens()` Input Validation

*   **T4.3.01 Non-String Input (Int)**: `count_tokens(42)`. Expect `TypeError`.
*   **T4.3.02 Non-String Input (None)**: `count_tokens(None)`. Expect `TypeError`.
*   **T4.3.03 Non-String Input (List)**: `count_tokens(["hello"])`. Expect `TypeError`.
*   **T4.3.04 Empty String**: `count_tokens("")`. Expect `0`.
*   **T4.3.05 Known Token Count**: `count_tokens("hello world")`. Expect integer > 0.
*   **T4.3.06 CJK/Emoji Heavy Text**: `count_tokens("😀" * 100)`. Expect reasonable count (not `chars/4` = 25, which is wrong for multi-byte chars).
*   **T4.3.07 Massive String (1MB)**: Expect success without OOM. No max input size per spec.
*   **T4.3.08 Approximation Accuracy**: If using fallback (chars/4), verify off-by-less-than-50% for English text. **Log a WARNING per spec.**

---

## 5. Factory Tests (`LLMFactory`)

### 5.1 Basic Factory Operations

*   **T5.1.01 Create Valid Profile**: `factory.create("default")`. Expect configured `LLMProvider` instance.
*   **T5.1.02 Create Returns Cached Instance**: Call `factory.create("default")` twice. Expect same object (`id(a) == id(b)`).
*   **T5.1.03 Create Different Profiles**: `factory.create("default")` and `factory.create("coding_expert")`. Expect different objects.
*   **T5.1.04 Unknown Profile Name**: `factory.create("nonexistent_profile")`. Expect `ProfileNotFoundError` with the profile name in the message and a suggestion to check `flow_config.json`.
*   **T5.1.05 Unknown Provider Name**: Profile exists but `provider: "chatgpt_plus"` is not in registry. Expect `ProviderRegistrationError` or similar.
*   **T5.1.06 Provider Name Mismatch**: Adapter's `provider_name` property returns `"goog"` but registry key is `"gemini"`. Expect `ProviderRegistrationError` per §5.1 #3.
*   **T5.1.07 Profile Missing `provider` Key**: Profile exists in config but has no `provider` field. Expect `ProviderConfigError` with clear message during `create()`.
*   **T5.1.08 Profile Missing `config` Sub-Key**: Profile exists with `provider` but no `config` section (no model, no temperature). Expect `ProviderConfigError` during `configure()`.
*   **T5.1.09 Profile With Empty String Provider**: Profile has `provider: ""`. Expect `ProviderRegistrationError` or `ProviderConfigError` — NOT a silent `KeyError` from the registry.
*   **T5.1.10 Profile Name Case Sensitivity**: Config has profile `"default"`. Call `factory.create("Default")`. Expect `ProfileNotFoundError` — profile names are case-sensitive. Document this behavior explicitly.
*   **T5.1.11 Unicode Profile Name**: Config has profile `"日本語_profile"`. Call `factory.create("日本語_profile")`. Expect success — the Factory should handle Unicode keys in the config dict.
*   **T5.1.12 Per-Profile Close (Class Diagram Verification)**: The class diagram (spec §2) shows `close(profile_name: str)` on `LLMFactory`. If this method exists, test full lifecycle: `create() → close("default") → create("default")` returns a new instance. If it does NOT exist, this test documents the discrepancy and the diagram must be corrected.

### 5.2 Reset & Invalidation

*   **T5.2.01 Reset Single Profile**: `factory.create("default")` → `factory.reset("default")` → `factory.create("default")`. Expect a NEW instance (different `id()`). Expect `close()` was called on the evicted instance.
*   **T5.2.02 Reset All**: Create multiple profiles → `factory.reset_all()`. Expect all caches cleared. Expect `close()` called on each.
*   **T5.2.03 Reset Uncreated Profile**: `factory.reset("never_created")`. Expect **silent no-op** — no error raised. This is the definitive behavior per spec §5.2.
*   **T5.2.04 Use After Reset**: Get instance via `create()`, call `reset()`, use old reference: `old_ref.generate(...)`. Expect `ProviderNotConfiguredError` since `close()` was called on it.
*   **T5.2.05 Reset During Active Call**: **(The DAU Danger)** Thread A is mid-`generate()`. Thread B calls `factory.reset("default")`. **Recommended behavior: Thread A gets `ProviderNotConfiguredError` because `close()` sets an internal `_closed` flag checked by in-flight operations. At minimum, expect no crash and no deadlock.** Document actual behavior.
*   **T5.2.06 Manual Close Bypasses Factory Cache**: `adapter = factory.create("default")`. User directly calls `adapter.close()` (bypassing Factory). Then `factory.create("default")` returns the cached instance — which is now dead (closed). Expect `ProviderNotConfiguredError` on `generate()`. **This is a cache staleness trap.** Document whether the Factory detects this or returns the dead instance.
*   **T5.2.07 Rapid Create-Reset Loop (Memory Leak Check)**: Loop 1000 times: `factory.create("default") → factory.reset("default")`. Verify no memory leak — adapter objects must be garbage collected. Measure process memory before/after.
*   **T5.2.08 Reset All After Close All**: `factory.close_all()` → `factory.reset_all()`. Expect `FactoryClosedError` — consistent with T5.3.03 for single-profile `reset()`.

### 5.3 Graceful Shutdown

*   **T5.3.01 Close All**: `factory.close_all()`. Expect `close()` called on every cached adapter. Factory is marked as **shut down**.
*   **T5.3.02 Create After Close All**: `factory.close_all()` → `factory.create("default")`. Expect `FactoryClosedError`. The Factory refuses to return dead instances. To resume, the Engine must instantiate a new `LLMFactory` (spec §5.2 Graceful Shutdown).
*   **T5.3.03 Reset After Close All**: `factory.close_all()` → `factory.reset("default")`. Expect `FactoryClosedError`. No operations on a shut-down Factory.
*   **T5.3.04 Close All During Active Generate**: Thread A is mid-`generate()` on a cached adapter. Thread B calls `factory.close_all()`. Expect at minimum no crash and no deadlock. Document whether Thread A's call completes, gets `ProviderNotConfiguredError`, or gets `TimeoutError`. This is distinct from T8.03 (single adapter `close()`) — this tests factory-level shutdown during active work across potentially multiple adapters.
*   **T5.3.05 New Factory After Close All**: Engine calls `factory.close_all()`. Engine creates a new `LLMFactory()` instance. New `factory.create("default")` succeeds. Verify the old Factory's closed state does not leak into the new one — no global/class-level state contamination.
*   **T5.3.06 Close All Per-Adapter Timeout Independence**: Factory has 3 cached adapters (A, B, C). Mock adapter B's `close()` to hang forever. `close_all()` completes within ≤6s (5s hard timeout per spec §5.2 + margin). Verify adapter A and C are confirmed closed. Adapter B is abandoned after timeout.
*   **T5.3.07 Two Factory Instances No Shared State**: Create two independent `LLMFactory` instances pointing at the same config. `factory1.create("default")` and `factory2.create("default")`. Verify they return independent adapter instances (different `id()`). `factory1.close_all()` does NOT affect `factory2`'s cached adapters.

### 5.4 Thread Safety

*   **T5.4.01 Concurrent Create Same Profile**: 10 threads simultaneously call `factory.create("default")`. Expect all threads get the same instance. `configure()` was called exactly once.
*   **T5.4.02 Concurrent Create Different Profiles**: 5 threads create 5 different profiles simultaneously. Expect 5 distinct instances, no deadlock.
*   **T5.4.03 Concurrent Create and Reset**: One thread creates, another resets the same profile in a loop. Expect no crash, no deadlock, no corruption.

### 5.5 Dependency Isolation

*   **T5.5.01 Missing SDK Lazy Error**: Provider SDK not installed. `factory.create("coding_expert")` (Anthropic). Expect `MissingDependencyError` with `"pip install"` instructions. Expect the error occurs at `create()` time (during `configure()` → `import`), NOT at Factory initialization.
*   **T5.5.02 Core Does Not Import SDK**: Verify that `from src.flow.llm.factory import LLMFactory` does NOT trigger import of `google`, `openai`, `anthropic`, or `ollama` modules. **This is a static analysis test.**

---

## 6. Authentication & Credential Tests

### 6.1 Environment Variable Resolution

*   **T6.1.01 API Key From Env**: Set `OPENAI_API_KEY` in env. `configure()` with `method: api_key`. Expect success.
*   **T6.1.02 Missing Env Var**: Unset `OPENAI_API_KEY`. `configure()` with `method: api_key, api_key_env: OPENAI_API_KEY`. Expect `LLMAuthError` with actionable message.
*   **T6.1.03 Empty Env Var**: Set `OPENAI_API_KEY=""`. Expect `LLMAuthError` — empty string is NOT a valid key.
*   **T6.1.04 Whitespace-Only Env Var**: Set `OPENAI_API_KEY="   "`. Expect `LLMAuthError`.
*   **T6.1.05 Env Var With Trailing Newline**: Set `OPENAI_API_KEY="sk-abc123\n"`. Expect adapter to strip whitespace or reject.
*   **T6.1.06 Cross-Provider Credential Mismatch**: Set `AZURE_OPENAI_API_KEY` to an Anthropic API Key or an Ollama host URL. Call Azure `configure()`. Ensure provider's HTTP 400/401 format is cleanly mapped to `LLMAuthError` without cryptic `JSONDecodeError`s.
*   **T6.1.07 Non-Breaking Space in API Key**: Set `OPENAI_API_KEY="sk-abc123\u00A0"` (trailing Non-Breaking Space from Outlook copy-paste). Expect adapter to sanitize it and auth succeeds.
*   **T6.1.08 Windows CRLF in API Key**: Set `OPENAI_API_KEY="sk-abc123\r\n"` (Windows line ending from notepad copy-paste). Expect adapter to sanitize it and auth succeeds.
*   **T6.1.09 Tab and Em-Space in API Key**: Set `OPENAI_API_KEY="\tsk-abc123\u2003"` (leading tab, trailing Em Space). Expect adapter to sanitize it and auth succeeds.
*   **T6.1.10 Keyring Timeout Wall-Clock Verification**: Mock `keyring.get_password()` to block for 60s. Expect `configure()` fails with `LLMAuthError` within **3.5s** (3s hard timeout per spec §4.6.4 WARNING + margin). Measure wall-clock time to verify.

### 6.2 Keyring Resolution

*   **T6.2.01 Keyring Happy Path**: Mock keyring to return a valid key. `method: keyring`. Expect success.
*   **T6.2.02 Keyring Missing**: Keyring returns `None`. No env var set. Expect `LLMAuthError` with `"Run 'flow secret set'"` message.
*   **T6.2.03 Env Overrides Keyring**: Both env var and keyring set. Expect env var wins (per §4.6.4).
*   **T6.2.04 Keyring Package Not Installed**: `method: keyring` but `import keyring` fails. Expect `MissingDependencyError` with `"pip install keyring"`.
*   **T6.2.05 Keyring Fallback Silently Skipped**: `method: api_key`, keyring not installed. Env var works. Expect success — no error about missing keyring.

### 6.3 ADC (Application Default Credentials)

*   **T6.3.01 ADC Happy Path**: Mock Google SDK ADC resolution. `method: adc`. Expect `genai.Client()` called with no API key arg.
*   **T6.3.02 ADC Token Expired**: Mock SDK raises auth error. Expect `LLMAuthError` with `"Run 'gcloud auth application-default login'"` message.
*   **T6.3.03 ADC Skips Env/Keyring**: `method: adc`, `GOOGLE_API_KEY` is set in env. Expect ADC path taken (env var ignored per §4.4).
*   **T6.3.04 Vertex ADC With Project/Location**: `method: vertex_adc`, `project_id` and `location` in config. Expect `genai.Client(vertexai=True, ...)` called.
*   **T6.3.05 Vertex ADC Missing Project ID**: `method: vertex_adc`, no `project_id`. Expect `ProviderConfigError`.

### 6.4 Credential Security

*   **T6.4.01 API Key Not In Logs**: Inject a known API key. Log all log output during `configure()` and `generate()`. Grep for the key. Expect ZERO matches.
*   **T6.4.02 API Key Not In Exception Message**: Force `configure()` to fail after receiving the key. Inspect `str(exception)` and `exception.args`. Expect NO key substring.
*   **T6.4.03 API Key Not In AtomResult Exports**: After `generate()`, verify the key is not in any export dict, context, or serialized state.
*   **T6.4.04 Unknown Auth Method**: `method: "oauth2_custom"`. Expect `ProviderConfigError` with supported methods listed.

### 6.5 `none` Auth (Ollama)

*   **T6.5.01 No Auth Required**: `method: none`, `base_url: http://localhost:11434`. Expect no credential resolution attempted.
*   **T6.5.02 Ollama Not Running**: `method: none`, connection refused. Expect `LLMConnectionError` (not `LLMAuthError`).

---

## 7. Error Handling & Retry Tests

### 7.1 Error Classification

*   **T7.1.01 Network Error → LLMConnectionError**: Mock HTTP connection refused. Expect `LLMConnectionError`.
*   **T7.1.02 DNS Failure → LLMConnectionError**: Mock DNS resolution failure. Expect `LLMConnectionError`.
*   **T7.1.03 HTTP 401 → LLMAuthError**: Mock 401 response. Expect `LLMAuthError`.
*   **T7.1.04 HTTP 403 → LLMAuthError**: Mock 403 response. Expect `LLMAuthError`.
*   **T7.1.05 HTTP 429 → LLMRateLimitError**: Mock 429 response. Expect `LLMRateLimitError`.
*   **T7.1.06 HTTP 500 → LLMGenerationError**: Mock 500 response. Expect `LLMGenerationError`.
*   **T7.1.07 Safety Filter Block → LLMGenerationError**: Mock safety filter response. Expect `LLMGenerationError` with descriptive message — NOT `None` or empty string.
*   **T7.1.08 Model Not Found (404) → ProviderConfigError**: Mock model-not-found response. Expect `ProviderConfigError` (NOT `LLMConnectionError`). Message must include model name per spec.
*   **T7.1.09 Context Window Overflow → Non-Retryable LLMGenerationError**: Mock context-overflow error from provider. Expect `LLMGenerationError`. Verify it is NOT retried (see T7.2.06).
*   **T7.1.10 Empty Response → LLMGenerationError**: Provider returns empty string. Expect `LLMGenerationError` per spec ("NEVER returns None, empty string, or whitespace-only string").
*   **T7.1.11 Whitespace-Only Response → LLMGenerationError**: Provider returns `"   \n  "`. Expect `LLMGenerationError`.
*   **T7.1.12 None Response Text → LLMGenerationError**: Mock SDK returning `None` as the response text (common with Gemini safety-filtered responses where `response.text` is `None`). Expect `LLMGenerationError`, NOT `TypeError: cannot strip NoneType` (spec §3 Returns).
*   **T7.1.13 Malformed Response Object → LLMGenerationError**: Mock SDK returning a response object where the `.text` attribute does not exist or raises an `AttributeError`. Expect `LLMGenerationError` with descriptive message, NOT an unhandled `AttributeError`.
*   **T7.1.14 Unicode Provider Error Message**: Mock provider error response with Unicode message: `"限速 🚫: リクエストが多すぎます"`. Expect the mapped error (e.g., `LLMRateLimitError`) preserves the Unicode message without encoding crashes.
*   **T7.1.15 SDK Throws RuntimeError → LLMGenerationError**: Mock the SDK's `generate()` raising `RuntimeError("internal SDK bug")`. Expect `LLMGenerationError` wrapping it with a descriptive message — NOT a raw `RuntimeError` leaking to the Engine. Adapters MUST catch all non-standard SDK exceptions.
*   **T7.1.16 SDK Throws KeyError → LLMGenerationError**: Mock the SDK's `generate()` raising `KeyError("response")` (buggy response parsing). Expect `LLMGenerationError`, NOT an unhandled `KeyError` propagating to the Engine.
*   **T7.1.17 SDK Throws RecursionError → LLMGenerationError**: Mock the SDK raising `RecursionError`. Expect `LLMGenerationError`. This catches deeply nested JSON or protocol parsing bugs in SDKs.

### 7.2 Retry Behavior

*   **T7.2.01 Connection Error Retried 3x**: Mock 4 consecutive `LLMConnectionError` (1 initial + 3 retries = 4 total calls). Expect 3 retries with exponential backoff (1s, 2s, 4s). After the 3rd retry (4th total call) fails, original exception re-raised (spec §6.3: Max Retries = 3, Total Calls = 4).
*   **T7.2.02 Rate Limit Retried 3x**: Mock 3 consecutive 429. Expect 3 retries with longer backoff (5s, 15s, 30s).
*   **T7.2.03 Auth Error NOT Retried**: Mock `LLMAuthError`. Expect immediate failure, no retry.
*   **T7.2.04 Config Error NOT Retried**: Mock `ProviderConfigError` (model not found). Expect immediate failure.
*   **T7.2.05 Generation Error Retried Once**: Mock `LLMGenerationError` (non-overflow). Expect single retry (max 2 attempts).
*   **T7.2.06 Context Overflow NOT Retried**: Mock context-overflow `LLMGenerationError`. Expect immediate failure (no retry).
*   **T7.2.07 Timeout Retried**: Mock `TimeoutError` on first call, success on second. Expect retry with same timeout.
*   **T7.2.08 Retry Logging**: Verify each retry attempt is logged at `WARNING` level.
*   **T7.2.09 Retry-After Header**: Mock 429 with `Retry-After: 10` header. Expect adapter to wait ~10s before retry (not default backoff).
*   **T7.2.10 Transient Then Success**: First call raises `LLMConnectionError`, second succeeds. Expect final result is the success response.
*   **T7.2.11 Retry-Amplified Timeout Bound**: `generate(timeout_seconds=1)` with Tenacity connection error retries enabled (3 retries). Each attempt times out after 1s. Total wall-clock MUST be bounded: `4 × 1s + backoff delays (1+2+4=7s) = ~11s max`. Verify total does not exceed ~15s. If unbounded, this is a circuit-breaker gap.
*   **T7.2.12 Full Dual-Layer Retry Lifecycle**: End-to-end test proving adapter-level and engine-level retries are independent: (1) Adapter Tenacity retries 3× (all fail with `LLMConnectionError`) → exception raised. (2) `AgentAtom` catches, yields `AtomResult(RETRY, strategy=BACKOFF)`. (3) Engine persists `next_retry_at` timestamp to state DB. (4) Simulate crash + restart. (5) Engine waits until `next_retry_at` expires. (6) Atom re-dispatched. (7) Adapter Tenacity starts fresh (attempt 1, not attempt 4) → success on 2nd adapter attempt. Verify adapter retry count resets across engine-level retries.

### 7.3 Timeout Contract

*   **T7.3.01 Generate Respects Timeout**: `generate(..., timeout_seconds=2)`. Mock provider takes 5s. Expect `TimeoutError` at ~2s.
*   **T7.3.02 Embed Respects Timeout**: `embed(..., timeout_seconds=1)`. Mock provider takes 5s. Expect `TimeoutError`.
*   **T7.3.03 Default Timeout Generate**: No explicit timeout. Expect 120s default per spec.
*   **T7.3.04 Default Timeout Embed**: No explicit timeout. Expect 60s default per spec.
*   **T7.3.05 Zero Timeout**: `generate(..., timeout_seconds=0)`. Expect immediate `TimeoutError` or `ValueError`.
*   **T7.3.06 Negative Timeout**: `generate(..., timeout_seconds=-1)`. Expect `ValueError`.
*   **T7.3.07 Float Timeout**: `generate(..., timeout_seconds=0.5)`. Expect `TypeError` (spec says `int`) or truncation to `0` — document which behavior is chosen.
*   **T7.3.08 None Timeout**: `generate(..., timeout_seconds=None)`. Expect `TypeError` or fallback to default 120s — NOT an unhandled error deep in the SDK.
*   **T7.3.09 String Timeout**: `generate(..., timeout_seconds="ten")`. Expect `TypeError`.

---

## 8. Concurrency & Thread Safety Tests

*   **T8.01 5-Thread Concurrent Generate**: 5 threads call `generate()` on the same adapter simultaneously. Expect all return valid strings. No exceptions, no cross-thread data leaks.
*   **T8.02 Concurrent Generate and Embed**: Thread A calls `generate()`, Thread B calls `embed()` on same adapter. Expect both succeed independently.
*   **T8.03 Concurrent Generate and Close**: Thread A is mid-`generate()`. Thread B calls `close()`. Document behavior: does Thread A's call complete, fail, or hang? **At minimum, expect no crash.**
*   **T8.04 Concurrent Generate and CountTokens**: Thread A calls `generate()`, Thread B calls `count_tokens()`. Expect both succeed.
*   **T8.05 High Contention (50 threads)**: 50 threads simultaneously calling `generate()`. Expect no deadlock, no shared state corruption, no segfault.
*   **T8.06 Concurrent Factory Create**: 20 threads call `factory.create("default")` simultaneously (first use). Expect `configure()` called exactly once. All threads receive same instance.
*   **T8.07 Strong System Prompt Isolation**: Two threads using the identical cached `LLMProvider` instance call `generate()` concurrently with completely distinct System prompts and parameters. Assert both get outputs corresponding directly to their specific prompt, proving no state bleeds internally.
*   **T8.08 Concurrent Configure on Raw Adapter**: Two threads call `configure()` simultaneously on a raw adapter instance (bypassing Factory). Expect one succeeds, one gets `ProviderAlreadyConfiguredError`. No crash, no race condition leading to double-initialization of SDK clients.
*   **T8.09 Concurrent Embed (5 Threads)**: 5 threads call `embed(["text"])` on the same adapter simultaneously (the RAG batch indexing scenario). Expect all return valid vectors. No crash, no cross-thread data leaks.
*   **T8.10 Concurrent CountTokens (10 Threads)**: 10 threads call `count_tokens("hello world")` simultaneously on the same adapter. Some tokenizers (e.g., tiktoken) use global C-level state. Expect all return the same integer. No segfault, no race condition.

---

## 9. Adapter Contract Test Base Class

> Per spec §8.1, all adapters must be testable against a shared `AbstractProviderContractTest`.

### 9.1 Mandatory Contract Tests (from spec)

These are the ~15 tests the spec explicitly lists. Each adapter MUST pass all of them via a shared base class.

*   **CT-01** `test_generate_before_configure_raises`
*   **CT-02** `test_double_configure_raises`
*   **CT-03** `test_generate_empty_messages_raises`
*   **CT-04** `test_generate_invalid_role_raises`
*   **CT-05** `test_generate_missing_content_key_raises`
*   **CT-06** `test_embed_empty_list_returns_empty`
*   **CT-07** `test_count_tokens_non_string_raises`
*   **CT-08** `test_count_tokens_empty_string_returns_zero`
*   **CT-09** `test_provider_name_matches_registry`
*   **CT-10** `test_close_then_generate_raises`
*   **CT-11** `test_concurrent_generate_no_crash` (5-thread smoke test)

### 9.2 Additional Contract Tests (QA Extension)

*   **CT-12** `test_generate_returns_non_empty_string`: Verify result is a non-empty, non-whitespace string.
*   **CT-13** `test_embed_result_length_matches_input`: `len(embed(texts)) == len(texts)`.
*   **CT-14** `test_embed_vectors_same_dimension`: All vectors in a batch have identical length.
*   **CT-15** `test_close_idempotent`: Calling `close()` multiple times raises nothing.
*   **CT-16** `test_close_without_configure_is_noop`: Calling `close()` without `configure()` raises nothing.
*   **CT-17** `test_generate_missing_role_key_raises`: `[{"content": "hi"}]` → `ValueError`.
*   **CT-18** `test_generate_none_messages_raises`: `generate(None)` → error.
*   **CT-19** `test_timeout_respected`: `generate(..., timeout_seconds=1)` with slow mock → `TimeoutError`.
*   **CT-20** `test_configure_then_generate_then_close_then_generate_raises`: Full lifecycle.
*   **CT-21** `test_validate_override_avoids_generate`: Create an adapter that overrides `validate()` with a mock lightweight check (e.g., `models.list()`). Verify `generate()` was NOT called during `validate()`. Verify `validate()` returns `True`.
*   **CT-22** `test_validate_exception_returns_false`: Override `validate()` to raise an exception (e.g., network error). Verify it returns `False`, NOT an unhandled crash.
*   **CT-23** `test_unknown_kwargs_not_rejected`: `generate([valid_msg], my_custom_param=42)` MUST NOT raise on the adapter side. Unknown kwargs are passed through to the provider SDK.

---

## 10. Integration with Engine & Atoms

### 10.1 AgentAtom → LLMProvider Integration

*   **T10.1.01 AgentAtom Gets Provider Via Factory**: `AgentAtom.run()` calls `LLMFactory.create(profile_name)`. Verify the atom does NOT import any provider SDK directly.
*   **T10.1.02 AgentAtom Context Budget Check**: Before calling `generate()`, `AgentAtom` calls `count_tokens()` on the assembled messages. If over budget, expect a non-retryable `LLMGenerationError` WITHOUT making the API call (per §6.6).
*   **T10.1.03 AgentAtom Handles LLMAuthError**: Provider raises `LLMAuthError`. Expect `AgentAtom` to yield `AtomStatus.FAILED` with structured error — NOT crash the Engine.
*   **T10.1.04 AgentAtom Handles LLMRateLimitError**: After retries exhausted, `AgentAtom` surfaces the error to the Engine for flow-level retry decisions.
*   **T10.1.05 AgentAtom Uses Timeout**: Verify `AgentAtom` passes `timeout_seconds` to `generate()`.

### 10.2 KnowledgeService → LLMProvider Integration

*   **T10.2.01 RAG Uses Embedding Profile**: `KnowledgeService` uses a profile with embedding support. Verifying it calls `embed()` through the service, NOT directly.
*   **T10.2.02 RAG Startup Validates Embedding Support**: At startup, RAG checks that the configured profile supports `embed()`. If it uses Anthropic (no embeddings), expect early error.
*   **T10.2.03 RAG Handles NotImplementedError**: `embed()` raises `NotImplementedError`. RAG must handle gracefully (fallback or clear error).

---

## 11. Sub-Workflow, Break/Restart & Deep Resume

These tests validate the LLM Binding in the context of the Engine's break/restart lifecycle, sub-workflows, and crash recovery.

### 11.1 Crash Recovery

*   **T11.1.01 Engine Crash During Generate**: `AgentAtom` calls `generate()`. Engine receives `SIGKILL` while waiting for API response. On restart: expect the Engine to re-instantiate the Factory, re-create the provider via `create()`, and the `AgentAtom` to resume its ReAct loop from the last checkpoint — calling `generate()` again with restored context.
*   **T11.1.02 Factory Survives Engine Restart**: Engine restarts. Factory is a fresh instance. `create()` re-initializes providers from config. Expect no stale cached adapters from the dead process.
*   **T11.1.03 Credential Change Between Crash and Restart**: API key rotates while Engine is down. On restart, `configure()` uses the new env var. Expect success with new key.
*   **T11.1.04 Duplicate Request on Crash Recovery (Idempotency Tax)**: Simulate a flow resuming and making the EXACT identical API call that succeeded immediately before a crash. Verify adapter handles repeating the request statelessly without corrupting the factory connection pool.

### 11.2 Sub-Workflow LLM Context

*   **T11.2.01 Parent and Child Use Different Profiles**: Parent flow uses `"reasoning"` profile. Child sub-workflow uses `"coding_expert"` profile. Expect both providers are independently cached in the Factory.
*   **T11.2.02 Child Sub-Workflow Provider Failure**: Child's `generate()` hits `LLMConnectionError` after retries. Expect child flow → `FAILED`. Parent flow handles child failure per its flow definition. Parent's own provider is unaffected.
*   **T11.2.03 Deep Resume Rehydrates Provider**: L1 → L2 → L3 sub-workflow chain. Crash at L3 during `generate()`. On restart, Engine walks down to L3, Factory re-creates the L3 profile's provider, L3 `AgentAtom` resumes. Expect no stale handles from pre-crash.
*   **T11.2.04 Sub-Workflow Connection Pool Starvation**: Child spawns 100 concurrent parallel fan-out generation requests. Ensure the underling SDK connection pools (e.g. `httpx.Client`) gracefully enforce limits or queue without triggering `TimeoutError` in the unrelated concurrently running parent workflow sharing the same LLM profile.
*   **T11.2.05 Parent and Child Use Same Profile**: Parent flow and child sub-workflow both use profile `"default"` (the most common case). Since the Factory uses singleton caching, they share the same adapter instance. If the child's `generate()` triggers `LLMRateLimitError`, verify that the parent's in-flight or subsequent request behavior is documented. At minimum, the shared adapter MUST NOT corrupt. Rate limit affects are expected due to shared connection pool — document this explicitly.
*   **T11.2.06 Error Blast Radius Isolation Between Profiles**: Sub-workflow at L3 uses profile `"coding_expert"` (Anthropic). That profile hits `LLMAuthError` (key expired). L3 flow fails. Parent L2 flow catches child failure. Parent L2 then calls `generate()` on its own profile `"reasoning"` (OpenAI). Verify profile `"reasoning"` is **completely unaffected** by `"coding_expert"`'s auth failure — Factory cache isolation between profiles.
*   **T11.2.07 Stale Model After Long Pause**: Flow is paused at approval gate for 7 days. During pause, the LLM provider deprecates the model (returns 404 on next `generate()`). On resume, expect `ProviderConfigError` (NOT `LLMConnectionError`). Engine should mark the atom as `FAILED` and NOT retry the deprecated model infinitely.
*   **T11.2.08 Circular Sub-Workflow Defense**: Flow A references Sub-Flow B, which references Sub-Flow A (circular). Verify the Engine detects the cycle (01_03 §3.4.2) and that the LLM Factory does NOT end up in an infinite `create()` loop. Expect cycle detection error before any LLM calls are made.

### 11.3 Break/Restart Edge Cases

*   **T11.3.01 Pause During Rate Limit Backoff**: `AgentAtom` is waiting for rate limit backoff (15s sleep). Engine receives `SIGTERM`. On restart, expect the atom does NOT immediately retry (honoring the backoff timer stored in state DB per 01_05 §2 `RetryStrategy.BACKOFF`). **Clarification (Two Backoff Layers)**: There are two distinct backoff mechanisms: (1) **Adapter-level** (Tenacity decorator, spec §6.3) — in-memory only, lost on crash, handles transient retries within a single `generate()` invocation; (2) **Engine-level** (01_05 §2 `RetryStrategy.BACKOFF`) — persisted to state DB, survives crash, handles flow-level retry decisions. This test validates the **Engine-level** backoff. The adapter-level Tenacity state is lost on crash (acceptable — retries restart from attempt 1).
*   **T11.3.02 Config Change During Pause**: Flow is paused (`WAITING_FOR_APPROVAL`). Operator changes `flow_config.json` to switch from Gemini to OpenAI for the `"default"` profile. Flow resumes. **Expect the old provider is still used for this flow run** — config changes require an explicit `reset()` or engine restart per §5.2.
*   **T11.3.03 Provider SDK Uninstalled During Pause**: Flow is paused. Someone runs `pip uninstall anthropic`. Flow resumes, tries to create the Anthropic provider. Expect `MissingDependencyError`.

---

## 12. Graceful Teardown & Shutdown

*   **T12.01 SIGTERM Triggers close_all**: Engine receives `SIGTERM`. Expect `factory.close_all()` is called as part of the teardown sequence.
*   **T12.02 Close Releases HTTP Pools**: Mock an adapter with `httpx.Client`. After `close()`, verify `client.close()` was called.
*   **T12.03 Close Does Not Block Shutdown**: `close()` has a 2s timeout internally. If the HTTP pool close hangs, expect abandonment after timeout — SIGTERM must not be held up by a hung provider.
*   **T12.04 Multiple SIGTERM Signals**: Engine receives 3 rapid `SIGTERM` signals. Expect `close_all()` called exactly once (latch behavior per 01_05 T8.07).
*   **T12.05 SIGINT (Ctrl+C) Triggers Same Path**: `SIGINT` triggers the same `close_all()` shutdown path as `SIGTERM`.

---

## 13. Observability & Logging

*   **T13.01 Generate Logs Profile and Model**: After `generate()`, verify log entry contains `profile_name`, `model`, and `latency_ms`.
*   **T13.02 Generate Logs Token Counts**: If provider response includes token usage, verify `prompt_tokens` and `completion_tokens` in log.
*   **T13.03 Retry Logs at WARNING**: On retry, verify `WARNING` level log emitted with error type and attempt number.
*   **T13.04 Final Failure Logs at ERROR**: After retries exhausted, verify `ERROR` level log.
*   **T13.05 No Secrets in Logs**: Full integration test: set API key, exercise generate/embed/validate, collect all log output, grep for key. Expect ZERO matches.

---

## 14. Configuration Edge Cases

*   **T14.01 Missing `model` in Config**: Profile has no `model` key. Expect `ProviderConfigError` during `configure()`.
*   **T14.02 Empty Config Dict**: `configure({})`. Expect `ProviderConfigError`.
*   **T14.03 Extra Unknown Keys**: Config has `{"model": "gpt-4o", "unicorn": true}`. Expect unknown keys are ignored — no crash.
*   **T14.04 Azure Missing `deployment_name`**: Azure OpenAI profile missing `deployment_name`. Expect `ProviderConfigError`.
*   **T14.05 Azure Missing `endpoint`**: Azure OpenAI profile missing `endpoint`. Expect `ProviderConfigError`.
*   **T14.06 Ollama Invalid Base URL**: `base_url: "not-a-url"`. Expect `ProviderConfigError` or `LLMConnectionError` on first use.
*   **T14.07 Profile With No `auth` Block**: Profile exists but has no `auth` section. Expect a `WARNING` log (`"No auth method specified, defaulting to 'api_key'"`) and default to `method: api_key` using the provider's conventional env var. Verify the warning IS emitted (spec §4.1 NOTE).
*   **T14.08 Massive Max Tokens Configuration**: `max_tokens: 9999999`. Verify the adapter gracefully passes the provider's HTTP 400 bad request logic back as a `ProviderConfigError` or truncates it to the model limit, rather than crashing internally.
*   **T14.09 Token Count After Provider Deprecation**: Configure adapter with a valid model. Model is subsequently deprecated at the provider. `count_tokens("hello")` succeeds (uses local tokenizer). `generate()` raises `ProviderConfigError`. Verify this asymmetric behavior is expected and documented — local tokenization does NOT depend on provider availability.
*   **T14.10 Empty Model Name**: Profile has `model: ""` (empty string). Expect `ProviderConfigError` during `configure()` — NOT a silent fallback to some default model.
*   **T14.11 Config JSON Trailing Comma**: `flow_config.json` has a trailing comma (common DAU edit error like `{"model": "gpt-4o",}`). Expect a clear JSON parse error at config load time, NOT a cryptic error deep in the LLM stack.
*   **T14.12 Negative Temperature in Config**: Profile config has `temperature: -1`. Expect `ProviderConfigError` or clean SDK rejection during `configure()` or first `generate()` call.
*   **T14.13 Absurd Temperature in Config**: Profile config has `temperature: 999`. Expect `ProviderConfigError` or clean SDK rejection — NOT a silent clamp to a valid range.

---

## 15. Capability Matrix Edge Cases

*   **T15.01 Anthropic Embed Raises NotImplementedError**: Call `embed()` on Anthropic adapter. Expect `NotImplementedError`.
*   **T15.02 Ollama Token Count Is Approximation**: Call `count_tokens()` on Ollama adapter. Expect a positive integer. Verify a `WARNING` log about approximation.
*   **T15.03 Provider Capability Check at Startup**: RAG system at startup calls `embed()` and catches `NotImplementedError`. If caught, logs error and refuses to start indexing (rather than crashing mid-index).

---

## 16. Startup & Cold Boot Tests

> [!IMPORTANT]
> These tests cover what happens when the Engine boots for the very first time, or after a crash.

*   **T16.01 No Config File**: `flow_config.json` is missing entirely. Expect clear error at engine startup, not a `KeyError` deep in the LLM stack.
*   **T16.02 Malformed Config JSON**: `flow_config.json` has invalid JSON. Expect parse error, not crash.
*   **T16.03 Config Has No `knowledge.profiles`**: Config exists but has no `knowledge` or `profiles` section. Expect clear error when any component tries to create an LLM profile.
*   **T16.04 All Providers Lazy**: On startup, NO provider SDK is imported, NO `configure()` is called, NO network calls are made. Everything is deferred to first use.
*   **T16.05 First Generate Is Slow (Cold Start)**: First `generate()` call triggers `import`, `configure()`, and API call. Measure latency. Verify it is bounded and does not cause engine timeout.
*   **T16.06 Multiple Profiles Same Provider**: Two profiles both use `"gemini"` but different models. Expect two separate adapter instances cached under their respective profile names.

---

## 17. Future Proposals (Not For V1 Implementation)

> [!NOTE]
> The following are explicitly marked as **FUTURE** proposals. They should NOT be implemented now but should inform V2 design.

*   **P17.01 Streaming Generate**: `generate_stream()` returning `Iterator[str]`. Required for real-time agent output display.
*   **P17.02 Fallback Profiles**: If primary provider fails after all retries, auto-switch to a configured fallback profile. Requires careful error semantic design.
*   **P17.03 Cross-Branch Rate Limiter**: Centralized token bucket shared across parallel fan-out branches using the same provider.
*   **P17.04 Provider Health Dashboard**: `flow status llm` command showing health, latency percentiles, and error rates per profile.
*   **P17.05 Context Window Size Exposure**: Add `get_context_window_size()` to `LLMProvider` so callers don't need hardcoded model metadata.
*   **P17.06 Adapter Hot-Reload**: Allow `flow_config.json` changes to take effect without engine restart (watch file, diff, auto-reset affected profiles).
*   **P17.07 Embedding Dimension Declaration**: Add `get_embedding_dimensions()` to `LLMProvider` for callers to validate dimension compatibility at startup rather than at insertion time.
*   **P17.08 [PROPOSAL] Engine-Level Prompt Caching**: To prevent burning tokens and rate limits during the "Idempotency Tax" scenario, implement an MD5 cache of `(prompt + config) -> response` with a short TTL (e.g., 5 mins) across the workflow engine.
*   **P17.09 [PROPOSAL] Connection Pool Sizing Configuration**: Expose `max_connections` in `flow_config.json` per profile to explicitly manage concurrent API limits during massive fan-out executions without starving the system.
*   **P17.10 [PROPOSAL] Startup Health Report (`factory.health_report()`)**: A `flow health-check llm` CLI command that iterates over all configured profiles, calls `validate()` on each, and reports success/failure. Reduces "first-use surprise" failures from lazy initialization. Not V1 — lazy init is correct for V1 to avoid burning tokens on startup.
*   **P17.11 [PROPOSAL] Rate Limit Coordination Across Profiles Sharing a Provider**: If profiles `"fast"` and `"coding"` both use `provider: "openai"` with the same API key, they share quota. V1 treats them independently. V2 should introduce a per-provider-key rate limiter.
*   **P17.12 [PROPOSAL] Token Cost Tracking**: Aggregate `prompt_tokens` and `completion_tokens` from adapter logs into a `flow usage report` command showing total tokens consumed per profile per workflow run. Essential for cost management.
*   **P17.13 [PROPOSAL] `generate()` Response Metadata**: V1 returns `str`. V2 should return a `GenerateResult` object containing response text + metadata: `finish_reason`, `usage`, `model_version`, `latency_ms`. Avoids losing information the SDK provides.

---

## 18. Resolved Spec Gaps

The following gaps were identified during the initial audit and have been **resolved** in the spec (01_06_llm_binding_spec.md). This table serves as a cross-reference.

| ID | Gap | Resolution | Spec Section |
|:---|:---|:---|:---|
| **GAP-01** | `count_tokens()` requires `configure()` | ✅ Yes — even local tokenizers need configure() to know which model | §3 Lifecycle #4 |
| **GAP-02** | Adapter dead after `close()` | ✅ Permanently dead. `configure()` after `close()` → `ProviderAlreadyConfiguredError` | §3 Lifecycle #7 |
| **GAP-03** | Failed `configure()` poisons adapter | ✅ Adapter is unusable. Must discard via `Factory.reset()` + `create()` | §3 Lifecycle #5 |
| **GAP-04** | Unknown profile → `ProfileNotFoundError` | ✅ Clear error with profile name | §5.1 |
| **GAP-05** | `create()` after `close_all()` → `FactoryClosedError` | ✅ Factory marks itself as shut down, prevents dead instances | §5.2 |
| **GAP-06** | Empty string content → RECOMMENDED reject | ✅ SHOULD raise ValueError (not mandatory) | §3 generate() validation |
| **GAP-07** | Null bytes → RECOMMENDED reject | ✅ SHOULD strip or reject (not mandatory) | §3 generate() validation |
| **GAP-08** | Missing `auth` block → WARNING + default `api_key` | ✅ Log warning, default to provider convention env var | §4.1 NOTE |
| **GAP-09** | Embedding dimension declaration | ✅ SHOULD expose `embedding_dimensions` property | §4.8 |
| **GAP-10** | Credential leakage via exceptions | ✅ **Explicitly forbidden** — treated as security bug | §4.7 |
| **GAP-11** | `configure()` partial failure leaks SDK resources | ✅ Adapter MUST clean up partially-initialized SDK resources in exception handler. `close()` MUST handle poisoned adapters. | §3 Lifecycle #5a |
| **GAP-12** | `reset()` on uncreated profile — undefined behavior | ✅ Silent no-op. MUST NOT raise. | §5.2 |
| **GAP-13** | Retry table ambiguous ("Max Attempts") | ✅ Clarified with "Max Retries" + "Total Calls" columns | §6.3 |
| **GAP-14** | `generate()` returns None from SDK (safety filter) | ✅ Adapters MUST guard against None SDK response. Raise `LLMGenerationError`. | §3 Returns |
| **GAP-15** | Unknown kwargs rejected by adapter | ✅ Unknown kwargs SHOULD be silently passed through to provider SDK | §3 Kwargs Pass-Through |

---

## 19. Hostile Environments & DAU Traps

These tests validate resilience against exceptionally hostile environments, proxies, and DAU (Dumbest Available User) actions.

### 19.1 Unforgiving DAU Contexts
*   **T19.1.01 ZWSP API Key Trap**: Mock config key containing `\u200B` (Zero-Width Space) and `\xEF\xBB\xBF` (BOM) from bad copy-paste. Verify the adapter sanitizes it before the SDK call and authentication succeeds.
*   **T19.1.02 Corporate Proxy / MITM DPI**: Mock an SDK HTTP client raising `[SSL: CERTIFICATE_VERIFY_FAILED]`. Expect `LLMConnectionError` with a hint about cert bounds, not an unhandled SSL crash.
*   **T19.1.03 The 000 Config Trap**: Change `flow_config.json` permissions to `000`. Expect a clean `PermissionError` message during initialization instead of a parser crash.
*   **T19.1.04 Cloudflare Middlebox HTML**: Mock a 502 Bad Gateway response returning `text/html`. Verify the adapter intercepts `json.decoder.JSONDecodeError` and throws a clean `LLMConnectionError`.

### 19.2 Threading & Resource Exhaustion
*   **T19.2.01 Thread Pool Exhaustion (The Fan-Out Bomb)**: Simulate 1000 concurrent agents calling `generate()` using an adapter relying on `ThreadPoolExecutor` for timeouts. Verify it does not crash with `RuntimeError: can't start new thread` due to capping the executor pool.
*   **T19.2.02 File Descriptor Leak**: Execute an `LLMConnectionError` via SDK 10,000 times sequentially. Verify `lsof` (or process FD count) remains stable, ensuring HTTP connections/sockets are properly closed on failure.

---

## 20. Deep Lifecycle & State Resumability Edge Cases

These tests validate absolute correctness when navigating complex hierarchical breaks, restarts, and crashes.

### 20.1 Teardown & Exceptional Exits
*   **T20.1.01 Headless Keyring Lockout**: Mock the `keyring` library to block indefinitely during `get_password`. Verify the 3-second hard timeout fires and raises `LLMAuthError` describing the locked GUI environment.
*   **T20.1.02 SIGTERM Zombie Locks**: Mock an HTTP socket to wait infinitely during `adapter.close()`. Verify `factory.close_all()` abandons the frozen connection after the 5-second hard timeout rather than becoming an unkillable zombie.

### 20.2 Sub-Workflows & Resumability State (Break/Restart)
*   **T20.2.01 Dynamic Kwarg Amnesia**: Parent workflow injects `stop_sequences=["```"]` to a child agent. `SIGKILL` the process mid-call. Resume Engine. Verify `stop_sequences` is perfectly rehydrated in the repeated API call from `.flow_state/` JSON logic.
*   **T20.2.02 Context Bloat on Deep Resume**: Simulate an L3 workflow crashing loop 50. Verify the state reconstruction strictly measures token limits (`count_tokens()`) and avoids inheriting runaway context overflow from concatenated failures.
*   **T20.2.03 The Idempotency Tax**: Re-run the exact `generate()` API call from a simulated Engine crash recovery step. Verify the adapter behaves gracefully despite redundant state.
*   **T20.2.04 Markdown RAG Poisoning**: LLM responds with 10,000 nested markdown blockquotes causing the context tree parser to exhaust depth recursion limits. Verify the `LLMProvider` or its consumer catches deep text parsing limits cleanly to prevent silent downstream state corruption.

### 20.3 Response Size & Cross-Spec Boundary
*   **T20.3.01 10MB Generate Response vs 128KB Exports Limit**: `generate()` returns a valid 10MB response string. The adapter returns it successfully. Verify that `AgentAtom` (01_05 §2) correctly routes this to a blob file (`.flow/artifacts/blob_*.txt`) rather than putting it into `AtomResult.exports` — the LLM layer MUST NOT enforce the 128KB limit, but the consumer must handle it. Document the boundary.
*   **T20.3.02 Embed Timeout Scope**: `embed(texts, timeout_seconds=5)` where `texts` has 100 items. If the adapter internally chunks the batch (not V1, but defense-in-depth), verify the timeout applies to the **total** call, NOT per-chunk. Each chunk taking 3s would pass a per-chunk timeout but fail a total timeout.

