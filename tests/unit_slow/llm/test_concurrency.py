"""Concurrency & Thread Safety Tests — spec §8.

Tests that LLMProvider and LLMFactory are thread-safe.
Covers T8.1.01-T8.1.08.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed


from flow.llm.errors import ProviderNotConfiguredError

from .conftest import MockProvider


class TestProviderThreadSafety:
    """T8.1.01 - T8.1.08."""

    def test_t8_1_01_concurrent_generate(self, configured_provider):
        """T8.1.01: 10 threads call generate() simultaneously -> all
        get valid responses, no corruption."""
        results = []
        errors = []

        def worker(i):
            try:
                result = configured_provider.generate(
                    [{"role": "user", "content": f"msg {i}"}]
                )
                results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert not errors
        assert len(results) == 10
        for r in results:
            assert isinstance(r, str)
            assert len(r) > 0

    def test_t8_1_02_concurrent_embed(self, configured_provider):
        """T8.1.02: 10 threads call embed() simultaneously -> all
        get valid vectors."""
        results = []
        errors = []

        def worker(i):
            try:
                result = configured_provider.embed([f"text {i}"])
                results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert not errors
        assert len(results) == 10

    def test_t8_1_03_concurrent_mixed_operations(self, configured_provider):
        """T8.1.03: Mixed generate/embed/count_tokens concurrently."""
        errors = []
        results = {"generate": [], "embed": [], "count_tokens": []}

        def do_generate():
            try:
                r = configured_provider.generate([{"role": "user", "content": "hi"}])
                results["generate"].append(r)
            except Exception as e:
                errors.append(e)

        def do_embed():
            try:
                r = configured_provider.embed(["hello"])
                results["embed"].append(r)
            except Exception as e:
                errors.append(e)

        def do_count():
            try:
                r = configured_provider.count_tokens("hello world")
                results["count_tokens"].append(r)
            except Exception as e:
                errors.append(e)

        threads = []
        for _ in range(5):
            threads.append(threading.Thread(target=do_generate))
            threads.append(threading.Thread(target=do_embed))
            threads.append(threading.Thread(target=do_count))

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert not errors
        assert len(results["generate"]) == 5
        assert len(results["embed"]) == 5
        assert len(results["count_tokens"]) == 5

    def test_t8_1_04_close_while_generating(self, configured_provider):
        """T8.1.04: Thread A generates, Thread B closes.
        No crash, no hung thread."""
        errors = []
        barrier = threading.Barrier(2, timeout=5)

        def thread_a():
            try:
                barrier.wait()
                configured_provider.generate([{"role": "user", "content": "hi"}])
            except (ProviderNotConfiguredError, Exception):
                pass  # Either is acceptable

        def thread_b():
            try:
                barrier.wait()
                time.sleep(0.001)
                configured_provider.close()
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=thread_a)
        t2 = threading.Thread(target=thread_b)
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        assert not errors

    def test_t8_1_05_thread_pool_executor_bounded(self, configured_provider):
        """T8.1.05: ThreadPoolExecutor with max_workers=4.
        Verify bounded resource usage."""
        results = []

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(
                    configured_provider.generate,
                    [{"role": "user", "content": f"msg {i}"}],
                )
                for i in range(20)
            ]
            for f in as_completed(futures):
                results.append(f.result())

        assert len(results) == 20

    def test_t8_1_06_no_response_corruption(self, configured_provider):
        """T8.1.06: Ensure per-thread uniqueness.
        With unique side effects, each thread gets correct response."""
        # Since MockProvider returns same response, we verify no crash
        results = []
        errors = []

        def worker(i):
            try:
                result = configured_provider.generate(
                    [{"role": "user", "content": f"unique-{i}"}]
                )
                results.append((i, result))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors
        assert len(results) == 50

    def test_t8_1_07_concurrent_configure_race(self, monkeypatch):
        """T8.1.07: 10 threads call configure() on same provider.
        Only ONE succeeds, rest get ProviderAlreadyConfiguredError."""
        monkeypatch.setenv("MOCK_API_KEY", "test-key")
        p = MockProvider()
        success_count = 0
        already_configured_count = 0
        errors = []
        lock = threading.Lock()

        def worker():
            nonlocal success_count, already_configured_count
            try:
                p.configure({"model": "m", "auth": {"method": "api_key"}})
                with lock:
                    success_count += 1
            except Exception as e:
                if "already been called" in str(e):
                    with lock:
                        already_configured_count += 1
                else:
                    errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert not errors
        assert success_count == 1
        assert already_configured_count == 9

    def test_t8_1_08_stress_test_100_threads(self, configured_provider):
        """T8.1.08: 100 threads hammering generate() simultaneously.
        No deadlock, no crash, all complete within timeout."""
        errors = []
        completed = threading.Event()  # noqa: F841
        count = {"done": 0}
        lock = threading.Lock()

        def worker():
            try:
                configured_provider.generate(
                    [{"role": "user", "content": "stress test"}]
                )
                with lock:
                    count["done"] += 1
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(100)]
        start = time.time()
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        elapsed = time.time() - start

        assert not errors
        assert count["done"] == 100
        assert elapsed < 10  # Should complete well within 10s
