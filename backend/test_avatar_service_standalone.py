"""
Standalone tests for the AI Avatar Studio backend.

Run:
    cd backend
    python test_avatar_service_standalone.py

These tests do NOT call any real image-generation API. They monkey-patch
``avatar_service._generate_image`` (and the GCS upload) so the service can
be exercised end-to-end without network access.
"""

import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))

import avatar_service
from avatar_service import (
    AvatarServiceError,
    build_avatar_prompt,
    create_avatar_model,
    validate_required,
)


REQUIRED_OK_SELECTIONS = {
    "gender": "female",
    "ethnicity": "latin_american",
    "skinTone": "medium",
    "age": "adult",
    "bodyType": "athletic",
    "hairType": "wavy",
    "hairColor": "dark_brown",
    "outfit": "streetwear",
    # Optional bits — should all merge into the prompt cleanly.
    "eyeColor": "green",
    "hairLength": "medium",
    "tattoos": "subtle",
    "piercings": "ears",
    "extras": ["freckles", "glasses"],
}


def _write_dummy_image(path: str) -> str:
    from PIL import Image
    Image.new("RGB", (8, 8), color=(127, 127, 127)).save(path)
    return path


class TestPromptBuilder(unittest.TestCase):
    def test_required_validation_reports_missing(self):
        missing = validate_required({"gender": "male"})
        self.assertIn("ethnicity", missing)
        self.assertIn("hairType", missing)
        self.assertNotIn("gender", missing)

    def test_required_validation_passes_for_complete(self):
        self.assertEqual(validate_required(REQUIRED_OK_SELECTIONS), [])

    def test_prompt_includes_known_fragments(self):
        prompt = build_avatar_prompt(REQUIRED_OK_SELECTIONS)
        for fragment in [
            "female-presenting",
            "Latin American",
            "medium / olive skin tone",
            "athletic toned build",
            "soft wavy hair",
            "dark brown hair",
            "modern streetwear",
            "green eyes",
            "freckles",
            "wearing thin-frame modern glasses",
        ]:
            self.assertIn(fragment, prompt, f"missing fragment: {fragment!r}")

    def test_prompt_ignores_unknown_ids(self):
        prompt = build_avatar_prompt({"gender": "definitely_not_real"})
        # It still produces a valid descriptor with the boilerplate framing.
        self.assertIn("Studio portrait", prompt)
        self.assertNotIn("definitely_not_real", prompt)


class TestCreateAvatarModel(unittest.TestCase):
    def test_create_avatar_model_happy_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            jobs_dir = os.path.join(tmp, "jobs")
            os.makedirs(jobs_dir, exist_ok=True)

            def fake_generate(prompt, output_path):
                _write_dummy_image(output_path)
                return output_path, "fake-provider"

            saved_records = {}

            class FakeStore:
                def save(self, model_id, payload):
                    saved_records[model_id] = payload

            class FakeGcs:
                bucket_name = "fake-bucket"

                def upload_file_public(self, local_path, object_name):
                    return {
                        "bucket": self.bucket_name,
                        "object": object_name,
                        "url": f"https://example.com/{object_name}",
                    }

            steps_seen = []

            def on_step(key, status, message=""):
                steps_seen.append((key, status))

            with mock.patch.object(avatar_service, "_generate_image", side_effect=fake_generate), \
                 mock.patch.object(avatar_service, "model_metadata_store", FakeStore()), \
                 mock.patch("storage_gcs.GcsStorage", return_value=FakeGcs()):
                record = create_avatar_model(
                    selections=REQUIRED_OK_SELECTIONS,
                    label="Test Avatar",
                    prompt_summary="quick summary",
                    jobs_dir=jobs_dir,
                    on_step=on_step,
                )

            self.assertEqual(record["source"], "avatar_studio")
            self.assertEqual(record["label"], "Test Avatar")
            self.assertEqual(record["filename"], "avatar.png")
            self.assertEqual(record["bucket"], "fake-bucket")
            self.assertTrue(record["url"].startswith("https://example.com/"))
            self.assertEqual(record["promptSummary"], "quick summary")
            self.assertEqual(record["provider"], "fake-provider")
            self.assertIn(record["modelId"], saved_records)
            self.assertEqual(record["avatarConfig"]["gender"], "female")
            self.assertEqual(record["avatarConfig"]["extras"], ["freckles", "glasses"])

            for required_step in ("validate", "prompt", "generate", "upload", "save"):
                self.assertIn(
                    (required_step, "completed"),
                    steps_seen,
                    f"step {required_step!r} never reached completed",
                )

    def test_create_avatar_model_rejects_incomplete_selections(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(avatar_service, "_generate_image") as gen_mock:
                with self.assertRaises(AvatarServiceError):
                    create_avatar_model(
                        selections={"gender": "male"},
                        label="Bad",
                        prompt_summary="",
                        jobs_dir=tmp,
                    )
            gen_mock.assert_not_called()

    def test_create_avatar_model_surfaces_image_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            def boom(prompt, output_path):
                raise AvatarServiceError("nope")

            with mock.patch.object(avatar_service, "_generate_image", side_effect=boom):
                with self.assertRaises(AvatarServiceError) as ctx:
                    create_avatar_model(
                        selections=REQUIRED_OK_SELECTIONS,
                        label="x",
                        prompt_summary="",
                        jobs_dir=tmp,
                    )
            self.assertIn("nope", ctx.exception.message)


class TestAvatarApiEndpoint(unittest.TestCase):
    """Lightweight integration test for the FastAPI route."""

    def test_endpoint_validates_and_starts_generation(self):
        try:
            from fastapi.testclient import TestClient
        except Exception:
            self.skipTest("fastapi.testclient unavailable")
            return

        # Importing api triggers store + GCS imports which may need env vars.
        # If that import fails (e.g. missing dep at test-time), skip.
        try:
            import api as api_module
        except Exception as exc:  # pragma: no cover - environment-dependent
            self.skipTest(f"api module unavailable: {exc}")
            return

        client = TestClient(api_module.app)

        # Missing selections returns 400.
        resp = client.post("/api/avatars", json={"selections": {"gender": "male"}})
        self.assertEqual(resp.status_code, 400, resp.text)
        self.assertIn("Missing required selections", resp.json().get("detail", ""))

        # Patch the service worker so we don't actually call image APIs / GCS.
        with mock.patch.object(api_module, "create_avatar_model") as fake_create, \
             mock.patch.object(api_module, "_refresh_model_url", side_effect=lambda r: r):
            fake_create.return_value = {
                "modelId": "abc123",
                "url": "https://example.com/avatar.png",
                "bucket": "b",
                "object": "o",
                "label": "x",
                "filename": "avatar.png",
                "createdAt": "2026-01-01T00:00:00+00:00",
                "source": "avatar_studio",
                "avatarConfig": REQUIRED_OK_SELECTIONS,
                "promptSummary": "",
                "provider": "fake",
            }

            resp = client.post(
                "/api/avatars",
                json={
                    "selections": REQUIRED_OK_SELECTIONS,
                    "promptSummary": "demo",
                    "label": "Demo Avatar",
                },
            )

            self.assertEqual(resp.status_code, 200, resp.text)
            data = resp.json()
            self.assertIn("generationId", data)
            self.assertTrue(data["generationId"])

            # Worker is asynchronous; give it a moment to drain.
            import time
            for _ in range(40):
                if fake_create.called:
                    break
                time.sleep(0.05)
            self.assertTrue(fake_create.called, "background avatar worker never ran")

            # Generation record should exist and be marked completed by the worker.
            gen = api_module.generation_store.get(data["generationId"])
            self.assertIsNotNone(gen)
            self.assertEqual(gen["type"], "avatar")
            for _ in range(40):
                gen = api_module.generation_store.get(data["generationId"])
                if gen and gen.get("status") == "completed":
                    break
                time.sleep(0.05)
            self.assertEqual(gen["status"], "completed", gen)
            self.assertEqual(gen["output"]["modelId"], "abc123")

            # Cleanup the test record so we don't pollute the store.
            api_module.generation_store.delete(data["generationId"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
