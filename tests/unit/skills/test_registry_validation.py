"""Ch.3: Skill Registry Startup Validation (T3.01–T3.60)

Tests all registry JSON validation: module import, metadata cross-validation,
parameters_schema validation, category validation, duplicate detection,
tool dependency verification.
"""

import json
import types
import pytest

from flow.skills.errors import ConfigParseError, SchemaVersionError, RegistryError
from flow.skills.validators import validate_skill_registry
from flow.skills.base import Skill
from flow.skills.result import SkillResult, SkillStatus
from tests.unit.skills.conftest import make_skill_class


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _make_skill_entry(
    name="test_skill", version="1", module="test_mod.TestSkillSkill",
    category="reasoning", description="A test skill.",
    required_tools=None, expected_duration_ms=None,
):
    entry = {
        "version": version,
        "module": module,
        "category": category,
        "description": description,
    }
    if required_tools is not None:
        entry["required_tools"] = required_tools
    else:
        entry["required_tools"] = []
    if expected_duration_ms is not None:
        entry["expected_duration_ms"] = expected_duration_ms
    return entry


def _make_import_fn(skill_classes=None):
    """Create a mock import function that returns modules with skill classes."""
    if skill_classes is None:
        skill_classes = {}

    def _import(mod_path):
        if mod_path in skill_classes:
            mod = types.ModuleType(mod_path)
            for cls_name, cls in skill_classes[mod_path].items():
                setattr(mod, cls_name, cls)
            return mod
        raise ImportError(f"No module named '{mod_path}'")

    return _import


def _validate(text, tool_registry=None, import_fn=None):
    if tool_registry is None:
        tool_registry = {"read_file", "write_file", "edit_file", "run_test"}
    return validate_skill_registry(text, tool_registry, import_module_fn=import_fn)


def _wrap(skills, schema_version="1"):
    return json.dumps({"schema_version": schema_version, "skills": skills})


def _make_valid_setup(name="test_skill", **kwargs):
    """Create both a registry JSON and matching import function."""
    cls = make_skill_class(name=name, **kwargs)
    entry = _make_skill_entry(
        name=name,
        version=kwargs.get("version", "1"),
        module=f"test_mod.{cls.__name__}",
        category=kwargs.get("category", "reasoning"),
        description=kwargs.get("description", "A test skill."),
        required_tools=kwargs.get("required_tools", []),
    )
    import_fn = _make_import_fn({"test_mod": {cls.__name__: cls}})
    text = _wrap({name: entry})
    return text, import_fn


# ─── Happy Paths ─────────────────────────────────────────────────────────────


def test_t3_01_valid_registry_loads():
    text, import_fn = _make_valid_setup()
    result = _validate(text, import_fn=import_fn)
    assert "skills" in result
    assert "test_skill" in result["_loaded_skills"]


# ─── JSON Parse Errors ───────────────────────────────────────────────────────


def test_t3_02_malformed_json():
    with pytest.raises(ConfigParseError, match="Failed to parse"):
        _validate('{"schema_version": "1", "skills": {"a": {},}}')


def test_t3_03_registry_file_missing():
    """File-not-found is at loader level. Validator sees empty string."""
    with pytest.raises(ConfigParseError, match="Failed to parse"):
        _validate("")


def test_t3_40_empty_file():
    with pytest.raises(ConfigParseError, match="Failed to parse"):
        _validate("")


def test_t3_41_whitespace_only():
    with pytest.raises(ConfigParseError, match="Failed to parse"):
        _validate("  \n\t  ")


# ─── Schema Version ─────────────────────────────────────────────────────────


def test_t3_04_schema_version_mismatch():
    text = _wrap({}, schema_version="99")
    with pytest.raises(SchemaVersionError, match="99"):
        _validate(text)


def test_t3_34_schema_version_integer():
    text = json.dumps({"schema_version": 1, "skills": {}})
    with pytest.raises(SchemaVersionError, match="must be a string"):
        _validate(text)


# ─── Skills Key Validation ───────────────────────────────────────────────────


def test_t3_22_skills_key_missing():
    text = json.dumps({"schema_version": "1"})
    with pytest.raises(ConfigParseError, match="missing 'skills'"):
        _validate(text)


def test_t3_23_skills_value_null():
    text = json.dumps({"schema_version": "1", "skills": None})
    with pytest.raises(ConfigParseError, match="null"):
        _validate(text)


def test_t3_24_skills_value_is_list():
    text = json.dumps({"schema_version": "1", "skills": []})
    with pytest.raises(ConfigParseError, match="must be an object"):
        _validate(text)


# ─── Module Import ───────────────────────────────────────────────────────────


def test_t3_05_module_import_failure():
    entry = _make_skill_entry(module="bad_mod.BadClass")
    text = _wrap({"test_skill": entry})
    import_fn = _make_import_fn({})  # Nothing importable
    with pytest.raises(RegistryError, match="ImportError"):
        _validate(text, import_fn=import_fn)


def test_t3_06_class_not_subclass_of_skill():
    class NotASkill:
        pass

    import_fn = _make_import_fn({"test_mod": {"NotSkill": NotASkill}})
    entry = _make_skill_entry(module="test_mod.NotSkill")
    text = _wrap({"test_skill": entry})
    with pytest.raises(RegistryError, match="not a subclass of Skill"):
        _validate(text, import_fn=import_fn)


def test_t3_28_module_non_existent_package():
    entry = _make_skill_entry(module="flow.skills.does_not_exist.Cls")
    text = _wrap({"test_skill": entry})
    import_fn = _make_import_fn({})
    with pytest.raises(RegistryError, match="ImportError"):
        _validate(text, import_fn=import_fn)


def test_t3_29_module_without_expected_class():
    import_fn = _make_import_fn({"test_mod": {}})  # No class in module
    entry = _make_skill_entry(module="test_mod.MissingClass")
    text = _wrap({"test_skill": entry})
    with pytest.raises(RegistryError, match="not found"):
        _validate(text, import_fn=import_fn)


def test_t3_42_module_path_uses_os_separators():
    entry = _make_skill_entry(module="flow\\skills\\code")
    text = _wrap({"test_skill": entry})
    with pytest.raises(RegistryError, match="dotted Python path"):
        _validate(text)


def test_t3_49_module_empty_string():
    entry = _make_skill_entry(module="")
    text = _wrap({"test_skill": entry})
    with pytest.raises(RegistryError, match="empty string"):
        _validate(text)


def test_t3_58_class_init_raises():
    cls = make_skill_class(init_raises=RuntimeError("boom"))
    import_fn = _make_import_fn({"test_mod": {cls.__name__: cls}})
    entry = _make_skill_entry(module=f"test_mod.{cls.__name__}")
    text = _wrap({"test_skill": entry})
    with pytest.raises(RegistryError, match="instantiation failed"):
        _validate(text, import_fn=import_fn)


# ─── Metadata Cross-Validation ──────────────────────────────────────────────


def test_t3_07_metadata_mismatch_name():
    cls = make_skill_class(name="code_review")  # Doesn't match registry key
    import_fn = _make_import_fn({"test_mod": {cls.__name__: cls}})
    entry = _make_skill_entry(name="code_review_v2", module=f"test_mod.{cls.__name__}")
    text = _wrap({"code_review_v2": entry})
    with pytest.raises(RegistryError, match="does not match"):
        _validate(text, import_fn=import_fn)


def test_t3_08_metadata_mismatch_version():
    cls = make_skill_class(version="2")
    import_fn = _make_import_fn({"test_mod": {cls.__name__: cls}})
    entry = _make_skill_entry(version="1", module=f"test_mod.{cls.__name__}")
    text = _wrap({"test_skill": entry})
    with pytest.raises(RegistryError, match="does not match"):
        _validate(text, import_fn=import_fn)


def test_t3_35_metadata_mismatch_description():
    cls = make_skill_class(description="Class says this.")
    import_fn = _make_import_fn({"test_mod": {cls.__name__: cls}})
    entry = _make_skill_entry(description="Registry says that.", module=f"test_mod.{cls.__name__}")
    text = _wrap({"test_skill": entry})
    with pytest.raises(RegistryError, match="does not match"):
        _validate(text, import_fn=import_fn)


def test_t3_36_metadata_mismatch_required_tools():
    cls = make_skill_class(required_tools=["read_file"])
    import_fn = _make_import_fn({"test_mod": {cls.__name__: cls}})
    entry = _make_skill_entry(
        required_tools=["write_file"], module=f"test_mod.{cls.__name__}"
    )
    text = _wrap({"test_skill": entry})
    with pytest.raises(RegistryError, match="does not match"):
        _validate(text, import_fn=import_fn)


def test_t3_57_required_tools_order_differs():
    """Set-based comparison, not ordered."""
    cls = make_skill_class(required_tools=["read_file", "write_file"])
    import_fn = _make_import_fn({"test_mod": {cls.__name__: cls}})
    entry = _make_skill_entry(
        required_tools=["write_file", "read_file"], module=f"test_mod.{cls.__name__}"
    )
    text = _wrap({"test_skill": entry})
    result = _validate(text, import_fn=import_fn)
    assert "test_skill" in result["_loaded_skills"]


def test_t3_43_skill_name_property_raises():
    cls = make_skill_class(name_raises=RuntimeError("boom"))
    import_fn = _make_import_fn({"test_mod": {cls.__name__: cls}})
    entry = _make_skill_entry(module=f"test_mod.{cls.__name__}")
    text = _wrap({"test_skill": entry})
    with pytest.raises(RegistryError, match="name property raised"):
        _validate(text, import_fn=import_fn)


def test_t3_44_parameters_schema_returns_none():
    cls = make_skill_class(parameters_schema=None, schema_raises=None)
    # Override to return None directly
    import_fn = _make_import_fn({"test_mod": {cls.__name__: cls}})
    entry = _make_skill_entry(module=f"test_mod.{cls.__name__}")
    text = _wrap({"test_skill": entry})
    # The make_skill_class with parameters_schema=None will set the default schema
    # We need to use schema_raises or a custom approach
    cls2 = make_skill_class()
    cls2.parameters_schema

    class NoneSchemaSkill(Skill):
        @property
        def name(self):
            return "test_skill"

        @property
        def version(self):
            return "1"

        @property
        def description(self):
            return "A test skill."

        @property
        def parameters_schema(self):
            return None

        def execute(self, context, tool_context, **kwargs):
            return SkillResult(status=SkillStatus.SUCCESS)

    import_fn = _make_import_fn({"test_mod": {"NoneSchemaSkill": NoneSchemaSkill}})
    entry = _make_skill_entry(module="test_mod.NoneSchemaSkill")
    text = _wrap({"test_skill": entry})
    with pytest.raises(RegistryError, match="parameters_schema is None"):
        _validate(text, import_fn=import_fn)


# ─── Parameters Schema Validation ───────────────────────────────────────────


def test_t3_09_invalid_parameters_schema():
    schema = {"type": "object", "$ref": "http://invalid", "additionalProperties": False}
    text, import_fn = _make_valid_setup(parameters_schema=schema)
    # External ref should fail
    with pytest.raises(RegistryError, match="external"):
        _validate(text, import_fn=import_fn)


def test_t3_10_schema_type_array():
    schema = {"type": "array", "additionalProperties": False}
    text, import_fn = _make_valid_setup(parameters_schema=schema)
    with pytest.raises(RegistryError, match="must have type 'object'"):
        _validate(text, import_fn=import_fn)


def test_t3_11_schema_missing_additional_properties_false():
    schema = {"type": "object", "properties": {}}
    text, import_fn = _make_valid_setup(parameters_schema=schema)
    with pytest.raises(RegistryError, match="additionalProperties"):
        _validate(text, import_fn=import_fn)


def test_t3_20_empty_schema():
    text, import_fn = _make_valid_setup(parameters_schema={})
    with pytest.raises(RegistryError, match="must have type 'object'"):
        _validate(text, import_fn=import_fn)


def test_t3_30_schema_type_string():
    schema = {"type": "string", "additionalProperties": False}
    text, import_fn = _make_valid_setup(parameters_schema=schema)
    with pytest.raises(RegistryError, match="must have type 'object'"):
        _validate(text, import_fn=import_fn)


def test_t3_31_schema_type_integer():
    schema = {"type": "integer", "additionalProperties": False}
    text, import_fn = _make_valid_setup(parameters_schema=schema)
    with pytest.raises(RegistryError, match="must have type 'object'"):
        _validate(text, import_fn=import_fn)


def test_t3_32_schema_additional_properties_true():
    schema = {"type": "object", "additionalProperties": True}
    text, import_fn = _make_valid_setup(parameters_schema=schema)
    with pytest.raises(RegistryError, match="additionalProperties"):
        _validate(text, import_fn=import_fn)


def test_t3_33_schema_missing_additional_properties_key():
    schema = {"type": "object", "properties": {"a": {"type": "string"}}}
    text, import_fn = _make_valid_setup(parameters_schema=schema)
    with pytest.raises(RegistryError, match="additionalProperties"):
        _validate(text, import_fn=import_fn)


def test_t3_45_schema_internal_ref():
    schema = {
        "type": "object",
        "$defs": {"TargetFile": {"type": "string"}},
        "properties": {"target": {"$ref": "#/$defs/TargetFile"}},
        "additionalProperties": False,
    }
    text, import_fn = _make_valid_setup(parameters_schema=schema)
    result = _validate(text, import_fn=import_fn)
    assert "test_skill" in result["_loaded_skills"]


def test_t3_17_schema_external_ref_url():
    schema = {
        "type": "object",
        "properties": {"a": {"$ref": "https://example.com/schema.json"}},
        "additionalProperties": False,
    }
    text, import_fn = _make_valid_setup(parameters_schema=schema)
    with pytest.raises(RegistryError, match="external"):
        _validate(text, import_fn=import_fn)


# ─── Field Validation ────────────────────────────────────────────────────────


def test_t3_25_missing_module():
    entry = {"version": "1", "category": "reasoning", "description": "X", "required_tools": []}
    text = _wrap({"test_skill": entry})
    with pytest.raises(RegistryError, match="missing required field 'module'"):
        _validate(text)


def test_t3_26_missing_category():
    entry = {"version": "1", "module": "x.Y", "description": "X", "required_tools": []}
    text = _wrap({"test_skill": entry})
    with pytest.raises(RegistryError, match="missing required field 'category'"):
        _validate(text)


def test_t3_27_invalid_category():
    text, import_fn = _make_valid_setup()
    # Override the registry entry's category to an invalid value
    data = json.loads(text)
    data["skills"]["test_skill"]["category"] = "magic"
    text = json.dumps(data)
    with pytest.raises(RegistryError, match="not valid"):
        _validate(text, import_fn=import_fn)


def test_t3_50_description_null():
    data = {"schema_version": "1", "skills": {"test_skill": {
        "version": "1", "module": "x.Y", "category": "reasoning",
        "description": None, "required_tools": []
    }}}
    with pytest.raises(RegistryError, match="description is null"):
        _validate(json.dumps(data))


def test_t3_51_category_null():
    data = {"schema_version": "1", "skills": {"test_skill": {
        "version": "1", "module": "x.Y", "category": None,
        "description": "X", "required_tools": []
    }}}
    with pytest.raises(RegistryError, match="category is null"):
        _validate(json.dumps(data))


def test_t3_52_version_null():
    data = {"schema_version": "1", "skills": {"test_skill": {
        "version": None, "module": "x.Y", "category": "reasoning",
        "description": "X", "required_tools": []
    }}}
    with pytest.raises(RegistryError, match="version is null"):
        _validate(json.dumps(data))


def test_t3_53_version_integer():
    data = {"schema_version": "1", "skills": {"test_skill": {
        "version": 2, "module": "x.Y", "category": "reasoning",
        "description": "X", "required_tools": []
    }}}
    with pytest.raises(RegistryError, match="must be a string"):
        _validate(json.dumps(data))


def test_t3_37_version_empty_string():
    data = {"schema_version": "1", "skills": {"test_skill": {
        "version": "", "module": "x.Y", "category": "reasoning",
        "description": "X", "required_tools": []
    }}}
    with pytest.raises(RegistryError, match="empty string"):
        _validate(json.dumps(data))


def test_t3_16_version_float_string():
    data = {"schema_version": "1", "skills": {"test_skill": {
        "version": "1.1", "module": "x.Y", "category": "reasoning",
        "description": "X", "required_tools": []
    }}}
    with pytest.raises(RegistryError, match="not a valid integer string"):
        _validate(json.dumps(data))


def test_t3_56_category_wrong_case():
    data = {"schema_version": "1", "skills": {"test_skill": {
        "version": "1", "module": "x.Y", "category": "Action",
        "description": "X", "required_tools": []
    }}}
    with pytest.raises(RegistryError, match="not valid"):
        _validate(json.dumps(data))


# ─── Skill Name Validation ──────────────────────────────────────────────────


def test_t3_19_name_with_spaces():
    data = {"schema_version": "1", "skills": {"my skill": {
        "version": "1", "module": "x.Y", "category": "reasoning",
        "description": "X", "required_tools": []
    }}}
    with pytest.raises(RegistryError, match="invalid characters"):
        _validate(json.dumps(data))


def test_t3_55_name_leading_trailing_whitespace():
    data = {"schema_version": "1", "skills": {" refactor_code ": {
        "version": "1", "module": "x.Y", "category": "reasoning",
        "description": "X", "required_tools": []
    }}}
    with pytest.raises(RegistryError, match="whitespace"):
        _validate(json.dumps(data))


# ─── required_tools ──────────────────────────────────────────────────────────


def test_t3_13_required_tools_unknown_tool():
    text, import_fn = _make_valid_setup(required_tools=["deploy_to_prod"])
    # Override registry entry
    data = json.loads(text)
    data["skills"]["test_skill"]["required_tools"] = ["deploy_to_prod"]
    text = json.dumps(data)
    with pytest.raises(RegistryError, match="not found in Tool Registry"):
        _validate(text, import_fn=import_fn)


def test_t3_18_required_tools_duplicates():
    text, import_fn = _make_valid_setup(required_tools=["read_file", "read_file"])
    data = json.loads(text)
    data["skills"]["test_skill"]["required_tools"] = ["read_file", "read_file"]
    text = json.dumps(data)
    with pytest.raises(RegistryError, match="duplicate"):
        _validate(text, import_fn=import_fn)


def test_t3_46_required_tools_null():
    text, import_fn = _make_valid_setup()
    data = json.loads(text)
    data["skills"]["test_skill"]["required_tools"] = None
    text = json.dumps(data)
    with pytest.raises(RegistryError, match="null"):
        _validate(text, import_fn=import_fn)


def test_t3_47_required_tools_empty_string_entry():
    text, import_fn = _make_valid_setup(required_tools=["", "read_file"])
    data = json.loads(text)
    data["skills"]["test_skill"]["required_tools"] = ["", "read_file"]
    text = json.dumps(data)
    with pytest.raises(RegistryError, match="invalid entry"):
        _validate(text, import_fn=import_fn)


# ─── Duplicate Detection ────────────────────────────────────────────────────


def test_t3_12_duplicate_skill_name():
    text = '{"schema_version": "1", "skills": {"refactor_code": {}, "refactor_code": {}}}'
    with pytest.raises(ConfigParseError, match="Duplicate key"):
        _validate(text)


# ─── expected_duration_ms ────────────────────────────────────────────────────


def test_t3_15_expected_duration_zero_or_negative():
    text, import_fn = _make_valid_setup(expected_duration_ms=0)
    data = json.loads(text)
    data["skills"]["test_skill"]["expected_duration_ms"] = 0
    text = json.dumps(data)
    with pytest.raises(RegistryError, match="Must be None or > 0"):
        _validate(text, import_fn=import_fn)


def test_t3_38_expected_duration_float():
    text, import_fn = _make_valid_setup()
    data = json.loads(text)
    data["skills"]["test_skill"]["expected_duration_ms"] = 30000.5
    text = json.dumps(data)
    with pytest.raises(RegistryError, match="must be integer"):
        _validate(text, import_fn=import_fn)


# ─── Multi-Error & Stress ───────────────────────────────────────────────────


def test_t3_39_multiple_skills_one_invalid():
    """Full startup failure, not partial."""
    cls1 = make_skill_class(name="skill_a")
    cls2 = make_skill_class(name="skill_b", parameters_schema={})  # Invalid
    import_fn = _make_import_fn({
        "mod_a": {cls1.__name__: cls1},
        "mod_b": {cls2.__name__: cls2},
    })
    skills = {
        "skill_a": _make_skill_entry(name="skill_a", module=f"mod_a.{cls1.__name__}"),
        "skill_b": _make_skill_entry(name="skill_b", module=f"mod_b.{cls2.__name__}"),
    }
    text = _wrap(skills)
    with pytest.raises(RegistryError):
        _validate(text, import_fn=import_fn)


def test_t3_48_100_skills_stress():
    skill_classes = {}
    skills = {}
    for i in range(100):
        name = f"skill_{i}"
        cls = make_skill_class(name=name, description=f"Skill {i}.")
        mod_name = f"mod_{i}"
        skill_classes[mod_name] = {cls.__name__: cls}
        skills[name] = _make_skill_entry(
            name=name, module=f"{mod_name}.{cls.__name__}",
            description=f"Skill {i}."
        )
    import_fn = _make_import_fn(skill_classes)
    text = _wrap(skills)
    result = _validate(text, import_fn=import_fn)
    assert len(result["_loaded_skills"]) == 100


def test_t3_59_two_skills_same_module():
    """Two registry entries pointing to same module, different classes."""
    cls_a = make_skill_class(name="skill_a", description="A.")
    cls_b = make_skill_class(name="skill_b", description="B.")
    import_fn = _make_import_fn({
        "shared_mod": {cls_a.__name__: cls_a, cls_b.__name__: cls_b}
    })
    skills = {
        "skill_a": _make_skill_entry(
            name="skill_a", module=f"shared_mod.{cls_a.__name__}",
            description="A."
        ),
        "skill_b": _make_skill_entry(
            name="skill_b", module=f"shared_mod.{cls_b.__name__}",
            description="B."
        ),
    }
    text = _wrap(skills)
    result = _validate(text, import_fn=import_fn)
    assert len(result["_loaded_skills"]) == 2


def test_t3_21_empty_description_warning():
    text, import_fn = _make_valid_setup(description="")
    data = json.loads(text)
    data["skills"]["test_skill"]["description"] = ""
    text = json.dumps(data)
    result = _validate(text, import_fn=import_fn)
    assert any("empty" in w for w in result["_warnings"])


def test_t3_54_multiple_errors_reported_together():
    """3 skills with different issues; all errors collected."""
    skills = {
        "bad_version": {"version": "1.1", "module": "x.Y",
                        "category": "action", "description": "X", "required_tools": []},
        "bad_category": {"version": "1", "module": "x.Y",
                         "category": "Magic", "description": "X", "required_tools": []},
        "bad_name": {"version": None, "module": "x.Y",
                     "category": "rag", "description": "X", "required_tools": []},
    }
    text = _wrap(skills)
    with pytest.raises(RegistryError) as exc_info:
        _validate(text)
    # Should contain multiple errors
    msg = str(exc_info.value)
    assert "bad_version" in msg or "bad_category" in msg or "bad_name" in msg
