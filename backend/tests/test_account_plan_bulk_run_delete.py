"""Tests for deleting account plan bulk runs."""

from backend.account_plan_generation_service import delete_plan_bulk_run
from backend.account_plan_store import AccountPlanStore


class TestDeletePlanBulkRun:
    def test_delete_bulk_run_resets_posts(self, tmp_path, monkeypatch):
        store = AccountPlanStore(str(tmp_path / "plans.json"))
        monkeypatch.setattr("backend.account_plan_generation_service.account_plan_store", store)

        plan = store.create({
            "status": "generated",
            "activeBulkRunId": "planrun_old",
            "plannedPosts": [
                {
                    "slot": 1,
                    "status": "generated",
                    "reviewStatus": "pending",
                    "bulkRunId": "planrun_old",
                    "generatedMediaUrl": "https://example.com/a.mp4",
                    "jobId": "job_1",
                },
                {
                    "slot": 2,
                    "status": "planned",
                    "reviewStatus": "pending",
                    "bulkRunId": "",
                },
            ],
        })

        result = delete_plan_bulk_run(plan["id"], "planrun_old")

        assert result["removedPosts"] == 1
        refreshed = store.get(plan["id"])
        assert refreshed["activeBulkRunId"] == ""
        assert refreshed["plannedPosts"][0]["status"] == "planned"
        assert refreshed["plannedPosts"][0]["bulkRunId"] == ""
        assert refreshed["plannedPosts"][0]["generatedMediaUrl"] == ""
        assert refreshed["plannedPosts"][1]["bulkRunId"] == ""

    def test_delete_bulk_run_blocks_scheduled_posts(self, tmp_path, monkeypatch):
        store = AccountPlanStore(str(tmp_path / "plans.json"))
        monkeypatch.setattr("backend.account_plan_generation_service.account_plan_store", store)

        plan = store.create({
            "status": "generated",
            "plannedPosts": [
                {
                    "slot": 1,
                    "status": "scheduled",
                    "reviewStatus": "scheduled",
                    "bulkRunId": "planrun_old",
                },
            ],
        })

        try:
            delete_plan_bulk_run(plan["id"], "planrun_old")
            assert False, "expected error"
        except Exception as exc:
            assert "scheduled" in str(exc).lower()
