"""
Tests unitaires pour app/services/auth_service.py
Couvre : hash_password, verify_password, create_access_token, decode_token
"""
import pytest
from jose import JWTError

from app.services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    decode_token,
)


# ─────────────────────────────────────────────────────────────
# hash_password
# ─────────────────────────────────────────────────────────────

class TestHashPassword:

    def test_retourne_une_chaine(self):
        result = hash_password("motdepasse123")
        assert isinstance(result, str)

    def test_prefixe_bcrypt(self):
        result = hash_password("motdepasse123")
        assert result.startswith("$2b$")

    def test_deux_hashes_differents_meme_mdp(self):
        h1 = hash_password("motdepasse")
        h2 = hash_password("motdepasse")
        assert h1 != h2  # bcrypt utilise un salt aléatoire

    def test_hash_non_vide(self):
        result = hash_password("a")
        assert len(result) > 0

    def test_mot_de_passe_long_tronque(self):
        mdp_long = "a" * 200
        result = hash_password(mdp_long)
        assert isinstance(result, str)


# ─────────────────────────────────────────────────────────────
# verify_password
# ─────────────────────────────────────────────────────────────

class TestVerifyPassword:

    def test_mdp_correct_retourne_vrai(self):
        h = hash_password("monmotdepasse")
        assert verify_password("monmotdepasse", h) is True

    def test_mdp_incorrect_retourne_faux(self):
        h = hash_password("monmotdepasse")
        assert verify_password("mauvaismdp", h) is False

    def test_mdp_vide_retourne_faux(self):
        h = hash_password("monmotdepasse")
        assert verify_password("", h) is False

    def test_sensible_a_la_casse(self):
        h = hash_password("MonMotDePasse")
        assert verify_password("monmotdepasse", h) is False

    def test_espace_en_plus_retourne_faux(self):
        h = hash_password("monmdp")
        assert verify_password("monmdp ", h) is False

    def test_mdp_avec_caracteres_speciaux(self):
        mdp = "P@$$w0rd!#2024"
        h = hash_password(mdp)
        assert verify_password(mdp, h) is True


# ─────────────────────────────────────────────────────────────
# create_access_token
# ─────────────────────────────────────────────────────────────

class TestCreateAccessToken:

    def test_retourne_une_chaine(self):
        token = create_access_token({"sub": "test@example.com"})
        assert isinstance(token, str)

    def test_token_non_vide(self):
        token = create_access_token({"sub": "test@example.com"})
        assert len(token) > 20

    def test_format_jwt_trois_parties(self):
        token = create_access_token({"sub": "test@example.com"})
        parts = token.split(".")
        assert len(parts) == 3  # header.payload.signature

    def test_payload_personnalise_preserve(self):
        token = create_access_token({"sub": "user@test.com", "role": "admin"})
        payload = decode_token(token)
        assert payload.get("role") == "admin"

    def test_payloads_differents_donnent_tokens_differents(self):
        t1 = create_access_token({"sub": "a@b.com"})
        t2 = create_access_token({"sub": "autre@b.com"})
        assert t1 != t2


# ─────────────────────────────────────────────────────────────
# decode_token
# ─────────────────────────────────────────────────────────────

class TestDecodeToken:

    def test_decode_retourne_le_sub(self):
        token = create_access_token({"sub": "utilisateur@test.com"})
        payload = decode_token(token)
        assert payload["sub"] == "utilisateur@test.com"

    def test_decode_contient_exp(self):
        token = create_access_token({"sub": "a@b.com"})
        payload = decode_token(token)
        assert "exp" in payload

    def test_token_invalide_leve_exception(self):
        with pytest.raises(Exception):
            decode_token("ceci.nest.pas.un.jwt")

    def test_token_falsifie_leve_exception(self):
        token = create_access_token({"sub": "a@b.com"})
        falsifie = token[:-5] + "XXXXX"
        with pytest.raises(Exception):
            decode_token(falsifie)

    def test_token_vide_leve_exception(self):
        with pytest.raises(Exception):
            decode_token("")

    def test_sub_email_complexe(self):
        email = "narjess.mhibik+test@historiar.io"
        token = create_access_token({"sub": email})
        assert decode_token(token)["sub"] == email
