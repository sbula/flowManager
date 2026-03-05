"""Shared fixtures for Skills & Personas tests."""

import json
import pytest
from flow.skills.base import Skill
from flow.skills.result import SkillResult, SkillStatus


# ─── Concrete Skill Factories ───────────────────────────────────────────────


def make_skill_class(
    name="test_skill",
    version="1",
    description="A test skill.",
    required_tools=None,
    parameters_schema=None,
    expected_duration_ms=None,
    strict_schema=True,
    execute_fn=None,
    cleanup_fn=None,
    name_raises=None,
    version_raises=None,
    description_raises=None,
    required_tools_raises=None,
    schema_raises=None,
    init_raises=None,
):
    """Create a concrete Skill subclass with configurable properties."""
    if required_tools is None:
        required_tools = []
    if parameters_schema is None:
        parameters_schema = {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        }

    class _TestSkill(Skill):
        def __init__(self):
            if init_raises:
                raise init_raises

        @property
        def name(self):
            if name_raises:
                raise name_raises
            return name

        @property
        def version(self):
            if version_raises:
                raise version_raises
            return version

        @property
        def description(self):
            if description_raises:
                raise description_raises
            return description

        @property
        def required_tools(self):
            if required_tools_raises:
                raise required_tools_raises
            return required_tools

        @property
        def parameters_schema(self):
            if schema_raises:
                raise schema_raises
            return parameters_schema

        @property
        def expected_duration_ms(self):
            return expected_duration_ms

        @property
        def strict_schema(self):
            return strict_schema

        def execute(self, context, tool_context, **kwargs):
            if execute_fn:
                return execute_fn(context, tool_context, **kwargs)
            return SkillResult(status=SkillStatus.SUCCESS)

        def cleanup(self):
            if cleanup_fn:
                cleanup_fn()

    _TestSkill.__name__ = name.title().replace("_", "") + "Skill"
    _TestSkill.__qualname__ = _TestSkill.__name__
    return _TestSkill


# ─── JSON Builders ───────────────────────────────────────────────────────────


def build_persona_json(
    personas=None,
    schema_version="1",
    include_schema_version=True,
):
    """Build a valid persona JSON string."""
    data = {}
    if include_schema_version:
        data["schema_version"] = schema_version
    if personas is not None:
        data["personas"] = personas
    else:
        data["personas"] = {
            "TestDev": {
                "version": "1",
                "Description": "A test persona.",
                "SystemPrompt": "You are a test developer.",
                "Focus": ["Testing"],
                "AllowedSkills": [{"name": "test_skill", "version": "1"}],
                "AllowedTools": ["read_file"],
            }
        }
    return json.dumps(data)


def build_registry_json(
    skills=None,
    schema_version="1",
    include_schema_version=True,
):
    """Build a valid skill registry JSON string."""
    data = {}
    if include_schema_version:
        data["schema_version"] = schema_version
    if skills is not None:
        data["skills"] = skills
    else:
        data["skills"] = {
            "test_skill": {
                "version": "1",
                "module": "flow.skills.test_stub.TestSkillSkill",
                "category": "reasoning",
                "description": "A test skill.",
                "required_tools": ["read_file"],
            }
        }
    return json.dumps(data)


# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def skill_registry():
    """Returns a minimal valid skill registry dict for persona validation."""
    return {
        "test_skill": {"version": "1"},
        "code_review": {"version": "1"},
        "debug_error": {"version": "1"},
        "refactor_code": {"version": "1"},
        "write_unit_tests": {"version": "1"},
    }


@pytest.fixture
def tool_registry():
    """Returns a set of known tool names."""
    return {
        "read_file", "write_file", "edit_file", "search_file",
        "list_files", "run_test", "run_lint", "git_commit",
        "git_status", "git_diff", "search_knowledge",
    }


@pytest.fixture
def valid_persona_text(skill_registry):
    """Returns valid persona JSON text."""
    return build_persona_json()


@pytest.fixture
def valid_registry_text():
    """Returns valid skill registry JSON text."""
    return build_registry_json()
