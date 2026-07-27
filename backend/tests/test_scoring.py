"""
Tests unitaires pour app/scoring.py
Couvre : get_email_quality, get_sector_score, get_company_type_score, extract_features
"""
import math
import numpy as np
import pandas as pd
import pytest

from app.scoring import (
    get_email_quality,
    get_sector_score,
    get_company_type_score,
    extract_features,
    FEATURE_COLUMNS,
)


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _make_lead_df(**overrides):
    """DataFrame d'un lead complet par défaut, avec surcharge via kwargs."""
    defaults = {
        "email":            ["ceo@techcorp.tn"],
        "phone":            ["+216 99 000 000"],
        "website":          ["https://techcorp.tn"],
        "address":          ["Tunis, Tunisie"],
        "region":           ["Tunis"],
        "sector":           ["Informatique & Tech"],
        "description":      ["Startup B2B spécialisée en IA"],
        "email_confidence": [85.0],
        "company_type":     ["Startup"],
    }
    defaults.update(overrides)
    return pd.DataFrame(defaults)


# ─────────────────────────────────────────────────────────────
# get_email_quality
# ─────────────────────────────────────────────────────────────

class TestGetEmailQuality:

    def test_ceo_email_score_max(self):
        assert get_email_quality("ceo@company.com") == 1.0

    def test_founder_email(self):
        assert get_email_quality("founder@startup.tn") == 0.95

    def test_pdg_email(self):
        assert get_email_quality("pdg@company.ma") == 0.90

    def test_director_email(self):
        assert get_email_quality("director@firm.com") == 0.90

    def test_directeur_email(self):
        assert get_email_quality("directeur@societe.fr") == 0.90

    def test_sales_email(self):
        assert get_email_quality("sales@shop.com") == 0.85

    def test_commercial_email(self):
        assert get_email_quality("commercial@agence.tn") == 0.85

    def test_marketing_email(self):
        assert get_email_quality("marketing@brand.com") == 0.80

    def test_contact_email(self):
        assert get_email_quality("contact@company.com") == 0.50

    def test_info_email(self):
        assert get_email_quality("info@company.com") == 0.40

    def test_admin_email(self):
        assert get_email_quality("admin@backend.com") == 0.30

    def test_support_email(self):
        assert get_email_quality("support@helpdesk.com") == 0.25

    def test_generic_name_returns_default(self):
        assert get_email_quality("john.doe@company.com") == 0.60

    def test_none_returns_zero(self):
        assert get_email_quality(None) == 0.0

    def test_empty_string_returns_zero(self):
        assert get_email_quality("") == 0.0

    def test_uppercase_email_normalized(self):
        assert get_email_quality("CEO@COMPANY.COM") == 1.0


# ─────────────────────────────────────────────────────────────
# get_sector_score
# ─────────────────────────────────────────────────────────────

class TestGetSectorScore:

    def test_tech_sector_max(self):
        assert get_sector_score("Informatique & Tech") == 1.0

    def test_culture_musees_max(self):
        assert get_sector_score("Culture & Musées") == 1.0

    def test_culture_patrimoine_max(self):
        assert get_sector_score("Culture & Patrimoine") == 1.0

    def test_education_formation_max(self):
        assert get_sector_score("Education & Formation") == 1.0

    def test_finance_score(self):
        assert get_sector_score("Finance & Comptabilité") == 0.90

    def test_finance_sans_accent(self):
        assert get_sector_score("Finance & Comptabilite") == 0.90

    def test_sante_score(self):
        assert get_sector_score("Santé") == 0.85

    def test_marketing_score(self):
        assert get_sector_score("Marketing & Communication") == 0.80

    def test_immobilier_score(self):
        assert get_sector_score("Immobilier") == 0.75

    def test_tourisme_score(self):
        assert get_sector_score("Tourisme & Loisirs") == 0.55

    def test_tourisme_voyages_score(self):
        assert get_sector_score("Tourisme & Voyages") == 0.55

    def test_restauration_score(self):
        assert get_sector_score("Restauration & Hôtellerie") == 0.55

    def test_unknown_sector_returns_default(self):
        assert get_sector_score("Secteur inconnu") == 0.50

    def test_none_returns_nan(self):
        assert np.isnan(get_sector_score(None))

    def test_empty_string_returns_nan(self):
        assert np.isnan(get_sector_score(""))


# ─────────────────────────────────────────────────────────────
# get_company_type_score
# ─────────────────────────────────────────────────────────────

class TestGetCompanyTypeScore:

    def test_startup_max(self):
        assert get_company_type_score("Startup") == 1.0

    def test_pme_score(self):
        assert get_company_type_score("PME") == 0.85

    def test_grande_entreprise_score(self):
        assert get_company_type_score("Grande entreprise") == 0.70

    def test_independant_score(self):
        assert get_company_type_score("Independant") == 0.50

    def test_association_score(self):
        assert get_company_type_score("Association") == 0.30

    def test_none_returns_default(self):
        assert get_company_type_score(None) == 0.60

    def test_unknown_type_returns_default(self):
        assert get_company_type_score("Autre structure") == 0.60

    def test_case_insensitive_startup(self):
        assert get_company_type_score("startup") == 1.0

    def test_case_insensitive_pme(self):
        assert get_company_type_score("pme") == 0.85


# ─────────────────────────────────────────────────────────────
# extract_features
# ─────────────────────────────────────────────────────────────

class TestExtractFeatures:

    def test_retourne_les_bonnes_colonnes(self):
        df = _make_lead_df()
        feats = extract_features(df)
        assert list(feats.columns) == FEATURE_COLUMNS

    def test_has_email_present(self):
        df = _make_lead_df(email=["test@company.com"])
        assert extract_features(df)["has_email"].iloc[0] == 1.0

    def test_has_email_absent(self):
        df = _make_lead_df(email=[None])
        assert extract_features(df)["has_email"].iloc[0] == 0.0

    def test_has_phone_present(self):
        df = _make_lead_df(phone=["+216 99 000 000"])
        assert extract_features(df)["has_phone"].iloc[0] == 1.0

    def test_has_phone_absent(self):
        df = _make_lead_df(phone=[None])
        assert extract_features(df)["has_phone"].iloc[0] == 0.0

    def test_has_website_present(self):
        df = _make_lead_df(website=["https://example.com"])
        assert extract_features(df)["has_website"].iloc[0] == 1.0

    def test_has_website_absent(self):
        df = _make_lead_df(website=[None])
        assert extract_features(df)["has_website"].iloc[0] == 0.0

    def test_has_address_present(self):
        df = _make_lead_df(address=["Sfax, Tunisie"])
        assert extract_features(df)["has_address"].iloc[0] == 1.0

    def test_has_region_present(self):
        df = _make_lead_df(region=["Sfax"])
        assert extract_features(df)["has_region"].iloc[0] == 1.0

    def test_sector_score_tech(self):
        df = _make_lead_df(sector=["Informatique & Tech"])
        assert extract_features(df)["sector_score"].iloc[0] == 1.0

    def test_sector_score_absent_donne_nan(self):
        df = _make_lead_df(sector=[None])
        assert pd.isna(extract_features(df)["sector_score"].iloc[0])

    def test_email_confidence_normalise(self):
        df = _make_lead_df(email_confidence=[80.0])
        val = extract_features(df)["email_confidence"].iloc[0]
        assert abs(val - 0.80) < 0.01

    def test_email_confidence_absent_donne_nan(self):
        df = _make_lead_df(email_confidence=[None])
        assert pd.isna(extract_features(df)["email_confidence"].iloc[0])

    def test_company_type_startup(self):
        df = _make_lead_df(company_type=["Startup"])
        assert extract_features(df)["company_type_score"].iloc[0] == 1.0

    def test_has_description_present(self):
        df = _make_lead_df(description=["Description de la société"])
        assert extract_features(df)["has_description"].iloc[0] == 1.0

    def test_has_description_absent_donne_nan(self):
        df = _make_lead_df(description=[None])
        assert pd.isna(extract_features(df)["has_description"].iloc[0])

    def test_email_quality_ceo(self):
        df = _make_lead_df(email=["ceo@company.com"])
        assert extract_features(df)["email_quality"].iloc[0] == 1.0

    def test_lead_complet_retourne_un_dataframe(self):
        df = _make_lead_df()
        feats = extract_features(df)
        assert len(feats) == 1
        assert not feats.empty

    def test_plusieurs_leads(self):
        df = pd.DataFrame({
            "email":            ["ceo@a.com", None, "info@b.com"],
            "phone":            ["+216 99", None, "+33 6"],
            "website":          ["https://a.com", "https://b.com", None],
            "address":          ["Tunis", None, "Paris"],
            "region":           ["Tunis", None, "Île-de-France"],
            "sector":           ["Informatique & Tech", None, "Finance & Comptabilité"],
            "description":      ["desc", None, "desc2"],
            "email_confidence": [90.0, None, 50.0],
            "company_type":     ["Startup", None, "PME"],
        })
        feats = extract_features(df)
        assert len(feats) == 3
        assert feats["has_email"].iloc[0] == 1.0
        assert feats["has_email"].iloc[1] == 0.0
