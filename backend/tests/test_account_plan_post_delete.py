"""Tests for removing posts from account plans."""

import pytest

from backend.account_planner_service import AccountPlannerError, remove_studytok_plan_post
from backend.account_plan_store import AccountPlanStore


class TestRemovePlanPost:
    def test_remove_post_updates_plan(self, tmp_path, monkeypatch):
        store = AccountPlanStore(str(tmp_path / "plans.json"))
        monkeypatch.setattr("backend.account_planner_service.account_plan_store", store)
        monkeypatch.setattr("backend.account_plan_generation_service.account_plan_store", store)

        plan = store.create({
            "status": "approved",
            "settings": {"postCount": 2},
            "plannedPosts": [
                {"slot": 1, "status": "planned", "purpose": "relatable", "reviewStatus": "pending"},
                {"slot": 2, "status": "planned", "purpose": "hook_demo", "reviewStatus": "pending"},
            ],
        })

        result = remove_studytok_plan_post(plan["id"], 1)

        assert len(result["plannedPosts"]) == 1
        assert result["plannedPosts"][0]["slot"] == 2
        assert result["settings"]["postCount"] == 1
        assert result["contentMix"][0]["count"] == 1

    def test_remove_post_blocks_scheduled(self, tmp_path, monkeypatch):
        store = AccountPlanStore(str(tmp_path / "plans.json"))
        monkeypatch.setattr("backend.account_planner_service.account_plan_store", store)

        plan = store.create({
            "status": "generated",
            "plannedPosts": [
                {
                    "slot": 1,
                    "status": "scheduled",
                    "reviewStatus": "scheduled",
                },
            ],
        })

        with pytest.raises(AccountPlannerError) as exc:
            remove_studytok_plan_post(plan["id"], 1)
        assert exc.value.status_code == 409

    def test_remove_post_blocks_generating(self, tmp_path, monkeypatch):
        store = AccountPlanStore(str(tmp_path / "plans.json"))
        monkeypatch.setattr("backend.account_planner_service.account_plan_store", store)

        plan = store.create({
            "status": "generating",
            "plannedPosts": [
                {"slot": 1, "status": "generating", "reviewStatus": "pending"},
            ],
        })

        with pytest.raises(AccountPlannerError) as exc:
            remove_studytok_plan_post(plan["id"], 1)
        assert exc.value.status_code == 409
