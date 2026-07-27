"""
Tests d'intégration pour les endpoints /leads/
Couvre : GET /leads/, GET /leads/{id}, POST /leads/, DELETE /leads/{id},
         PUT /leads/{id}/status, GET /leads/feature-importance
"""
import pytest

pytestmark = pytest.mark.asyncio

# ─── Helpers ──────────────────────────────────────────────────────────────────

LEAD_PAYLOAD = {
    "company":    "Historiar Tech",
    "email":      "contact@historiar.io",
    "phone":      "+216 99 000 000",
    "website":    "https://historiar.io",
    "sector":     "Informatique & Tech",
    "region":     "Tunis",
    "source":     "manual",
    "first_name": "Narjess",
    "last_name":  "Test",
}


# ─── GET /leads/ ──────────────────────────────────────────────────────────────

class TestListLeads:

    async def test_liste_vide_par_defaut(self, api_client):
        response = await api_client.get("/leads/")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] == 0
        assert data["items"] == []

    async def test_pagination_defaut(self, api_client):
        response = await api_client.get("/leads/")
        data = response.json()
        assert data["page"] == 1
        assert data["limit"] == 50

    async def test_liste_apres_creation(self, api_client):
        await api_client.post("/leads/", json=LEAD_PAYLOAD)
        response = await api_client.get("/leads/")
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1

    async def test_filtre_par_segment(self, api_client):
        response = await api_client.get("/leads/?segment=Chaud")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["items"], list)

    async def test_filtre_par_secteur(self, api_client):
        response = await api_client.get("/leads/?sector=Informatique+%26+Tech")
        assert response.status_code == 200

    async def test_filtre_has_email_vrai(self, api_client):
        await api_client.post("/leads/", json=LEAD_PAYLOAD)
        response = await api_client.get("/leads/?has_email=true")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    async def test_filtre_has_email_faux(self, api_client):
        await api_client.post("/leads/", json={"company": "Sans Email", "source": "manual"})
        response = await api_client.get("/leads/?has_email=false")
        assert response.status_code == 200

    async def test_recherche_par_entreprise(self, api_client):
        await api_client.post("/leads/", json=LEAD_PAYLOAD)
        response = await api_client.get("/leads/?search=Historiar")
        data = response.json()
        assert data["total"] >= 1

    async def test_pagination_page_2(self, api_client):
        for i in range(3):
            await api_client.post("/leads/", json={"company": f"Corp {i}", "source": "manual"})
        response = await api_client.get("/leads/?page=1&limit=2")
        data = response.json()
        assert data["limit"] == 2
        assert data["pages"] >= 2


# ─── GET /leads/{id} ──────────────────────────────────────────────────────────

class TestGetLead:

    async def test_get_lead_existant(self, api_client):
        created = (await api_client.post("/leads/", json=LEAD_PAYLOAD)).json()
        lead_id = created["id"]
        response = await api_client.get(f"/leads/{lead_id}")
        assert response.status_code == 200
        assert response.json()["id"] == lead_id

    async def test_get_lead_inexistant_retourne_404(self, api_client):
        response = await api_client.get("/leads/99999")
        assert response.status_code == 404

    async def test_lead_contient_les_champs_attendus(self, api_client):
        created = (await api_client.post("/leads/", json=LEAD_PAYLOAD)).json()
        response = await api_client.get(f"/leads/{created['id']}")
        data = response.json()
        assert data["company"] == "Historiar Tech"
        assert data["email"] == "contact@historiar.io"


# ─── POST /leads/ ─────────────────────────────────────────────────────────────

class TestCreateLead:

    async def test_creation_succes(self, api_client):
        response = await api_client.post("/leads/", json=LEAD_PAYLOAD)
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["company"] == "Historiar Tech"

    async def test_lead_minimal(self, api_client):
        response = await api_client.post("/leads/", json={"company": "Mini Corp"})
        assert response.status_code == 200
        assert response.json()["company"] == "Mini Corp"

    async def test_lead_avec_email(self, api_client):
        payload = {"email": "ceo@startup.tn", "company": "Startup TN", "source": "google_maps"}
        response = await api_client.post("/leads/", json=payload)
        assert response.status_code == 200
        assert response.json()["email"] == "ceo@startup.tn"

    async def test_score_initial_est_zero(self, api_client):
        response = await api_client.post("/leads/", json=LEAD_PAYLOAD)
        data = response.json()
        # lead_score est NULL ou 0 à la création
        assert data.get("lead_score") in (None, 0, 0.0)

    async def test_statut_initial_est_new(self, api_client):
        response = await api_client.post("/leads/", json=LEAD_PAYLOAD)
        assert response.json().get("status") == "new"

    async def test_plusieurs_leads_crees(self, api_client):
        for i in range(5):
            r = await api_client.post("/leads/", json={"company": f"Corp {i}", "source": "manual"})
            assert r.status_code == 200
        total = (await api_client.get("/leads/")).json()["total"]
        assert total == 5


# ─── DELETE /leads/{id} ───────────────────────────────────────────────────────

class TestDeleteLead:

    async def test_suppression_succes(self, api_client):
        created = (await api_client.post("/leads/", json=LEAD_PAYLOAD)).json()
        response = await api_client.delete(f"/leads/{created['id']}")
        assert response.status_code == 200
        assert response.json()["success"] is True

    async def test_lead_supprime_non_retrouve(self, api_client):
        created = (await api_client.post("/leads/", json=LEAD_PAYLOAD)).json()
        await api_client.delete(f"/leads/{created['id']}")
        response = await api_client.get(f"/leads/{created['id']}")
        assert response.status_code == 404

    async def test_suppression_inexistant_retourne_404(self, api_client):
        response = await api_client.delete("/leads/99999")
        assert response.status_code == 404


# ─── PUT /leads/{id}/status ───────────────────────────────────────────────────

class TestUpdateLeadStatus:

    async def test_mise_a_jour_statut(self, api_client):
        created = (await api_client.post("/leads/", json=LEAD_PAYLOAD)).json()
        response = await api_client.put(
            f"/leads/{created['id']}/status",
            json={"status": "contacted"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "contacted"

    async def test_update_statut_inexistant_retourne_404(self, api_client):
        response = await api_client.put("/leads/99999/status", json={"status": "contacted"})
        assert response.status_code == 404


# ─── GET /leads/feature-importance ───────────────────────────────────────────

class TestFeatureImportance:

    async def test_retourne_une_liste(self, api_client):
        response = await api_client.get("/leads/feature-importance")
        assert response.status_code == 200
        data = response.json()
        assert "features" in data
        assert isinstance(data["features"], list)
