import shutil

import pytest

from flow.engine.events import Event, EventBus


def test_t5_01_payload_inline(tmp_path):
    """T5.01: Payload < 8KB is inline."""
    bus = EventBus(flow_dir=tmp_path)
    payload = {"data": "x" * 100}  # Small
    event = bus.emit("test.event", payload)

    assert event.payload == payload
    assert "ref" not in event.metadata


def test_t5_02_payload_reference(tmp_path):
    """T5.02: Payload > 8KB is referenced."""
    bus = EventBus(flow_dir=tmp_path)
    (tmp_path / "artifacts").mkdir()

    large_data = "x" * 9000  # > 8192
    payload = {"data": large_data}

    event = bus.emit("test.large", payload)

    # Expect payload replaced structure
    assert "ref" in event.payload
    assert event.payload["type"] == "blob_ref"

    # Verify file existence
    blob_path = tmp_path / "artifacts" / event.payload["ref"]
    assert blob_path.exists()
    assert large_data in blob_path.read_text("utf-8")


def test_t5_03_jsonl_streaming(tmp_path):
    """T5.03: Events streamed to jsonl."""
    (tmp_path / "logs").mkdir()
    bus = EventBus(flow_dir=tmp_path)

    bus.emit("seq.1", {"a": 1})
    bus.emit("seq.2", {"a": 2})

    log_file = tmp_path / "logs" / "events.jsonl"
    lines = log_file.read_text("utf-8").strip().split("\n")
    assert len(lines) == 2
    assert "seq.1" in lines[0]
    assert "seq.2" in lines[1]


def test_t5_04_payload_boundary(tmp_path):
    """T5.04: Exact 8KB boundary."""
    bus = EventBus(flow_dir=tmp_path)
    (tmp_path / "artifacts").mkdir()

    # Payload size depends on JSON structure: {"d": "..."}
    # overhead: `{"d": ""}` is 9 chars.
    # 8192 - 9 = 8183 chars of data => 8192 total.

    # Case A: 8192 bytes (Inline)
    s_inline = "x" * 8183
    event = bus.emit("boundary.inline", {"d": s_inline})
    # serialized: {"d": "xxxx..."} length 8192
    assert "ref" not in event.payload

    # Case B: 8193 bytes (Blob)
    s_blob = "x" * 8184
    event = bus.emit("boundary.blob", {"d": s_blob})
    assert "ref" in event.payload


def test_t5_05_blob_write_failure(tmp_path):
    """T5.05: Write fail -> Warning, no crash."""
    bus = EventBus(flow_dir=tmp_path)
    (tmp_path / "artifacts").mkdir()

    # Create a file at expected blob path to cause collision? No uuid is random.
    # Mock artifacts_dir to be read-only? On Windows tricky.
    # Mock `write_text` to raise OSError.

    import unittest.mock

    large_payload = {"d": "x" * 9000}

    with unittest.mock.patch(
        "pathlib.Path.write_text", side_effect=OSError("Disk Full")
    ):
        event = bus.emit("fail.test", large_payload)

    assert "error" in event.payload
    assert event.payload["error"] == "Blob Write Failed"
