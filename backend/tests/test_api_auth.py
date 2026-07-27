"""
Tests d'intégration pour les endpoints d'authentification
Couvre : POST /auth/register, POST /auth/login, GET /auth/me, PUT /auth/me
"""
import pytest

pytestmark = pytest.mark.asyncio


# ─────────────────────────────────────────────────────────────
# POST /auth/register
# ─────────────────────────────────────────────────────────────

class TestRegister:

    async def test_inscription_succes(self, api_client):
        response = await api_client.post("/auth/register", json={
            "email": "test@example.com",
            "password": "password123",
            "full_name": "Test User",
        })
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["email"] == "test@example.com"

    async def test_email_deja_utilise_retourne_400(self, api_client):
        payload = {
            "email": "doublon@example.com",
            "password": "pass123",
            "full_name": "Doublon",
        }
        await api_client.post("/auth/register", json=payload)
        response = await api_client.post("/auth/register", json=payload)
        assert response.status_code == 400

    async def test_email_invalide_retourne_422(self, api_client):
        response = await api_client.post("/auth/register", json={
            "email": "pas-un-email",
            "password": "pass123",
            "full_name": "User",
        })
        assert response.status_code == 422

    async def test_champs_manquants_retourne_422(self, api_client):
        response = await api_client.post("/auth/register", json={
            "email": "test@test.com",
        })
        assert response.status_code == 422


# ─────────────────────────────────────────────────────────────
# POST /auth/login
# ─────────────────────────────────────────────────────────────

class TestLogin:

    async def test_login_succes(self, api_client):
        await api_client.post("/auth/register", json={
            "email": "login@example.com",
            "password": "motdepasse",
            "full_name": "Login User",
        })
        response = await api_client.post("/auth/login", json={
            "email": "login@example.com",
            "password": "motdepasse",
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["email"] == "login@example.com"

    async def test_mauvais_mot_de_passe_retourne_401(self, api_client):
        await api_client.post("/auth/register", json={
            "email": "wrong@example.com",
            "password": "correct",
            "full_name": "User",
        })
        response = await api_client.post("/auth/login", json={
            "email": "wrong@example.com",
            "password": "incorrect",
        })
        assert response.status_code == 401

    async def test_email_inexistant_retourne_401(self, api_client):
        response = await api_client.post("/auth/login", json={
            "email": "inexistant@example.com",
            "password": "nimportequoi",
        })
        assert response.status_code == 401

    async def test_token_jwt_valide_dans_reponse(self, api_client):
        await api_client.post("/auth/register", json={
            "email": "token@example.com",
            "password": "testpass",
            "full_name": "Token User",
        })
        response = await api_client.post("/auth/login", json={
            "email": "token@example.com",
            "password": "testpass",
        })
        token = response.json()["access_token"]
        assert len(token.split(".")) == 3  # header.payload.signature


# ─────────────────────────────────────────────────────────────
# GET /auth/me
# ─────────────────────────────────────────────────────────────

class TestGetMe:

    async def _create_and_login(self, api_client, email="me@example.com"):
        await api_client.post("/auth/register", json={
            "email": email,
            "password": "pass123",
            "full_name": "Me User",
        })
        resp = await api_client.post("/auth/login", json={
            "email": email,
            "password": "pass123",
        })
        return resp.json()["access_token"]

    async def test_get_me_avec_token_valide(self, api_client):
        token = await self._create_and_login(api_client)
        response = await api_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json()["email"] == "me@example.com"

    async def test_get_me_sans_token_retourne_401(self, api_client):
        response = await api_client.get("/auth/me")
        assert response.status_code == 401

    async def test_get_me_token_invalide_retourne_401(self, api_client):
        response = await api_client.get("/auth/me", headers={"Authorization": "Bearer token.faux.ici"})
        assert response.status_code == 401

    async def test_get_me_retourne_full_name(self, api_client):
        await api_client.post("/auth/register", json={
            "email": "fullname@example.com",
            "password": "pass123",
            "full_name": "Narjess Mhibik",
        })
        resp = await api_client.post("/auth/login", json={
            "email": "fullname@example.com",
            "password": "pass123",
        })
        token = resp.json()["access_token"]
        response = await api_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.json()["full_name"] == "Narjess Mhibik"


# ─────────────────────────────────────────────────────────────
# PUT /auth/me
# ─────────────────────────────────────────────────────────────

class TestUpdateMe:

    async def test_mise_a_jour_full_name(self, api_client):
        await api_client.post("/auth/register", json={
            "email": "update@example.com",
            "password": "pass123",
            "full_name": "Ancien Nom",
        })
        resp = await api_client.post("/auth/login", json={
            "email": "update@example.com",
            "password": "pass123",
        })
        token = resp.json()["access_token"]

        response = await api_client.put(
            "/auth/me",
            json={"full_name": "Nouveau Nom"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["full_name"] == "Nouveau Nom"

    async def test_update_sans_token_retourne_401(self, api_client):
        response = await api_client.put("/auth/me", json={"full_name": "X"})
        assert response.status_code == 401
