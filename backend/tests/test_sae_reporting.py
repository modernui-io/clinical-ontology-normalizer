"""Tests for SAE Regulatory Reporting API (CLINICAL-SAE)."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

API_PREFIX = "/api/v1/sae-reporting"


@pytest.fixture(autouse=True)
def reset_service():
    from app.services.sae_reporting_service import reset_sae_reporting_service
    reset_sae_reporting_service()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=True) as c:
        yield c


class TestSeedData:
    @pytest.mark.anyio
    async def test_seed_reports(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/")
        assert r.status_code == 200
        assert r.json()["total"] == 10

    @pytest.mark.anyio
    async def test_reports_have_ids(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/")
        for item in r.json()["items"]:
            assert "id" in item


class TestSAECrud:
    @pytest.mark.anyio
    async def test_list(self, client: AsyncClient):
        assert (await client.get(f"{API_PREFIX}/")).status_code == 200

    @pytest.mark.anyio
    async def test_get(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/")
        rid = r.json()["items"][0]["id"]
        assert (await client.get(f"{API_PREFIX}/{rid}")).status_code == 200

    @pytest.mark.anyio
    async def test_get_not_found(self, client: AsyncClient):
        assert (await client.get(f"{API_PREFIX}/NONEXISTENT")).status_code == 404

    @pytest.mark.anyio
    async def test_create(self, client: AsyncClient):
        r = await client.post(f"{API_PREFIX}/", json={
            "trial_id": "TRIAL-001", "site_id": "SITE-001", "subject_id": "SUBJ-100",
            "event_term": "Headache", "event_description": "Severe headache",
            "onset_date": "2026-01-10T00:00:00Z", "awareness_date": "2026-01-11T00:00:00Z",
            "seriousness": "hospitalization", "outcome": "recovered",
            "study_drug": "Dupixent", "initial_narrative": "Patient reported headache",
        })
        assert r.status_code == 201
        assert r.json()["event_term"] == "Headache"

    @pytest.mark.anyio
    async def test_update(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/")
        rid = r.json()["items"][0]["id"]
        r2 = await client.put(f"{API_PREFIX}/{rid}", json={"outcome": "recovered"})
        assert r2.status_code == 200

    @pytest.mark.anyio
    async def test_update_not_found(self, client: AsyncClient):
        assert (await client.put(f"{API_PREFIX}/X", json={"outcome": "recovered"})).status_code == 404

    @pytest.mark.anyio
    async def test_delete(self, client: AsyncClient):
        r = await client.post(f"{API_PREFIX}/", json={
            "trial_id": "T", "site_id": "S-DEL", "subject_id": "S",
            "event_term": "Del", "event_description": "Del event",
            "onset_date": "2026-01-01T00:00:00Z", "awareness_date": "2026-01-02T00:00:00Z",
            "seriousness": "death", "outcome": "fatal",
            "study_drug": "Test Drug", "initial_narrative": "Test narrative",
        })
        assert (await client.delete(f"{API_PREFIX}/{r.json()['id']}")).status_code == 204

    @pytest.mark.anyio
    async def test_delete_not_found(self, client: AsyncClient):
        assert (await client.delete(f"{API_PREFIX}/X")).status_code == 404


class TestLifecycle:
    @pytest.mark.anyio
    async def test_submit_for_review(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/")
        rid = r.json()["items"][0]["id"]
        assert (await client.post(f"{API_PREFIX}/{rid}/submit-for-review")).status_code == 200

    @pytest.mark.anyio
    async def test_submit_not_found(self, client: AsyncClient):
        assert (await client.post(f"{API_PREFIX}/X/submit-for-review")).status_code == 404

    @pytest.mark.anyio
    async def test_approve_review(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/")
        rid = r.json()["items"][0]["id"]
        await client.post(f"{API_PREFIX}/{rid}/submit-for-review")
        assert (await client.post(f"{API_PREFIX}/{rid}/approve-review")).status_code == 200

    @pytest.mark.anyio
    async def test_approve_not_found(self, client: AsyncClient):
        assert (await client.post(f"{API_PREFIX}/X/approve-review")).status_code == 404

    @pytest.mark.anyio
    async def test_close(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/")
        rid = r.json()["items"][0]["id"]
        await client.post(f"{API_PREFIX}/{rid}/submit-for-review")
        await client.post(f"{API_PREFIX}/{rid}/approve-review")
        assert (await client.post(f"{API_PREFIX}/{rid}/close")).status_code == 200

    @pytest.mark.anyio
    async def test_close_not_found(self, client: AsyncClient):
        assert (await client.post(f"{API_PREFIX}/X/close")).status_code == 404

    @pytest.mark.anyio
    async def test_follow_up(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/")
        rid = r.json()["items"][0]["id"]
        r2 = await client.post(f"{API_PREFIX}/{rid}/follow-up", json={
            "trial_id": "TRIAL-001", "site_id": "SITE-001", "subject_id": "SUBJ-100",
            "event_term": "Headache follow-up", "event_description": "Follow-up assessment",
            "onset_date": "2026-01-10T00:00:00Z", "awareness_date": "2026-01-15T00:00:00Z",
            "seriousness": "hospitalization", "outcome": "recovering",
            "study_drug": "Dupixent", "initial_narrative": "Follow-up report",
        })
        assert r2.status_code == 201

    @pytest.mark.anyio
    async def test_follow_up_not_found(self, client: AsyncClient):
        r = await client.post(f"{API_PREFIX}/X/follow-up", json={
            "trial_id": "TRIAL-001", "site_id": "SITE-001", "subject_id": "SUBJ-100",
            "event_term": "Test", "event_description": "Test",
            "onset_date": "2026-01-10T00:00:00Z", "awareness_date": "2026-01-11T00:00:00Z",
            "seriousness": "hospitalization", "outcome": "recovered",
            "study_drug": "Test", "initial_narrative": "Test",
        })
        assert r.status_code in (400, 404)

    @pytest.mark.anyio
    async def test_final(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/")
        rid = r.json()["items"][0]["id"]
        r2 = await client.post(f"{API_PREFIX}/{rid}/final", json={
            "trial_id": "TRIAL-001", "site_id": "SITE-001", "subject_id": "SUBJ-100",
            "event_term": "Headache final", "event_description": "Final assessment",
            "onset_date": "2026-01-10T00:00:00Z", "awareness_date": "2026-01-15T00:00:00Z",
            "seriousness": "hospitalization", "outcome": "recovered",
            "study_drug": "Dupixent", "initial_narrative": "Final report",
        })
        assert r2.status_code == 201

    @pytest.mark.anyio
    async def test_final_not_found(self, client: AsyncClient):
        r = await client.post(f"{API_PREFIX}/X/final", json={
            "trial_id": "TRIAL-001", "site_id": "SITE-001", "subject_id": "SUBJ-100",
            "event_term": "Test", "event_description": "Test",
            "onset_date": "2026-01-10T00:00:00Z", "awareness_date": "2026-01-11T00:00:00Z",
            "seriousness": "hospitalization", "outcome": "recovered",
            "study_drug": "Test", "initial_narrative": "Test",
        })
        assert r.status_code in (400, 404)


class TestCausality:
    @pytest.mark.anyio
    async def test_list_causality(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/")
        rid = r.json()["items"][0]["id"]
        assert (await client.get(f"{API_PREFIX}/{rid}/causality-records")).status_code == 200

    @pytest.mark.anyio
    async def test_create_causality(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/")
        rid = r.json()["items"][0]["id"]
        r2 = await client.post(f"{API_PREFIX}/{rid}/causality-records", json={
            "assessor": "Dr. Smith", "assessment": "possibly_related", "rationale": "Temporal relationship",
        })
        assert r2.status_code == 201

    @pytest.mark.anyio
    async def test_get_causality_record(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/")
        rid = r.json()["items"][0]["id"]
        cr = await client.get(f"{API_PREFIX}/{rid}/causality-records")
        if cr.json()["total"] > 0:
            crid = cr.json()["items"][0]["id"]
            assert (await client.get(f"{API_PREFIX}/causality-records/{crid}")).status_code == 200


class TestRegulatorySubmissions:
    @pytest.mark.anyio
    async def test_list_submissions(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/")
        rid = r.json()["items"][0]["id"]
        assert (await client.get(f"{API_PREFIX}/{rid}/regulatory-submissions")).status_code == 200

    @pytest.mark.anyio
    async def test_create_submission(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/")
        rid = r.json()["items"][0]["id"]
        # Must advance status before regulatory submission
        await client.post(f"{API_PREFIX}/{rid}/submit-for-review")
        await client.post(f"{API_PREFIX}/{rid}/approve-review")
        r2 = await client.post(f"{API_PREFIX}/{rid}/regulatory-submissions", json={
            "authority": "fda", "submission_type": "initial", "submitted_date": "2026-01-15T00:00:00Z",
        })
        assert r2.status_code == 201

    @pytest.mark.anyio
    async def test_get_submission(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/")
        rid = r.json()["items"][0]["id"]
        subs = await client.get(f"{API_PREFIX}/{rid}/regulatory-submissions")
        if subs.json()["total"] > 0:
            sid = subs.json()["items"][0]["id"]
            assert (await client.get(f"{API_PREFIX}/regulatory-submissions/{sid}")).status_code == 200

    @pytest.mark.anyio
    async def test_acknowledge_submission(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/")
        rid = r.json()["items"][0]["id"]
        subs = await client.get(f"{API_PREFIX}/{rid}/regulatory-submissions")
        if subs.json()["total"] > 0:
            sid = subs.json()["items"][0]["id"]
            assert (await client.post(f"{API_PREFIX}/regulatory-submissions/{sid}/acknowledge")).status_code == 200


class TestNarratives:
    @pytest.mark.anyio
    async def test_get_narrative(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/")
        # Find a report with a narrative (SAE-001 has one in seed data)
        rid = None
        for item in r.json()["items"]:
            nr = await client.get(f"{API_PREFIX}/{item['id']}/narrative")
            if nr.status_code == 200:
                rid = item["id"]
                break
        assert rid is not None, "No report with a narrative found in seed data"

    @pytest.mark.anyio
    async def test_narrative_not_found(self, client: AsyncClient):
        assert (await client.get(f"{API_PREFIX}/X/narrative")).status_code == 404

    @pytest.mark.anyio
    async def test_follow_up_narrative(self, client: AsyncClient):
        # Use SAE-001 which has a narrative in seed data
        r2 = await client.post(f"{API_PREFIX}/SAE-001/narrative/follow-up", json={"text": "Update"})
        assert r2.status_code == 200

    @pytest.mark.anyio
    async def test_medical_review_narrative(self, client: AsyncClient):
        r2 = await client.post(f"{API_PREFIX}/SAE-001/narrative/medical-review", json={"text": "Medical review by Dr. A: Assessment OK"})
        assert r2.status_code == 200


class TestForms:
    @pytest.mark.anyio
    async def test_medwatch(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/")
        rid = r.json()["items"][0]["id"]
        assert (await client.get(f"{API_PREFIX}/{rid}/medwatch")).status_code == 200

    @pytest.mark.anyio
    async def test_medwatch_not_found(self, client: AsyncClient):
        assert (await client.get(f"{API_PREFIX}/X/medwatch")).status_code == 404

    @pytest.mark.anyio
    async def test_cioms(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/")
        rid = r.json()["items"][0]["id"]
        assert (await client.get(f"{API_PREFIX}/{rid}/cioms")).status_code == 200

    @pytest.mark.anyio
    async def test_cioms_not_found(self, client: AsyncClient):
        assert (await client.get(f"{API_PREFIX}/X/cioms")).status_code == 404


class TestAggregates:
    @pytest.mark.anyio
    async def test_metrics(self, client: AsyncClient):
        assert (await client.get(f"{API_PREFIX}/metrics")).status_code == 200

    @pytest.mark.anyio
    async def test_overdue(self, client: AsyncClient):
        assert (await client.get(f"{API_PREFIX}/overdue")).status_code == 200

    @pytest.mark.anyio
    async def test_deadlines(self, client: AsyncClient):
        assert (await client.get(f"{API_PREFIX}/deadlines")).status_code == 200

    @pytest.mark.anyio
    async def test_safety_summary(self, client: AsyncClient):
        r = await client.get(f"{API_PREFIX}/")
        tid = r.json()["items"][0].get("trial_id", "TRIAL-001")
        assert (await client.get(f"{API_PREFIX}/trial/{tid}/safety-summary")).status_code == 200
