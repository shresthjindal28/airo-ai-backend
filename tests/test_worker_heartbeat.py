import pytest
from datetime import UTC, datetime


class TestWorkerHeartbeat:
    def test_publish_payload(self):
        from app.workers.worker_heartbeat import WorkerHeartbeat

        published = {}

        def mock_set_json(key, value, *, ttl_seconds):
            published["key"] = key
            published["value"] = value
            published["ttl"] = ttl_seconds
            return True

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "app.workers.worker_heartbeat.redis_set_json",
                mock_set_json,
            )
            hb = WorkerHeartbeat(
                worker_id="test-worker",
                get_active_jobs=lambda: 1,
                get_jobs_processed=lambda: 10,
                get_jobs_failed=lambda: 2,
            )
            hb.publish()

        assert published["key"] == "airo:worker:test-worker"
        assert published["value"]["worker_id"] == "test-worker"
        assert published["value"]["active_jobs"] == 1
        assert published["value"]["jobs_processed"] == 10
        assert published["ttl"] == 45
