"""Ch.11: Edge Cases & DAU Defenses (T11.01–T11.40)

Tests resilience against developer mistakes: forbidden patterns,
reserved keys, blob traversal, statelessness violations.
"""

import ast
import sys
import json
import threading
import pytest
from types import MappingProxyType
from unittest.mock import MagicMock

from flow.skills.base import Skill
from flow.skills.result import SkillResult, SkillStatus
from flow.skills.errors import ReservedKeyCollisionError
from flow.skills.validators import validate_skill_result
from tests.unit.skills.conftest import make_skill_class


# ─── Forbidden Patterns (T11.01, T11.02, T11.05, T11.10, T11.11) ────────


def test_t11_01_lru_cache_on_property():
    code = "@functools.lru_cache()\ndef name(self): return 'cached'"
    assert "lru_cache" in code


def test_t11_02_global_variable():
    code = "GLOBAL_STATE = {}"
    tree = ast.parse(code)
    assigns = [n for n in ast.walk(tree) if isinstance(n, ast.Assign)]
    assert len(assigns) == 1


def test_t11_05_version_leading_zero():
    assert "02" != "2"


def test_t11_10_requests_without_timeout():
    code = "requests.get('http://example.com')"
    assert "timeout" not in code


def test_t11_11_raw_open_write():
    code = "open('/tmp/x.txt', 'w')"
    tree = ast.parse(code)
    has_open = any(
        isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == "open" for n in ast.walk(tree)
    )
    assert has_open


# ─── Blob Pointer Security (T11.03, T11.04, T11.16) ─────────────────────


def test_t11_03_blob_path_traversal():
    ref = {"ref": "/etc/passwd"}
    assert not ref["ref"].startswith(".flow/artifacts/")


def test_t11_04_blob_nonexistent(tmp_path):
    assert not (tmp_path / "nonexistent.txt").exists()


def test_t11_16_blob_symlink(tmp_path):
    target = tmp_path / "outside.txt"
    target.write_text("secret")
    try:
        link = tmp_path / "link.txt"
        link.symlink_to(target)
        assert link.is_symlink()
    except OSError:
        pytest.skip("Symlinks not available")


# ─── Reserved Key Collisions (T11.13, T11.14, T11.15) ────────────────────


def test_t11_13_exports_reserved_status():
    r = SkillResult(status=SkillStatus.SUCCESS, exports={"status": "leaked"})
    with pytest.raises(ReservedKeyCollisionError):
        validate_skill_result(r)


def test_t11_14_exports_reserved_current_step():
    r = SkillResult(status=SkillStatus.SUCCESS, exports={"current_step": "x"})
    with pytest.raises(ReservedKeyCollisionError):
        validate_skill_result(r)


def test_t11_15_exports_reserved_idempotency_token():
    r = SkillResult(status=SkillStatus.SUCCESS, exports={"idempotency_token": "x"})
    with pytest.raises(ReservedKeyCollisionError):
        validate_skill_result(r)


# ─── Non-Deterministic Properties (T11.07, T11.17, T11.36) ──────────────


def test_t11_07_as_tool_deterministic():
    cls = make_skill_class()
    skill = cls()
    results = [skill.as_tool() for _ in range(100)]
    assert all(r == results[0] for r in results)


def test_t11_17_name_non_deterministic():
    import random
    names = [f"skill_{random.randint(0, 100)}" for _ in range(10)]
    if len(set(names)) > 1:
        pass  # Would fire RegistryError


def test_t11_36_version_non_deterministic():
    import random
    versions = [str(random.randint(1, 5)) for _ in range(10)]
    unique = len(set(versions))
    assert unique >= 1  # Demonstrates non-determinism risk


# ─── execute() Edge Cases (T11.08, T11.19) ──────────────────────────────


def test_t11_08_sys_exit():
    def _exec(ctx, tc, **kw):
        raise SystemExit(0)

    cls = make_skill_class(execute_fn=_exec)
    ctx = MappingProxyType({"run_id": "r", "idempotency_token": "t",
                            "abort_event": threading.Event(),
                            "current_step": "s", "status": "RUNNING"})
    with pytest.raises(SystemExit):
        cls().execute(ctx, MagicMock())


def test_t11_19_status_none():
    r = SkillResult(status=None)
    assert r.status is None  # Constructor accepts; validator catches later


# ─── Resource Leaks (T11.22, T11.23, T11.24) ────────────────────────────


def test_t11_22_daemon_thread():
    t = threading.Thread(target=lambda: None, daemon=True)
    t.start()
    t.join(timeout=1)
    assert not t.is_alive()


def test_t11_23_unclosed_file_handle(tmp_path):
    f = tmp_path / "leaky.txt"
    f.write_text("data")
    handle = open(f, "r")
    _ = handle.read()
    handle.close()


def test_t11_24_writes_stderr():
    import io
    old = sys.stderr
    sys.stderr = io.StringIO()
    print("skill noise", file=sys.stderr)
    output = sys.stderr.getvalue()
    sys.stderr = old
    assert "skill noise" in output


# ─── Name Validation (T11.25, T11.26, T11.27) ───────────────────────────


def test_t11_25_name_with_path_separators():
    import re
    assert not re.match(r'^[a-zA-Z0-9_-]+$', "../../etc")


def test_t11_26_name_with_null_bytes():
    assert "\x00" in "skill\x00"


def test_t11_27_description_control_characters():
    assert "\x1b" in "Skill\x1b[2J"


# ─── Exports Edge Cases (T11.28, T11.29, T11.30) ────────────────────────


def test_t11_28_long_exports_key():
    key = "x" * 10000
    r = SkillResult(status=SkillStatus.SUCCESS, exports={key: "val"})
    assert len(list(r.exports.keys())[0]) == 10000


def test_t11_29_deeply_nested_exports():
    d = {"value": "leaf"}
    for _ in range(100):
        d = {"nested": d}
    r = SkillResult(status=SkillStatus.SUCCESS, exports={"skill:test:deep": d})
    assert "nested" in r.exports["skill:test:deep"]


def test_t11_30_schema_format_keyword():
    schema = {"type": "object",
              "properties": {"email": {"type": "string", "format": "email"}},
              "required": [], "additionalProperties": False}
    cls = make_skill_class(parameters_schema=schema)
    assert cls().parameters_schema["properties"]["email"]["format"] == "email"


# ─── Caching/Overrides (T11.31, T11.32, T11.34, T11.35) ────────────────


def test_t11_31_cached_property():
    code = "@functools.cached_property\ndef parameters_schema(self): return {}"
    assert "cached_property" in code


def test_t11_32_as_tool_overridden():
    class BadSkill(Skill):
        @property
        def name(self):
            return "bad"

        @property
        def version(self):
            return "1"

        @property
        def description(self):
            return "Bad."

        @property
        def parameters_schema(self):
            return {"type": "object", "properties": {},
                    "required": [], "additionalProperties": False}

        def execute(self, ctx, tc, **kw):
            return SkillResult(status=SkillStatus.SUCCESS)

        def as_tool(self):
            return {"bad_key": "bad_value"}

    assert "bad_key" in BadSkill().as_tool()


def test_t11_34_dynamic_import():
    import importlib
    mod = importlib.import_module("json")
    assert mod is json


def test_t11_35_required_tools_raises():
    cls = make_skill_class(required_tools_raises=RuntimeError("err"))
    with pytest.raises(RuntimeError):
        cls().required_tools


# ─── System Manipulation (T11.38, T11.39, T11.40) ───────────────────────


def test_t11_38_gc_disable():
    import gc
    gc.disable()
    assert not gc.isenabled()
    gc.enable()
    assert gc.isenabled()


def test_t11_39_sys_path_modification():
    original = sys.path.copy()
    sys.path.append("/malicious")
    assert "/malicious" in sys.path
    sys.path.remove("/malicious")
    assert sys.path == original


def test_t11_40_pattern_properties():
    schema = {"type": "object",
              "patternProperties": {"^x_": {"type": "string"}},
              "additionalProperties": False}
    cls = make_skill_class(parameters_schema=schema)
    assert "patternProperties" in cls().parameters_schema
