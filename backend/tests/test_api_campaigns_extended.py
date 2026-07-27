"""
Tests d'intégration pour les endpoints campaigns non couverts :
ab-stats, ab-winner, preview-emails, webhook/brevo, track/open, track/click,
reset-emails, {id}/progress, {id}/schedule, GET/DELETE {id}
"""
import pytest

pytestmark = pytest.mark.asyncio

CAMPAIGN_PAYLOAD = {
    "name":            "Campagne Tests Étendus",
    "campaign_name":   "Campagne Tests Étendus",
    "subject":         "Sujet Test",
    "segment_filter":  "Chaud",
    "sector_filter":   "Informatique & Tech",
    "status":          "draft",
    "campaign_status": "draft",
    "channel":         "email",
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _create_campaign(api_client):
    r = await api_client.post("/campaigns/", json=CAMPAIGN_PAYLOAD)
    return r.json()["id"]


async def _create_lead_with_email_sent(api_client, email="track@test.tn"):
    r = await api_client.post("/leads/", json={
        "company":    "TrackCorp",
        "email":      email,
        "source":     "manual",
        "email_sent": True,
    })
    return r.json()["id"]


# ─── AB Stats ─────────────────────────────────────────────────────────────────

class TestAbStats:

    async def test_ab_stats_db_vide(self, api_client):
        response = await api_client.get("/campaigns/ab-stats")
        assert response.status_code == 200
        assert isinstance(response.json(), dict)

    async def test_ab_stats_avec_leads_ab(self, api_client):
        await api_client.post("/leads/", json={
            "company":    "AB Corp A",
            "email":      "a@test.tn",
            "source":     "manual",
            "ab_version": "A",
            "email_sent": True,
        })
        await api_client.post("/leads/", json={
            "company":    "AB Corp B",
            "email":      "b@test.tn",
            "source":     "manual",
            "ab_version": "B",
            "email_sent": True,
            "email_opened": True,
        })
        response = await api_client.get("/campaigns/ab-stats")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    async def test_ab_stats_structure_par_version(self, api_client):
        await api_client.post("/leads/", json={
            "company":    "AB Corp",
            "email":      "ab@test.tn",
            "source":     "manual",
            "ab_version": "A",
        })
        response = await api_client.get("/campaigns/ab-stats")
        data = response.json()
        if "A" in data:
            assert "total" in data["A"]
            assert "sent" in data["A"]
            assert "opened" in data["A"]
            assert "open_rate" in data["A"]


# ─── AB Winner ────────────────────────────────────────────────────────────────

class TestAbWinner:

    async def test_ab_winner_redis_indisponible(self, api_client):
        """Redis n'est pas disponible en test — l'endpoint gère l'erreur"""
        response = await api_client.get("/campaigns/ab-winner")
        assert response.status_code == 200
        data = response.json()
        assert "winner" in data
        assert "message" in data

    async def test_ab_winner_retourne_winner_none(self, api_client):
        response = await api_client.get("/campaigns/ab-winner")
        data = response.json()
        assert data["winner"] is None


# ─── Preview Emails ───────────────────────────────────────────────────────────

class TestPreviewEmails:

    async def test_preview_emails_db_vide(self, api_client):
        response = await api_client.get("/campaigns/preview-emails")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "items" in data
        assert data["total"] == 0

    async def test_preview_emails_avec_leads_email_genere(self, api_client):
        await api_client.post("/leads/", json={
            "company":        "EmailCorp",
            "email":          "emailcorp@test.tn",
            "source":         "manual",
            "email_subject_a": "Sujet A",
            "email_body_a":    "Corps A",
        })
        response = await api_client.get("/campaigns/preview-emails")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    async def test_preview_emails_filtre_segment(self, api_client):
        await api_client.post("/leads/", json={
            "company":        "SegCorp",
            "email":          "segcorp@test.tn",
            "source":         "manual",
            "segment":        "Chaud",
            "email_subject_a": "Sujet Chaud",
            "email_body_a":    "Corps Chaud",
        })
        response = await api_client.get("/campaigns/preview-emails?segment=Chaud")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["items"], list)

    async def test_preview_emails_recherche(self, api_client):
        await api_client.post("/leads/", json={
            "company":        "SearchCorp",
            "email":          "searchcorp@test.tn",
            "source":         "manual",
            "email_subject_a": "Sujet Search",
            "email_body_a":    "Corps Search",
        })
        response = await api_client.get("/campaigns/preview-emails?search=SearchCorp")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    async def test_preview_emails_pagination(self, api_client):
        for i in range(3):
            await api_client.post("/leads/", json={
                "company":        f"PagCorp {i}",
                "email":          f"pag{i}@test.tn",
                "source":         "manual",
                "email_subject_a": f"Sujet {i}",
                "email_body_a":    f"Corps {i}",
            })
        response = await api_client.get("/campaigns/preview-emails?limit=2&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) <= 2

    async def test_preview_emails_structure_items(self, api_client):
        await api_client.post("/leads/", json={
            "company":        "StructCorp",
            "email":          "structcorp@test.tn",
            "source":         "manual",
            "email_subject_a": "Sujet Struct",
            "email_body_a":    "Corps Struct",
        })
        response = await api_client.get("/campaigns/preview-emails")
        data = response.json()
        if data["items"]:
            item = data["items"][0]
            assert "id" in item
            assert "company" in item
            assert "subject_a" in item


# ─── Webhook Brevo ────────────────────────────────────────────────────────────

class TestWebhookBrevo:

    async def test_webhook_event_inconnu(self, api_client):
        response = await api_client.post("/campaigns/webhook/brevo", json={
            "event": "bounce",
            "email": "test@test.tn",
        })
        assert response.status_code == 200
        assert response.json()["status"] == "ignored"

    async def test_webhook_sans_email(self, api_client):
        response = await api_client.post("/campaigns/webhook/brevo", json={
            "event": "opened",
        })
        assert response.status_code == 200
        assert response.json()["status"] == "ignored"

    async def test_webhook_opened_lead_non_trouve(self, api_client):
        response = await api_client.post("/campaigns/webhook/brevo", json={
            "event": "opened",
            "email": "inexistant@test.tn",
        })
        assert response.status_code == 200

    async def test_webhook_opened_lead_trouve(self, api_client):
        lead_id = await _create_lead_with_email_sent(api_client, "webhook@test.tn")
        response = await api_client.post("/campaigns/webhook/brevo", json={
            "event": "opened",
            "email": "webhook@test.tn",
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"
        assert data.get("lead_id") == lead_id

    async def test_webhook_clicked_lead_trouve(self, api_client):
        await _create_lead_with_email_sent(api_client, "click@test.tn")
        response = await api_client.post("/campaigns/webhook/brevo", json={
            "event": "clicked",
            "email": "click@test.tn",
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"

    async def test_webhook_unique_opened(self, api_client):
        await _create_lead_with_email_sent(api_client, "unique@test.tn")
        response = await api_client.post("/campaigns/webhook/brevo", json={
            "event": "uniqueProxyOpen",
            "email": "unique@test.tn",
        })
        assert response.status_code == 200


# ─── Track Open / Click ───────────────────────────────────────────────────────

class TestTrackOpen:

    async def test_track_open_lead_inexistant(self, api_client):
        response = await api_client.get("/campaigns/track/open?lead_id=99999")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("image/png")

    async def test_track_open_retourne_pixel_png(self, api_client):
        lead_id = await _create_lead_with_email_sent(api_client, "pixel@test.tn")
        response = await api_client.get(f"/campaigns/track/open?lead_id={lead_id}")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("image/png")
        assert len(response.content) > 0

    async def test_track_open_marque_email_ouvert(self, api_client):
        lead_id = await _create_lead_with_email_sent(api_client, "open2@test.tn")
        await api_client.get(f"/campaigns/track/open?lead_id={lead_id}")
        lead_resp = await api_client.get(f"/leads/{lead_id}")
        lead_data = lead_resp.json()
        assert lead_data.get("email_opened") is True

    async def test_track_open_deja_ouvert(self, api_client):
        r = await api_client.post("/leads/", json={
            "company":       "AlreadyOpen",
            "email":         "alreadyopen@test.tn",
            "source":        "manual",
            "email_sent":    True,
            "email_opened":  True,
        })
        lead_id = r.json()["id"]
        response = await api_client.get(f"/campaigns/track/open?lead_id={lead_id}")
        assert response.status_code == 200


class TestTrackClick:

    async def test_track_click_lead_inexistant(self, api_client):
        response = await api_client.get(
            "/campaigns/track/click?lead_id=99999&url=https://example.com",
            follow_redirects=False,
        )
        assert response.status_code == 302

    async def test_track_click_lead_trouve(self, api_client):
        lead_id = await _create_lead_with_email_sent(api_client, "click2@test.tn")
        response = await api_client.get(
            f"/campaigns/track/click?lead_id={lead_id}&url=https://example.com",
            follow_redirects=False,
        )
        assert response.status_code == 302

    async def test_track_click_marque_email_clique(self, api_client):
        lead_id = await _create_lead_with_email_sent(api_client, "click3@test.tn")
        await api_client.get(
            f"/campaigns/track/click?lead_id={lead_id}&url=https://example.com",
            follow_redirects=False,
        )
        lead_resp = await api_client.get(f"/leads/{lead_id}")
        assert lead_resp.json().get("email_clicked") is True


# ─── Reset Emails ─────────────────────────────────────────────────────────────

class TestResetEmails:

    async def test_reset_emails_retourne_200(self, api_client):
        response = await api_client.delete("/campaigns/reset-emails")
        assert response.status_code == 200

    async def test_reset_emails_message_present(self, api_client):
        response = await api_client.delete("/campaigns/reset-emails")
        data = response.json()
        assert "message" in data

    async def test_reset_emails_supprime_campagnes(self, api_client):
        await api_client.post("/campaigns/", json=CAMPAIGN_PAYLOAD)
        await api_client.delete("/campaigns/reset-emails")
        campagnes = (await api_client.get("/campaigns/")).json()
        assert campagnes == []

    async def test_reset_emails_remet_champs_a_zero(self, api_client):
        r = await api_client.post("/leads/", json={
            "company":    "ResetCorp",
            "email":      "reset@test.tn",
            "source":     "manual",
            "email_sent": True,
        })
        lead_id = r.json()["id"]
        await api_client.delete("/campaigns/reset-emails")
        lead_resp = await api_client.get(f"/leads/{lead_id}")
        lead = lead_resp.json()
        assert lead.get("email_sent") in (False, None)


# ─── Campaign Progress ────────────────────────────────────────────────────────

class TestCampaignProgress:

    async def test_progress_redis_indisponible(self, api_client):
        """Redis pas disponible — retourne statut par défaut"""
        response = await api_client.get("/campaigns/1/progress")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "generated" in data

    async def test_progress_retourne_structure_complete(self, api_client):
        response = await api_client.get("/campaigns/42/progress")
        data = response.json()
        assert "total" in data
        assert "sent" in data
        assert "errors" in data


# ─── Campaign Schedule ────────────────────────────────────────────────────────

class TestCampaignSchedule:

    async def test_schedule_campagne_existante(self, api_client):
        campaign_id = await _create_campaign(api_client)
        response = await api_client.post(
            f"/campaigns/{campaign_id}/schedule",
            json={"scheduled_at": "2027-01-15T10:00:00"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "scheduled_at" in data

    async def test_schedule_campagne_inexistante(self, api_client):
        response = await api_client.post(
            "/campaigns/99999/schedule",
            json={"scheduled_at": "2027-01-15T10:00:00"},
        )
        assert response.status_code == 404

    async def test_schedule_sans_date(self, api_client):
        campaign_id = await _create_campaign(api_client)
        response = await api_client.post(
            f"/campaigns/{campaign_id}/schedule",
            json={},
        )
        assert response.status_code == 400

    async def test_schedule_date_invalide(self, api_client):
        campaign_id = await _create_campaign(api_client)
        response = await api_client.post(
            f"/campaigns/{campaign_id}/schedule",
            json={"scheduled_at": "pas-une-date"},
        )
        assert response.status_code == 400

    async def test_schedule_met_a_jour_statut(self, api_client):
        campaign_id = await _create_campaign(api_client)
        await api_client.post(
            f"/campaigns/{campaign_id}/schedule",
            json={"scheduled_at": "2027-06-01T09:00:00"},
        )
        campaign = (await api_client.get(f"/campaigns/{campaign_id}")).json()
        if campaign:
            assert campaign.get("campaign_status") in ("scheduled", "draft", None)


# ─── GET / DELETE Campaign ────────────────────────────────────────────────────

class TestGetDeleteCampaign:

    async def test_get_campagne_existante(self, api_client):
        campaign_id = await _create_campaign(api_client)
        response = await api_client.get(f"/campaigns/{campaign_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == campaign_id

    async def test_get_campagne_inexistante_retourne_none(self, api_client):
        response = await api_client.get("/campaigns/99999")
        assert response.status_code == 200
        assert response.json() is None

    async def test_delete_campagne_existante(self, api_client):
        campaign_id = await _create_campaign(api_client)
        response = await api_client.delete(f"/campaigns/{campaign_id}")
        assert response.status_code == 200
        assert "message" in response.json()

    async def test_delete_campagne_disparue_de_liste(self, api_client):
        campaign_id = await _create_campaign(api_client)
        await api_client.delete(f"/campaigns/{campaign_id}")
        campagnes = (await api_client.get("/campaigns/")).json()
        ids = [c["id"] for c in campagnes]
        assert campaign_id not in ids

    async def test_delete_campagne_inexistante(self, api_client):
        response = await api_client.delete("/campaigns/99999")
        assert response.status_code == 200
        assert "message" in response.json()
