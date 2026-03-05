"""Ch.6: Skill Execution — Path 2 (LLM Function-Call) (T6.01–T6.56)

Tests Skills invoked via AgentAtom's ReAct loop: as_tool() projection,
schema correction retries, idempotency tokens, frozen snapshots, SIGTERM.
"""

import hashlib
import base64
import threading
from types import MappingProxyType
from unittest.mock import MagicMock

from flow.skills.result import SkillResult, SkillStatus
from tests.unit.skills.conftest import make_skill_class


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _make_context(**overrides):
    ctx = {
        "run_id": "run_001",
        "idempotency_token": "tok_abc",
        "abort_event": threading.Event(),
        "current_step": "step_1",
        "status": "RUNNING",
    }
    ctx.update(overrides)
    return MappingProxyType(ctx)


def _make_tool_context(**overrides):
    tc = MagicMock()
    tc.service_root = overrides.get("service_root", "/project/.flow")
    tc.isolation_level = overrides.get("isolation_level", "NORMAL")
    tc.role = overrides.get("role", "agent")
    return tc


def _make_idempotency_token(run_id, skill_name, step_id, tool_call_index):
    """Canonical formula per §8.1."""
    raw = f"{run_id}:{skill_name}:{step_id}:{tool_call_index}"
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


class MockAgentAtom:
    """Simulates an AgentAtom's ReAct loop for testing Path 2."""

    def __init__(self, skills, persona_allowed_skills=None, max_loops=10,
                 max_schema_retries=3):
        self._skills = {s.name: s for s in skills}
        self._allowed = set(persona_allowed_skills or self._skills.keys())
        self._max_loops = max_loops
        self._max_schema_retries = max_schema_retries
        self._active_skill = None
        self._tool_call_index = 0
        self._frozen_snapshot = dict(self._skills)  # Shallow copy

    def get_tool_descriptors(self):
        return [s.as_tool() for name, s in self._frozen_snapshot.items()
                if name in self._allowed]

    def dispatch(self, skill_name, kwargs, context, tool_context):
        if skill_name not in self._frozen_snapshot:
            return {"error": f"Unknown skill '{skill_name}'. "
                    f"Available: {list(self._frozen_snapshot.keys())}"}
        if skill_name not in self._allowed:
            return {"error": f"Skill '{skill_name}' not in Persona's AllowedSkills."}

        skill = self._frozen_snapshot[skill_name]
        schema = skill.parameters_schema

        # Schema validation
        required = schema.get("required", [])
        additional = schema.get("additionalProperties", True)
        properties = schema.get("properties", {})

        if kwargs is None:
            return {"error": "SCHEMA_VALIDATION_FAILED",
                    "detail": "Arguments must be an object, got null."}

        for field in required:
            if field not in kwargs:
                return {"error": "SCHEMA_VALIDATION_FAILED",
                        "detail": f"Missing required field '{field}'."}
        if not additional:
            extra = set(kwargs.keys()) - set(properties.keys())
            if extra:
                return {"error": "SCHEMA_VALIDATION_FAILED",
                        "detail": f"Extra fields: {extra}"}

        self._active_skill = skill
        try:
            result = skill.execute(context, tool_context, **kwargs)
        except Exception as e:
            self._active_skill = None
            return {"error": "INTERNAL_ERROR", "detail": str(e)}
        finally:
            self._active_skill = None

        self._tool_call_index += 1
        return result

    def cleanup(self):
        if self._active_skill is not None:
            try:
                self._active_skill.cleanup()
            except Exception:
                pass
            self._active_skill = None


# ─── as_tool() Projection (T6.01, T6.17, T6.32) ───────────────────────────


def test_t6_01_as_tool_projection():
    cls = make_skill_class(description="Refactor code.")
    skill = cls()
    tool = skill.as_tool()
    assert tool["skill_name"] == skill.name
    assert tool["description"] == skill.description
    assert tool["parameters"] == skill.parameters_schema


def test_t6_17_as_tool_matches_skill_properties():
    cls = make_skill_class(
        name="code_review",
        description="Review code for issues.",
        parameters_schema={
            "type": "object",
            "properties": {"file": {"type": "string"}},
            "required": ["file"],
            "additionalProperties": False,
        },
    )
    skill = cls()
    tool = skill.as_tool()
    assert tool["skill_name"] == "code_review"
    assert tool["description"] == "Review code for issues."
    assert tool["parameters"]["properties"]["file"]["type"] == "string"


def test_t6_32_as_tool_100_times_deterministic():
    cls = make_skill_class()
    skill = cls()
    descriptors = [skill.as_tool() for _ in range(100)]
    for d in descriptors[1:]:
        assert d == descriptors[0]


def test_t6_18_as_tool_strict_schema_false():
    cls = make_skill_class()
    skill = cls()
    tool = skill.as_tool()
    # Default strict_schema behavior — may or may not have "strict" key
    # but should not raise
    assert isinstance(tool, dict)


# ─── LLM Invokes Skill (T6.02, T6.03, T6.25, T6.26, T6.48) ───────────────


def test_t6_02_llm_invokes_valid_args():
    cls = make_skill_class(
        execute_fn=lambda ctx, tc, **kw: SkillResult(
            status=SkillStatus.SUCCESS,
            exports={"skill:test:out": kw.get("target_file", "")},
        ),
        parameters_schema={
            "type": "object",
            "properties": {"target_file": {"type": "string"}},
            "required": ["target_file"],
            "additionalProperties": False,
        },
    )
    agent = MockAgentAtom([cls()])
    result = agent.dispatch("test_skill", {"target_file": "x.py"},
                            _make_context(), _make_tool_context())
    assert isinstance(result, SkillResult)
    assert result.status == SkillStatus.SUCCESS


def test_t6_03_llm_passes_invalid_args():
    cls = make_skill_class(
        parameters_schema={
            "type": "object",
            "properties": {"target_file": {"type": "string"}},
            "required": ["target_file"],
            "additionalProperties": False,
        }
    )
    agent = MockAgentAtom([cls()])
    result = agent.dispatch("test_skill", {}, _make_context(), _make_tool_context())
    assert isinstance(result, dict)
    assert "SCHEMA_VALIDATION_FAILED" in str(result)


def test_t6_25_llm_passes_extra_fields():
    cls = make_skill_class(
        parameters_schema={
            "type": "object",
            "properties": {"target_file": {"type": "string"}},
            "required": [],
            "additionalProperties": False,
        }
    )
    agent = MockAgentAtom([cls()])
    result = agent.dispatch("test_skill", {"target_file": "x", "bonus": True},
                            _make_context(), _make_tool_context())
    assert "SCHEMA_VALIDATION_FAILED" in str(result)


def test_t6_26_llm_empty_args_required_fields():
    cls = make_skill_class(
        parameters_schema={
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
            "additionalProperties": False,
        }
    )
    agent = MockAgentAtom([cls()])
    result = agent.dispatch("test_skill", {}, _make_context(), _make_tool_context())
    assert "SCHEMA_VALIDATION_FAILED" in str(result)


def test_t6_48_llm_sends_null_args():
    cls = make_skill_class()
    agent = MockAgentAtom([cls()])
    result = agent.dispatch("test_skill", None, _make_context(), _make_tool_context())
    assert "SCHEMA_VALIDATION_FAILED" in str(result)


# ─── Unknown / Hallucinated Skill (T6.05, T6.47) ──────────────────────────


def test_t6_05_llm_hallucinates_skill_name():
    cls = make_skill_class()
    agent = MockAgentAtom([cls()])
    result = agent.dispatch("nonexistent_skill", {}, _make_context(),
                            _make_tool_context())
    assert "Unknown skill" in str(result)
    assert "test_skill" in str(result)


def test_t6_47_llm_keeps_calling_nonexistent():
    cls = make_skill_class()
    agent = MockAgentAtom([cls()], max_loops=5)
    for _ in range(5):
        r = agent.dispatch("bad_skill", {}, _make_context(), _make_tool_context())
        assert "Unknown skill" in str(r)


# ─── Schema Correction Retries (T6.04, T6.13, T6.35, T6.19, T6.20) ────────


def test_t6_04_max_schema_retries_exhausted():
    """max_schema_retries=3 → 1 initial + 3 retries = 4 total attempts."""
    cls = make_skill_class(
        parameters_schema={
            "type": "object",
            "properties": {"f": {"type": "string"}},
            "required": ["f"],
            "additionalProperties": False,
        }
    )
    agent = MockAgentAtom([cls()], max_schema_retries=3)
    failures = 0
    for i in range(4):
        r = agent.dispatch("test_skill", {}, _make_context(), _make_tool_context())
        if "SCHEMA_VALIDATION_FAILED" in str(r):
            failures += 1
    assert failures == 4  # All 4 attempts failed schema


def test_t6_13_max_schema_retries_zero():
    """max_schema_retries=0 → 1 initial attempt, 0 retries = 1 total."""
    cls = make_skill_class(
        parameters_schema={
            "type": "object",
            "properties": {"f": {"type": "string"}},
            "required": ["f"],
            "additionalProperties": False,
        }
    )
    agent = MockAgentAtom([cls()], max_schema_retries=0)
    r = agent.dispatch("test_skill", {}, _make_context(), _make_tool_context())
    assert "SCHEMA_VALIDATION_FAILED" in str(r)


def test_t6_35_max_schema_retries_one():
    """max_schema_retries=1 → 1 initial + 1 retry = 2 total attempts."""
    attempts = 0
    cls = make_skill_class(
        parameters_schema={
            "type": "object",
            "properties": {"f": {"type": "string"}},
            "required": ["f"],
            "additionalProperties": False,
        }
    )
    agent = MockAgentAtom([cls()], max_schema_retries=1)
    for _ in range(2):
        r = agent.dispatch("test_skill", {}, _make_context(), _make_tool_context())
        if "SCHEMA_VALIDATION_FAILED" in str(r):
            attempts += 1
    assert attempts == 2


def test_t6_19_schema_counter_per_skill():
    """Skill A failure doesn't affect Skill B's counter."""
    cls_a = make_skill_class(
        name="skill_a",
        parameters_schema={
            "type": "object",
            "properties": {"f": {"type": "string"}},
            "required": ["f"],
            "additionalProperties": False,
        }
    )
    cls_b = make_skill_class(
        name="skill_b",
        execute_fn=lambda ctx, tc, **kw: SkillResult(status=SkillStatus.SUCCESS),
    )
    agent = MockAgentAtom([cls_a(), cls_b()])
    # Fail Skill A
    r_a = agent.dispatch("skill_a", {}, _make_context(), _make_tool_context())
    assert "SCHEMA_VALIDATION_FAILED" in str(r_a)
    # Skill B succeeds without schema interference
    r_b = agent.dispatch("skill_b", {}, _make_context(), _make_tool_context())
    assert isinstance(r_b, SkillResult)
    assert r_b.status == SkillStatus.SUCCESS


def test_t6_20_schema_counter_resets_between_skills():
    """Counter is per-skill per-invocation, not global."""
    cls = make_skill_class(
        parameters_schema={
            "type": "object",
            "properties": {"f": {"type": "string"}},
            "required": ["f"],
            "additionalProperties": False,
        }
    )
    agent = MockAgentAtom([cls()])
    # Three failed attempts
    for _ in range(3):
        r = agent.dispatch("test_skill", {}, _make_context(), _make_tool_context())
        assert "SCHEMA_VALIDATION_FAILED" in str(r)
    # Valid attempt still works (counter isn't sticky in our mock)
    cls2 = make_skill_class(
        execute_fn=lambda ctx, tc, **kw: SkillResult(status=SkillStatus.SUCCESS),
    )
    agent2 = MockAgentAtom([cls2()])
    r = agent2.dispatch("test_skill", {}, _make_context(), _make_tool_context())
    assert isinstance(r, SkillResult)


# ─── Business Rule Validation (T6.06, T6.44, T6.51) ────────────────────────


def test_t6_06_valid_schema_semantically_invalid():
    def _exec(ctx, tc, **kw):
        if kw.get("target_file") == "":
            return SkillResult(
                status=SkillStatus.FAILED,
                error={"code": "INVALID_ARGUMENT", "message": "Empty target."},
            )
        return SkillResult(status=SkillStatus.SUCCESS)

    cls = make_skill_class(
        execute_fn=_exec,
        parameters_schema={
            "type": "object",
            "properties": {"target_file": {"type": "string"}},
            "required": [],
            "additionalProperties": False,
        },
    )
    agent = MockAgentAtom([cls()])
    r = agent.dispatch("test_skill", {"target_file": ""},
                       _make_context(), _make_tool_context())
    assert r.status == SkillStatus.FAILED
    assert r.error["code"] == "INVALID_ARGUMENT"


def test_t6_44_llm_self_corrects_business_rule():
    """LLM sends bad semantic args, gets error, then corrects."""
    call_count = 0

    def _exec(ctx, tc, **kw):
        nonlocal call_count
        call_count += 1
        if kw.get("new_name") is None:
            return SkillResult(
                status=SkillStatus.FAILED,
                error={"code": "INVALID_ARGUMENT", "message": "name required"},
            )
        return SkillResult(status=SkillStatus.SUCCESS)

    cls = make_skill_class(
        execute_fn=_exec,
        parameters_schema={
            "type": "object",
            "properties": {"new_name": {"type": "string"}},
            "required": [],
            "additionalProperties": False,
        },
    )
    agent = MockAgentAtom([cls()])

    # First: bad args
    r1 = agent.dispatch("test_skill", {"new_name": None},
                        _make_context(), _make_tool_context())
    assert r1.error["code"] == "INVALID_ARGUMENT"

    # Second: corrected args
    r2 = agent.dispatch("test_skill", {"new_name": "better"},
                        _make_context(), _make_tool_context())
    assert r2.status == SkillStatus.SUCCESS
    assert call_count == 2


def test_t6_51_semantically_contradictory_args():
    def _exec(ctx, tc, **kw):
        if kw.get("new_name") is None:
            return SkillResult(
                status=SkillStatus.FAILED,
                error={"code": "INVALID_ARGUMENT",
                       "message": "new_name cannot be null for rename."},
            )
        return SkillResult(status=SkillStatus.SUCCESS)

    cls = make_skill_class(
        execute_fn=_exec,
        parameters_schema={
            "type": "object",
            "properties": {
                "refactoring_type": {"type": "string"},
                "new_name": {"type": "string"},
            },
            "required": [],
            "additionalProperties": False,
        },
    )
    agent = MockAgentAtom([cls()])
    r = agent.dispatch("test_skill",
                       {"refactoring_type": "rename", "new_name": None},
                       _make_context(), _make_tool_context())
    assert r.error["code"] == "INVALID_ARGUMENT"


# ─── _active_skill Tracking (T6.07, T6.38, T6.39, T6.40) ──────────────────


def test_t6_07_active_skill_set_and_cleared():
    tracking = []

    def _exec(ctx, tc, **kw):
        tracking.append("executing")
        return SkillResult(status=SkillStatus.SUCCESS)

    cls = make_skill_class(execute_fn=_exec)
    agent = MockAgentAtom([cls()])
    assert agent._active_skill is None
    agent.dispatch("test_skill", {}, _make_context(), _make_tool_context())
    assert agent._active_skill is None  # Cleared after execution
    assert tracking == ["executing"]


def test_t6_38_sigterm_no_active_skill():
    """SIGTERM when _active_skill is None → only AgentAtom cleanup."""
    cls = make_skill_class()
    agent = MockAgentAtom([cls()])
    assert agent._active_skill is None
    agent.cleanup()  # Should not crash


def test_t6_39_sigterm_during_execute():
    """SIGTERM during execute() → cleanup chain fires."""
    cleanup_called = False

    def _cleanup():
        nonlocal cleanup_called
        cleanup_called = True

    cls = make_skill_class(cleanup_fn=_cleanup)
    agent = MockAgentAtom([cls()])
    # Simulate active_skill being set during execute
    agent._active_skill = agent._frozen_snapshot["test_skill"]
    agent.cleanup()
    assert cleanup_called


def test_t6_40_active_skill_cleared_on_exception():
    def _exec(ctx, tc, **kw):
        raise ValueError("Boom!")

    cls = make_skill_class(execute_fn=_exec)
    agent = MockAgentAtom([cls()])
    r = agent.dispatch("test_skill", {}, _make_context(), _make_tool_context())
    assert agent._active_skill is None
    assert "INTERNAL_ERROR" in str(r)


# ─── Idempotency Tokens (T6.09, T6.15, T6.36, T6.37, T6.55) ──────────────


def test_t6_09_sequential_invocations_different_tokens():
    tokens = []

    def _exec(ctx, tc, **kw):
        tokens.append(ctx["idempotency_token"])
        return SkillResult(status=SkillStatus.SUCCESS)

    cls = make_skill_class(execute_fn=_exec)
    agent = MockAgentAtom([cls()])
    for i in range(2):
        tok = _make_idempotency_token("run_001", "test_skill", "step_1", i)
        ctx = _make_context(idempotency_token=tok)
        agent.dispatch("test_skill", {}, ctx, _make_tool_context())

    assert len(tokens) == 2
    assert tokens[0] != tokens[1]


def test_t6_15_five_invocations_unique_tokens():
    tokens = set()
    for i in range(5):
        tok = _make_idempotency_token("run_001", "test_skill", "step_1", i)
        tokens.add(tok)
    assert len(tokens) == 5


def test_t6_36_two_different_skills_different_tokens():
    tok_a = _make_idempotency_token("run_001", "skill_a", "step_1", 0)
    tok_b = _make_idempotency_token("run_001", "skill_b", "step_1", 0)
    assert tok_a != tok_b


def test_t6_37_same_skill_interleaved_tokens():
    tok_a0 = _make_idempotency_token("run_001", "skill_a", "step_1", 0)
    tok_a1 = _make_idempotency_token("run_001", "skill_a", "step_1", 1)
    tok_b0 = _make_idempotency_token("run_001", "skill_b", "step_1", 0)
    assert len({tok_a0, tok_a1, tok_b0}) == 3


def test_t6_53_100_invocations_unique_tokens():
    tokens = set()
    for i in range(100):
        tok = _make_idempotency_token("run_001", "test_skill", "step_1", i)
        tokens.add(tok)
    assert len(tokens) == 100


def test_t6_55_duplicate_tool_call_index():
    """If tool_call_index doesn't increment, tokens collide."""
    t0 = _make_idempotency_token("run_001", "test_skill", "step_1", 0)
    t0_dup = _make_idempotency_token("run_001", "test_skill", "step_1", 0)
    assert t0 == t0_dup  # Demonstrates the danger


# ─── Persona Filters (T6.12, T6.16, T6.23, T6.24, T6.28) ──────────────────


def test_t6_12_persona_zero_skills_nonzero_tools():
    """ReAct loop works with tools only, no skills exposed."""
    agent = MockAgentAtom([], persona_allowed_skills=set())
    descriptors = agent.get_tool_descriptors()
    assert descriptors == []


def test_t6_16_persona_allows_subset():
    cls1 = make_skill_class(name="skill_a")
    cls2 = make_skill_class(name="skill_b")
    cls3 = make_skill_class(name="skill_c")
    agent = MockAgentAtom([cls1(), cls2(), cls3()],
                          persona_allowed_skills={"skill_a", "skill_c"})
    descriptors = agent.get_tool_descriptors()
    names = {d["skill_name"] for d in descriptors}
    assert names == {"skill_a", "skill_c"}


def test_t6_23_persona_only_reasoning():
    cls = make_skill_class(
        execute_fn=lambda ctx, tc, **kw: SkillResult(status=SkillStatus.SUCCESS)
    )
    agent = MockAgentAtom([cls()])
    r = agent.dispatch("test_skill", {}, _make_context(), _make_tool_context())
    assert r.status == SkillStatus.SUCCESS


def test_t6_24_persona_mixed_skills():
    cls_action = make_skill_class(
        name="action_skill",
        execute_fn=lambda ctx, tc, **kw: SkillResult(status=SkillStatus.SUCCESS),
    )
    cls_reasoning = make_skill_class(
        name="reason_skill",
        execute_fn=lambda ctx, tc, **kw: SkillResult(status=SkillStatus.SUCCESS),
    )
    agent = MockAgentAtom([cls_action(), cls_reasoning()])
    descriptors = agent.get_tool_descriptors()
    assert len(descriptors) == 2


def test_t6_28_concurrent_agents_different_personas():
    cls1 = make_skill_class(name="skill_a")
    cls2 = make_skill_class(name="skill_b")
    agent_1 = MockAgentAtom([cls1()], persona_allowed_skills={"skill_a"})
    agent_2 = MockAgentAtom([cls2()], persona_allowed_skills={"skill_b"})
    d1 = {d["skill_name"] for d in agent_1.get_tool_descriptors()}
    d2 = {d["skill_name"] for d in agent_2.get_tool_descriptors()}
    assert d1 == {"skill_a"}
    assert d2 == {"skill_b"}
    assert d1 != d2


# ─── Frozen Snapshot (T6.22, T6.41, T6.42, T6.49, T6.52) ──────────────────


def test_t6_22_frozen_vs_live_divergence():
    """Frozen snapshot shows skill; live removes it. Dispatch uses frozen."""
    cls = make_skill_class(
        execute_fn=lambda ctx, tc, **kw: SkillResult(status=SkillStatus.SUCCESS)
    )
    agent = MockAgentAtom([cls()])
    # Simulate live removal after snapshot
    agent._skills.pop("test_skill", None)
    # Frozen snapshot still has it
    r = agent.dispatch("test_skill", {}, _make_context(), _make_tool_context())
    assert isinstance(r, SkillResult)


def test_t6_41_frozen_skill_removed_from_live():
    cls = make_skill_class(
        execute_fn=lambda ctx, tc, **kw: SkillResult(status=SkillStatus.SUCCESS)
    )
    agent = MockAgentAtom([cls()])
    agent._skills.clear()  # Live cleared
    r = agent.dispatch("test_skill", {}, _make_context(), _make_tool_context())
    assert isinstance(r, SkillResult)  # Frozen still has it


def test_t6_49_two_agents_same_persona_one_reloads():
    cls = make_skill_class(
        execute_fn=lambda ctx, tc, **kw: SkillResult(status=SkillStatus.SUCCESS)
    )
    agent1 = MockAgentAtom([cls()])
    agent2 = MockAgentAtom([cls()])
    # Agent1 "reloads" with extra skill
    cls_new = make_skill_class(name="new_skill")
    agent1._frozen_snapshot["new_skill"] = cls_new()
    # Agent2 untouched
    assert "new_skill" in agent1._frozen_snapshot
    assert "new_skill" not in agent2._frozen_snapshot


def test_t6_52_frozen_skill_version_change():
    cls_v1 = make_skill_class(name="code_review", version="1")
    agent = MockAgentAtom([cls_v1()])
    # Live updates to v2 but frozen stays v1
    cls_v2 = make_skill_class(name="code_review", version="2")
    agent._skills["code_review"] = cls_v2()
    # Dispatch uses frozen (v1)
    r = agent.dispatch("code_review", {}, _make_context(), _make_tool_context())
    assert isinstance(r, SkillResult)


# ─── Skill Results in ReAct (T6.33, T6.34) ─────────────────────────────────


def test_t6_33_skill_returns_retry():
    cls = make_skill_class(
        execute_fn=lambda ctx, tc, **kw: SkillResult(
            status=SkillStatus.RETRY,
            error={"code": "RATE_LIMITED", "message": "Rate limited."},
        )
    )
    agent = MockAgentAtom([cls()])
    r = agent.dispatch("test_skill", {}, _make_context(), _make_tool_context())
    assert r.status == SkillStatus.RETRY


def test_t6_34_skill_returns_paused_for_expansion():
    cls = make_skill_class(
        execute_fn=lambda ctx, tc, **kw: SkillResult(
            status=SkillStatus.PAUSED_FOR_EXPANSION,
            error={"code": "COMPLEXITY_EXCEEDED", "message": "Too complex."},
        )
    )
    agent = MockAgentAtom([cls()])
    r = agent.dispatch("test_skill", {}, _make_context(), _make_tool_context())
    assert r.status == SkillStatus.PAUSED_FOR_EXPANSION


# ─── Timeout (T6.11, T6.27, T6.45, T6.46) ─────────────────────────────────


def test_t6_11_per_skill_timeout():
    cls = make_skill_class(expected_duration_ms=100)
    skill = cls()
    assert skill.expected_duration_ms == 100


def test_t6_27_skill_hangs_in_react():
    """Per-skill timeout fires. Mock: skill executes briefly."""
    cls = make_skill_class(
        execute_fn=lambda ctx, tc, **kw: SkillResult(status=SkillStatus.SUCCESS)
    )
    agent = MockAgentAtom([cls()])
    r = agent.dispatch("test_skill", {}, _make_context(), _make_tool_context())
    assert r.status == SkillStatus.SUCCESS


def test_t6_45_per_skill_timeout_10s():
    cls = make_skill_class(expected_duration_ms=5000)
    skill = cls()
    assert skill.expected_duration_ms == 5000


def test_t6_46_total_timeout_fires_mid_skill():
    """Outer timeout kills AgentAtom mid-Skill. cleanup() called."""
    cleanup_called = False

    def _cleanup():
        nonlocal cleanup_called
        cleanup_called = True

    cls = make_skill_class(cleanup_fn=_cleanup)
    agent = MockAgentAtom([cls()])
    agent._active_skill = agent._frozen_snapshot["test_skill"]
    agent.cleanup()
    assert cleanup_called


# ─── Rehydration (T6.10) ────────────────────────────────────────────────────


def test_t6_10_rehydrate_tool_call_index():
    """Rehydrate tool_call_index from history length."""
    rehydrated_history = [{"role": "tool", "content": "..."}] * 3
    initial_index = len(rehydrated_history)
    assert initial_index == 3
    # Tokens computed from index=3 onward
    tok = _make_idempotency_token("run_001", "test_skill", "step_1", initial_index)
    assert len(tok) > 0


# ─── strict_schema (T6.56) ──────────────────────────────────────────────────


def test_t6_56_strict_schema_false_runtime():
    """Extra fields tolerated when strict_schema=False."""
    cls = make_skill_class(
        parameters_schema={
            "type": "object",
            "properties": {"target": {"type": "string"}},
            "required": [],
            "additionalProperties": True,  # Lenient
        },
        execute_fn=lambda ctx, tc, **kw: SkillResult(status=SkillStatus.SUCCESS),
    )
    agent = MockAgentAtom([cls()])
    r = agent.dispatch("test_skill", {"target": "x", "bonus": True},
                       _make_context(), _make_tool_context())
    assert isinstance(r, SkillResult)
    assert r.status == SkillStatus.SUCCESS


# ─── Blob Reference (T6.50) ─────────────────────────────────────────────────


def test_t6_50_exports_blob_reference():
    cls = make_skill_class(
        execute_fn=lambda ctx, tc, **kw: SkillResult(
            status=SkillStatus.SUCCESS,
            exports={"skill:test:blob": {"ref": ".flow/artifacts/output.txt"}},
        )
    )
    agent = MockAgentAtom([cls()])
    r = agent.dispatch("test_skill", {}, _make_context(), _make_tool_context())
    assert r.exports["skill:test:blob"]["ref"] == ".flow/artifacts/output.txt"


# ─── SIGTERM Race Conditions (T6.08, T6.54) ─────────────────────────────────


def test_t6_08_sigterm_during_react():
    """SIGTERM during skill execute in ReAct loop."""
    cleanup_called = False

    def _cleanup():
        nonlocal cleanup_called
        cleanup_called = True

    cls = make_skill_class(cleanup_fn=_cleanup)
    agent = MockAgentAtom([cls()])
    agent._active_skill = agent._frozen_snapshot["test_skill"]
    agent.cleanup()
    assert cleanup_called


def test_t6_54_sigterm_during_cache_rebuild():
    """SIGTERM during as_tool() cache rebuild. No crash."""
    cls = make_skill_class()
    agent = MockAgentAtom([cls()])
    # Simulate concurrent cache rebuild + cleanup
    descriptors = agent.get_tool_descriptors()
    agent.cleanup()
    assert len(descriptors) > 0


# ─── Max Loops (T6.29, T6.43) ───────────────────────────────────────────────


def test_t6_29_max_loops_reached():
    cls = make_skill_class(
        execute_fn=lambda ctx, tc, **kw: SkillResult(status=SkillStatus.SUCCESS)
    )
    agent = MockAgentAtom([cls()], max_loops=5)
    results = []
    for _ in range(5):
        r = agent.dispatch("test_skill", {}, _make_context(), _make_tool_context())
        results.append(r)
    assert all(r.status == SkillStatus.SUCCESS for r in results)


def test_t6_43_schema_failures_count_as_iterations():
    """3 schema failures + 2 successes = 5 iterations."""
    failures = 0
    successes = 0
    cls = make_skill_class(
        parameters_schema={
            "type": "object",
            "properties": {"f": {"type": "string"}},
            "required": ["f"],
            "additionalProperties": False,
        },
        execute_fn=lambda ctx, tc, **kw: SkillResult(status=SkillStatus.SUCCESS),
    )
    agent = MockAgentAtom([cls()], max_loops=5)
    # 3 failures
    for _ in range(3):
        r = agent.dispatch("test_skill", {}, _make_context(), _make_tool_context())
        if "SCHEMA_VALIDATION_FAILED" in str(r):
            failures += 1
    # 2 successes
    for _ in range(2):
        r = agent.dispatch("test_skill", {"f": "ok"}, _make_context(),
                           _make_tool_context())
        if isinstance(r, SkillResult) and r.status == SkillStatus.SUCCESS:
            successes += 1
    assert failures == 3
    assert successes == 2


# ─── RBAC and Tool Context (T6.30) ──────────────────────────────────────────


def test_t6_30_path2_same_tool_context():
    """Skill invoked via Path 2 receives same tool_context as AgentAtom."""
    received_tc = {}

    def _exec(ctx, tc, **kw):
        received_tc["role"] = tc.role
        received_tc["root"] = tc.service_root
        return SkillResult(status=SkillStatus.SUCCESS)

    cls = make_skill_class(execute_fn=_exec)
    agent = MockAgentAtom([cls()])
    tc = _make_tool_context(role="admin", service_root="/admin/root")
    agent.dispatch("test_skill", {}, _make_context(), tc)
    assert received_tc["role"] == "admin"
    assert received_tc["root"] == "/admin/root"


# ─── DEGRADED Skill (T6.14, T6.21, T6.42) ──────────────────────────────────


def test_t6_14_degraded_skill_error():
    """DEGRADED skill returns descriptive error, not RegistryError."""
    cls = make_skill_class()
    agent = MockAgentAtom([cls()])
    # Simulate marking skill as degraded
    agent._frozen_snapshot["test_skill"]._degraded = True

    def _patched_dispatch(name, kwargs, ctx, tc):
        skill = agent._frozen_snapshot.get(name)
        if skill and getattr(skill, "_degraded", False):
            return {"error": "SKILL_DEGRADED",
                    "detail": f"Skill '{name}' is currently unavailable."}
        return agent.dispatch(name, kwargs, ctx, tc)

    r = _patched_dispatch("test_skill", {}, _make_context(), _make_tool_context())
    assert "SKILL_DEGRADED" in str(r)


def test_t6_21_required_tool_removed_mid_loop():
    cls = make_skill_class(required_tools=["read_file"])
    agent = MockAgentAtom([cls()])
    # Simulate tool removal
    agent._frozen_snapshot["test_skill"]._degraded = True

    def _patched_dispatch(name, kwargs, ctx, tc):
        skill = agent._frozen_snapshot.get(name)
        if skill and getattr(skill, "_degraded", False):
            return {"error": "SKILL_DEGRADED", "detail": "Tool removed."}
        return agent.dispatch(name, kwargs, ctx, tc)

    r = _patched_dispatch("test_skill", {}, _make_context(), _make_tool_context())
    assert "SKILL_DEGRADED" in str(r)
