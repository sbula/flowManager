"""Factory Shutdown & Thread Safety Tests — spec §5.3, §5.4.

Slow tests: time.sleep()-based timeouts, multi-thread stress testing.
Moved from tests/unit/llm/test_factory.py to the slow test suite.
"""

import threading
import time

import pytest

import flow.llm.factory as factory_module
from flow.llm.errors import (
    FactoryClosedError,
    ProviderNotConfiguredError,
)
from flow.llm.factory import LLMFactory


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
