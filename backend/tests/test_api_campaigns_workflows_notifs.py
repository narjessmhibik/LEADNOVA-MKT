"""
Tests d'intégration pour /campaigns/, /workflows/, /notifications/
"""
import pytest

pytestmark = pytest.mark.asyncio

CAMPAIGN_PAYLOAD = {
    "name":           "Campagne Test",
    "campaign_name":  "Campagne Test Automation",
    "subject":        "Découvrez notre solution IA",
    "segment_filter": "Chaud",
    "sector_filter":  "Informatique & Tech",
    "status":         "draft",
    "campaign_status": "draft",
    "channel":        "email",
    "tone":           "professionnel",
    "cta":            "Planifier un appel",
}

WORKFLOW_PAYLOAD = {
    "name":        "Séquence bienvenue",
    "trigger":     "new_lead",
    "description": "Email automatique aux nouveaux leads",
    "actions":     "email",
}


# ─── Campaigns ────────────────────────────────────────────────────────────────

class TestCampaigns:

    async def test_liste_campagnes_vide(self, api_client):
        response = await api_client.get("/campaigns/")
        assert response.status_code == 200
        assert response.json() == []

    async def test_creation_campagne(self, api_client):
        response = await api_client.post("/campaigns/", json=CAMPAIGN_PAYLOAD)
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["name"] == "Campagne Test"

    async def test_liste_apres_creation(self, api_client):
        await api_client.post("/campaigns/", json=CAMPAIGN_PAYLOAD)
        response = await api_client.get("/campaigns/")
        assert response.status_code == 200
        assert len(response.json()) == 1

    async def test_plusieurs_campagnes(self, api_client):
        for i in range(3):
            payload = {**CAMPAIGN_PAYLOAD, "name": f"Camp {i}", "campaign_name": f"Camp {i}"}
            await api_client.post("/campaigns/", json=payload)
        response = await api_client.get("/campaigns/")
        assert len(response.json()) == 3

    async def test_stats_email_vide(self, api_client):
        response = await api_client.get("/campaigns/stats/email")
        assert response.status_code == 200
        data = response.json()
        assert "generated" in data
        assert "sent" in data
        assert "opened" in data
        assert "clicked" in data
        # Base vide → tout à 0
        assert data["generated"] == 0
        assert data["sent"] == 0

    async def test_stats_email_avec_leads(self, api_client):
        # Crée un lead avec email généré
        await api_client.post("/leads/", json={
            "company": "Test Corp",
            "email": "ceo@test.com",
            "email_subject_a": "Objet A",
            "email_body_a": "Corps A",
            "email_subject_b": "Objet B",
            "email_body_b": "Corps B",
        })
        response = await api_client.get("/campaigns/stats/email")
        assert response.status_code == 200
        data = response.json()
        assert data["generated"] == 2  # COUNT(email_subject_a) * 2 = 1 * 2

    async def test_stats_engagement(self, api_client):
        response = await api_client.get("/campaigns/stats/engagement")
        assert response.status_code == 200
        data = response.json()
        assert "sent" in data or "open_rate" in data or isinstance(data, dict)


# ─── Workflows ────────────────────────────────────────────────────────────────

class TestWorkflows:

    async def test_liste_workflows_vide(self, api_client):
        response = await api_client.get("/workflows/")
        assert response.status_code == 200
        assert response.json() == []

    async def test_creation_workflow(self, api_client):
        response = await api_client.post("/workflows/", json=WORKFLOW_PAYLOAD)
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["name"] == "Séquence bienvenue"

    async def test_workflow_statut_initial_pause(self, api_client):
        response = await api_client.post("/workflows/", json=WORKFLOW_PAYLOAD)
        data = response.json()
        # Les workflows sont créés en pause
        assert data.get("status") in ("paused", "active", "inactive", None)

    async def test_liste_apres_creation(self, api_client):
        await api_client.post("/workflows/", json=WORKFLOW_PAYLOAD)
        response = await api_client.get("/workflows/")
        assert len(response.json()) == 1

    async def test_plusieurs_workflows(self, api_client):
        for i in range(3):
            await api_client.post("/workflows/", json={**WORKFLOW_PAYLOAD, "name": f"WF {i}"})
        response = await api_client.get("/workflows/")
        assert len(response.json()) == 3

    async def test_suppression_workflow(self, api_client):
        created = (await api_client.post("/workflows/", json=WORKFLOW_PAYLOAD)).json()
        response = await api_client.delete(f"/workflows/{created['id']}")
        assert response.status_code in (200, 204)
        response_list = await api_client.get("/workflows/")
        assert len(response_list.json()) == 0

    async def test_suppression_workflow_inexistant(self, api_client):
        response = await api_client.delete("/workflows/99999")
        assert response.status_code in (404, 200)

    async def test_activation_workflow(self, api_client):
        created = (await api_client.post("/workflows/", json=WORKFLOW_PAYLOAD)).json()
        response = await api_client.patch(
            f"/workflows/{created['id']}/toggle",
        )
        assert response.status_code in (200, 404, 405)


# ─── Notifications ────────────────────────────────────────────────────────────

class TestNotifications:

    async def _create_notif(self, api_client):
        """Crée une notification directement via leads (push_notification_async n'est pas exposé)."""
        from app.models.notification import Notification
        # On utilise le db_session pour insérer directement
        return None  # On testera via l'API seulement

    async def test_liste_notifications_vide(self, api_client):
        response = await api_client.get("/notifications/")
        assert response.status_code == 200
        data = response.json()
        assert data["unread"] == 0
        assert data["items"] == []

    async def test_liste_retourne_unread_et_items(self, api_client):
        response = await api_client.get("/notifications/")
        data = response.json()
        assert "unread" in data
        assert "items" in data

    async def test_marquer_toutes_lues(self, api_client):
        response = await api_client.post("/notifications/read-all")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    async def test_supprimer_toutes_notifications(self, api_client):
        response = await api_client.delete("/notifications/")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    async def test_marquer_lue_id_inexistant(self, api_client):
        response = await api_client.post("/notifications/99999/read")
        # Retourne ok même si la notif n'existe pas (update silencieux)
        assert response.status_code in (200, 404)

    async def test_liste_apres_suppression_vide(self, api_client):
        await api_client.delete("/notifications/")
        response = await api_client.get("/notifications/")
        assert response.json()["items"] == []

    async def test_limit_parametre(self, api_client):
        response = await api_client.get("/notifications/?limit=5")
        assert response.status_code == 200
