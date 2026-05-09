import json

from app import logging as bonplan_logging


class FakeLokiSender:
    def __init__(self):
        self.records = []

    def emit(self, record, logs_subdir):
        self.records.append((record, logs_subdir))

    def shutdown(self, timeout_seconds=5.0):
        return None


def test_normalize_loki_url_accepts_base_or_push_endpoint():
    assert (
        bonplan_logging._normalize_loki_url("https://logs.example.com")
        == "https://logs.example.com/loki/api/v1/push"
    )
    assert (
        bonplan_logging._normalize_loki_url("https://logs.example.com/loki/api/v1/push")
        == "https://logs.example.com/loki/api/v1/push"
    )


def test_non_local_logging_streams_structured_record_to_loki(monkeypatch):
    sender = FakeLokiSender()
    logger = bonplan_logging.get_api_logger("tests.api")

    monkeypatch.setattr(bonplan_logging.settings, "LOCAL_DEVELOPMENT", False, raising=False)
    monkeypatch.setattr(bonplan_logging, "_get_loki_sender", lambda: sender)

    logger.info("Request completed", request_id="req-123", status_code=200)

    assert len(sender.records) == 1
    record, logs_subdir = sender.records[0]
    assert logs_subdir == "api"
    assert record["msg"] == "Request completed"
    assert record["logger"] == "tests.api"
    assert record["level"] == "INFO"
    assert record["environment"] == "remote"
    assert record["component"] == "api"
    assert record["request_id"] == "req-123"
    assert record["status_code"] == 200

    line = json.dumps(record, default=str)
    assert "\"msg\": \"Request completed\"" in line
