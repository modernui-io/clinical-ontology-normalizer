"""Tests for Data Review & Lock API (CLINICAL-DL)."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

API_PREFIX = "/api/v1/data-locks"


@pytest.fixture(autouse=True)
def reset_service():
    from app.services.data_lock_service import reset_data_lock_service
    reset_data_lock_service()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=True) as c:
        yield c


class TestSeedData:
    @pytest.mark.anyio
    async def test_seed_locks(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/locks")
        assert r.status_code == 200
        assert r.json()["total"] == 8

    @pytest.mark.anyio
    async def test_seed_data_cuts(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/data-cuts")
        assert r.status_code == 200
        assert r.json()["total"] == 5

    @pytest.mark.anyio
    async def test_seed_clean_data(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/clean-data")
        assert r.status_code == 200
        assert r.json()["total"] == 12

    @pytest.mark.anyio
    async def test_seed_unblinding(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/unblinding-requests")
        assert r.status_code == 200
        assert r.json()["total"] == 3

    @pytest.mark.anyio
    async def test_seed_checklists(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/checklists")
        assert r.status_code == 200
        assert r.json()["total"] == 2


class TestLockCrud:
    @pytest.mark.anyio
    async def test_list_locks(self, client: AsyncClient):
        assert (await client.get(f"{API_PREFIX}/locks")).status_code == 200

    @pytest.mark.anyio
    async def test_get_lock(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/locks")
        lid = r.json()["items"][0]["id"]
        assert (await client.get(f"{API_PREFIX}/locks/{lid}")).status_code == 200

    @pytest.mark.anyio
    async def test_get_lock_not_found(self, client: AsyncClient):
        assert (await client.get(f"{API_PREFIX}/locks/X")).status_code == 404

    @pytest.mark.anyio
    async def test_create_lock(self, client: AsyncClient):
        r = await client.post(f"{API_PREFIX}/locks", json={
            "trial_id": "TRIAL-NEW", "lock_type": "soft_lock", "description": "Test lock", "planned_date": "2026-04-01T00:00:00Z",
        })
        assert r.status_code == 201
        assert r.json()["trial_id"] == "TRIAL-NEW"

    @pytest.mark.anyio
    async def test_update_lock(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/locks")
        lid = r.json()["items"][0]["id"]
        r2 = await client.put(f"{API_PREFIX}/locks/{lid}", json={"description": "Updated"})
        assert r2.status_code == 200

    @pytest.mark.anyio
    async def test_update_lock_not_found(self, client: AsyncClient):
        assert (await client.put(f"{API_PREFIX}/locks/X", json={"description": "N"})).status_code == 404

    @pytest.mark.anyio
    async def test_delete_lock(self, client: AsyncClient):
        r = await client.post(f"{API_PREFIX}/locks", json={
            "trial_id": "DEL", "lock_type": "soft_lock", "description": "D", "planned_date": "2026-04-01T00:00:00Z",
        })
        assert (await client.delete(f"{API_PREFIX}/locks/{r.json()['id']}")).status_code == 204

    @pytest.mark.anyio
    async def test_delete_lock_not_found(self, client: AsyncClient):
        assert (await client.delete(f"{API_PREFIX}/locks/X")).status_code == 404


class TestLockLifecycle:
    @pytest.mark.anyio
    async def test_start_lock(self, client: AsyncClient):
        r = await client.post(f"{API_PREFIX}/locks", json={
            "trial_id": "T", "lock_type": "soft_lock", "description": "D", "planned_date": "2026-04-01T00:00:00Z",
        })
        lid = r.json()["id"]
        assert (await client.post(f"{API_PREFIX}/locks/{lid}/start")).status_code == 200

    @pytest.mark.anyio
    async def test_soft_lock(self, client: AsyncClient):
        r = await client.post(f"{API_PREFIX}/locks", json={
            "trial_id": "T", "lock_type": "soft_lock", "description": "D", "planned_date": "2026-04-01T00:00:00Z",
        })
        lid = r.json()["id"]
        await client.post(f"{API_PREFIX}/locks/{lid}/start")
        assert (await client.post(f"{API_PREFIX}/locks/{lid}/soft-lock", json={"locked_by": "DM Smith"})).status_code == 200

    @pytest.mark.anyio
    async def test_hard_lock(self, client: AsyncClient):
        r = await client.post(f"{API_PREFIX}/locks", json={
            "trial_id": "T", "lock_type": "hard_lock", "description": "D", "planned_date": "2026-04-01T00:00:00Z",
        })
        lid = r.json()["id"]
        await client.post(f"{API_PREFIX}/locks/{lid}/start")
        await client.post(f"{API_PREFIX}/locks/{lid}/soft-lock", json={"locked_by": "DM Smith"})
        assert (await client.post(f"{API_PREFIX}/locks/{lid}/hard-lock", json={"locked_by": "DM Smith"})).status_code == 200

    @pytest.mark.anyio
    async def test_unlock(self, client: AsyncClient):
        r = await client.post(f"{API_PREFIX}/locks", json={
            "trial_id": "T", "lock_type": "soft_lock", "description": "D", "planned_date": "2026-04-01T00:00:00Z",
        })
        lid = r.json()["id"]
        await client.post(f"{API_PREFIX}/locks/{lid}/start")
        await client.post(f"{API_PREFIX}/locks/{lid}/soft-lock", json={"locked_by": "DM Smith"})
        assert (await client.post(f"{API_PREFIX}/locks/{lid}/unlock", json={"unlocked_by": "DM Smith", "unlock_reason": "Corrections needed"})).status_code == 200

    @pytest.mark.anyio
    async def test_cancel_lock(self, client: AsyncClient):
        r = await client.post(f"{API_PREFIX}/locks", json={
            "trial_id": "T", "lock_type": "interim_lock", "description": "D", "planned_date": "2026-04-01T00:00:00Z",
        })
        assert (await client.post(f"{API_PREFIX}/locks/{r.json()['id']}/cancel")).status_code == 200

    @pytest.mark.anyio
    async def test_start_not_found(self, client: AsyncClient):
        assert (await client.post(f"{API_PREFIX}/locks/X/start")).status_code == 404

    @pytest.mark.anyio
    async def test_soft_lock_not_found(self, client: AsyncClient):
        assert (await client.post(f"{API_PREFIX}/locks/X/soft-lock", json={"locked_by": "DM"})).status_code == 404

    @pytest.mark.anyio
    async def test_hard_lock_not_found(self, client: AsyncClient):
        assert (await client.post(f"{API_PREFIX}/locks/X/hard-lock", json={"locked_by": "DM"})).status_code == 404

    @pytest.mark.anyio
    async def test_unlock_not_found(self, client: AsyncClient):
        assert (await client.post(f"{API_PREFIX}/locks/X/unlock", json={"unlocked_by": "DM", "unlock_reason": "R"})).status_code == 404

    @pytest.mark.anyio
    async def test_cancel_not_found(self, client: AsyncClient):
        assert (await client.post(f"{API_PREFIX}/locks/X/cancel")).status_code == 404


class TestPreLockChecks:
    @pytest.mark.anyio
    async def test_pre_lock_checks(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/locks")
        lid = r.json()["items"][0]["id"]
        assert (await client.get(f"{API_PREFIX}/locks/{lid}/pre-lock-checks")).status_code == 200

    @pytest.mark.anyio
    async def test_pre_lock_checks_not_found(self, client: AsyncClient):
        assert (await client.get(f"{API_PREFIX}/locks/X/pre-lock-checks")).status_code == 404


class TestDataCuts:
    @pytest.mark.anyio
    async def test_list(self, client: AsyncClient):
        assert (await client.get(f"{API_PREFIX}/data-cuts")).status_code == 200

    @pytest.mark.anyio
    async def test_get(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/data-cuts")
        cid = r.json()["items"][0]["id"]
        assert (await client.get(f"{API_PREFIX}/data-cuts/{cid}")).status_code == 200

    @pytest.mark.anyio
    async def test_get_not_found(self, client: AsyncClient):
        assert (await client.get(f"{API_PREFIX}/data-cuts/X")).status_code == 404

    @pytest.mark.anyio
    async def test_create(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/locks")
        lid = r.json()["items"][0]["id"]
        r2 = await client.post(f"{API_PREFIX}/locks/{lid}/data-cuts", json={
            "cut_type": "interim_analysis", "cutoff_date": "2026-01-15T00:00:00Z",
        })
        assert r2.status_code == 201

    @pytest.mark.anyio
    async def test_delete(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/data-cuts")
        cid = r.json()["items"][0]["id"]
        assert (await client.delete(f"{API_PREFIX}/data-cuts/{cid}")).status_code == 204

    @pytest.mark.anyio
    async def test_delete_not_found(self, client: AsyncClient):
        assert (await client.delete(f"{API_PREFIX}/data-cuts/X")).status_code == 404


class TestCleanData:
    @pytest.mark.anyio
    async def test_list(self, client: AsyncClient):
        assert (await client.get(f"{API_PREFIX}/clean-data")).status_code == 200

    @pytest.mark.anyio
    async def test_get(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/clean-data")
        rid = r.json()["items"][0]["id"]
        assert (await client.get(f"{API_PREFIX}/clean-data/{rid}")).status_code == 200

    @pytest.mark.anyio
    async def test_get_not_found(self, client: AsyncClient):
        assert (await client.get(f"{API_PREFIX}/clean-data/X")).status_code == 404

    @pytest.mark.anyio
    async def test_create(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/locks")
        lid = r.json()["items"][0]["id"]
        r2 = await client.post(f"{API_PREFIX}/locks/{lid}/clean-data", json={
            "subject_id": "S001", "form": "Vitals", "visit": "Visit 1",
        })
        assert r2.status_code == 201

    @pytest.mark.anyio
    async def test_update(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/clean-data")
        rid = r.json()["items"][0]["id"]
        assert (await client.put(f"{API_PREFIX}/clean-data/{rid}", json={"notes": "Updated"})).status_code == 200

    @pytest.mark.anyio
    async def test_update_not_found(self, client: AsyncClient):
        assert (await client.put(f"{API_PREFIX}/clean-data/X", json={"notes": "N"})).status_code == 404

    @pytest.mark.anyio
    async def test_flag(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/clean-data")
        rid = r.json()["items"][0]["id"]
        assert (await client.post(f"{API_PREFIX}/clean-data/{rid}/flag", json=["field1", "field2"], params={"notes": "Discrepancy"})).status_code == 200

    @pytest.mark.anyio
    async def test_flag_not_found(self, client: AsyncClient):
        assert (await client.post(f"{API_PREFIX}/clean-data/X/flag", json=["field1"])).status_code == 404

    @pytest.mark.anyio
    async def test_mark_clean(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/clean-data")
        rid = r.json()["items"][0]["id"]
        assert (await client.post(f"{API_PREFIX}/clean-data/{rid}/mark-clean", params={"reviewer": "DM Smith"})).status_code == 200

    @pytest.mark.anyio
    async def test_mark_clean_not_found(self, client: AsyncClient):
        assert (await client.post(f"{API_PREFIX}/clean-data/X/mark-clean", params={"reviewer": "DM"})).status_code == 404

    @pytest.mark.anyio
    async def test_clean_data_summary(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/locks")
        lid = r.json()["items"][0]["id"]
        assert (await client.get(f"{API_PREFIX}/locks/{lid}/clean-data-summary")).status_code == 200


class TestUnblinding:
    @pytest.mark.anyio
    async def test_list(self, client: AsyncClient):
        assert (await client.get(f"{API_PREFIX}/unblinding-requests")).status_code == 200

    @pytest.mark.anyio
    async def test_get(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/unblinding-requests")
        rid = r.json()["items"][0]["id"]
        assert (await client.get(f"{API_PREFIX}/unblinding-requests/{rid}")).status_code == 200

    @pytest.mark.anyio
    async def test_get_not_found(self, client: AsyncClient):
        assert (await client.get(f"{API_PREFIX}/unblinding-requests/X")).status_code == 404

    @pytest.mark.anyio
    async def test_create(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/locks")
        lid = r.json()["items"][0]["id"]
        r2 = await client.post(f"{API_PREFIX}/locks/{lid}/unblinding-requests", json={
            "requestor": "Dr. Smith", "justification": "SAE review requires unblinding", "unblinding_type": "emergency",
        })
        assert r2.status_code == 201

    @pytest.mark.anyio
    async def test_approve(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/unblinding-requests")
        rid = r.json()["items"][0]["id"]
        assert (await client.post(f"{API_PREFIX}/unblinding-requests/{rid}/approve", json={"approver": "PI"})).status_code == 200

    @pytest.mark.anyio
    async def test_approve_not_found(self, client: AsyncClient):
        assert (await client.post(f"{API_PREFIX}/unblinding-requests/X/approve", json={"approver": "N"})).status_code == 404

    @pytest.mark.anyio
    async def test_execute(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/unblinding-requests")
        rid = r.json()["items"][0]["id"]
        await client.post(f"{API_PREFIX}/unblinding-requests/{rid}/approve", json={"approver": "PI"})
        assert (await client.post(f"{API_PREFIX}/unblinding-requests/{rid}/execute", json={"subjects_unblinded": ["P001", "P002"]})).status_code == 200

    @pytest.mark.anyio
    async def test_execute_not_found(self, client: AsyncClient):
        assert (await client.post(f"{API_PREFIX}/unblinding-requests/X/execute", json={"subjects_unblinded": ["P001"]})).status_code == 404

    @pytest.mark.anyio
    async def test_audit_trail(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/locks")
        lid = r.json()["items"][0]["id"]
        assert (await client.get(f"{API_PREFIX}/locks/{lid}/unblinding-audit")).status_code == 200


class TestChecklists:
    @pytest.mark.anyio
    async def test_list(self, client: AsyncClient):
        assert (await client.get(f"{API_PREFIX}/checklists")).status_code == 200

    @pytest.mark.anyio
    async def test_get(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/checklists")
        cid = r.json()["items"][0]["id"]
        assert (await client.get(f"{API_PREFIX}/checklists/{cid}")).status_code == 200

    @pytest.mark.anyio
    async def test_get_not_found(self, client: AsyncClient):
        assert (await client.get(f"{API_PREFIX}/checklists/X")).status_code == 404

    @pytest.mark.anyio
    async def test_create(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/locks")
        lid = r.json()["items"][0]["id"]
        r2 = await client.post(f"{API_PREFIX}/locks/{lid}/checklists", json={"name": "Test Checklist"})
        assert r2.status_code == 201

    @pytest.mark.anyio
    async def test_completion(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/checklists")
        cid = r.json()["items"][0]["id"]
        assert (await client.get(f"{API_PREFIX}/checklists/{cid}/completion")).status_code == 200


class TestMetrics:
    @pytest.mark.anyio
    async def test_metrics(self, client: AsyncClient):
        assert (await client.get(f"{API_PREFIX}/metrics")).status_code == 200
