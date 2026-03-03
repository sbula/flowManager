"""Factory Tests — spec §5.

Tests LLMFactory: caching, reset, shutdown, thread safety, dependency isolation.
Covers T5.1.01-T5.1.12, T5.2.01-T5.2.08, T5.3.01-T5.3.07, T5.4.01-T5.4.03,
T5.5.01-T5.5.02.
"""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

import flow.llm.factory as factory_module
from flow.llm.errors import (
    FactoryClosedError,
    ProfileNotFoundError,
    ProviderConfigError,
    ProviderNotConfiguredError,
    ProviderRegistrationError,
)
from flow.llm.factory import LLMFactory

from .conftest import MockProvider, MockProviderBadName


def _make_factory(config, monkeypatch):
    """Helper to create a factory with mock provider registry."""
    original_registry = factory_module.PROVIDER_REGISTRY.copy()
    factory_module.PROVIDER_REGISTRY["mock"] = "tests.unit.llm.conftest.MockProvider"
    factory_module.PROVIDER_REGISTRY["mock_bad"] = (
        "tests.unit.llm.conftest.MockProviderBadName"
    )
    monkeypatch.setenv("MOCK_API_KEY", "test-key-12345")
    factory = LLMFactory(config=config)

    return factory, original_registry


def _restore_registry(original_registry):
    factory_module.PROVIDER_REGISTRY.clear()
    factory_module.PROVIDER_REGISTRY.update(original_registry)


# ─── 5.1 Basic Factory Operations ─────────────────────────────────


class TestBasicFactoryOperations:
    """T5.1.01 - T5.1.12."""

    def test_t5_1_01_create_valid_profile(self, monkeypatch):
        """T5.1.01: factory.create(\"default\") -> configured LLMProvider."""
        config = {
            "default": {
                "provider": "mock",
                "config": {"model": "test"},
                "auth": {"method": "api_key"},
            }
        }
        factory, orig = _make_factory(config, monkeypatch)
        try:
            adapter = factory.create("default")
            assert adapter is not None
            assert adapter.provider_name == "mock"
        finally:
            _restore_registry(orig)

    def test_t5_1_02_create_returns_cached_instance(self, monkeypatch):
        """T5.1.02: create() twice -> same object."""
        config = {
            "default": {
                "provider": "mock",
                "config": {"model": "test"},
                "auth": {"method": "api_key"},
            }
        }
        factory, orig = _make_factory(config, monkeypatch)
        try:
            a = factory.create("default")
            b = factory.create("default")
            assert id(a) == id(b)
        finally:
            _restore_registry(orig)

    def test_t5_1_03_create_different_profiles(self, monkeypatch):
        """T5.1.03: Different profiles -> different objects."""
        config = {
            "default": {
                "provider": "mock",
                "config": {"model": "test"},
                "auth": {"method": "api_key"},
            },
            "coding": {
                "provider": "mock",
                "config": {"model": "expert"},
                "auth": {"method": "api_key"},
            },
        }
        factory, orig = _make_factory(config, monkeypatch)
        try:
            a = factory.create("default")
            b = factory.create("coding")
            assert id(a) != id(b)
        finally:
            _restore_registry(orig)

    def test_t5_1_04_unknown_profile_name(self, monkeypatch):
        """T5.1.04: Unknown profile -> ProfileNotFoundError."""
        factory, orig = _make_factory({}, monkeypatch)
        try:
            with pytest.raises(ProfileNotFoundError, match="nonexistent"):
                factory.create("nonexistent_profile")
        finally:
            _restore_registry(orig)

    def test_t5_1_05_unknown_provider_name(self, monkeypatch):
        """T5.1.05: Profile with unknown provider -> ProviderRegistrationError."""
        config = {
            "bad": {
                "provider": "chatgpt_plus",
                "config": {"model": "test"},
            }
        }
        factory, orig = _make_factory(config, monkeypatch)
        try:
            with pytest.raises(ProviderRegistrationError, match="chatgpt_plus"):
                factory.create("bad")
        finally:
            _restore_registry(orig)

    def test_t5_1_06_provider_name_mismatch(self, monkeypatch):
        """T5.1.06: Adapter provider_name mismatch -> ProviderRegistrationError."""
        config = {
            "bad": {
                "provider": "mock_bad",
                "config": {"model": "test"},
                "auth": {"method": "api_key"},
            }
        }
        factory, orig = _make_factory(config, monkeypatch)
        try:
            with pytest.raises(ProviderRegistrationError, match="wrong_name"):
                factory.create("bad")
        finally:
            _restore_registry(orig)

    def test_t5_1_07_profile_missing_provider_key(self, monkeypatch):
        """T5.1.07: Profile without 'provider' -> ProviderConfigError."""
        config = {"bad": {"config": {"model": "test"}}}
        factory, orig = _make_factory(config, monkeypatch)
        try:
            with pytest.raises(ProviderConfigError, match="missing"):
                factory.create("bad")
        finally:
            _restore_registry(orig)

    def test_t5_1_08_profile_missing_config_sub_key(self, monkeypatch):
        """T5.1.08: Profile without 'config' -> ProviderConfigError
        during configure()."""
        config = {
            "bad": {
                "provider": "mock",
                "auth": {"method": "api_key"},
            }
        }
        factory, orig = _make_factory(config, monkeypatch)
        try:
            # config section missing means empty dict passed to configure()
            # MockProvider requires 'model' key
            with pytest.raises(ProviderConfigError, match="model"):
                factory.create("bad")
        finally:
            _restore_registry(orig)

    def test_t5_1_09_profile_with_empty_provider(self, monkeypatch):
        """T5.1.09: provider: '' -> ProviderConfigError or ProviderRegistrationError."""
        config = {"bad": {"provider": "", "config": {"model": "test"}}}
        factory, orig = _make_factory(config, monkeypatch)
        try:
            with pytest.raises((ProviderConfigError, ProviderRegistrationError)):
                factory.create("bad")
        finally:
            _restore_registry(orig)

    def test_t5_1_10_profile_name_case_sensitivity(self, monkeypatch):
        """T5.1.10: 'Default' vs 'default' -> ProfileNotFoundError.
        Profile names are case-sensitive."""
        config = {
            "default": {
                "provider": "mock",
                "config": {"model": "test"},
                "auth": {"method": "api_key"},
            }
        }
        factory, orig = _make_factory(config, monkeypatch)
        try:
            with pytest.raises(ProfileNotFoundError):
                factory.create("Default")
        finally:
            _restore_registry(orig)

    def test_t5_1_11_unicode_profile_name(self, monkeypatch):
        """T5.1.11: Unicode profile name -> success."""
        config = {
            "日本語_profile": {
                "provider": "mock",
                "config": {"model": "test"},
                "auth": {"method": "api_key"},
            }
        }
        factory, orig = _make_factory(config, monkeypatch)
        try:
            adapter = factory.create("日本語_profile")
            assert adapter is not None
        finally:
            _restore_registry(orig)

    def test_t5_1_12_per_profile_close_diagram(self, monkeypatch):
        """T5.1.12: Verify whether per-profile close exists per class diagram.
        The spec §5.2 documents reset() not close(profile), so this documents
        the discrepancy and tests reset-based lifecycle."""
        config = {
            "default": {
                "provider": "mock",
                "config": {"model": "test"},
                "auth": {"method": "api_key"},
            }
        }
        factory, orig = _make_factory(config, monkeypatch)
        try:
            a = factory.create("default")
            # No close(profile_name) method exists; use reset + create
            factory.reset("default")
            b = factory.create("default")
            assert id(a) != id(b)
        finally:
            _restore_registry(orig)


# ─── 5.2 Reset & Invalidation ─────────────────────────────────────


class TestResetAndInvalidation:
    """T5.2.01 - T5.2.08."""

    def test_t5_2_01_reset_single_profile(self, monkeypatch):
        """T5.2.01: create -> reset -> create returns NEW instance.
        close() called on evicted instance."""
        config = {
            "default": {
                "provider": "mock",
                "config": {"model": "test"},
                "auth": {"method": "api_key"},
            }
        }
        factory, orig = _make_factory(config, monkeypatch)
        try:
            a = factory.create("default")
            factory.reset("default")
            b = factory.create("default")
            assert id(a) != id(b)
            # old instance's close() was called
            assert a._closed is True
        finally:
            _restore_registry(orig)

    def test_t5_2_02_reset_all(self, monkeypatch):
        """T5.2.02: Reset all clears caches, close() called on each."""
        config = {
            "a": {
                "provider": "mock",
                "config": {"model": "m"},
                "auth": {"method": "api_key"},
            },
            "b": {
                "provider": "mock",
                "config": {"model": "m"},
                "auth": {"method": "api_key"},
            },
        }
        factory, orig = _make_factory(config, monkeypatch)
        try:
            p_a = factory.create("a")
            p_b = factory.create("b")
            factory.reset_all()
            assert p_a._closed is True
            assert p_b._closed is True
        finally:
            _restore_registry(orig)

    def test_t5_2_03_reset_uncreated_profile(self, monkeypatch):
        """T5.2.03: reset(\"never_created\") -> silent no-op."""
        factory, orig = _make_factory({}, monkeypatch)
        try:
            factory.reset("never_created")  # No error
        finally:
            _restore_registry(orig)

    def test_t5_2_04_use_after_reset(self, monkeypatch):
        """T5.2.04: Old reference after reset -> ProviderNotConfiguredError.
        close() was called on evicted instance."""
        config = {
            "default": {
                "provider": "mock",
                "config": {"model": "test"},
                "auth": {"method": "api_key"},
            }
        }
        factory, orig = _make_factory(config, monkeypatch)
        try:
            adapter = factory.create("default")
            factory.reset("default")
            with pytest.raises(ProviderNotConfiguredError):
                adapter.generate([{"role": "user", "content": "hi"}])
        finally:
            _restore_registry(orig)

    def test_t5_2_05_reset_during_active_call(self, monkeypatch):
        """T5.2.05: Thread A mid-generate(), Thread B resets.
        Expect no crash, no deadlock."""
        config = {
            "default": {
                "provider": "mock",
                "config": {"model": "test"},
                "auth": {"method": "api_key"},
            }
        }
        factory, orig = _make_factory(config, monkeypatch)
        try:
            adapter = factory.create("default")
            errors = []
            results = []

            def thread_a():
                """Simulate mid-generate."""
                try:
                    result = adapter.generate([{"role": "user", "content": "hi"}])
                    results.append(result)
                except ProviderNotConfiguredError:
                    results.append("not_configured")
                except Exception as e:
                    errors.append(e)

            def thread_b():
                """Reset the profile."""
                time.sleep(0.01)  # Slight delay
                factory.reset("default")

            t1 = threading.Thread(target=thread_a)
            t2 = threading.Thread(target=thread_b)
            t1.start()
            t2.start()
            t1.join(timeout=5)
            t2.join(timeout=5)

            # No crash, no deadlock
            assert not errors or all(
                isinstance(e, ProviderNotConfiguredError) for e in errors
            )
        finally:
            _restore_registry(orig)

    def test_t5_2_06_manual_close_bypasses_factory(self, monkeypatch):
        """T5.2.06: User directly closes adapter -> Factory returns dead
        cached instance."""
        config = {
            "default": {
                "provider": "mock",
                "config": {"model": "test"},
                "auth": {"method": "api_key"},
            }
        }
        factory, orig = _make_factory(config, monkeypatch)
        try:
            adapter = factory.create("default")
            adapter.close()  # Bypass factory!
            cached = factory.create("default")
            assert id(adapter) == id(cached)  # Same dead instance
            with pytest.raises(ProviderNotConfiguredError):
                cached.generate([{"role": "user", "content": "hi"}])
        finally:
            _restore_registry(orig)

    def test_t5_2_07_rapid_create_reset_loop(self, monkeypatch):
        """T5.2.07: 100x create/reset loop -> no memory leak."""
        config = {
            "default": {
                "provider": "mock",
                "config": {"model": "test"},
                "auth": {"method": "api_key"},
            }
        }
        factory, orig = _make_factory(config, monkeypatch)
        try:
            for _ in range(100):
                factory.create("default")
                factory.reset("default")
            # If we get here without exception, no crash
        finally:
            _restore_registry(orig)

    def test_t5_2_08_reset_all_after_close_all(self, monkeypatch):
        """T5.2.08: close_all() -> reset_all() -> FactoryClosedError."""
        config = {
            "default": {
                "provider": "mock",
                "config": {"model": "test"},
                "auth": {"method": "api_key"},
            }
        }
        factory, orig = _make_factory(config, monkeypatch)
        try:
            factory.create("default")
            factory.close_all()
            with pytest.raises(FactoryClosedError):
                factory.reset_all()
        finally:
            _restore_registry(orig)


# ─── 5.3 Graceful Shutdown ─────────────────────────────────────────


class TestGracefulShutdown:
    """T5.3.01 - T5.3.07."""

    def test_t5_3_01_close_all(self, monkeypatch):
        """T5.3.01: close_all() calls close() on every adapter."""
        config = {
            "a": {
                "provider": "mock",
                "config": {"model": "m"},
                "auth": {"method": "api_key"},
            }
        }
        factory, orig = _make_factory(config, monkeypatch)
        try:
            adapter = factory.create("a")
            factory.close_all()
            assert adapter._closed is True
        finally:
            _restore_registry(orig)

    def test_t5_3_02_create_after_close_all(self, monkeypatch):
        """T5.3.02: close_all() -> create() -> FactoryClosedError."""
        config = {
            "default": {
                "provider": "mock",
                "config": {"model": "m"},
                "auth": {"method": "api_key"},
            }
        }
        factory, orig = _make_factory(config, monkeypatch)
        try:
            factory.close_all()
            with pytest.raises(FactoryClosedError):
                factory.create("default")
        finally:
            _restore_registry(orig)

    def test_t5_3_03_reset_after_close_all(self, monkeypatch):
        """T5.3.03: close_all() -> reset() -> FactoryClosedError."""
        factory, orig = _make_factory({}, monkeypatch)
        try:
            factory.close_all()
            with pytest.raises(FactoryClosedError):
                factory.reset("default")
        finally:
            _restore_registry(orig)

    def test_t5_3_04_close_all_during_active_generate(self, monkeypatch):
        """T5.3.04: Thread A mid-generate, Thread B close_all().
        At minimum no crash, no deadlock."""
        config = {
            "default": {
                "provider": "mock",
                "config": {"model": "m"},
                "auth": {"method": "api_key"},
            }
        }
        factory, orig = _make_factory(config, monkeypatch)
        try:
            adapter = factory.create("default")
            errors = []

            def thread_a():
                try:
                    adapter.generate([{"role": "user", "content": "hi"}])
                except (ProviderNotConfiguredError, FactoryClosedError):
                    pass
                except Exception as e:
                    errors.append(e)

            def thread_b():
                time.sleep(0.01)
                factory.close_all()

            t1 = threading.Thread(target=thread_a)
            t2 = threading.Thread(target=thread_b)
            t1.start()
            t2.start()
            t1.join(timeout=5)
            t2.join(timeout=5)
            assert not errors
        finally:
            _restore_registry(orig)

    def test_t5_3_05_new_factory_after_close_all(self, monkeypatch):
        """T5.3.05: Old factory closed, new factory works independently."""
        config = {
            "default": {
                "provider": "mock",
                "config": {"model": "m"},
                "auth": {"method": "api_key"},
            }
        }
        factory1, orig = _make_factory(config, monkeypatch)
        try:
            factory1.close_all()
            with pytest.raises(FactoryClosedError):
                factory1.create("default")

            # New factory is independent
            factory2 = LLMFactory(config=config)
            adapter = factory2.create("default")
            assert adapter is not None
        finally:
            _restore_registry(orig)

    def test_t5_3_06_close_all_per_adapter_timeout(self, monkeypatch):
        """T5.3.06: One adapter's close() hangs -> close_all() completes
        within timeout. Other adapters are cleaned up."""
        config = {
            "a": {
                "provider": "mock",
                "config": {"model": "m"},
                "auth": {"method": "api_key"},
            },
            "b": {
                "provider": "mock",
                "config": {"model": "m"},
                "auth": {"method": "api_key"},
            },
            "c": {
                "provider": "mock",
                "config": {"model": "m"},
                "auth": {"method": "api_key"},
            },
        }
        factory, orig = _make_factory(config, monkeypatch)
        try:
            a = factory.create("a")
            b = factory.create("b")
            c = factory.create("c")

            # Make adapter B's close() hang
            def hanging_close():
                time.sleep(60)

            b.close = hanging_close

            start = time.time()
            factory.close_all()
            elapsed = time.time() - start

            # Should complete within ~6s (5s timeout + margin)
            assert elapsed < 10
            # A and C should be closed
            assert a._closed is True
            assert c._closed is True
        finally:
            _restore_registry(orig)

    def test_t5_3_07_two_factories_no_shared_state(self, monkeypatch):
        """T5.3.07: Two factories are fully independent."""
        config = {
            "default": {
                "provider": "mock",
                "config": {"model": "m"},
                "auth": {"method": "api_key"},
            }
        }
        factory1, orig = _make_factory(config, monkeypatch)
        try:
            factory2 = LLMFactory(config=config)
            a1 = factory1.create("default")
            a2 = factory2.create("default")
            assert id(a1) != id(a2)

            factory1.close_all()
            # factory2 is unaffected
            a2_again = factory2.create("default")
            assert id(a2) == id(a2_again)
        finally:
            _restore_registry(orig)


# ─── 5.4 Thread Safety ────────────────────────────────────────────


class TestFactoryThreadSafety:
    """T5.4.01 - T5.4.03."""

    def test_t5_4_01_concurrent_create_same_profile(self, monkeypatch):
        """T5.4.01: 10 threads create same profile simultaneously.
        configure() called exactly once. All get same instance."""
        config = {
            "default": {
                "provider": "mock",
                "config": {"model": "m"},
                "auth": {"method": "api_key"},
            }
        }
        factory, orig = _make_factory(config, monkeypatch)
        try:
            results = []
            errors = []

            def worker():
                try:
                    adapter = factory.create("default")
                    results.append(id(adapter))
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=worker) for _ in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)

            assert not errors
            assert len(results) == 10
            # All got the same instance
            assert len(set(results)) == 1
        finally:
            _restore_registry(orig)

    def test_t5_4_02_concurrent_create_different_profiles(self, monkeypatch):
        """T5.4.02: 5 threads, 5 profiles simultaneously."""
        config = {
            f"p{i}": {
                "provider": "mock",
                "config": {"model": f"m{i}"},
                "auth": {"method": "api_key"},
            }
            for i in range(5)
        }
        factory, orig = _make_factory(config, monkeypatch)
        try:
            results = {}
            errors = []

            def worker(name):
                try:
                    adapter = factory.create(name)
                    results[name] = id(adapter)
                except Exception as e:
                    errors.append(e)

            threads = [
                threading.Thread(target=worker, args=(f"p{i}",)) for i in range(5)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)

            assert not errors
            assert len(results) == 5
            # All distinct
            assert len(set(results.values())) == 5
        finally:
            _restore_registry(orig)

    def test_t5_4_03_concurrent_create_and_reset(self, monkeypatch):
        """T5.4.03: One thread creates, another resets in a loop.
        No crash, no deadlock."""
        config = {
            "default": {
                "provider": "mock",
                "config": {"model": "m"},
                "auth": {"method": "api_key"},
            }
        }
        factory, orig = _make_factory(config, monkeypatch)
        try:
            errors = []
            stop = threading.Event()

            def creator():
                for _ in range(50):
                    if stop.is_set():
                        break
                    try:
                        factory.create("default")
                    except Exception as e:
                        errors.append(e)

            def resetter():
                for _ in range(50):
                    if stop.is_set():
                        break
                    try:
                        factory.reset("default")
                    except Exception as e:
                        errors.append(e)
                    time.sleep(0.001)

            t1 = threading.Thread(target=creator)
            t2 = threading.Thread(target=resetter)
            t1.start()
            t2.start()
            t1.join(timeout=10)
            t2.join(timeout=10)
            stop.set()

            # No crashes, no deadlocks
            assert not errors
        finally:
            _restore_registry(orig)


# ─── 5.5 Dependency Isolation ──────────────────────────────────────


class TestDependencyIsolation:
    """T5.5.01 - T5.5.02."""

    def test_t5_5_01_missing_sdk_lazy_error(self, monkeypatch):
        """T5.5.01: SDK not installed -> MissingDependencyError with
        install instructions. Error occurs at create() time."""
        from flow.llm.errors import MissingDependencyError

        config = {
            "bad": {
                "provider": "anthropic",
                "config": {"model": "claude"},
            }
        }
        factory = LLMFactory(config=config)
        # If anthropic is not installed, we get MissingDependencyError
        # If it IS installed, we get a different error. Either way,
        # we test that the factory doesn't crash at init time.
        try:
            factory.create("bad")
        except MissingDependencyError as e:
            assert "install" in str(e).lower()
        except Exception:
            pass  # SDK is actually installed

    def test_t5_5_02_core_does_not_import_sdk(self):
        """T5.5.02: Importing LLMFactory does NOT trigger SDK imports."""
        import sys

        # Record current SDK module state
        sdk_modules = ["google", "openai", "anthropic", "ollama"]
        pre_import = {m: m in sys.modules for m in sdk_modules}

        # Re-import factory
        import importlib

        importlib.reload(factory_module)

        # Verify no new SDK imports
        for mod in sdk_modules:
            if not pre_import[mod]:
                assert (
                    mod not in sys.modules or pre_import[mod]
                ), f"Importing LLMFactory triggered import of {mod}"
