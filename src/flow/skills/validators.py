"""Validators for Persona and Skill Registry startup checks.

Implements the validation rules from 01_07 spec §2.3 and §5.2.
"""

import importlib
import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from flow.skills.errors import (
    ConfigParseError,
    SchemaVersionError,
    RegistryError,
    ReservedKeyCollisionError,
)

# --- Constants ---

EXPECTED_SCHEMA_VERSION = "1"

RECOGNIZED_MODEL_PARAMS = frozenset(
    {"temperature", "top_p", "top_k", "max_tokens", "stop_sequences"}
)

RESERVED_CONTEXT_KEYS = frozenset(
    {"status", "run_id", "current_step", "abort_event", "idempotency_token"}
)

MAX_SYSTEM_PROMPT_LENGTH = 8192
DEFAULT_MAX_TOOLS_PER_PERSONA = 30
TOOL_COUNT_WARNING_THRESHOLD = 20
MAX_EXPORTS_SIZE_BYTES = 128 * 1024  # 128KB

VALID_CATEGORIES = frozenset({"reasoning", "action", "rag"})

SKILL_NAME_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]*$")


# --- JSON Helpers ---


def _json_loads_with_duplicate_detection(text: str, filename: str = "<unknown>"):
    """Parse JSON with duplicate key detection (§5.2 step 5)."""

    def _check_pairs(pairs):
        seen = {}
        for key, value in pairs:
            if key in seen:
                raise ConfigParseError(
                    f"Duplicate key '{key}' in {filename}."
                )
            seen[key] = value
        return seen

    try:
        return json.loads(text, object_pairs_hook=_check_pairs)
    except json.JSONDecodeError as e:
        raise ConfigParseError(
            f"Failed to parse {filename} at line {e.lineno}: {e.msg}"
        ) from e


def _validate_schema_version(data: dict, filename: str):
    """Validate schema_version field (§2.3 step 1, §5.2 step 1)."""
    if "schema_version" not in data:
        raise SchemaVersionError(
            f"{filename}: missing 'schema_version' field."
        )
    version = data["schema_version"]
    if not isinstance(version, str):
        raise SchemaVersionError(
            f"{filename}: schema_version must be a string, got {type(version).__name__}."
        )
    if version == "":
        raise SchemaVersionError(
            f"{filename}: schema_version is empty string."
        )
    if version != EXPECTED_SCHEMA_VERSION:
        raise SchemaVersionError(
            f"{filename} version '{version}' is not supported by this Engine "
            f"(expected '{EXPECTED_SCHEMA_VERSION}'). Update the file or downgrade the Engine."
        )


def _validate_integer_version_string(version: Any, context: str) -> str:
    """Validate version is an integer string (§9.6)."""
    if version is None:
        raise ConfigParseError(f"{context}: version is null.")
    if not isinstance(version, str):
        raise ConfigParseError(
            f"{context}: version must be a string, got {type(version).__name__}."
        )
    if version == "":
        raise RegistryError(f"{context}: version is empty string.")
    # Must be a valid non-negative integer string
    if version.startswith("-"):
        raise RegistryError(f"{context}: version '{version}' is negative.")
    try:
        int_val = int(version)
        # Reject leading zeros like '02'
        if version != str(int_val):
            raise RegistryError(
                f"{context}: version '{version}' is not a valid integer string."
            )
    except ValueError:
        raise RegistryError(
            f"{context}: version '{version}' is not a valid integer string."
        )
    return version


# --- Persona Validation Helpers (§2.3) ---


REQUIRED_PERSONA_FIELDS = {"version", "Description", "SystemPrompt", "Focus",
                           "AllowedSkills", "AllowedTools"}


def _validate_personas_container(data: dict, filename: str) -> dict:
    """Validate and return the 'personas' object from parsed data."""
    if "personas" not in data:
        raise ConfigParseError(f"{filename}: missing 'personas' key.")
    personas = data["personas"]
    if personas is None:
        raise ConfigParseError(f"{filename}: 'personas' is null.")
    if not isinstance(personas, dict):
        raise ConfigParseError(
            f"{filename}: 'personas' must be an object, got {type(personas).__name__}."
        )
    return personas


def _validate_persona_fields(persona_def: dict, ctx: str, warnings: list):
    """Validate required fields and field types for a single persona."""
    for field in REQUIRED_PERSONA_FIELDS:
        if field not in persona_def:
            raise ConfigParseError(f"{ctx}: missing required field '{field}'.")

    _validate_integer_version_string(persona_def["version"], ctx)

    description = persona_def.get("Description")
    if not isinstance(description, str):
        raise ConfigParseError(f"{ctx}: 'Description' must be a string.")

    system_prompt = persona_def.get("SystemPrompt")
    if not isinstance(system_prompt, str):
        raise ConfigParseError(f"{ctx}: 'SystemPrompt' must be a string.")
    if len(system_prompt) > MAX_SYSTEM_PROMPT_LENGTH:
        raise RegistryError(
            f"{ctx} SystemPrompt exceeds {MAX_SYSTEM_PROMPT_LENGTH} characters "
            f"(actual: {len(system_prompt)})."
        )
    if system_prompt == "":
        warnings.append(f"{ctx}: SystemPrompt is empty.")

    _validate_nullable_list_field(persona_def, "Focus", ctx)
    _validate_nullable_list_field(persona_def, "AllowedSkills", ctx)
    _validate_nullable_list_field(persona_def, "AllowedTools", ctx)


def _validate_nullable_list_field(persona_def: dict, field: str, ctx: str):
    """Validate a field that must be a non-null list."""
    value = persona_def.get(field)
    if value is None:
        raise ConfigParseError(f"{ctx}: '{field}' is null.")
    if not isinstance(value, list):
        raise ConfigParseError(f"{ctx}: '{field}' must be a list.")


def _validate_skill_name_field(entry: dict, ctx: str):
    """Validate the 'name' field of an AllowedSkills entry."""
    skill_name = entry["name"]
    if skill_name is None or not isinstance(skill_name, str):
        raise RegistryError(f"{ctx}: AllowedSkills entry 'name' must be a non-null string.")
    if skill_name == "":
        raise RegistryError(f"{ctx}: AllowedSkills entry 'name' is empty string.")
    return skill_name


def _validate_skill_version_field(entry: dict, ctx: str):
    """Validate the 'version' field of an AllowedSkills entry."""
    skill_version = entry["version"]
    if skill_version is None:
        raise ConfigParseError(f"{ctx}: AllowedSkills entry 'version' is null.")
    if not isinstance(skill_version, str):
        raise ConfigParseError(
            f"{ctx}: AllowedSkills entry 'version' must be a string, "
            f"got {type(skill_version).__name__}."
        )
    if skill_version == "":
        raise RegistryError(f"{ctx}: AllowedSkills entry 'version' is empty string.")
    return skill_version


def _validate_allowed_skills_entry(entry: Any, ctx: str, warnings: list):
    """Validate a single AllowedSkills entry structure and return (name, version)."""
    if not isinstance(entry, dict):
        raise ConfigParseError(f"{ctx}: AllowedSkills entry must be an object.")
    if "name" not in entry:
        raise ConfigParseError(f"{ctx}: AllowedSkills entry missing 'name' key.")
    if "version" not in entry:
        raise ConfigParseError(f"{ctx}: AllowedSkills entry missing 'version' key.")

    skill_name = _validate_skill_name_field(entry, ctx)
    skill_version = _validate_skill_version_field(entry, ctx)

    known_keys = {"name", "version"}
    extra = set(entry.keys()) - known_keys
    if extra:
        warnings.append(f"{ctx}: AllowedSkills entry has unexpected keys: {extra}.")

    return skill_name, skill_version


def _validate_allowed_skills(
    allowed_skills: list, ctx: str, skill_registry: Dict[str, Any], warnings: list,
) -> list:
    """Validate AllowedSkills entries and return version mismatches."""
    seen_skill_names: Set[str] = set()
    version_mismatches = []

    for entry in allowed_skills:
        skill_name, skill_version = _validate_allowed_skills_entry(entry, ctx, warnings)

        if skill_name in seen_skill_names:
            raise RegistryError(
                f"{ctx} has duplicate AllowedSkills entry '{skill_name}'. "
                "Remove the duplicate."
            )
        seen_skill_names.add(skill_name)

        if skill_name not in skill_registry:
            raise RegistryError(
                f"{ctx} references unknown skill '{skill_name}'. "
                "Register it in skills.registry.json or remove it from AllowedSkills."
            )
        reg_version = skill_registry[skill_name].get("version", "")
        if skill_version != reg_version:
            version_mismatches.append(
                f"{ctx} references skill '{skill_name}' version '{skill_version}' "
                f"(registry has '{reg_version}')"
            )

    return version_mismatches


def _validate_allowed_tools(allowed_tools: list, ctx: str, tool_registry: Set[str]):
    """Validate AllowedTools entries (§2.3 step 3)."""
    seen_tools: Set[str] = set()
    for tool_name in allowed_tools:
        if not isinstance(tool_name, str):
            raise ConfigParseError(
                f"{ctx}: AllowedTools entry must be a string, "
                f"got {type(tool_name).__name__}."
            )
        if tool_name == "" or tool_name.strip() == "":
            raise RegistryError(
                f"{ctx}: AllowedTools entry is empty or whitespace-only."
            )
        if tool_name in seen_tools:
            raise RegistryError(
                f"{ctx} has duplicate AllowedTools entry '{tool_name}'. "
                "Remove the duplicate."
            )
        seen_tools.add(tool_name)

        if tool_name not in tool_registry:
            raise RegistryError(f"{ctx} references unknown tool '{tool_name}'.")


def _validate_tool_counts(
    allowed_skills: list, allowed_tools: list, ctx: str, max_tools: int, warnings: list,
):
    """Validate tool count cap and empty-capability warning (§2.3 steps 4–5)."""
    total_tools = len(allowed_skills) + len(allowed_tools)
    if total_tools > max_tools:
        raise RegistryError(
            f"{ctx} exposes {total_tools} tools, exceeding the hard cap of {max_tools}."
        )
    if total_tools > TOOL_COUNT_WARNING_THRESHOLD:
        warnings.append(
            f"{ctx} exposes {total_tools} tools to the LLM. "
            "Provider accuracy degrades above 20 tools."
        )
    if len(allowed_skills) == 0 and len(allowed_tools) == 0:
        warnings.append(
            f"{ctx} has no AllowedSkills and no AllowedTools. "
            "This agent has no capabilities."
        )


def _validate_model_params(persona_def: dict, ctx: str, warnings: list):
    """Validate model_params (§2.3 step 6) and deprecated Checklist."""
    model_params = persona_def.get("model_params")
    if model_params is not None:
        if not isinstance(model_params, dict):
            raise ConfigParseError(
                f"{ctx}: 'model_params' must be an object, "
                f"got {type(model_params).__name__}."
            )
        for key in model_params:
            if key not in RECOGNIZED_MODEL_PARAMS:
                warnings.append(
                    f"{ctx} has unrecognized model_params key '{key}'. "
                    "Check for typos."
                )

    if "Checklist" in persona_def:
        warnings.append(f"{ctx}: 'Checklist' field is deprecated and ignored.")


# --- Persona Validation (§2.3) ---


def validate_persona_file(
    text: str,
    skill_registry: Dict[str, Any],
    tool_registry: Set[str],
    config: Optional[Dict[str, Any]] = None,
    filename: str = "expert_personas.json",
) -> Dict[str, Any]:
    """Validate persona config JSON and return parsed data.

    Args:
        text: Raw JSON string of the persona file.
        skill_registry: Parsed skill registry {name: {version, ...}}.
        tool_registry: Set of known tool names.
        config: Optional engine config with max_tools_per_persona.
        filename: Filename for error messages.

    Returns:
        Parsed persona data dict.

    Raises:
        ConfigParseError: On structural/parse issues.
        SchemaVersionError: On version mismatches.
        RegistryError: On validation failures.
    """
    if config is None:
        config = {}

    max_tools = config.get("max_tools_per_persona", DEFAULT_MAX_TOOLS_PER_PERSONA)
    warnings: List[str] = []

    data = _json_loads_with_duplicate_detection(text, filename)
    if not isinstance(data, dict):
        raise ConfigParseError(f"{filename}: expected object, got {type(data).__name__}.")

    _validate_schema_version(data, filename)
    personas = _validate_personas_container(data, filename)

    version_mismatches: List[str] = []

    for persona_name, persona_def in personas.items():
        ctx = f"Persona '{persona_name}'"
        if persona_name == "":
            raise ConfigParseError("Persona name is empty string.")
        if not isinstance(persona_def, dict):
            raise ConfigParseError(f"{ctx}: expected object, got {type(persona_def).__name__}.")

        _validate_persona_fields(persona_def, ctx, warnings)

        mismatches = _validate_allowed_skills(
            persona_def["AllowedSkills"], ctx, skill_registry, warnings,
        )
        version_mismatches.extend(mismatches)

        _validate_allowed_tools(persona_def["AllowedTools"], ctx, tool_registry)
        _validate_tool_counts(
            persona_def["AllowedSkills"], persona_def["AllowedTools"],
            ctx, max_tools, warnings,
        )
        _validate_model_params(persona_def, ctx, warnings)

    if version_mismatches:
        raise RegistryError(
            "Persona→Skill version mismatches detected: "
            + "; ".join(version_mismatches)
            + ". Update these Personas in expert_personas.json."
        )

    data["_warnings"] = warnings
    return data


# --- Skill Registry Validation Helpers (§5.2) ---


REQUIRED_SKILL_FIELDS = {"version", "module", "category", "description"}


def _validate_skills_container(data: dict, filename: str) -> dict:
    """Validate and return the 'skills' object from parsed data."""
    if "skills" not in data:
        raise ConfigParseError(f"{filename}: missing 'skills' key.")
    skills = data["skills"]
    if skills is None:
        raise ConfigParseError(f"{filename}: 'skills' is null.")
    if not isinstance(skills, dict):
        raise ConfigParseError(
            f"{filename}: 'skills' must be an object, got {type(skills).__name__}."
        )
    return skills


def _validate_skill_name(skill_name: str, ctx: str) -> Optional[str]:
    """Validate skill name. Returns error string or None."""
    if skill_name == "" or skill_name.strip() != skill_name:
        return f"{ctx}: name is empty or has leading/trailing whitespace."
    if not SKILL_NAME_PATTERN.match(skill_name):
        return f"{ctx}: name contains invalid characters."
    return None


def _validate_skill_fields(
    skill_def: dict, ctx: str, warnings: list,
) -> Optional[str]:
    """Validate version, category, description, module fields. Returns error or None."""
    checks = [
        _validate_skill_version(skill_def, ctx),
        _validate_skill_category(skill_def, ctx),
        _validate_skill_description(skill_def, ctx, warnings),
        _validate_skill_module_path(skill_def, ctx),
    ]
    for error in checks:
        if error is not None:
            return error
    return None


def _validate_skill_version(skill_def: dict, ctx: str) -> Optional[str]:
    """Validate the version field of a skill definition."""
    version = skill_def.get("version")
    if version is None:
        return f"{ctx}: version is null."
    if not isinstance(version, str):
        return f"{ctx}: version must be a string, got {type(version).__name__}."
    if version == "":
        return f"{ctx}: version is empty string."
    try:
        _validate_integer_version_string(version, ctx)
    except (RegistryError, ConfigParseError) as e:
        return str(e)
    return None


def _validate_skill_category(skill_def: dict, ctx: str) -> Optional[str]:
    """Validate the category field of a skill definition."""
    category = skill_def.get("category")
    if category is None:
        return f"{ctx}: category is null."
    if not isinstance(category, str):
        return f"{ctx}: category must be a string."
    if category not in VALID_CATEGORIES:
        return (
            f"{ctx}: category '{category}' is not valid. "
            f"Must be one of: {', '.join(sorted(VALID_CATEGORIES))}."
        )
    return None


def _validate_skill_description(
    skill_def: dict, ctx: str, warnings: list,
) -> Optional[str]:
    """Validate the description field of a skill definition."""
    desc = skill_def.get("description")
    if desc is None:
        return f"{ctx}: description is null."
    if not isinstance(desc, str):
        return f"{ctx}: description must be a string."
    if desc == "":
        warnings.append(f"{ctx}: description is empty.")
    return None


def _validate_skill_module_path(skill_def: dict, ctx: str) -> Optional[str]:
    """Validate the module path field of a skill definition."""
    module_path = skill_def.get("module")
    if module_path is None or not isinstance(module_path, str):
        return f"{ctx}: 'module' must be a non-null string."
    if module_path == "":
        return f"{ctx}: 'module' is empty string."
    if "\\" in module_path or "/" in module_path:
        return f"{ctx}: 'module' must be a dotted Python path, not OS path."
    return None


def _validate_skill_import(
    module_path: str, ctx: str, import_module_fn,
) -> Tuple[Optional[Any], Optional[Any], Optional[str]]:
    """Import module and locate class. Returns (cls, instance, error)."""
    from flow.skills.base import Skill as SkillBase

    try:
        parts = module_path.rsplit(".", 1)
        if len(parts) != 2:
            return None, None, f"{ctx}: module path '{module_path}' must be 'package.ClassName'."
        mod_path, class_name = parts
        mod = import_module_fn(mod_path)
        cls = getattr(mod, class_name, None)
        if cls is None:
            return None, None, f"{ctx}: class '{class_name}' not found in module '{mod_path}'."
    except Exception as e:
        return None, None, f"{ctx}: ImportError — {e}"

    if not (isinstance(cls, type) and issubclass(cls, SkillBase)):
        return None, None, f"{ctx}: {class_name} is not a subclass of Skill."

    try:
        instance = cls()
    except Exception as e:
        return None, None, f"{ctx}: instantiation failed — {e}"

    return cls, instance, None


def _validate_skill_metadata(
    instance: Any, skill_name: str, version: str, desc: str, ctx: str,
) -> list:
    """Cross-validate instance metadata vs registry. Returns list of errors."""
    errors = []

    try:
        cls_name = instance.name
    except Exception as e:
        return [f"{ctx}: name property raised — {e}"]
    if cls_name != skill_name:
        errors.append(f"{ctx}: class name '{cls_name}' does not match registry key '{skill_name}'.")

    try:
        cls_version = instance.version
    except Exception as e:
        return errors + [f"{ctx}: version property raised — {e}"]
    if cls_version != version:
        errors.append(f"{ctx}: class version '{cls_version}' does not match registry '{version}'.")

    try:
        cls_desc = instance.description
    except Exception as e:
        return errors + [f"{ctx}: description property raised — {e}"]
    if cls_desc != desc:
        errors.append(f"{ctx}: class description does not match registry description.")

    return errors


def _validate_tool_entries(
    req_tools: list, ctx: str,
) -> list:
    """Validate individual entries in required_tools list."""
    errors = []
    seen: Set[str] = set()
    for t in req_tools:
        if not isinstance(t, str) or t == "":
            errors.append(f"{ctx}: required_tools contains invalid entry '{t}'.")
            break
        if t in seen:
            errors.append(f"{ctx}: duplicate in required_tools: '{t}'.")
            break
        seen.add(t)
    return errors


def _validate_required_tools(
    skill_def: dict, instance: Any, ctx: str, tool_registry: Set[str],
) -> Tuple[list, bool]:
    """Validate required_tools. Returns (errors, should_continue)."""
    req_tools = skill_def.get("required_tools", [])
    if req_tools is None:
        return [f"{ctx}: 'required_tools' is null (must be list or omitted)."], True
    if not isinstance(req_tools, list):
        return [f"{ctx}: 'required_tools' must be a list."], True

    errors = _validate_tool_entries(req_tools, ctx)

    try:
        cls_tools = set(instance.required_tools)
    except Exception as e:
        return errors + [f"{ctx}: required_tools property raised — {e}"], True

    if cls_tools != set(req_tools):
        errors.append(
            f"{ctx}: class required_tools {cls_tools} does not match "
            f"registry {set(req_tools)}."
        )

    for t in req_tools:
        if t not in tool_registry:
            errors.append(f"{ctx}: required tool '{t}' not found in Tool Registry.")

    return errors, False


def _validate_parameters_schema(instance: Any, ctx: str) -> Tuple[list, bool]:
    """Validate parameters_schema. Returns (errors, should_continue)."""
    errors = []
    try:
        schema = instance.parameters_schema
    except Exception as e:
        return [f"{ctx}: parameters_schema property raised — {e}"], True

    if schema is None:
        return [f"{ctx}: parameters_schema is None."], True
    if not isinstance(schema, dict):
        return [f"{ctx}: parameters_schema must be a dict."], True
    if schema.get("type") != "object":
        return [
            f"{ctx}: parameters_schema must have type 'object', "
            f"got '{schema.get('type')}'."
        ], True
    if schema.get("additionalProperties") is not False:
        errors.append(f"{ctx}: parameters_schema must set additionalProperties: false.")

    schema_str = json.dumps(schema)
    if '"$ref"' in schema_str:
        ref_pattern = re.compile(r'"\$ref"\s*:\s*"(https?://|file://)')
        if ref_pattern.search(schema_str):
            errors.append(f"{ctx}: parameters_schema contains external $ref (security risk).")

    return errors, False


def _validate_expected_duration(
    instance: Any, skill_def: dict, ctx: str,
) -> Tuple[list, bool]:
    """Validate expected_duration_ms. Returns (errors, should_continue)."""
    errors = []
    try:
        duration = instance.expected_duration_ms
    except Exception as e:
        return [f"{ctx}: expected_duration_ms property raised — {e}"], True

    if duration is not None:
        if not isinstance(duration, int) or isinstance(duration, bool):
            errors.append(f"{ctx}: expected_duration_ms must be int or None.")
        elif duration <= 0:
            errors.append(f"{ctx}: expected_duration_ms={duration}. Must be None or > 0.")

    exp_dur_ms = skill_def.get("expected_duration_ms")
    if exp_dur_ms is not None:
        if not isinstance(exp_dur_ms, int) or isinstance(exp_dur_ms, bool):
            errors.append(f"{ctx}: expected_duration_ms must be integer.")
        elif exp_dur_ms <= 0:
            errors.append(f"{ctx}: expected_duration_ms={exp_dur_ms}. Must be None or > 0.")

    return errors, False


# --- Skill Registry Validation (§5.2) ---


def validate_skill_registry(
    text: str,
    tool_registry: Set[str],
    filename: str = "skills.registry.json",
    import_module_fn=None,
) -> Dict[str, Any]:
    """Validate skill registry JSON and return parsed data.

    Args:
        text: Raw JSON string of the registry file.
        tool_registry: Set of available tool names.
        filename: Filename for error messages.
        import_module_fn: Optional override for importlib.import_module (for testing).

    Returns:
        Parsed registry data dict including imported Skill classes.

    Raises:
        ConfigParseError: On structural/parse issues.
        SchemaVersionError: On version mismatches.
        RegistryError: On validation failures.
    """
    if import_module_fn is None:
        import_module_fn = importlib.import_module

    data = _json_loads_with_duplicate_detection(text, filename)
    if not isinstance(data, dict):
        raise ConfigParseError(f"{filename}: expected object, got {type(data).__name__}.")

    _validate_schema_version(data, filename)
    skills = _validate_skills_container(data, filename)

    errors: List[str] = []
    warnings: List[str] = []
    loaded_skills: Dict[str, Any] = {}

    for skill_name, skill_def in skills.items():
        ctx = f"Skill '{skill_name}'"
        skill_errors = _validate_single_skill(
            skill_name, skill_def, ctx, tool_registry, import_module_fn,
            warnings, loaded_skills,
        )
        errors.extend(skill_errors)

    if errors:
        raise RegistryError("Skill Registry validation failed:\n" + "\n".join(errors))

    data["_loaded_skills"] = loaded_skills
    data["_warnings"] = warnings
    return data


def _validate_single_skill(
    skill_name: str, skill_def: Any, ctx: str,
    tool_registry: Set[str], import_module_fn,
    warnings: list, loaded_skills: dict,
) -> list:
    """Validate a single skill entry. Returns list of errors."""
    if not isinstance(skill_def, dict):
        return [f"{ctx}: expected object."]

    name_err = _validate_skill_name(skill_name, ctx)
    if name_err:
        return [name_err]

    for field in REQUIRED_SKILL_FIELDS:
        if field not in skill_def:
            return [f"{ctx}: missing required field '{field}'."]

    fields_err = _validate_skill_fields(skill_def, ctx, warnings)
    if fields_err:
        return [fields_err]

    module_path = skill_def["module"]
    cls, instance, import_err = _validate_skill_import(module_path, ctx, import_module_fn)
    if import_err:
        return [import_err]

    errors = _validate_skill_metadata(
        instance, skill_name, skill_def["version"], skill_def["description"], ctx,
    )

    tool_errors, should_stop = _validate_required_tools(skill_def, instance, ctx, tool_registry)
    errors.extend(tool_errors)
    if should_stop:
        return errors

    schema_errors, should_stop = _validate_parameters_schema(instance, ctx)
    errors.extend(schema_errors)
    if should_stop:
        return errors

    dur_errors, should_stop = _validate_expected_duration(instance, skill_def, ctx)
    errors.extend(dur_errors)
    if should_stop:
        return errors

    loaded_skills[skill_name] = {
        "instance": instance,
        "class": cls,
        "definition": skill_def,
    }

    return errors


# --- SkillResult Validation Helpers (§4) ---


def _validate_result_exports(result: Any, reserved_keys: Set[str]) -> list:
    """Validate exports size and reserved key collisions. Returns warnings."""
    warnings: List[str] = []
    if not result.exports:
        return warnings

    exports_json = json.dumps(result.exports)
    if len(exports_json.encode("utf-8")) > MAX_EXPORTS_SIZE_BYTES:
        raise RegistryError(
            f"Exports exceed {MAX_EXPORTS_SIZE_BYTES} byte limit."
        )

    for key in result.exports:
        bare_key = key.split(":")[-1] if ":" in key else key
        if bare_key in reserved_keys and not key.startswith("skill:"):
            raise ReservedKeyCollisionError(
                f"Export key '{key}' shadows reserved Engine key '{bare_key}'."
            )

    return warnings


def _validate_result_error(result: Any) -> list:
    """Validate error dict structure. Returns warnings."""
    warnings: List[str] = []
    if result.error is None:
        return warnings

    if isinstance(result.error, str):
        warnings.append("SkillResult.error is a string, not a dict. Wrapping.")
        result.error = {"message": result.error}
    elif isinstance(result.error, dict):
        if "code" not in result.error:
            warnings.append("SkillResult.error dict missing 'code' key.")
        elif result.error["code"] == "":
            warnings.append("SkillResult.error has empty 'code' string.")
        if "message" not in result.error:
            warnings.append("SkillResult.error dict missing 'message' key.")

    return warnings


# --- SkillResult Validation (§4) ---


def validate_skill_result(
    result: Any,
    reserved_keys: Set[str] = None,
) -> list:
    """Validate a SkillResult from a Skill execution.

    Returns list of warnings. Raises on hard errors.
    """
    from flow.skills.result import SkillResult, SkillStatus

    if reserved_keys is None:
        reserved_keys = RESERVED_CONTEXT_KEYS

    if result is None:
        raise TypeError("execute() returned None instead of SkillResult.")

    if not isinstance(result, SkillResult):
        raise TypeError(
            f"execute() returned {type(result).__name__} instead of SkillResult."
        )

    if not isinstance(result.status, SkillStatus):
        raise ValueError(
            f"SkillResult.status must be a SkillStatus enum, got {type(result.status).__name__}."
        )

    warnings: List[str] = []

    if result.status == SkillStatus.SUCCESS and result.error is not None:
        warnings.append(
            f"Skill '{result.skill_name}' returned SUCCESS with a non-null error field. "
            "The error field will be discarded."
        )
        result.error = None

    warnings.extend(_validate_result_exports(result, reserved_keys))
    warnings.extend(_validate_result_error(result))

    return warnings
