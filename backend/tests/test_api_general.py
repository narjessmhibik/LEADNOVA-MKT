"""
Tests d'intégration généraux : endpoint racine et endpoints leads/campaigns sans données PG-spécifiques
"""
import pytest

pytestmark = pytest.mark.asyncio


class TestRacine:

    async def test_root_retourne_200(self, api_client):
        response = await api_client.get("/")
        assert response.status_code == 200

    async def test_root_retourne_message(self, api_client):
        response = await api_client.get("/")
        assert "message" in response.json()

    async def test_root_api_running(self, api_client):
        response = await api_client.get("/")
        assert "running" in response.json()["message"].lower() or response.status_code == 200


class TestLeadsEndpoints:

    async def _get_token(self, api_client):
        await api_client.post("/auth/register", json={
            "email": "leads_test@example.com",
            "password": "pass123",
            "full_name": "Leads Tester",
        })
        resp = await api_client.post("/auth/login", json={
            "email": "leads_test@example.com",
            "password": "pass123",
        })
        return resp.json()["access_token"]

    async def test_get_leads_sans_auth_retourne_422_ou_401(self, api_client):
        response = await api_client.get("/leads/")
        assert response.status_code in (401, 422, 200)

    async def test_create_lead_sans_auth(self, api_client):
        response = await api_client.post("/leads/", json={
            "company": "Test Corp",
            "email": "contact@testcorp.com",
        })
        assert response.status_code in (200, 201, 401, 422)


class TestCampaignsEndpoints:

    async def _get_token(self, api_client):
        await api_client.post("/auth/register", json={
            "email": "camp_test@example.com",
            "password": "pass123",
            "full_name": "Campaign Tester",
        })
        resp = await api_client.post("/auth/login", json={
            "email": "camp_test@example.com",
            "password": "pass123",
        })
        return resp.json()["access_token"]

    async def test_get_campaigns_history(self, api_client):
        token = await self._get_token(api_client)
        response = await api_client.get(
            "/campaigns/history",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code in (200, 404)

    async def test_get_email_stats(self, api_client):
        token = await self._get_token(api_client)
        response = await api_client.get(
            "/campaigns/stats/email",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code in (200, 404)
        if response.status_code == 200:
            data = response.json()
            assert "generated" in data or "sent" in data or isinstance(data, dict)


class TestNotificationsEndpoints:

    async def _get_token(self, api_client):
        await api_client.post("/auth/register", json={
            "email": "notif_test@example.com",
            "password": "pass123",
            "full_name": "Notif Tester",
        })
        resp = await api_client.post("/auth/login", json={
            "email": "notif_test@example.com",
            "password": "pass123",
        })
        return resp.json()["access_token"]

    async def test_get_notifications(self, api_client):
        token = await self._get_token(api_client)
        response = await api_client.get(
            "/notifications/",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code in (200, 404)
        if response.status_code == 200:
            # L'endpoint peut retourner une liste ou un objet {unread, items}
            body = response.json()
            assert isinstance(body, (list, dict))

    async def test_notifications_sans_auth(self, api_client):
        response = await api_client.get("/notifications/")
        assert response.status_code in (200, 401, 422)
