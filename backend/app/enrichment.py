import os
import json
import re
import time
import logging
import requests
from datetime import datetime
from urllib.parse import urlparse
from dotenv import load_dotenv

try:
    import json_repair
    HAS_JSON_REPAIR = True
except ImportError:
    HAS_JSON_REPAIR = False

try:
    import redis as redis_lib
    _redis = redis_lib.Redis(host='localhost', port=6379, db=1)
    _redis.ping()
    HAS_REDIS = True
except Exception:
    HAS_REDIS = False

try:
    import dns.resolver
    HAS_DNS = True
except ImportError:
    HAS_DNS = False

from app.database import SyncSessionLocal
from app.models.lead import Lead

load_dotenv()

HUNTER_API_KEY      = os.getenv("HUNTER_API_KEY")
GROQ_API_KEY        = os.getenv("GROQ_API_KEY")
OPENROUTER_API_KEY  = os.getenv("OPENROUTER_API_KEY")

# LOGGING
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('enrichment.log', encoding='utf-8')
    ]
)
logger = logging.getLogger("leadpilot.enrichment")

# CONSTANTES
BLOCKED_DOMAINS = [
    "facebook.com", "instagram.com", "linkedin.com",
    "youtube.com", "tiktok.com", "twitter.com",
    "google.com", "wa.me", "whatsapp.com",
    "snapchat.com", "pinterest.com",
    "edicom.ma", "telecontact.ma", "pagesjaunes.ma",
    "tunisieindex.com", "kompass.com", "europages.com",
]

BLOCKED_EMAIL_DOMAINS = [
    "booking.com", "expedia.com", "tripadvisor.com",
    "airbnb.com", "marriott.com", "hilton.com",
    "accor.com", "barcelo.com", "radissonhotels.com",
    "iberostar.com", "ttshotels.com.tn"
]

ALLOWED_SECTORS = [
    "Marketing & Communication", "Informatique & Tech",
    "Finance & Comptabilité", "Santé", "Immobilier",
    "Construction & BTP", "Transport & Logistique",
    "Education & Formation", "Restauration & Hôtellerie",
    "Industrie & Production", "Commerce & Distribution",
    "Services aux entreprises", "Agriculture & Alimentaire",
    "Energie & Environnement", "Juridique",
]

VALID_COMPANY_TYPES = {
    "PME", "Indépendant", "Grande entreprise", "Startup", "Association"
}

INVALID_COMPANY_TYPES = {
    "tunis", "sfax", "ariana", "sousse", "monastir",
    "bizerte", "nabeul", "gabes", "gafsa", "kairouan",
    "tunisia", "tunisie", "none", "n/a", "null", ""
}

KEYWORD_SECTORS = {
    "informatique":    "Informatique & Tech",
    "software":        "Informatique & Tech",
    "telecom":         "Informatique & Tech",
    "digital":         "Informatique & Tech",
    "network":         "Informatique & Tech",
    "audit":           "Finance & Comptabilité",
    "comptabilite":    "Finance & Comptabilité",
    "comptabilité":    "Finance & Comptabilité",
    "financier":       "Finance & Comptabilité",
    "factoring":       "Finance & Comptabilité",
    "clinique":        "Santé",
    "polyclinique":    "Santé",
    "pharmacie":       "Santé",
    "laboratoire":     "Santé",
    "ophtalmologie":   "Santé",
    "medical":         "Santé",
    "médical":         "Santé",
    "hotel":           "Restauration & Hôtellerie",
    "hôtel":           "Restauration & Hôtellerie",
    "restaurant":      "Restauration & Hôtellerie",
    "resort":          "Restauration & Hôtellerie",
    "résidence":       "Restauration & Hôtellerie",
    "avocat":          "Juridique",
    "huissier":        "Juridique",
    "notaire":         "Juridique",
    "transport":       "Transport & Logistique",
    "logistique":      "Transport & Logistique",
    "transit":         "Transport & Logistique",
    "maritime":        "Transport & Logistique",
    "construction":    "Construction & BTP",
    "architecte":      "Construction & BTP",
    "immobilier":      "Immobilier",
    "formation":       "Education & Formation",
    "université":      "Education & Formation",
    "marketing":       "Marketing & Communication",
    "communication":   "Marketing & Communication",
    "publicité":       "Marketing & Communication",
    "agricole":        "Agriculture & Alimentaire",
    "agroalimentaire": "Agriculture & Alimentaire",
    "energie":         "Energie & Environnement",
    "solaire":         "Energie & Environnement",
    "recyclage":       "Energie & Environnement",
}

SECTOR_CORRECTIONS = {
    "tourisme":      "Restauration & Hôtellerie",
    "finance":       "Finance & Comptabilité",
    "sante":         "Santé",
    "santé":         "Santé",
    "commerce":      "Commerce & Distribution",
    "services":      "Services aux entreprises",
    "industrie":     "Industrie & Production",
    "transport":     "Transport & Logistique",
    "immobilier":    "Immobilier",
    "education":     "Education & Formation",
    "juridique":     "Juridique",
    "energie":       "Energie & Environnement",
    "agriculture":   "Agriculture & Alimentaire",
    "construction":  "Construction & BTP",
    "marketing":     "Marketing & Communication",
    "informatique":  "Informatique & Tech",
    "communication": "Marketing & Communication",
    "mobility":      "Transport & Logistique",
    "agritech":      "Agriculture & Alimentaire",
    "foodtech":      "Agriculture & Alimentaire",
    "food tech":     "Agriculture & Alimentaire",
    "fintech":       "Finance & Comptabilité",
    "edtech":        "Education & Formation",
    "healthtech":    "Santé",
    "health tech":   "Santé",
    "insurtech":     "Finance & Comptabilité",
    "proptech":      "Immobilier",
    "legaltech":     "Juridique",
    "cleantech":     "Energie & Environnement",
    "greentech":     "Energie & Environnement",
    "martech":       "Marketing & Communication",
    "saas":          "Informatique & Tech",
    "e-commerce":    "Commerce & Distribution",
    "ecommerce":     "Commerce & Distribution",
    "tunis":         "Services aux entreprises",
    "sfax":          "Services aux entreprises",
    "ariana":        "Services aux entreprises",
    "sousse":        "Services aux entreprises",
    "monastir":      "Services aux entreprises",
    "bizerte":       "Services aux entreprises",
    "nabeul":        "Services aux entreprises",
    "gabes":         "Services aux entreprises",
    "non spécifié":  "Services aux entreprises",
}

# MAPPING GOOGLE MAPS SECTEURS NORMALISÉS
# Utilisé pour normaliser les catégories brutes
# du scraping Google Maps avant d'appeler Groq
GOOGLE_SECTOR_MAPPING = {
    "consultant informatique":          "Informatique & Tech",
    "entreprise de gestion de bases":   "Informatique & Tech",
    "développement web":                "Informatique & Tech",
    "logiciel":                         "Informatique & Tech",
    "telecom":                          "Informatique & Tech",
    "digital":                          "Informatique & Tech",
    "software":                         "Informatique & Tech",
    "réseau":                           "Informatique & Tech",
    "internet":                         "Informatique & Tech",
    "expert-comptable":                 "Finance & Comptabilité",
    "comptable":                        "Finance & Comptabilité",
    "banque":                           "Finance & Comptabilité",
    "assurance":                        "Finance & Comptabilité",
    "financier":                        "Finance & Comptabilité",
    "audit":                            "Finance & Comptabilité",
    "microfinance":                     "Finance & Comptabilité",
    "leasing":                          "Finance & Comptabilité",
    "administration municipale":        "Services aux entreprises",
    "centre d'affaires":                "Services aux entreprises",
    "consultant en ingénierie":         "Services aux entreprises",
    "ministère":                        "Services aux entreprises",
    "centre d'information":             "Services aux entreprises",
    "service de maintenance":           "Services aux entreprises",
    "maintenance d'ascenseurs":         "Services aux entreprises",
    "service gouvernemental":           "Services aux entreprises",
    "organisme gouvernemental":         "Services aux entreprises",
    "chambre de commerce":              "Services aux entreprises",
    "bureau d'études":                  "Services aux entreprises",
    "fournisseur":                      "Commerce & Distribution",
    "grossiste":                        "Commerce & Distribution",
    "distributeur":                     "Commerce & Distribution",
    "magasin":                          "Commerce & Distribution",
    "supermarché":                      "Commerce & Distribution",
    "importateur":                      "Commerce & Distribution",
    "exportateur":                      "Commerce & Distribution",
    "construction":                     "Construction & BTP",
    "entreprise de vrd":                "Construction & BTP",
    "entrepreneur en bâtiment":         "Construction & BTP",
    "architecte":                       "Construction & BTP",
    "btp":                              "Construction & BTP",
    "bâtiment":                         "Construction & BTP",
    "immobilier":                       "Immobilier",
    "agence immobilière":               "Immobilier",
    "promoteur":                        "Immobilier",
    "compagnie d'autobus":              "Transport & Logistique",
    "transport":                        "Transport & Logistique",
    "logistique":                       "Transport & Logistique",
    "transit":                          "Transport & Logistique",
    "maritime":                         "Transport & Logistique",
    "livraison":                        "Transport & Logistique",
    "service forestier":                "Agriculture & Alimentaire",
    "agricole":                         "Agriculture & Alimentaire",
    "agriculture":                      "Agriculture & Alimentaire",
    "agroalimentaire":                  "Agriculture & Alimentaire",
    "alimentaire":                      "Agriculture & Alimentaire",
    "clinique":                         "Santé",
    "médecin":                          "Santé",
    "pharmacie":                        "Santé",
    "hôpital":                          "Santé",
    "sante":                            "Santé",
    "santé":                            "Santé",
    "dentiste":                         "Santé",
    "ophtalmologie":                    "Santé",
    "laboratoire":                      "Santé",
    "médical":                          "Santé",
    "restaurant":                       "Restauration & Hôtellerie",
    "hôtel":                            "Restauration & Hôtellerie",
    "hotel":                            "Restauration & Hôtellerie",
    "café":                             "Restauration & Hôtellerie",
    "pizzeria":                         "Restauration & Hôtellerie",
    "traiteur":                         "Restauration & Hôtellerie",
    "boulangerie":                      "Restauration & Hôtellerie",
    "école":                            "Education & Formation",
    "université":                       "Education & Formation",
    "formation":                        "Education & Formation",
    "education":                        "Education & Formation",
    "éducation":                        "Education & Formation",
    "lycée":                            "Education & Formation",
    "centre de formation":              "Education & Formation",
    "avocat":                           "Juridique",
    "notaire":                          "Juridique",
    "huissier":                         "Juridique",
    "énergie":                          "Energie & Environnement",
    "energie":                          "Energie & Environnement",
    "solaire":                          "Energie & Environnement",
    "recyclage":                        "Energie & Environnement",
    "environnement":                    "Energie & Environnement",
    "marketing":                        "Marketing & Communication",
    "communication":                    "Marketing & Communication",
    "publicité":                        "Marketing & Communication",
    "médias":                           "Marketing & Communication",
    "industrie":                        "Industrie & Production",
    "usine":                            "Industrie & Production",
    "manufacture":                      "Industrie & Production",
    "textile":                          "Industrie & Production",
    "mécanique":                        "Industrie & Production",
    "compresseur":                      "Industrie & Production",
    "nettoyage":                        "Industrie & Production",
}

# RÈGLES COMPANY TYPE PAR MOT-CLÉ
COMPANY_TYPE_NAME_RULES = [
    (["startup", "tech", "digital", "app", "saas", "fintech",
      "edtech", "healthtech", "innovation", "labs", "hub"], "Startup"),
    (["groupe", "group", "holding", "international", "national",
      "banque", "bank", "assurance", "compagnie",
      "steg", "sonede", "tunisair", "tunisie telecom"], "Grande entreprise"),
    (["association", "fondation", "ong", "ngo", "club",
      "federation", "fédération", "syndicat"], "Association"),
    (["cabinet", "bureau", "studio", "atelier", "dr ",
      "docteur", "maître", "me ", "avocat", "notaire",
      "expert", "consultant", "freelance"], "Indépendant"),
]

# Règle par secteur si company_type toujours manquant
SECTOR_DEFAULT_COMPANY_TYPE = {
    "Informatique & Tech":       "Startup",
    "Finance & Comptabilité":    "PME",
    "Juridique":                 "Indépendant",
    "Santé":                     "Indépendant",
    "Restauration & Hôtellerie": "Indépendant",
    "Industrie & Production":    "Grande entreprise",
}

EMAIL_ROLE_SCORES = {
    "ceo":        100,
    "founder":     95,
    "director":    90,
    "directeur":   90,
    "pdg":         90,
    "dg":          85,
    "sales":       85,
    "commercial":  85,
    "marketing":   80,
    "contact":     50,
    "info":        40,
    "admin":       30,
    "support":     25,
}

CONTACT_PAGES = ["/contact", "/contact-us", "/nous-contacter", "/about"]

EMAIL_BLACKLIST = [
    "example", "sentry", "wix", "wordpress", "schema",
    "google", "facebook", "jquery", "png", "jpg",
    "svg", "noreply", "no-reply", "donotreply",
    "webmaster", "spam", "test@", "info@example"
]

HEADERS          = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}
CACHE_TTL        = 60 * 60 * 24 * 30
CACHE_TTL_GROQ   = 60 * 60 * 24 * 7
CACHE_TTL_OC     = 60 * 60 * 24 * 30
GROQ_MAX_RETRIES = 2

GROQ_MODELS = [
    "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile",
    "meta-llama/llama-4-scout-17b-16e-instruct",
]

OPENROUTER_MODELS = [
    "nvidia/llama-3.1-nemotron-ultra-253b-v1:free",
    "openai/gpt-oss-120b:free",
    "openai/gpt-oss-20b:free",
    "google/gemma-4-31b-it:free",
    "z-ai/glm-4.5-air:free",
    "nvidia/nemotron-3-nano-30b-a3b:free",
    "poolside/laguna-m1:free",
    "poolside/laguna-xs2:free",
]
# PROMPT COMMUN
def build_prompt(company: str, sector: str, website: str) -> str:
    return (
        f"Entreprise: {company} | Site: {website or 'N/A'}\n"
        f"Secteur déclaré: {sector or '?'}\n\n"
        f"Réponds UNIQUEMENT en JSON valide:\n"
        f'{{"description":"<60 mots>",'
        f'"company_type":"<UNIQUEMENT une de ces valeurs exactes: PME, Indépendant, Grande entreprise, Startup, Association. NE JAMAIS mettre une ville>",'
        f'"sector":"<choisis parmi UNIQUEMENT ces valeurs exactes: '
        f'Marketing & Communication, Informatique & Tech, Finance & Comptabilité, '
        f'Santé, Immobilier, Construction & BTP, Transport & Logistique, '
        f'Education & Formation, Restauration & Hôtellerie, Industrie & Production, '
        f'Commerce & Distribution, Services aux entreprises, Agriculture & Alimentaire, '
        f'Energie & Environnement, Juridique. '
        f'NE JAMAIS mettre un nom de ville ou pays comme secteur.>",'
        f'"services":["s1","s2","s3"]}}'
    )


# UTILITAIRES
def is_non_latin(text: str) -> bool:
    if not text:
        return False
    latin_chars = len(re.findall(r'[a-zA-Z]', text))
    total_chars = len(re.sub(r'\s', '', text))
    if total_chars == 0:
        return False
    return latin_chars / total_chars < 0.4

def normalize_sector(sector: str) -> str:
    if not sector:
        return "Non spécifié"
    s = sector.strip()
    if s.lower() in SECTOR_CORRECTIONS:
        return SECTOR_CORRECTIONS[s.lower()]
    matched = next((a for a in ALLOWED_SECTORS if a.lower() == s.lower()), None)
    if matched:
        return matched
    if len(s) > 3 and s[0].isupper():
        return s
    return "Non spécifié"

def normalize_google_sector(raw_sector: str) -> str:
    """Convertit catégorie brute Google Maps secteur normalisé sans API"""
    if not raw_sector:
        return None
    s = raw_sector.lower().strip()
    if raw_sector in ALLOWED_SECTORS:
        return raw_sector
    for key, normalized in GOOGLE_SECTOR_MAPPING.items():
        if key in s:
            return normalized
    if s in SECTOR_CORRECTIONS:
        return SECTOR_CORRECTIONS[s]
    return None

def normalize_company_type(ct: str) -> str:
    if not ct:
        return None
    ct = ct.strip()
    if "|" in ct:
        ct = ct.split("|")[0].strip()
    if ct.lower() in INVALID_COMPANY_TYPES:
        return None
    if ct in VALID_COMPANY_TYPES:
        return ct
    for valid in VALID_COMPANY_TYPES:
        if valid.lower() in ct.lower():
            return valid
    return None

def detect_company_type_from_name(company: str) -> str:
    """Détecte le type entreprise depuis le nom sans API"""
    if not company:
        return None
    c = company.lower()
    for keywords, company_type in COMPANY_TYPE_NAME_RULES:
        for kw in keywords:
            if kw in c:
                return company_type
    return None

def detect_sector_local(company: str) -> str:
    if not company:
        return None
    company_lower = company.lower()
    for keyword, sector in KEYWORD_SECTORS.items():
        if re.search(rf"\b{re.escape(keyword.strip())}\b", company_lower):
            return sector
    return None

def is_blocked_domain(domain: str) -> bool:
    try:
        clean = domain.lower().replace("www.", "")
        hostname = urlparse("https://" + clean).hostname or clean
        return any(hostname == b or hostname.endswith("." + b) for b in BLOCKED_DOMAINS)
    except Exception:
        return False

def has_mx_record(domain: str) -> bool:
    if not HAS_DNS:
        return False
    try:
        clean = domain.replace("www.", "").split("/")[0]
        dns.resolver.resolve(clean, 'MX')
        return True
    except Exception:
        return False

def get_email_quality(email: str) -> int:
    if not email:
        return 0
    local = email.split("@")[0].lower()
    for role, score in EMAIL_ROLE_SCORES.items():
        if role in local:
            return score
    return 60

def extract_emails_from_html(html: str, domain: str) -> list:
    emails = re.findall(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', html)
    clean_domain = domain.replace("www.", "").split(".")[0]
    valid = []
    for e in emails:
        e = e.lower()
        if any(b in e for b in EMAIL_BLACKLIST):
            continue
        if len(e) > 100:
            continue
        valid.append(e)
    same_domain = [e for e in valid if clean_domain in e]
    return same_domain if same_domain else valid[:3]

def parse_llm_json(content: str) -> dict:
    content = content.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    if HAS_JSON_REPAIR:
        try:
            return json_repair.loads(content)
        except Exception:
            pass
    try:
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except Exception:
        pass
    return {}

def validate_email_domain(email: str, website: str) -> bool:
    if not email or not website:
        return True
    try:
        email_domain = email.split("@")[1].lower().replace("www.", "")
        site_domain  = website.replace("https://", "").replace("http://", "").split("/")[0].lower().replace("www.", "")
        return (
            email_domain == site_domain or
            site_domain in email_domain or
            email_domain in site_domain
        )
    except Exception:
        return True

def finalize_result(result: dict, company: str) -> dict:
    if not result:
        return result
    result["sector"] = normalize_sector(result.get("sector", ""))
    if result["sector"] == "Non spécifié":
        local = detect_sector_local(company)
        if local:
            result["sector"] = local
    result["company_type"] = normalize_company_type(result.get("company_type", ""))
    return result


# REDIS CACHE
def cache_get(key: str) -> dict:
    if not HAS_REDIS:
        return None
    try:
        val = _redis.get(f"leadpilot:{key}")
        if val:
            return json.loads(val)
    except Exception:
        pass
    return None

def cache_set(key: str, value: dict, ttl: int = CACHE_TTL):
    if not HAS_REDIS:
        return
    try:
        _redis.setex(f"leadpilot:{key}", ttl, json.dumps(value))
    except Exception:
        pass


# OPENCORPORATES
def enrich_opencorporates(company: str) -> dict:
    if not company:
        return {}
    cache_key = f"oc:{company.lower()[:50]}"
    cached = cache_get(cache_key)
    if cached:
        return cached
    try:
        r = requests.get(
            "https://api.opencorporates.com/v0.4/companies/search",
            params={"q": company, "jurisdiction_code": "tn", "per_page": 1},
            timeout=10
        )
        data = r.json()
        companies = data.get("results", {}).get("companies", [])
        if companies:
            c = companies[0]["company"]
            result = {
                "legal_name":         c.get("name"),
                "status":             c.get("current_status"),
                "incorporation_date": c.get("incorporation_date"),
                "company_number":     c.get("company_number"),
            }
            cache_set(cache_key, result, CACHE_TTL_OC)
            return result
    except Exception as e:
        logger.debug(f"OpenCorporates error: {e}")
    return {}


# HUNTER.IO
def find_email_hunter(company_name: str, website: str = None) -> dict:
    if not HUNTER_API_KEY:
        return {"email": None, "confidence": 0, "pattern": None}

    domain = None
    if website:
        try:
            domain = website.replace("https://", "").replace("http://", "").rstrip("/").split("/")[0]
            if is_blocked_domain(domain):
                domain = None
        except Exception:
            domain = None

    cache_key = f"hunter:{domain or company_name or ''}"
    cached = cache_get(cache_key)
    if cached:
        logger.info(f" Cache Hunter: {cached.get('email')}")
        return cached

    try:
        if domain:
            r = requests.get(
                "https://api.hunter.io/v2/domain-search",
                params={"domain": domain, "api_key": HUNTER_API_KEY, "limit": 1},
                timeout=10
            )
            data = r.json()
            if data.get("data", {}).get("emails"):
                email_data = data["data"]["emails"][0]
                email = email_data.get("value")
                if email:
                    if email.split("@")[1].lower() in BLOCKED_EMAIL_DOMAINS:
                        return {"email": None, "confidence": 0, "pattern": None}
                    if not validate_email_domain(email, website):
                        return {"email": None, "confidence": 0, "pattern": None}
                result = {
                    "email": email,
                    "confidence": email_data.get("confidence", 0),
                    "pattern": data["data"].get("pattern")
                }
                cache_set(cache_key, result)
                return result

        if company_name:
            r = requests.get(
                "https://api.hunter.io/v2/email-finder",
                params={"company": company_name, "api_key": HUNTER_API_KEY},
                timeout=10
            )
            data = r.json()
            if data.get("data", {}).get("email"):
                email = data["data"]["email"]
                if email:
                    if email.split("@")[1].lower() in BLOCKED_EMAIL_DOMAINS:
                        return {"email": None, "confidence": 0, "pattern": None}
                    if website and not validate_email_domain(email, website):
                        return {"email": None, "confidence": 0, "pattern": None}
                result = {
                    "email": email,
                    "confidence": data["data"].get("score", 0),
                    "pattern": data["data"].get("pattern")
                }
                cache_set(cache_key, result)
                return result

    except Exception as e:
        logger.error(f" Hunter.io error: {e}")

    return {"email": None, "confidence": 0, "pattern": None}


# CONTACT PAGE CRAWLER
def scrape_email_from_site(website: str) -> dict:
    if not website:
        return {"email": None, "confidence": 0, "pattern": None}
    try:
        domain = website.replace("https://", "").replace("http://", "").split("/")[0].strip()
        if not domain or "." not in domain:
            return {"email": None, "confidence": 0, "pattern": None}
        if is_blocked_domain(domain):
            logger.warning(f" Domaine bloqué: {domain}")
            return {"email": None, "confidence": 0, "pattern": None}

        cached = cache_get(f"email:scrape:{domain}")
        if cached:
            logger.info(f" Cache scraping: {cached.get('email')}")
            return cached

        base_url = f"https://{domain}"
        found_email = None
        found_confidence = 0
        pages_to_visit = [base_url] + [base_url + p for p in CONTACT_PAGES]

        for page_url in pages_to_visit:
            try:
                r = requests.get(page_url, headers=HEADERS, timeout=5)
                if r.status_code != 200:
                    continue
                emails = extract_emails_from_html(r.text, domain)
                if emails:
                    found_email = emails[0]
                    found_confidence = 80 if any(p in page_url for p in ["/contact", "/about", "/team"]) else 60
                    logger.info(f"   Email trouvé sur {page_url}: {found_email}")
                    break
                time.sleep(0.2)
            except Exception as e:
                logger.debug(f" Page error {page_url}: {e}")
                continue

        result = {
            "email": found_email,
            "confidence": found_confidence,
            "pattern": f"*@{domain}" if found_email else None
        }
        if found_email:
            cache_set(f"email:scrape:{domain}", result)
        return result

    except Exception as e:
        logger.error(f" scrape_email error: {e}")
        return {"email": None, "confidence": 0, "pattern": None}


# PATTERN MATCHING
def guess_email_pattern(company: str, website: str) -> dict:
    if not website:
        return {"email": None, "confidence": 0, "pattern": None}
    try:
        domain = website.replace("https://", "").replace("http://", "")
        domain = domain.split("/")[0].strip().replace("www.", "")
        if not domain or "." not in domain:
            return {"email": None, "confidence": 0, "pattern": None}
        if is_blocked_domain(domain):
            return {"email": None, "confidence": 0, "pattern": None}
        if not has_mx_record(domain):
            logger.info(f" Pas de MX record pour {domain} — skip pattern")
            return {"email": None, "confidence": 0, "pattern": None}

        patterns = [f"contact@{domain}", f"info@{domain}", f"direction@{domain}"]
        if company:
            clean = re.sub(r'\b(sarl|sa|suarl|ste|société|company|group|tunisie|tunisia)\b', '', company.lower())
            clean = re.sub(r'[^a-z0-9]', '', clean).strip()
            if clean and 2 < len(clean) <= 15:
                patterns.insert(0, f"{clean}@{domain}")

        return {
            "email": patterns[0],
            "confidence": 15,
            "pattern": " | ".join(patterns[:3])
        }
    except Exception as e:
        logger.error(f" pattern matching error: {e}")
        return {"email": None, "confidence": 0, "pattern": None}


# CLEARBIT (email via domaine — gratuit 50/mois)
def find_email_clearbit(company_name: str, website: str = None) -> dict:
    """Clearbit Autocomplete + Enrichment API (gratuit, pas de clé requise pour l'autocomplete)."""
    if not website:
        return {"email": None, "confidence": 0}

    try:
        domain = website.replace("https://", "").replace("http://", "").rstrip("/").split("/")[0]
        domain = domain.replace("www.", "")
        if not domain or "." not in domain or is_blocked_domain(domain):
            return {"email": None, "confidence": 0}

        cache_key = f"clearbit:{domain}"
        cached = cache_get(cache_key)
        if cached:
            return cached

        # Clearbit Company API (public, sans authentification pour les données basiques)
        r = requests.get(
            f"https://autocomplete.clearbit.com/v1/companies/suggest?query={domain}",
            headers=HEADERS,
            timeout=8,
        )
        if r.status_code == 200:
            results = r.json()
            if results:
                company_data = results[0]
                domain_found = company_data.get("domain", "")
                if domain_found:
                    # Construire email générique depuis domaine Clearbit
                    email_guess = f"contact@{domain_found}"
                    if has_mx_record(domain_found):
                        result = {"email": email_guess, "confidence": 30}
                        cache_set(cache_key, result, CACHE_TTL)
                        logger.info(f"   Clearbit: {email_guess}")
                        return result
    except Exception as e:
        logger.debug(f" Clearbit error: {e}")

    return {"email": None, "confidence": 0}


# GROQ (principal)
def build_prompt_arabic(company: str, sector: str, website: str) -> str:
    """Prompt dédié pour les noms d'entreprises en arabe."""
    return (
        f"Entreprise (nom arabe): {company} | Site: {website or 'N/A'}\n"
        f"Secteur déclaré: {sector or '?'}\n\n"
        f"Cette entreprise a un nom en arabe. Détermine son secteur d'activité et son type.\n"
        f"Réponds UNIQUEMENT en JSON valide:\n"
        f'{{"description":"<description courte 40 mots en français>",'
        f'"company_type":"<PME, Indépendant, Grande entreprise, Startup, ou Association>",'
        f'"sector":"<choisis parmi: Marketing & Communication, Informatique & Tech, Finance & Comptabilité, '
        f'Santé, Immobilier, Construction & BTP, Transport & Logistique, '
        f'Education & Formation, Restauration & Hôtellerie, Industrie & Production, '
        f'Commerce & Distribution, Services aux entreprises, Agriculture & Alimentaire, '
        f'Energie & Environnement, Juridique>",'
        f'"services":["s1","s2"]}}'
    )


def enrich_with_groq(company: str, sector: str, city: str, website: str) -> dict:
    if not GROQ_API_KEY:
        return {}

    # Utiliser un prompt dédié pour les noms arabes au lieu de les ignorer
    use_arabic_prompt = is_non_latin(company)

    cache_key = f"groq:{'ar:' if use_arabic_prompt else ''}{company.lower()[:50]}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    prompt = build_prompt_arabic(company, sector, website) if use_arabic_prompt else build_prompt(company, sector, website)
    if use_arabic_prompt:
        logger.info(f" Nom arabe détecté — prompt arabe dédié")

    for model in GROQ_MODELS:
        for attempt in range(GROQ_MAX_RETRIES):
            try:
                r = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {GROQ_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1,
                        "max_tokens": 250
                    },
                    timeout=15
                )
                data = r.json()

                if "choices" not in data:
                    err_msg = data.get("error", {}).get("message", "?")
                    if "rate_limit" in err_msg.lower() or "Rate limit" in err_msg:
                        logger.warning(f" {model} quota épuisé modèle suivant")
                        break
                    logger.warning(f" {model} tentative {attempt+1}: {err_msg}")
                    time.sleep(2)
                    continue

                content = data["choices"][0]["message"]["content"].strip()
                result  = parse_llm_json(content)
                if not result:
                    time.sleep(1)
                    continue

                result = finalize_result(result, company)
                logger.info(f"   Groq ({model}): secteur={result.get('sector')} | type={result.get('company_type')}")
                cache_set(cache_key, result, CACHE_TTL_GROQ)
                return result

            except Exception as e:
                logger.error(f" {model} erreur tentative {attempt+1}: {e}")
                time.sleep(2)

    logger.warning(" Groq épuisé OpenRouter fallback")
    return {}


# OPENROUTER (fallback gratuit)
def enrich_with_openrouter(company: str, sector: str, website: str) -> dict:
    if not OPENROUTER_API_KEY:
        return {}

    cache_key = f"openrouter:{company.lower()[:50]}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    prompt = build_prompt(company, sector, website)

    for model in OPENROUTER_MODELS:
        try:
            r = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://leadpilot.tn",
                    "X-Title": "LeadPilot"
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 250
                },
                timeout=20
            )
            data = r.json()

            if "choices" not in data:
                err_msg = data.get("error", {}).get("message", "?")
                logger.warning(f" OpenRouter {model}: {err_msg}")
                continue

            content = data["choices"][0]["message"]["content"].strip()
            result  = parse_llm_json(content)
            if not result:
                continue

            result = finalize_result(result, company)
            logger.info(f"   OpenRouter ({model}): secteur={result.get('sector')} | type={result.get('company_type')}")
            cache_set(cache_key, result, CACHE_TTL_GROQ)
            return result

        except Exception as e:
            logger.error(f" OpenRouter {model} erreur: {e}")
            continue

    logger.error(" OpenRouter épuisé")
    return {}


# LLM UNIFIÉ : Groq OpenRouter
def enrich_with_llm(company: str, sector: str, city: str, website: str) -> dict:
    result = enrich_with_groq(company, sector, city, website)
    if result:
        return result
    if OPENROUTER_API_KEY:
        logger.info(" Fallback OpenRouter...")
        result = enrich_with_openrouter(company, sector, website)
        if result:
            return result
    logger.error(" Tous les LLMs épuisés")
    return {}


# CALCUL SCORE
def calculate_score(lead) -> float:
    score = 0.0
    if lead.company:  score += 10.0
    if lead.phone:    score += 15.0
    if lead.website:  score += 10.0
    if lead.address:  score += 5.0
    if lead.region:   score += 5.0
    if lead.sector and lead.sector != "Non spécifié": score += 10.0
    if lead.description:                              score += 10.0
    if lead.email:
        email_quality = get_email_quality(lead.email)
        confidence    = lead.email_confidence or 30
        score += (email_quality / 100) * (confidence / 100) * 35
    if lead.email_pattern:
        score += 5.0
    return round(min(score, 100.0), 2)


# LINKEDIN PARSER
def split_name(full_name):
    if not full_name:
        return None, None
    parts = full_name.strip().split()
    if len(parts) == 1:
        return parts[0], None
    return parts[0], " ".join(parts[1:])

def extract_linkedin_data(company_field, title_field):
    first_name, last_name = split_name(company_field)
    company = None
    job_title = None
    if title_field and " - " in title_field:
        parts = title_field.split(" - ", 1)
        job_title = parts[0].strip()
        company   = parts[1].strip()
    else:
        job_title = title_field
    return {
        "first_name": first_name,
        "last_name":  last_name,
        "company":    company,
        "job_title":  job_title,
    }


# PIPELINE PRINCIPAL
def enrich_leads(batch_size: int = 50, only_incomplete: bool = True, lead_ids: list = None):
    db = SyncSessionLocal()
    if lead_ids:
        # Cibler uniquement des leads spécifiques par ID
        leads = db.query(Lead).filter(Lead.id.in_(lead_ids)).all()
    else:
        leads = db.query(Lead).filter(
            Lead.email == None
        ).limit(batch_size).all()

    logger.info(f" Enrichissement de {len(leads)} leads...")
    logger.info(f" LLMs: Groq ({'' if GROQ_API_KEY else ' '}) | OpenRouter ({'' if OPENROUTER_API_KEY else ' '})")
    logger.info("=" * 50)

    enriched_count = skipped_count = 0

    for i, lead in enumerate(leads):
        logger.info(f"\n[{i+1}/{len(leads)}] {lead.company}")
        try:

            # ① LINKEDIN FIX
            if lead.source and "linkedin" in lead.source.lower():
                raw_title = lead.job_title or lead.description
                parsed = extract_linkedin_data(lead.company, raw_title)
                if not lead.first_name and parsed["first_name"]:
                    lead.first_name = parsed["first_name"]
                if not lead.last_name and parsed["last_name"]:
                    lead.last_name = parsed["last_name"]
                if parsed["company"]:
                    lead.company = parsed["company"]
                if parsed["job_title"] and not lead.job_title:
                    lead.job_title = parsed["job_title"]
                logger.info(
                    f"   LinkedIn: {lead.first_name} {lead.last_name} | "
                    f"job={lead.job_title} | company={lead.company}"
                )

            # ② EMAIL
            if not lead.email:
                result = {"email": None, "confidence": 0, "pattern": None}
                if lead.website or lead.company:
                    logger.info(" Hunter.io...")
                    result = find_email_hunter(lead.company, lead.website)
                    time.sleep(0.5)
                if not result["email"] and lead.website:
                    logger.info(" Contact page crawler...")
                    result = scrape_email_from_site(lead.website)
                if not result["email"] and lead.website:
                    logger.info(" Pattern matching...")
                    result = guess_email_pattern(lead.company or "", lead.website)
                if not result["email"] and lead.website:
                    logger.info(" Clearbit...")
                    result = find_email_clearbit(lead.company or "", lead.website)
                if result["email"]:
                    lead.email            = result["email"]
                    lead.email_confidence = result.get("confidence", 0)
                    lead.email_pattern    = result.get("pattern")
                    quality = get_email_quality(result["email"])
                    logger.info(f"   Email: {lead.email} ({result['confidence']}% conf | {quality}% qualité)")
                else:
                    logger.info(" Email non trouvé")

            # ③ NORMALISATION SECTEUR BRUT GOOGLE MAPS
            #    Sans API — mapping direct
            if lead.sector and lead.sector not in ALLOWED_SECTORS:
                normalized = normalize_google_sector(lead.sector)
                if normalized:
                    lead.sector = normalized
                    logger.info(f"   Secteur normalisé (mapping): {lead.sector}")
                else:
                    lead.sector = None
                    logger.info(f" Secteur brut inconnu reset pour Groq")

            # ④ SECTEUR + DESCRIPTION (LLM)
            if not lead.description or not lead.sector:
                if not lead.sector:
                    local = detect_sector_local(lead.company or "")
                    if local:
                        lead.sector = local
                        logger.info(f"   Secteur local (mots-clés): {lead.sector}")

                if not lead.description or not lead.sector:
                    llm = enrich_with_llm(
                        lead.company or "",
                        lead.sector  or "",
                        lead.region  or "",
                        lead.website or ""
                    )
                    if llm:
                        if not lead.description:
                            lead.description = llm.get("description")
                        groq_sector = normalize_sector(llm.get("sector", ""))
                        if not lead.sector or lead.sector == "Non spécifié":
                            lead.sector = groq_sector
                        if not lead.sector or lead.sector == "Non spécifié":
                            local = detect_sector_local(lead.company or "")
                            if local:
                                lead.sector = local
                        if llm.get("company_type") and not lead.company_type:
                            lead.company_type = llm["company_type"]
                        if llm.get("services"):
                            lead.services = json.dumps(llm["services"])
                        logger.info(f"   LLM: secteur={lead.sector} | type={lead.company_type}")
                time.sleep(0.3)

            # ⑤ COMPANY TYPE — si toujours manquant
            #    Sans API — règles par nom + secteur
            if not lead.company_type:
                # Depuis nom entreprise
                ct = detect_company_type_from_name(lead.company or "")
                if ct:
                    lead.company_type = ct
                    logger.info(f"   Company type (nom): {lead.company_type}")
                else:
                    # Depuis secteur
                    ct = SECTOR_DEFAULT_COMPANY_TYPE.get(lead.sector or "")
                    if ct:
                        lead.company_type = ct
                        logger.info(f"   Company type (secteur): {lead.company_type}")
                    else:
                        # Défaut PME
                        lead.company_type = "PME"
                        logger.info(f"   Company type (défaut): PME")

            # ⑥ OPENCORPORATES
            if not lead.company_type:
                oc = enrich_opencorporates(lead.company or "")
                if oc.get("status"):
                    logger.info(f" OpenCorporates: {oc.get('legal_name')} | {oc.get('status')}")

            # ⑦ SCORE FIABILITÉ + COMMIT
            lead.score_fiabilite = calculate_score(lead)
            lead.enriched        = True
            lead.enriched_at     = datetime.utcnow()
            db.commit()
            enriched_count += 1
            logger.info(f" Score: {lead.score_fiabilite}%")

        except Exception as e:
            logger.error(f" Erreur lead {lead.id}: {e}")
            skipped_count += 1
            db.rollback()

    db.close()
    logger.info(f"\n{'='*50}")
    logger.info(f"Terminé ! Enrichis: {enriched_count} | Ignorés: {skipped_count}")
    if HAS_REDIS:
        logger.info(" Cache Redis: actif")


if __name__ == "__main__":
    import sys
    enrich_leads(batch_size=int(sys.argv[1]) if len(sys.argv) > 1 else 50)