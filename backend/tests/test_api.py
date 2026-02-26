"""
Tests for the FastAPI endpoints.

All pipeline calls are mocked so no external APIs are needed.
"""

import io
import os
import sys
import time
import threading
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

# Make backend modules importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api import app
from job_manager import job_manager, JobStatus


@pytest.fixture(autouse=True)
def _clear_jobs():
    """Reset the job store between tests."""
    job_manager._jobs.clear()
    yield
    job_manager._jobs.clear()


@pytest.fixture()
def client():
    return TestClient(app)


# -- Helpers ----------------------------------------------------------------

def _dummy_image() -> io.BytesIO:
    """1x1 red PNG."""
    # Minimal valid PNG
    import struct, zlib
    def _png_bytes():
        sig = b"\x89PNG\r\n\x1a\n"
        # IHDR
        ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
        ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF
        ihdr = struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)
        # IDAT
        raw = zlib.compress(b"\x00\xff\x00\x00")
        idat_crc = zlib.crc32(b"IDAT" + raw) & 0xFFFFFFFF
        idat = struct.pack(">I", len(raw)) + b"IDAT" + raw + struct.pack(">I", idat_crc)
        # IEND
        iend_crc = zlib.crc32(b"IEND") & 0xFFFFFFFF
        iend = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc)
        return sig + ihdr + idat + iend
    buf = io.BytesIO(_png_bytes())
    buf.name = "test.png"
    return buf


def _dummy_video() -> io.BytesIO:
    """Tiny fake MP4 (just enough bytes for the upload validator)."""
    buf = io.BytesIO(b"\x00\x00\x00\x1c" + b"ftypisom" + b"\x00" * 100)
    buf.name = "test.mp4"
    return buf


# -- Upload validation tests -----------------------------------------------

class TestGenerateValidation:
    def test_missing_image_returns_422(self, client):
        resp = client.post(
            "/api/generate",
            files={"video": ("test.mp4", _dummy_video(), "video/mp4")},
        )
        assert resp.status_code == 422

    def test_missing_video_returns_422(self, client):
        resp = client.post(
            "/api/generate",
            files={"image": ("test.png", _dummy_image(), "image/png")},
        )
        assert resp.status_code == 422

    def test_wrong_image_type_returns_400(self, client):
        resp = client.post(
            "/api/generate",
            files={
                "image": ("test.txt", io.BytesIO(b"hello"), "text/plain"),
                "video": ("test.mp4", _dummy_video(), "video/mp4"),
            },
        )
        assert resp.status_code == 400
        assert "image" in resp.json()["detail"].lower()

    def test_wrong_video_type_returns_400(self, client):
        resp = client.post(
            "/api/generate",
            files={
                "image": ("test.png", _dummy_image(), "image/png"),
                "video": ("test.txt", io.BytesIO(b"hello"), "text/plain"),
            },
        )
        assert resp.status_code == 400
        assert "video" in resp.json()["detail"].lower()


# -- Job status tests -------------------------------------------------------

class TestJobStatus:
    def test_nonexistent_job_returns_404(self, client):
        resp = client.get("/api/jobs/doesnotexist")
        assert resp.status_code == 404

    def test_created_job_returns_queued(self, client):
        job = job_manager.create_job("/tmp/v.mp4", "/tmp/i.png", "/tmp/out")
        resp = client.get(f"/api/jobs/{job.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "queued"
        assert len(data["steps"]) == 6

    def test_step_progress_reflected(self, client):
        job = job_manager.create_job("/tmp/v.mp4", "/tmp/i.png", "/tmp/out")
        job_manager.mark_processing(job.id)
        job_manager.step_start(job.id, "scene_detection", "Detecting...")
        job_manager.step_complete(job.id, "scene_detection", "Done")
        job_manager.step_start(job.id, "frame_extraction", "Extracting...")

        resp = client.get(f"/api/jobs/{job.id}")
        data = resp.json()
        assert data["status"] == "processing"
        assert data["current_step"] == "frame_extraction"
        assert data["steps"][0]["status"] == "completed"
        assert data["steps"][1]["status"] == "running"


# -- Result download tests --------------------------------------------------

class TestJobResult:
    def test_nonexistent_job_returns_404(self, client):
        resp = client.get("/api/jobs/doesnotexist/result")
        assert resp.status_code == 404

    def test_incomplete_job_returns_409(self, client):
        job = job_manager.create_job("/tmp/v.mp4", "/tmp/i.png", "/tmp/out")
        resp = client.get(f"/api/jobs/{job.id}/result")
        assert resp.status_code == 409

    def test_failed_job_returns_500(self, client):
        job = job_manager.create_job("/tmp/v.mp4", "/tmp/i.png", "/tmp/out")
        job_manager.mark_failed(job.id, "Something went wrong")
        resp = client.get(f"/api/jobs/{job.id}/result")
        assert resp.status_code == 500

    def test_completed_job_streams_video(self, client, tmp_path):
        # Create a fake video file
        video_file = tmp_path / "output.mp4"
        video_file.write_bytes(b"\x00" * 200)

        job = job_manager.create_job("/tmp/v.mp4", "/tmp/i.png", "/tmp/out")
        job_manager.mark_completed(job.id, str(video_file), {"final_video": str(video_file)})

        resp = client.get(f"/api/jobs/{job.id}/result")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "video/mp4"
        assert len(resp.content) == 200


# -- Full submit + poll flow (mocked pipeline) ------------------------------

class TestFullFlow:
    @patch("api.run_full_pipeline")
    def test_submit_poll_download(self, mock_pipeline, client, tmp_path):
        """Submit a job, poll until done, download the result."""
        video_file = tmp_path / "final.mp4"
        video_file.write_bytes(b"\x00" * 500)

        def fake_pipeline(video_path, model_image_path, output_dir, on_step=None):
            """Simulates pipeline steps completing quickly."""
            if on_step:
                for step_key in [
                    "scene_detection", "frame_extraction", "caption_detection",
                    "scene_recreation", "motion_control", "caption_overlay",
                ]:
                    on_step(step_key, "start")
                    on_step(step_key, "complete")
            return {"final_video": str(video_file)}

        mock_pipeline.side_effect = fake_pipeline

        # 1. Submit
        resp = client.post(
            "/api/generate",
            files={
                "image": ("model.png", _dummy_image(), "image/png"),
                "video": ("input.mp4", _dummy_video(), "video/mp4"),
            },
        )
        assert resp.status_code == 200
        job_id = resp.json()["job_id"]

        # 2. Poll until complete (give thread time to finish)
        for _ in range(50):
            status_resp = client.get(f"/api/jobs/{job_id}")
            if status_resp.json()["status"] == "completed":
                break
            time.sleep(0.1)
        else:
            pytest.fail("Job did not complete within timeout")

        data = status_resp.json()
        assert data["status"] == "completed"
        assert all(s["status"] == "completed" for s in data["steps"])

        # 3. Download
        result_resp = client.get(f"/api/jobs/{job_id}/result")
        assert result_resp.status_code == 200
        assert len(result_resp.content) == 500

    @patch("api.run_full_pipeline")
    def test_pipeline_failure_reported(self, mock_pipeline, client):
        """When the pipeline raises, the job status reflects the failure."""
        mock_pipeline.side_effect = RuntimeError("Fal AI returned no video")

        resp = client.post(
            "/api/generate",
            files={
                "image": ("model.png", _dummy_image(), "image/png"),
                "video": ("input.mp4", _dummy_video(), "video/mp4"),
            },
        )
        job_id = resp.json()["job_id"]

        # Wait for thread to finish
        for _ in range(50):
            status_resp = client.get(f"/api/jobs/{job_id}")
            if status_resp.json()["status"] == "failed":
                break
            time.sleep(0.1)
        else:
            pytest.fail("Job did not fail within timeout")

        data = status_resp.json()
        assert data["status"] == "failed"
        assert "Fal AI" in data["error"]
