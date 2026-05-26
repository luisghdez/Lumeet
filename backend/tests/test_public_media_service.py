"""
Tests for public media URL resolution before Late/Zernio publishing.
"""

from backend.public_media_service import (
    ensure_public_media_url,
    extract_job_id_from_media_url,
    is_public_media_url,
    overlay_version_from_media_url,
)


class TestPublicMediaService:
    def test_is_public_media_url_rejects_local_backend(self):
        assert not is_public_media_url("http://127.0.0.1:8000/api/jobs/abc/result?v=1")
        assert not is_public_media_url("http://localhost:8000/api/jobs/abc/result")
        assert is_public_media_url("https://storage.googleapis.com/bucket/video.mp4")

    def test_extract_job_id_and_overlay_version(self):
        url = "http://127.0.0.1:8000/api/jobs/af7e6c7c9574/result?v=3"
        assert extract_job_id_from_media_url(url) == "af7e6c7c9574"
        assert overlay_version_from_media_url(url) == 3

    def test_ensure_public_media_url_uses_existing_gcs(self, monkeypatch):
        monkeypatch.setattr(
            "backend.public_media_service._resolve_existing_public_url",
            lambda _job_id: "https://storage.googleapis.com/test-bucket/video.mp4",
        )
        assert ensure_public_media_url(
            "http://127.0.0.1:8000/api/jobs/job123/result?v=1",
            job_id="job123",
            overlay_version=1,
        ) == "https://storage.googleapis.com/test-bucket/video.mp4"

    def test_ensure_public_media_url_uploads_local_file(self, monkeypatch, tmp_path):
        jobs_dir = tmp_path / "jobs" / "job123" / "output"
        jobs_dir.mkdir(parents=True)
        video_path = jobs_dir / "final_output.mp4"
        video_path.write_bytes(b"fake-video")

        monkeypatch.setattr("backend.public_media_service.JOBS_DIR", str(tmp_path / "jobs"))
        monkeypatch.setattr(
            "backend.public_media_service._resolve_existing_public_url",
            lambda _job_id: "",
        )
        monkeypatch.setattr(
            "backend.public_media_service._upload_video_public",
            lambda _local_path, _object_name: {
                "bucket": "test-bucket",
                "object": "videos/job123/final_output.mp4",
                "url": "https://storage.googleapis.com/test-bucket/videos/job123/final_output.mp4",
            },
        )
        monkeypatch.setattr("backend.public_media_service.persist_public_video_url", lambda *args, **kwargs: None)

        public_url = ensure_public_media_url(
            "http://127.0.0.1:8000/api/jobs/job123/result",
            job_id="job123",
        )
        assert public_url == "https://storage.googleapis.com/test-bucket/videos/job123/final_output.mp4"
