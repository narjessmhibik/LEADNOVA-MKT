"""
Tests d'intégration pour les endpoints /scraping/
Couvre : stats, jobs (CRUD), status update, cancel, delete, recent-leads, linkedin/status
"""
import pytest

pytestmark = pytest.mark.asyncio

JOB_PAYLOAD = {
    "name":      "Test Scraping Job",
    "source":    "Google Maps",
    "keywords":  "restaurants Tunis",
    "location":  "Tunis",
    "sector":    "Restauration",
    "maxLeads":  50,
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _create_job(api_client, **overrides):
    payload = {**JOB_PAYLOAD, **overrides}
    r = await api_client.post("/scraping/jobs", json=payload)
    assert r.status_code == 200
    return r.json()["id"]


# ─── Stats ────────────────────────────────────────────────────────────────────

class TestScrapingStats:

    async def test_stats_db_vide(self, api_client):
        response = await api_client.get("/scraping/stats")
        assert response.status_code == 200
        data = response.json()
        assert "jobs_actifs"     in data
        assert "leads_collectes" in data
        assert "en_attente"      in data
        assert "taux_succes"     in data
        assert "total_jobs"      in data

    async def test_stats_valeurs_initiales(self, api_client):
        response = await api_client.get("/scraping/stats")
        data = response.json()
        assert data["jobs_actifs"] == 0
        assert data["total_jobs"] == 0

    async def test_stats_apres_creation_job(self, api_client):
        await _create_job(api_client)
        response = await api_client.get("/scraping/stats")
        data = response.json()
        assert data["total_jobs"] >= 1
        assert data["en_attente"] >= 1

    async def test_stats_leads_collectes_compte_leads(self, api_client):
        await api_client.post("/leads/", json={
            "company": "StatsCorp",
            "email":   "stats@test.tn",
            "source":  "google_maps",
        })
        response = await api_client.get("/scraping/stats")
        data = response.json()
        assert data["leads_collectes"] >= 1


# ─── Jobs CRUD ────────────────────────────────────────────────────────────────

class TestScrapingJobs:

    async def test_liste_jobs_vide(self, api_client):
        response = await api_client.get("/scraping/jobs")
        assert response.status_code == 200
        assert response.json() == []

    async def test_creation_job(self, api_client):
        response = await api_client.post("/scraping/jobs", json=JOB_PAYLOAD)
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["name"] == "Test Scraping Job"
        assert data["source"] == "Google Maps"

    async def test_creation_job_statut_initial(self, api_client):
        response = await api_client.post("/scraping/jobs", json=JOB_PAYLOAD)
        data = response.json()
        assert data["status"] == "en_attente"

    async def test_creation_job_minimal(self, api_client):
        response = await api_client.post("/scraping/jobs", json={
            "name":   "Job Minimal",
            "source": "LinkedIn",
        })
        assert response.status_code == 200
        assert response.json()["name"] == "Job Minimal"

    async def test_liste_apres_creation(self, api_client):
        await _create_job(api_client)
        response = await api_client.get("/scraping/jobs")
        assert len(response.json()) == 1

    async def test_plusieurs_jobs(self, api_client):
        for i in range(3):
            await _create_job(api_client, name=f"Job {i}")
        response = await api_client.get("/scraping/jobs")
        assert len(response.json()) == 3

    async def test_job_contient_champs_attendus(self, api_client):
        await _create_job(api_client)
        jobs = (await api_client.get("/scraping/jobs")).json()
        job = jobs[0]
        for field in ("id", "name", "source", "status", "max_leads"):
            assert field in job


# ─── Update Job Status ────────────────────────────────────────────────────────

class TestUpdateJobStatus:

    async def test_update_statut_actif(self, api_client):
        job_id = await _create_job(api_client)
        response = await api_client.patch(
            f"/scraping/jobs/{job_id}/status",
            json={"status": "actif"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "actif"

    async def test_update_statut_termine(self, api_client):
        job_id = await _create_job(api_client)
        response = await api_client.patch(
            f"/scraping/jobs/{job_id}/status",
            json={"status": "termine", "leads_collected": 42, "success_rate": 95.0},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "termine"

    async def test_update_statut_job_inexistant(self, api_client):
        response = await api_client.patch(
            "/scraping/jobs/99999/status",
            json={"status": "actif"},
        )
        assert response.status_code == 404

    async def test_update_statut_actif_set_started_at(self, api_client):
        job_id = await _create_job(api_client)
        await api_client.patch(
            f"/scraping/jobs/{job_id}/status",
            json={"status": "actif"},
        )
        jobs = (await api_client.get("/scraping/jobs")).json()
        job = next(j for j in jobs if j["id"] == job_id)
        assert job.get("started_at") is not None


# ─── Cancel Job ───────────────────────────────────────────────────────────────

class TestCancelJob:

    async def test_cancel_job_en_attente(self, api_client):
        job_id = await _create_job(api_client)
        response = await api_client.post(f"/scraping/jobs/{job_id}/cancel")
        assert response.status_code == 200
        assert response.json()["status"] == "annule"

    async def test_cancel_job_deja_termine(self, api_client):
        job_id = await _create_job(api_client)
        await api_client.patch(
            f"/scraping/jobs/{job_id}/status",
            json={"status": "termine"},
        )
        response = await api_client.post(f"/scraping/jobs/{job_id}/cancel")
        # Job déjà terminé → retourne le job tel quel
        assert response.status_code == 200
        assert response.json()["status"] == "termine"

    async def test_cancel_job_inexistant(self, api_client):
        response = await api_client.post("/scraping/jobs/99999/cancel")
        assert response.status_code == 404


# ─── Delete Job ───────────────────────────────────────────────────────────────

class TestDeleteJob:

    async def test_suppression_job(self, api_client):
        job_id = await _create_job(api_client)
        response = await api_client.delete(f"/scraping/jobs/{job_id}")
        assert response.status_code == 200
        assert "message" in response.json()

    async def test_job_disparu_apres_suppression(self, api_client):
        job_id = await _create_job(api_client)
        await api_client.delete(f"/scraping/jobs/{job_id}")
        jobs = (await api_client.get("/scraping/jobs")).json()
        assert all(j["id"] != job_id for j in jobs)

    async def test_suppression_job_inexistant(self, api_client):
        response = await api_client.delete("/scraping/jobs/99999")
        assert response.status_code == 200


# ─── Recent Leads ─────────────────────────────────────────────────────────────

class TestRecentLeads:

    async def test_recent_leads_db_vide(self, api_client):
        response = await api_client.get("/scraping/recent-leads")
        assert response.status_code == 200
        assert response.json() == []

    async def test_recent_leads_avec_leads(self, api_client):
        await api_client.post("/leads/", json={
            "company": "RecentCorp",
            "email":   "recent@test.tn",
            "source":  "google_maps",
        })
        response = await api_client.get("/scraping/recent-leads")
        assert response.status_code == 200
        assert len(response.json()) >= 1

    async def test_recent_leads_structure(self, api_client):
        await api_client.post("/leads/", json={
            "company": "StructCorp",
            "sector":  "Finance",
            "region":  "Sfax",
            "source":  "google_maps",
        })
        response = await api_client.get("/scraping/recent-leads")
        data = response.json()
        if data:
            lead = data[0]
            for field in ("id", "company", "sector", "region", "email", "phone", "score", "segment"):
                assert field in lead

    async def test_recent_leads_parametre_limit(self, api_client):
        for i in range(5):
            await api_client.post("/leads/", json={
                "company": f"LimitCorp {i}",
                "source":  "google_maps",
            })
        response = await api_client.get("/scraping/recent-leads?limit=3")
        assert response.status_code == 200
        assert len(response.json()) <= 3


# ─── LinkedIn Status ──────────────────────────────────────────────────────────

class TestLinkedInStatus:

    async def test_linkedin_status_retourne_200(self, api_client):
        response = await api_client.get("/scraping/linkedin/status")
        assert response.status_code == 200

    async def test_linkedin_status_structure(self, api_client):
        response = await api_client.get("/scraping/linkedin/status")
        data = response.json()
        assert "session_exists" in data
        assert "message" in data

    async def test_linkedin_status_session_inexistante(self, api_client):
        response = await api_client.get("/scraping/linkedin/status")
        data = response.json()
        assert isinstance(data["session_exists"], bool)
        assert isinstance(data["message"], str)
