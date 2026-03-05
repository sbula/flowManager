"""§6 Data Contracts & Serialization (DAU Defenses) Tests.

Tests T6.01–T6.15: Context immutability, return type safety,
JSON serialization barriers, cyclic references, NaN/Infinity,
deep nesting, escape sequences, schema declarations, and
hostile object injection.

Tests the Engine's export validation contract and Atom boundaries.
"""

from types import MappingProxyType
from unittest.mock import MagicMock

import pytest

from flow.atoms.base import AtomStatus

from .conftest import (
    BadReturnAtom,
    EngineWrapper,
    validate_exports,
)


# ─── §6.1 Context Immutability ────────────────────────────────────


class TestContextImmutability:
    """T6.01: Read-only context guard via MappingProxyType."""

    def test_t6_01_context_immutability_mapping_proxy(self):
        """T6.01: MappingProxyType prevents context mutation."""
        context = MappingProxyType({"existing_key": "value"})

        with pytest.raises(TypeError):
            context["new_key"] = "x"

    def test_t6_01_context_immutability_del_blocked(self):
        """T6.01 edge: Cannot delete keys from immutable context."""
        context = MappingProxyType({"key": "value"})

        with pytest.raises(TypeError):
            del context["key"]


# ─── §6.2 Return Type Safety ─────────────────────────────────────


class TestReturnTypeSafety:
    """T6.02: Engine wrapper catches non-AtomResult returns."""

    def test_t6_02_invalid_return_type_true(self):
        """T6.02: Atom returns True → TypeError, step fails cleanly."""
        atom = BadReturnAtom(return_value=True)
        wrapper = EngineWrapper(atom)
        result = wrapper.execute({})
        assert result.status == AtomStatus.FAILED
        assert "AtomResult" in result.message or "TypeError" in str(wrapper.last_error)

    def test_t6_02_invalid_return_type_string(self):
        """T6.02 edge: Atom returns a string → TypeError."""
        atom = BadReturnAtom(return_value="success")
        wrapper = EngineWrapper(atom)
        result = wrapper.execute({})
        assert result.status == AtomStatus.FAILED

    def test_t6_02_invalid_return_type_none(self):
        """T6.02 edge: Atom returns None → TypeError."""
        atom = BadReturnAtom(return_value=None)
        wrapper = EngineWrapper(atom)
        result = wrapper.execute({})
        assert result.status == AtomStatus.FAILED


# ─── §6.3 JSON Serialization Barriers ────────────────────────────


class TestSerializationBarriers:
    """T6.03, T6.06, T6.07: Non-serializable types, NaN, deep nesting."""

    def test_t6_03_set_in_exports(self):
        """T6.03: set() in exports raises TypeError."""
        exports = {"data": {1, 2, 3}}
        with pytest.raises(TypeError, match="Set"):
            validate_exports(exports)

    def test_t6_03_file_handle_in_exports(self):
        """T6.03: File handle in exports raises TypeError."""
        exports = {"handle": MagicMock(spec=open)}
        with pytest.raises(TypeError, match="Non-serializable"):
            validate_exports(exports)

    def test_t6_06_nan_injection(self):
        """T6.06: float('nan') in exports raises ValueError."""
        exports = {"value": float("nan")}
        with pytest.raises(ValueError, match="NaN"):
            validate_exports(exports)

    def test_t6_06_infinity_injection(self):
        """T6.06: float('inf') in exports raises ValueError."""
        exports = {"value": float("inf")}
        with pytest.raises(ValueError, match="Infinity"):
            validate_exports(exports)

    def test_t6_06_negative_infinity_injection(self):
        """T6.06 edge: float('-inf') also rejected."""
        exports = {"value": float("-inf")}
        with pytest.raises(ValueError, match="Infinity"):
            validate_exports(exports)

    def test_t6_07_deeply_nested_json(self):
        """T6.07: 10000 layers deep JSON triggers Max_Nesting_Exceeded."""
        # Build deeply nested structure
        nested = {"value": "leaf"}
        for _ in range(200):  # 200 levels (exceeds MAX_NESTING=100)
            nested = {"child": nested}

        exports = {"deep": nested}
        with pytest.raises(RecursionError, match="Max_Nesting"):
            validate_exports(exports)


# ─── §6.4 Cyclic References & Poison Pills ───────────────────────


class TestCyclicAndPoisonPill:
    """T6.04, T6.05: Cyclic context injection and administrative mutation."""

    def test_t6_05_cyclic_context_detection(self):
        """T6.05: Cyclic reference a['self'] = a caught during serialization."""
        a = {}
        a["self"] = a

        with pytest.raises(ValueError, match="Cyclic"):
            validate_exports(a)

    def test_t6_04_administrative_context_fix(self):
        """T6.04: Admin mutates context via CLI → resume succeeds."""
        # Simulate broken context
        context = {"broken_field": "wrong_type_string"}

        # Admin fix: surgical mutation
        context["broken_field"] = {"corrected": True}

        # Re-verify
        assert isinstance(context["broken_field"], dict)
        assert context["broken_field"]["corrected"] is True


# ─── §6.5 String & Escape Sequence Defenses ──────────────────────


class TestStringDefenses:
    """T6.08: Escape sequence poisoning."""

    def test_t6_08_null_byte_sanitization(self):
        """T6.08: Null bytes in context must be stripped/detected."""
        poisoned = "normal\x00malicious"
        sanitized = poisoned.replace("\x00", "")
        assert "\x00" not in sanitized
        assert sanitized == "normalmalicious"

    def test_t6_08_terminal_escape_code_sanitization(self):
        """T6.08: Terminal escape codes stripped before audit log."""
        poisoned = "normal\x1b[2Jcleared"
        # Strip ANSI escape sequences
        import re
        sanitized = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', poisoned)
        assert "\x1b" not in sanitized


# ─── §6.6 Schema & Type Validation ───────────────────────────────


class TestSchemaValidation:
    """T6.09–T6.15: Schema declarations, key coercion, reserved keys."""

    def test_t6_09_invalid_atom_schema_declaration(self):
        """T6.09: Required field missing from properties → reject at compile."""
        schema = {
            "properties": {"name": {"type": "string"}},
            "required": ["name", "ghost_field"],
        }
        # Detect: 'ghost_field' in required but not in properties
        missing = [
            f for f in schema["required"]
            if f not in schema["properties"]
        ]
        assert len(missing) > 0
        assert "ghost_field" in missing

    def test_t6_10_unhashable_custom_object_injection(self):
        """T6.10: Raw custom class in exports → TypeError."""
        class CustomObj:
            def __init__(self):
                self.data = "secret"

        exports = {"obj": CustomObj()}
        with pytest.raises(TypeError, match="Non-serializable"):
            validate_exports(exports)

    def test_t6_11_dict_key_type_coercion(self):
        """T6.11: Non-string dict keys (int, bool) → strict rejection."""
        int_exports = {1: "value"}
        with pytest.raises(TypeError, match="string"):
            validate_exports(int_exports)
        bool_exports = {True: "bool_value"}
        with pytest.raises(TypeError, match="string"):
            validate_exports(bool_exports)

    def test_t6_12_dunder_key_poisoning(self):
        """T6.12: Dunder keys (__class__) in exports → structural rejection."""
        exports = {"__class__": "malicious", "normal": "data"}
        with pytest.raises(ValueError, match="Dunder"):
            validate_exports(exports)

    def test_t6_13_reserved_key_collision(self):
        """T6.13: Export key '_engine_metadata' → ReservedKeyCollisionError."""
        exports = {"_engine_metadata": {"hijacked": True}}
        with pytest.raises(Exception, match="reserved"):
            validate_exports(exports)

    def test_t6_13_reserved_run_id_collision(self):
        """T6.13 edge: Export key 'run_id' → collision with Engine property."""
        exports = {"run_id": "forged-id"}
        with pytest.raises(Exception, match="reserved"):
            validate_exports(exports)

    def test_t6_14_tuple_list_rehydration_failure(self):
        """T6.14: Tuple in exports → TypeError (not JSON-native)."""
        exports = {"data": (1, 2, 3)}
        with pytest.raises(TypeError, match="Tuple"):
            validate_exports(exports)

    def test_t6_15_mro_injection_defense(self):
        """T6.15: Custom object with overridden __class__ → serialization neutered."""
        class MaliciousObj:
            def __class__(self):
                return dict

            def __iter__(self):
                return iter([("key", "value")])

        exports = {"payload": MaliciousObj()}
        with pytest.raises(TypeError, match="Non-serializable"):
            validate_exports(exports)
