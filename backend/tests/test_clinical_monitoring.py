"""Tests for Clinical Monitoring API (CLINICAL-18)."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

API_PREFIX = "/api/v1/clinical-monitoring"


@pytest.fixture(autouse=True)
def reset_service():
    from app.services.clinical_monitoring_service import reset_clinical_monitoring_service
    reset_clinical_monitoring_service()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=True) as c:
        yield c


class TestSeedData:
    @pytest.mark.anyio
    async def test_seed_visits(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visits")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_seed_findings(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings")
        assert resp.status_code == 200
        assert resp.json()["total"] == 8

    @pytest.mark.anyio
    async def test_seed_sdv(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sdv")
        assert resp.status_code == 200
        assert resp.json()["total"] == 15

    @pytest.mark.anyio
    async def test_seed_reports(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reports")
        assert resp.status_code == 200
        assert resp.json()["total"] == 5

    @pytest.mark.anyio
    async def test_seed_capas(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/capas")
        assert resp.status_code == 200
        assert resp.json()["total"] == 4


class TestVisitCrud:
    @pytest.mark.anyio
    async def test_list_visits(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visits")
        assert resp.status_code == 200
        assert len(resp.json()["items"]) > 0

    @pytest.mark.anyio
    async def test_get_visit(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visits")
        vid = resp.json()["items"][0]["id"]
        resp2 = await client.get(f"{API_PREFIX}/visits/{vid}")
        assert resp2.status_code == 200
        assert resp2.json()["id"] == vid

    @pytest.mark.anyio
    async def test_get_visit_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visits/X")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_visit(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/visits", json={
            "site_id": "SITE-100", "trial_id": "TRIAL-001",
            "visit_type": "routine", "cra_name": "John Smith", "cra_id": "CRA-100",
            "scheduled_date": "2026-03-01T09:00:00Z",
        })
        assert resp.status_code == 201
        assert resp.json()["site_id"] == "SITE-100"

    @pytest.mark.anyio
    async def test_update_visit(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visits")
        vid = resp.json()["items"][0]["id"]
        resp2 = await client.put(f"{API_PREFIX}/visits/{vid}", json={"cra_name": "Jane Doe"})
        assert resp2.status_code == 200
        assert resp2.json()["cra_name"] == "Jane Doe"

    @pytest.mark.anyio
    async def test_update_visit_not_found(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/visits/X", json={"cra_name": "N"})
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_visit(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/visits", json={
            "site_id": "DEL", "trial_id": "T1", "visit_type": "routine", "cra_name": "D", "cra_id": "CRA-D", "scheduled_date": "2026-03-01T09:00:00Z",
        })
        vid = resp.json()["id"]
        assert (await client.delete(f"{API_PREFIX}/visits/{vid}")).status_code == 204

    @pytest.mark.anyio
    async def test_delete_visit_not_found(self, client: AsyncClient):
        assert (await client.delete(f"{API_PREFIX}/visits/X")).status_code == 404


class TestVisitLifecycle:
    @pytest.mark.anyio
    async def test_confirm(self, client: AsyncClient):
        r = await client.post(f"{API_PREFIX}/visits", json={
            "site_id": "S", "trial_id": "T", "visit_type": "routine", "cra_name": "M", "cra_id": "CRA-M", "scheduled_date": "2026-03-01T09:00:00Z",
        })
        assert (await client.post(f"{API_PREFIX}/visits/{r.json()['id']}/confirm")).status_code == 200

    @pytest.mark.anyio
    async def test_start(self, client: AsyncClient):
        r = await client.post(f"{API_PREFIX}/visits", json={
            "site_id": "S", "trial_id": "T", "visit_type": "routine", "cra_name": "M", "cra_id": "CRA-M", "scheduled_date": "2026-03-01T09:00:00Z",
        })
        vid = r.json()["id"]
        await client.post(f"{API_PREFIX}/visits/{vid}/confirm")
        assert (await client.post(f"{API_PREFIX}/visits/{vid}/start", json={"actual_start_date": "2026-03-01T09:30:00Z"})).status_code == 200

    @pytest.mark.anyio
    async def test_complete(self, client: AsyncClient):
        r = await client.post(f"{API_PREFIX}/visits", json={
            "site_id": "S", "trial_id": "T", "visit_type": "routine", "cra_name": "M", "cra_id": "CRA-M", "scheduled_date": "2026-03-01T09:00:00Z",
        })
        vid = r.json()["id"]
        await client.post(f"{API_PREFIX}/visits/{vid}/confirm")
        await client.post(f"{API_PREFIX}/visits/{vid}/start", json={"actual_start_date": "2026-03-01T09:30:00Z"})
        assert (await client.post(f"{API_PREFIX}/visits/{vid}/complete", json={"actual_end_date": "2026-03-01T17:00:00Z"})).status_code == 200

    @pytest.mark.anyio
    async def test_cancel(self, client: AsyncClient):
        r = await client.post(f"{API_PREFIX}/visits", json={
            "site_id": "S", "trial_id": "T", "visit_type": "routine", "cra_name": "M", "cra_id": "CRA-M", "scheduled_date": "2026-03-01T09:00:00Z",
        })
        assert (await client.post(f"{API_PREFIX}/visits/{r.json()['id']}/cancel")).status_code == 200

    @pytest.mark.anyio
    async def test_confirm_not_found(self, client: AsyncClient):
        assert (await client.post(f"{API_PREFIX}/visits/X/confirm")).status_code == 404

    @pytest.mark.anyio
    async def test_start_not_found(self, client: AsyncClient):
        assert (await client.post(f"{API_PREFIX}/visits/X/start", json={"actual_start_date": "2026-03-01T09:30:00Z"})).status_code == 404

    @pytest.mark.anyio
    async def test_complete_not_found(self, client: AsyncClient):
        assert (await client.post(f"{API_PREFIX}/visits/X/complete", json={"actual_end_date": "2026-03-01T17:00:00Z"})).status_code == 404

    @pytest.mark.anyio
    async def test_cancel_not_found(self, client: AsyncClient):
        assert (await client.post(f"{API_PREFIX}/visits/X/cancel")).status_code == 404


class TestFindings:
    @pytest.mark.anyio
    async def test_list(self, client: AsyncClient):
        assert (await client.get(f"{API_PREFIX}/findings")).status_code == 200

    @pytest.mark.anyio
    async def test_get(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/findings")
        fid = r.json()["items"][0]["id"]
        assert (await client.get(f"{API_PREFIX}/findings/{fid}")).status_code == 200

    @pytest.mark.anyio
    async def test_get_not_found(self, client: AsyncClient):
        assert (await client.get(f"{API_PREFIX}/findings/X")).status_code == 404

    @pytest.mark.anyio
    async def test_create(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/visits")
        vid = r.json()["items"][0]["id"]
        r2 = await client.post(f"{API_PREFIX}/findings", json={
            "visit_id": vid, "description": "Test finding", "severity": "minor", "category": "data_entry",
        })
        assert r2.status_code == 201

    @pytest.mark.anyio
    async def test_update(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/findings")
        fid = r.json()["items"][0]["id"]
        assert (await client.put(f"{API_PREFIX}/findings/{fid}", json={"description": "U"})).status_code == 200

    @pytest.mark.anyio
    async def test_update_not_found(self, client: AsyncClient):
        assert (await client.put(f"{API_PREFIX}/findings/X", json={"description": "N"})).status_code == 404

    @pytest.mark.anyio
    async def test_resolve(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/findings")
        fid = r.json()["items"][0]["id"]
        assert (await client.post(f"{API_PREFIX}/findings/{fid}/resolve", json={"resolution": "Fixed"})).status_code == 200

    @pytest.mark.anyio
    async def test_resolve_not_found(self, client: AsyncClient):
        assert (await client.post(f"{API_PREFIX}/findings/X/resolve", json={"resolution": "N"})).status_code == 404

    @pytest.mark.anyio
    async def test_escalate(self, client: AsyncClient):
        # Create a fresh finding to escalate (seed findings may already be resolved/escalated)
        r = await client.get(f"{API_PREFIX}/visits")
        vid = r.json()["items"][0]["id"]
        new_f = await client.post(f"{API_PREFIX}/findings", json={
            "visit_id": vid, "description": "Escalation test", "severity": "major", "category": "protocol_deviation",
        })
        fid = new_f.json()["id"]
        assert (await client.post(f"{API_PREFIX}/findings/{fid}/escalate")).status_code == 200

    @pytest.mark.anyio
    async def test_escalate_not_found(self, client: AsyncClient):
        assert (await client.post(f"{API_PREFIX}/findings/X/escalate")).status_code == 404


class TestSDV:
    @pytest.mark.anyio
    async def test_summary(self, client: AsyncClient):
        assert (await client.get(f"{API_PREFIX}/sdv/summary")).status_code == 200

    @pytest.mark.anyio
    async def test_rate(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/visits")
        sid = r.json()["items"][0]["site_id"]
        assert (await client.get(f"{API_PREFIX}/sdv/rate/{sid}")).status_code == 200

    @pytest.mark.anyio
    async def test_list(self, client: AsyncClient):
        assert (await client.get(f"{API_PREFIX}/sdv")).status_code == 200

    @pytest.mark.anyio
    async def test_get(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/sdv")
        sid = r.json()["items"][0]["id"]
        assert (await client.get(f"{API_PREFIX}/sdv/{sid}")).status_code == 200

    @pytest.mark.anyio
    async def test_get_not_found(self, client: AsyncClient):
        assert (await client.get(f"{API_PREFIX}/sdv/X")).status_code == 404

    @pytest.mark.anyio
    async def test_create(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/visits")
        vid = r.json()["items"][0]["id"]
        r2 = await client.post(f"{API_PREFIX}/sdv", json={
            "visit_id": vid, "subject_id": "P001", "form": "Vitals", "field": "blood_pressure", "source_verified": True,
        })
        assert r2.status_code == 201


class TestReports:
    @pytest.mark.anyio
    async def test_list(self, client: AsyncClient):
        assert (await client.get(f"{API_PREFIX}/reports")).status_code == 200

    @pytest.mark.anyio
    async def test_get(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/reports")
        rid = r.json()["items"][0]["id"]
        assert (await client.get(f"{API_PREFIX}/reports/{rid}")).status_code == 200

    @pytest.mark.anyio
    async def test_get_not_found(self, client: AsyncClient):
        assert (await client.get(f"{API_PREFIX}/reports/X")).status_code == 404

    @pytest.mark.anyio
    async def test_create(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/visits")
        vid = r.json()["items"][0]["id"]
        assert (await client.post(f"{API_PREFIX}/reports", json={"visit_id": vid, "summary": "Test report summary"})).status_code == 201

    @pytest.mark.anyio
    async def test_update(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/reports")
        rid = r.json()["items"][0]["id"]
        assert (await client.put(f"{API_PREFIX}/reports/{rid}", json={"summary": "Updated summary"})).status_code == 200

    @pytest.mark.anyio
    async def test_update_not_found(self, client: AsyncClient):
        assert (await client.put(f"{API_PREFIX}/reports/X", json={"summary": "N"})).status_code == 404

    @pytest.mark.anyio
    async def test_submit(self, client: AsyncClient):
        # Create a fresh draft report to submit
        r = await client.get(f"{API_PREFIX}/visits")
        vid = r.json()["items"][0]["id"]
        new_r = await client.post(f"{API_PREFIX}/reports", json={"visit_id": vid, "summary": "Submit test"})
        rid = new_r.json()["id"]
        assert (await client.post(f"{API_PREFIX}/reports/{rid}/submit", json={"submitted_date": "2026-03-01T17:00:00Z"})).status_code == 200

    @pytest.mark.anyio
    async def test_submit_not_found(self, client: AsyncClient):
        assert (await client.post(f"{API_PREFIX}/reports/X/submit", json={"submitted_date": "2026-03-01T17:00:00Z"})).status_code == 404

    @pytest.mark.anyio
    async def test_approve(self, client: AsyncClient):
        # Create and submit a report, then approve
        r = await client.get(f"{API_PREFIX}/visits")
        vid = r.json()["items"][0]["id"]
        new_r = await client.post(f"{API_PREFIX}/reports", json={"visit_id": vid, "summary": "Approve test"})
        rid = new_r.json()["id"]
        await client.post(f"{API_PREFIX}/reports/{rid}/submit", json={"submitted_date": "2026-03-01T17:00:00Z"})
        assert (await client.post(f"{API_PREFIX}/reports/{rid}/approve")).status_code == 200

    @pytest.mark.anyio
    async def test_approve_not_found(self, client: AsyncClient):
        assert (await client.post(f"{API_PREFIX}/reports/X/approve")).status_code == 404


class TestCAPAs:
    @pytest.mark.anyio
    async def test_list(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/capas")
        assert r.status_code == 200
        assert r.json()["total"] == 4

    @pytest.mark.anyio
    async def test_get(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/capas")
        cid = r.json()["items"][0]["id"]
        assert (await client.get(f"{API_PREFIX}/capas/{cid}")).status_code == 200

    @pytest.mark.anyio
    async def test_get_not_found(self, client: AsyncClient):
        assert (await client.get(f"{API_PREFIX}/capas/X")).status_code == 404

    @pytest.mark.anyio
    async def test_create(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/findings")
        fid = r.json()["items"][0]["id"]
        r2 = await client.post(f"{API_PREFIX}/capas", json={
            "finding_id": fid, "root_cause": "Root cause analysis", "corrective_action": "Fix the issue",
            "preventive_action": "Prevent recurrence", "responsible_party": "CRA Smith", "due_date": "2026-04-01T00:00:00Z",
        })
        assert r2.status_code == 201

    @pytest.mark.anyio
    async def test_update(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/capas")
        cid = r.json()["items"][0]["id"]
        assert (await client.put(f"{API_PREFIX}/capas/{cid}", json={"description": "U"})).status_code == 200

    @pytest.mark.anyio
    async def test_update_not_found(self, client: AsyncClient):
        assert (await client.put(f"{API_PREFIX}/capas/X", json={"description": "N"})).status_code == 404

    @pytest.mark.anyio
    async def test_close(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/capas")
        cid = r.json()["items"][0]["id"]
        assert (await client.post(f"{API_PREFIX}/capas/{cid}/close", params={"effectiveness_check": "Verified effective"})).status_code == 200

    @pytest.mark.anyio
    async def test_close_not_found(self, client: AsyncClient):
        assert (await client.post(f"{API_PREFIX}/capas/X/close", params={"effectiveness_check": "N"})).status_code == 404


class TestMetrics:
    @pytest.mark.anyio
    async def test_metrics(self, client: AsyncClient):
        assert (await client.get(f"{API_PREFIX}/metrics")).status_code == 200

    @pytest.mark.anyio
    async def test_site_summary(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/visits")
        sid = r.json()["items"][0]["site_id"]
        assert (await client.get(f"{API_PREFIX}/site-summary/{sid}")).status_code == 200
