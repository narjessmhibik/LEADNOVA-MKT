"""
Tests d'intégration pour les endpoints d'export /leads/export/*
Couvre : GET /leads/export/excel, GET /leads/export/pdf, GET /leads/export/report-pdf
"""
import pytest

pytestmark = pytest.mark.asyncio

LEAD_PAYLOAD = {
    "company": "Historiar Tech",
    "email":   "contact@historiar.io",
    "sector":  "Informatique & Tech",
    "region":  "Tunis",
    "source":  "manual",
}


# ─── Export Excel ─────────────────────────────────────────────────────────────

class TestExportExcel:

    async def test_export_excel_retourne_200(self, api_client):
        response = await api_client.get("/leads/export/excel")
        assert response.status_code == 200

    async def test_export_excel_content_type_xlsx(self, api_client):
        response = await api_client.get("/leads/export/excel")
        ct = response.headers.get("content-type", "")
        assert "spreadsheetml" in ct or "xlsx" in ct or "octet-stream" in ct

    async def test_export_excel_contenu_non_vide(self, api_client):
        response = await api_client.get("/leads/export/excel")
        assert len(response.content) > 0

    async def test_export_excel_content_disposition(self, api_client):
        response = await api_client.get("/leads/export/excel")
        cd = response.headers.get("content-disposition", "")
        assert "attachment" in cd

    async def test_export_excel_avec_leads(self, api_client):
        await api_client.post("/leads/", json=LEAD_PAYLOAD)
        response = await api_client.get("/leads/export/excel")
        assert response.status_code == 200
        assert len(response.content) > 100

    async def test_export_excel_avec_campagne(self, api_client):
        await api_client.post("/campaigns/", json={
            "name": "Camp Export",
            "campaign_name": "Camp Export Test",
            "subject": "Objet",
            "status": "draft",
            "campaign_status": "draft",
        })
        response = await api_client.get("/leads/export/excel")
        assert response.status_code == 200


# ─── Export PDF leads ──────────────────────────────────────────────────────────

class TestExportPdf:

    async def test_export_pdf_retourne_200(self, api_client):
        response = await api_client.get("/leads/export/pdf")
        assert response.status_code == 200

    async def test_export_pdf_content_type(self, api_client):
        response = await api_client.get("/leads/export/pdf")
        ct = response.headers.get("content-type", "")
        assert "pdf" in ct or "octet-stream" in ct

    async def test_export_pdf_contenu_non_vide(self, api_client):
        response = await api_client.get("/leads/export/pdf")
        assert len(response.content) > 100

    async def test_export_pdf_content_disposition(self, api_client):
        response = await api_client.get("/leads/export/pdf")
        cd = response.headers.get("content-disposition", "")
        assert "attachment" in cd

    async def test_export_pdf_avec_leads(self, api_client):
        await api_client.post("/leads/", json=LEAD_PAYLOAD)
        response = await api_client.get("/leads/export/pdf")
        assert response.status_code == 200

    async def test_export_pdf_plusieurs_leads(self, api_client):
        for i in range(5):
            await api_client.post("/leads/", json={
                "company": f"Entreprise {i}",
                "email": f"contact{i}@test.tn",
                "sector": "Finance",
                "region": "Sfax",
                "source": "manual",
                "segment": "Chaud" if i % 2 == 0 else "Froid",
            })
        response = await api_client.get("/leads/export/pdf")
        assert response.status_code == 200
        assert len(response.content) > 500


# ─── Export Rapport PDF analytique ────────────────────────────────────────────

class TestExportReportPdf:

    async def test_report_pdf_retourne_200(self, api_client):
        response = await api_client.get("/leads/export/report-pdf")
        assert response.status_code == 200

    async def test_report_pdf_content_type(self, api_client):
        response = await api_client.get("/leads/export/report-pdf")
        ct = response.headers.get("content-type", "")
        assert "pdf" in ct or "octet-stream" in ct

    async def test_report_pdf_contenu_non_vide(self, api_client):
        response = await api_client.get("/leads/export/report-pdf")
        assert len(response.content) > 100

    async def test_report_pdf_content_disposition(self, api_client):
        response = await api_client.get("/leads/export/report-pdf")
        cd = response.headers.get("content-disposition", "")
        assert "attachment" in cd

    async def test_report_pdf_db_vide(self, api_client):
        response = await api_client.get("/leads/export/report-pdf")
        assert response.status_code == 200
        assert len(response.content) > 0

    async def test_report_pdf_avec_leads_segmentes(self, api_client):
        for segment in ["Chaud", "Froid", "Chaud", "Prêts à Acheter"]:
            await api_client.post("/leads/", json={
                "company": f"Corp {segment}",
                "email": f"{segment.lower().replace(' ', '')}@test.tn",
                "sector": "Informatique & Tech",
                "region": "Tunis",
                "segment": segment,
                "source": "manual",
            })
        response = await api_client.get("/leads/export/report-pdf")
        assert response.status_code == 200

    async def test_report_pdf_avec_emails_envoyes(self, api_client):
        await api_client.post("/leads/", json={
            "company": "TechCorp",
            "email": "info@techcorp.tn",
            "sector": "Finance",
            "region": "Tunis",
            "source": "manual",
            "email_sent": True,
            "email_opened": True,
        })
        response = await api_client.get("/leads/export/report-pdf")
        assert response.status_code == 200

    async def test_report_pdf_avec_secteurs_multiples(self, api_client):
        secteurs = ["Finance", "Éducation", "Santé", "Tourisme", "Agriculture"]
        for i, sect in enumerate(secteurs):
            await api_client.post("/leads/", json={
                "company": f"Corp {i}",
                "sector": sect,
                "source": "manual",
            })
        response = await api_client.get("/leads/export/report-pdf")
        assert response.status_code == 200
