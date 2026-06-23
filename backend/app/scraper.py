import requests
import logging
import time
import re
import os
import glob
import csv
from bs4 import BeautifulSoup

logger = logging.getLogger("leadpilot.scraper")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# POINT D'ENTRÉE PRINCIPAL — dispatch selon source

def scrape_google_maps(keywords, location, sector, max_leads):
    return _scrape_google_maps_playwright(keywords, location, sector, max_leads)

def run_scraper(source: str, keywords: str, location: str, sector: str, max_leads: int) -> list:
    """Dispatch vers le bon scraper selon la source"""
    source = (source or "").strip()
    logger.info(f"[SCRAPER] Source={source} | keywords={keywords} | location={location} | max={max_leads}")

    if source == "Google Maps":
        return _scrape_google_maps_playwright(keywords, location, sector, max_leads)
    elif source == "Pages Jaunes":
        return _scrape_pages_jaunes(keywords, location, sector, max_leads)
    elif source == "Societe.com":
        return _scrape_societe_com(keywords, location, sector, max_leads)
    elif source == "LinkedIn":
        return _scrape_linkedin_simulation(keywords, location, sector, max_leads)
    elif source == "Import CSV":
        return _scrape_from_csv(keywords, location, sector, max_leads)
    elif source == "Pages Jaunes Maroc":
        return _scrape_pages_jaunes_maroc(keywords, location, sector, max_leads)
    elif source == "Europages":
        return _scrape_europages(keywords, location, sector, max_leads)
    elif source == "Kompass":
        return _scrape_kompass(keywords, location, sector, max_leads)
    elif source == "Foursquare":
        return _scrape_foursquare(keywords, location, sector, max_leads)
    else:
        return _scrape_overpass(keywords, location, sector, max_leads)


# SOURCE 1 — GOOGLE MAPS via Overpass API (OpenStreetMap)

KEYWORD_MAP = {
    "restaurant":   [("amenity", "restaurant")],
    "café":         [("amenity", "cafe")],
    "cafe":         [("amenity", "cafe")],
    "pharmacie":    [("amenity", "pharmacy")],
    "banque":       [("amenity", "bank")],
    "hôtel":        [("tourism", "hotel")],
    "hotel":        [("tourism", "hotel")],
    "supermarché":  [("shop", "supermarket")],
    "boulangerie":  [("shop", "bakery")],
    "médecin":      [("amenity", "doctors")],
    "dentiste":     [("amenity", "dentist")],
    "garage":       [("shop", "car_repair")],
    "coiffeur":     [("shop", "hairdresser")],
    "école":        [("amenity", "school")],
    "gym":          [("leisure", "fitness_centre")],
    "hôpital":      [("amenity", "hospital")],
    "librairie":    [("shop", "books")],
    "agence":       [("office", "company")],
    "entreprise":   [("office", "company")],
    "bureau":       [("office", "company")],
    "informatique": [("office", "it")],
}

SECTOR_MAP = {
    "Restauration & Hôtellerie": [("amenity", "restaurant"), ("amenity", "cafe"), ("tourism", "hotel")],
    "Santé":                     [("amenity", "pharmacy"), ("amenity", "hospital"), ("amenity", "doctors")],
    "Finance & Comptabilité":    [("amenity", "bank"), ("office", "financial")],
    "Education & Formation":     [("amenity", "school"), ("amenity", "university")],
    "Commerce & Distribution":   [("shop", "supermarket"), ("shop", "convenience")],
    "Services aux entreprises":  [("office", "company")],
    "Informatique & Tech":       [("office", "it")],
}

OVERPASS_SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

def _overpass_request(query: str) -> dict:
    """Envoie la requête Overpass — essaie GET puis POST sur chaque serveur"""
    import urllib.parse
    session = requests.Session()
    session.trust_env = True
    encoded = urllib.parse.quote(query)

    for server in OVERPASS_SERVERS:
        # Essai 1 : GET (évite le 406 sur overpass-api.de)
        for method in ("GET", "POST"):
            try:
                logger.info(f"[Overpass] {method} {server}")
                if method == "GET":
                    r = session.get(f"{server}?data={encoded}", timeout=35)
                else:
                    r = session.post(server, data={"data": query}, timeout=35)

                if r.status_code == 200 and r.text.strip().startswith("{"):
                    data = r.json()
                    n = len(data.get("elements", []))
                    logger.info(f"[Overpass] Succès {method} — {n} éléments")
                    return data
                logger.warning(f"[Overpass] {method} {server} {r.status_code}")
            except Exception as e:
                logger.warning(f"[Overpass] {method} {server} erreur: {e}")
        time.sleep(1)

    logger.warning("[Overpass] Tous les serveurs inaccessibles")
    return {}


TUNISIAN_CITIES = {
    "tunis": (36.8190, 10.1658), "sfax": (34.7398, 10.7600),
    "sousse": (35.8245, 10.6346), "monastir": (35.7643, 10.8113),
    "bizerte": (37.2744, 9.8739), "nabeul": (36.4561, 10.7376),
    "ariana": (36.8625, 10.1956), "gabes": (33.8833, 10.1000),
    "kairouan": (35.6712, 10.1005), "hammamet": (36.4000, 10.6167),
    "ben arous": (36.7531, 10.2281), "manouba": (36.8081, 10.0975),
}

def _geocode(city: str):
    # Chercher d'abord dans le dictionnaire local (pas de réseau)
    city_lower = (city or "tunis").lower().strip()
    for key, coords in TUNISIAN_CITIES.items():
        if key in city_lower or city_lower in key:
            logger.info(f"[Geocode] '{city}' {coords} (cache local)")
            return coords

    # Sinon appel Nominatim avec ville + Tunisie pour éviter ambiguïté
    try:
        session = requests.Session()
        session.trust_env = True
        query = city if "tunisi" in city_lower else f"{city}, Tunisia"
        r = session.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json", "limit": 1,
                    "countrycodes": "tn"},  # forcer Tunisie
            headers={"User-Agent": "LeadPilot/1.0"},
            timeout=10,
        )
        data = r.json()
        if data:
            lat, lon = float(data[0]["lat"]), float(data[0]["lon"])
            logger.info(f"[Geocode] '{city}' ({lat}, {lon}) via Nominatim")
            return lat, lon
    except Exception as e:
        logger.warning(f"Geocoding échoué pour '{city}': {e}")
    logger.info(f"[Geocode] Fallback Tunis pour '{city}'")
    return 36.8190, 10.1658  # Tunis fallback

def _get_tags(keywords, sector):
    tags = []
    if keywords:
        for kw in keywords.lower().split(","):
            kw = kw.strip()
            for key, mappings in KEYWORD_MAP.items():
                if key in kw:
                    tags.extend(mappings)
    if not tags and sector and sector in SECTOR_MAP:
        tags = SECTOR_MAP[sector]
    if not tags:
        tags = [("amenity", "restaurant"), ("office", "company")]
    seen, unique = set(), []
    for t in tags:
        if t not in seen:
            seen.add(t); unique.append(t)
    return unique

def _detect_sector(amenity, shop, office, tourism):
    if amenity in ("restaurant","cafe","fast_food","bar"):    return "Restauration & Hôtellerie"
    if tourism in ("hotel","hostel","guest_house"):           return "Restauration & Hôtellerie"
    if amenity in ("pharmacy","hospital","doctors","dentist"): return "Santé"
    if amenity == "bank" or office == "financial":            return "Finance & Comptabilité"
    if amenity in ("school","university","college"):          return "Education & Formation"
    if shop in ("supermarket","convenience","clothes"):       return "Commerce & Distribution"
    if office == "it":                                        return "Informatique & Tech"
    return "Services aux entreprises"

def _scrape_google_maps_playwright(keywords, location, sector, max_leads):
    """
    Scraping Google Maps via Playwright — données riches + pipeline email.
    Fallback vers Overpass si Playwright non disponible.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("[Google Maps] Playwright non installé fallback Overpass")
        return _scrape_overpass(keywords, location, sector, max_leads)

    search_query = f"{keywords or sector or 'entreprises'} {location or 'Tunis'}"
    logger.info(f"[Google Maps] Playwright search: {search_query}")
    leads = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            search_encoded = search_query.replace(" ", "+")
            url = f"https://www.google.com/maps/search/{search_encoded}/?hl=fr"
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(3000)

            try:
                page.wait_for_selector('//a[contains(@href, "https://www.google.com/maps/place")]', timeout=15000)
            except Exception:
                logger.warning("[Google Maps] Aucun résultat — fallback Overpass")
                browser.close()
                return _scrape_overpass(keywords, location, sector, max_leads)

            # Scroll pour charger les résultats
            prev = 0
            for _ in range(40):
                try:
                    panel = page.locator('div[role="feed"]').first
                    if panel.count() > 0:
                        panel.evaluate("el => el.scrollTop += 2000")
                    else:
                        page.mouse.wheel(0, 3000)
                    page.wait_for_timeout(1500)
                    found = page.locator('//a[contains(@href, "https://www.google.com/maps/place")]').count()
                    if found >= max_leads or found == prev:
                        break
                    prev = found
                except Exception:
                    break

            place_links = page.locator('//a[contains(@href, "https://www.google.com/maps/place")]').all()[:max_leads]
            # Capturer le nom via aria-label AVANT de cliquer (fiable)
            entries = []
            for a in place_links:
                try:
                    aria = (a.get_attribute("aria-label") or "").strip()
                except Exception:
                    aria = ""
                entries.append((a, aria))
            logger.info(f"[Google Maps] {len(entries)} listings à traiter")

            for idx, (link, aria_name) in enumerate(entries):
                try:
                    name = aria_name
                    # Ouvrir le détail et ATTENDRE que le panneau soit chargé
                    # (essentiel pour récupérer le site web et le téléphone)
                    try:
                        link.click()
                        # attendre le titre du panneau détail (panneau prêt)
                        try:
                            page.wait_for_selector('//h1[contains(@class,"DUwDvf")]', timeout=8000)
                        except Exception:
                            page.wait_for_timeout(2500)
                        page.wait_for_timeout(800)
                        if not name:
                            h1 = page.locator('//h1[contains(@class,"DUwDvf")]')
                            if h1.count() > 0:
                                candidate = h1.first.inner_text(timeout=2000).strip()
                                if candidate.lower() not in ('résultats', 'resultats', 'results', ''):
                                    name = candidate
                    except Exception:
                        pass

                    def _txt(sel, is_xpath=True):
                        try:
                            loc = page.locator(f'xpath={sel}') if is_xpath else page.locator(sel)
                            return loc.first.inner_text(timeout=3000).strip() if loc.count() > 0 else ''
                        except Exception:
                            return ''

                    # Attributs data-item-id stables
                    address = _txt('//button[@data-item-id="address"]//div[contains(@class,"fontBody")]')
                    phone   = _txt('//button[contains(@data-item-id,"phone:tel:")]//div[contains(@class,"fontBody")]')

                    # Website : href direct
                    website = ''
                    try:
                        wa = page.locator('a[data-item-id="authority"]')
                        if wa.count() > 0:
                            website = wa.first.get_attribute('href') or ''
                        if not website:
                            website = _txt('//a[@data-item-id="authority"]//div[contains(@class,"fontBody")]')
                    except Exception:
                        pass

                    ptype = ''
                    try:
                        pt = page.locator('button[jsaction*="category"]')
                        if pt.count() > 0:
                            ptype = pt.first.inner_text(timeout=2000)
                    except Exception:
                        pass

                    reviews_count, reviews_avg = None, None

                    if not name:
                        continue

                    # Pipeline email sur le site web
                    email = None
                    if website:
                        email = _gm_get_email(website)
                        if email:
                            logger.info(f"[Google Maps] [{idx+1}] Email: {email}")

                    leads.append({
                        "company":          name,
                        "phone":            phone or None,
                        "website":          website or None,
                        "address":          address or None,
                        "region":           location or "Tunisie",
                        "sector":           sector or _gm_detect_sector(ptype),
                        "email":            email,
                        "reviews_count":    reviews_count,
                        "reviews_average":  reviews_avg,
                        "source":           "google_maps",
                    })
                    logger.info(f"[Google Maps] [{idx+1}] {name} | {phone or 'N/A'} | {email or 'N/A'}")

                except Exception as e:
                    logger.warning(f"[Google Maps] Listing {idx+1} erreur: {e}")
                    continue

            browser.close()

    except Exception as e:
        logger.error(f"[Google Maps] Playwright erreur: {e} fallback Overpass")
        return _scrape_overpass(keywords, location, sector, max_leads)

    logger.info(f"[Google Maps] {len(leads)} leads collectés")
    return leads


def _gm_get_email(website: str) -> str:
    """Pipeline email pour Google Maps : homepage + pages contact"""
    try:
        domain = ""
        try:
            from urllib.parse import urlparse as _up
            parsed = _up(website if website.startswith("http") else "https://" + website)
            domain = parsed.hostname or ""
        except Exception:
            pass

        base = website if website.startswith("http") else "https://" + website

        try:
            r = requests.get(base, headers=HEADERS, timeout=6)
            if r.status_code == 200:
                html = r.text
                from bs4 import BeautifulSoup as _BS
                soup = _BS(html, "html.parser")

                # mailto: priorité absolue
                for a in soup.find_all("a", href=True):
                    if a["href"].startswith("mailto:"):
                        e = _clean_email(a["href"])
                        if _ti_is_valid_email(e):
                            return e

                # Schema.org
                for script in soup.find_all("script", type="application/ld+json"):
                    try:
                        import json as _j
                        emails = _ti_extract_emails(_j.dumps(_j.loads(script.string or "")))
                        if emails:
                            return _ti_best_email(emails, domain)
                    except Exception:
                        pass

                # Footer
                footer = soup.find("footer")
                if footer:
                    emails = _ti_extract_emails(footer.get_text())
                    if emails:
                        return _ti_best_email(emails, domain)

                # Regex homepage
                emails = _ti_extract_emails(html)
                if emails:
                    return _ti_best_email(emails, domain)
        except Exception:
            pass

        # Pages contact
        for path in CONTACT_PATHS:
            try:
                r = requests.get(base + path, headers=HEADERS, timeout=4)
                if r.status_code != 200:
                    continue
                from bs4 import BeautifulSoup as _BS2
                sp = _BS2(r.text, "html.parser")
                for a in sp.find_all("a", href=True):
                    if a["href"].startswith("mailto:"):
                        e = _clean_email(a["href"])
                        if _ti_is_valid_email(e):
                            return e
                emails = _ti_extract_emails(r.text)
                if emails:
                    return _ti_best_email(emails, domain)
                time.sleep(0.2)
            except Exception:
                continue
    except Exception:
        pass
    return None


def _gm_detect_sector(place_type: str) -> str:
    """Détecte le secteur depuis le type Google Maps"""
    if not place_type:
        return "Services aux entreprises"
    pt = place_type.lower()
    if any(x in pt for x in ["restaurant", "café", "hôtel", "pizzeria", "traiteur"]):
        return "Restauration & Hôtellerie"
    if any(x in pt for x in ["pharmacie", "médecin", "clinique", "hôpital", "dentiste"]):
        return "Santé"
    if any(x in pt for x in ["banque", "assurance", "financier"]):
        return "Finance & Comptabilité"
    if any(x in pt for x in ["école", "université", "formation"]):
        return "Education & Formation"
    if any(x in pt for x in ["informatique", "software", "tech", "digital"]):
        return "Informatique & Tech"
    if any(x in pt for x in ["construction", "bâtiment", "architecte"]):
        return "Construction & BTP"
    if any(x in pt for x in ["transport", "logistique"]):
        return "Transport & Logistique"
    if any(x in pt for x in ["immobilier", "agence immobilière"]):
        return "Immobilier"
    return "Services aux entreprises"


def _scrape_overpass(keywords, location, sector, max_leads):
    lat, lon = _geocode(location or "Tunis")
    time.sleep(1)
    tags = _get_tags(keywords or "", sector or "")
    radius = 20000  # 20km pour avoir plus de résultats
    parts = []
    for key, val in tags:
        parts.append(f'node["{key}"="{val}"](around:{radius},{lat},{lon});')
        parts.append(f'way["{key}"="{val}"](around:{radius},{lat},{lon});')
    # Toujours ajouter offices/companies pour avoir du B2B
    if ("office", "company") not in tags:
        parts.append(f'node["office"](around:{radius},{lat},{lon});')
        parts.append(f'way["office"](around:{radius},{lat},{lon});')
    query = f'[out:json][timeout:30];\n(\n  {"  ".join(parts)}\n);\nout center tags;'
    data = _overpass_request(query)
    if not data:
        return []

    leads = []
    for el in data.get("elements", []):
        t = el.get("tags", {})
        name = t.get("name") or t.get("name:fr") or t.get("name:ar")
        if not name: continue
        addr_parts = [t.get("addr:housenumber"), t.get("addr:street"), t.get("addr:city")]
        leads.append({
            "company": name,
            "phone":   t.get("phone") or t.get("contact:phone"),
            "website": t.get("website") or t.get("contact:website"),
            "address": " ".join(p for p in addr_parts if p) or None,
            "region":  t.get("addr:city") or t.get("addr:suburb") or location,
            "sector":  _detect_sector(t.get("amenity",""), t.get("shop",""), t.get("office",""), t.get("tourism","")),
            "source":  "scraping",
        })
        if len(leads) >= max_leads: break
    logger.info(f"[Overpass] {len(leads)} leads")
    return leads


# SOURCE 2 — PAGES JAUNES (tunisieindex.com)

# URLs réelles de tunisieindex.com (découvertes par analyse du scraper original)
TUNISIEINDEX_CATEGORIES = {
    "informatique":  "/annuaire-entreprises/informatique-internet-17/",
    "tourisme":      "/annuaire-entreprises/restauration-hotellerie-tourisme-8/",
    "restaurant":    "/annuaire-entreprises/restauration-hotellerie-tourisme-8/",
    "finance":       "/annuaire-entreprises/banques-assurances-12/",
    "sante":         "/annuaire-entreprises/sante-10/",
    "immobilier":    "/annuaire-entreprises/immobilier-13/",
    "commerce":      "/annuaire-entreprises/commerce-distribution-14/",
    "services":      "/annuaire-entreprises/services-aux-entreprises-15/",
    "agriculture":   "/annuaire-entreprises/agriculture-agro-alimentaire-1/",
    "construction":  "/annuaire-entreprises/matariaux-construction-2/",
    "transport":     "/annuaire-entreprises/transport-logistique-9/",
    "education":     "/annuaire-entreprises/enseignement-formation-11/",
    "communication": "/annuaire-entreprises/communication-medias-16/",
}

TUNISIEINDEX_REGIONS = {
    "tunis":    "/entreprises-par-region/Gouvernorat-TUNIS/classement-par-ordre-alphabetique.html",
    "sfax":     "/entreprises-par-region/Gouvernorat-SFAX/classement-par-ordre-alphabetique.html",
    "sousse":   "/entreprises-par-region/Gouvernorat-SOUSSE/classement-par-ordre-alphabetique.html",
    "ariana":   "/entreprises-par-region/Gouvernorat-ARIANA/classement-par-ordre-alphabetique.html",
    "monastir": "/entreprises-par-region/Gouvernorat-MONASTIR/classement-par-ordre-alphabetique.html",
    "bizerte":  "/entreprises-par-region/Gouvernorat-BIZERTE/classement-par-ordre-alphabetique.html",
    "nabeul":   "/entreprises-par-region/Gouvernorat-NABEUL/classement-par-ordre-alphabetique.html",
    "gabes":    "/entreprises-par-region/Gouvernorat-GABES/classement-par-ordre-alphabetique.html",
}

TUNISIEINDEX_BASE = "https://www.tunisieindex.com"

EMAIL_BLACKLIST_WORDS = [
    "example", "sentry", "wix", "wordpress", "schema",
    "google", "facebook", "jquery", "png", "jpg", "svg",
    "noreply", "no-reply", "donotreply", "webmaster",
    "spam", "test@", "tunisieindex", "donnees.personnelles",
    "privacy", "rgpd", "dpo@", "dpo.",
    "votre@", "votre.email", "your@", "your.email",
    "email@example", "adresse@", "contact@example",
    "info@example", "mail@example", "demo@",
    "rsultats@", "resultats@", "résultats@",
    "sultats@", "sults@",
]
EMAIL_BLACKLIST_DOMAINS = [
    "facebook.com", "instagram.com", "linkedin.com",
    "youtube.com", "tiktok.com", "twitter.com",
    "google.com", "wa.me", "whatsapp.com",
    "booking.com", "expedia.com", "tripadvisor.com",
    "edicom.ma", "telecontact.ma",
    "domain.com", "example.com", "test.com", "email.com",
    "yourcompany.com", "mycompany.com",
]

# Extensions de fichiers qui ne sont jamais des domaines email
_FAKE_EMAIL_TLDS = {"gif", "png", "jpg", "jpeg", "svg", "webp", "ico", "bmp", "mp4", "pdf", "zip"}
CONTACT_PATHS = [
    "/contact", "/contact-us", "/nous-contacter",
    "/contactez-nous", "/about", "/a-propos",
    "/mentions-legales", "/team",
]
ROLE_PRIORITY = ["ceo", "founder", "pdg", "dg", "direction",
                 "contact", "commercial", "sales", "info", "admin"]

def _clean_email(email: str) -> str:
    """Nettoie un email brut : retire préfixes URL, encodages, espaces."""
    if not email:
        return ""
    e = email.strip().lower()
    e = e.replace("mailto:", "").replace("http://", "").replace("https://", "")
    e = e.split("?")[0].split(" ")[0].replace("%20", "").replace("%40", "@").strip()
    return e

def _ti_is_valid_email(email: str) -> bool:
    if not email:
        return False
    email = _clean_email(email)
    if "@" not in email or len(email) > 100:
        return False
    if any(b in email.lower() for b in EMAIL_BLACKLIST_WORDS):
        return False
    try:
        domain = email.split("@")[1].lower()
        # Rejeter les extensions de fichiers (ex: fancybox_loading@2x.gif)
        tld = domain.rsplit(".", 1)[-1] if "." in domain else ""
        if tld in _FAKE_EMAIL_TLDS:
            return False
        if any(domain == b or domain.endswith("." + b) for b in EMAIL_BLACKLIST_DOMAINS):
            return False
    except Exception:
        return False
    return True

def _ti_extract_emails(text: str) -> list:
    raw = re.findall(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', text)
    return [e.lower() for e in raw if _ti_is_valid_email(e)]

def _ti_best_email(emails: list, domain: str = None) -> str:
    if not emails:
        return None
    if domain:
        clean = domain.replace("www.", "").split(".")[0]
        same = [e for e in emails if clean in e]
        if same:
            emails = same
    for role in ROLE_PRIORITY:
        for e in emails:
            if role in e.split("@")[0].lower():
                return e
    return emails[0]

def _ti_get_email(fiche_soup, fiche_text: str, website: str) -> str:
    """Pipeline email complet : fiche homepage pages contact"""
    domain = ""
    if website:
        try:
            from urllib.parse import urlparse as _up
            parsed = _up(website if website.startswith("http") else "https://" + website)
            domain = parsed.hostname or ""
        except Exception:
            pass

    # 1. mailto: dans la fiche tunisieindex
    for a in fiche_soup.find_all("a", href=True):
        if a["href"].startswith("mailto:"):
            email = a["href"].replace("mailto:", "").split("?")[0].strip().lower()
            if _ti_is_valid_email(email):
                return email

    # 2. Regex dans le texte de la fiche
    emails = _ti_extract_emails(fiche_text)
    if emails:
        return _ti_best_email(emails, domain)

    if not website:
        return None

    base = website if website.startswith("http") else "https://" + website

    # 3-5. Homepage : Schema.org, footer, meta, regex
    try:
        r = requests.get(base, headers=HEADERS, timeout=6)
        if r.status_code == 200:
            html = r.text
            soup_hp = BeautifulSoup(html, "html.parser")

            # mailto: homepage
            for a in soup_hp.find_all("a", href=True):
                if a["href"].startswith("mailto:"):
                    email = a["href"].replace("mailto:", "").split("?")[0].strip().lower()
                    if _ti_is_valid_email(email):
                        return email

            # Schema.org JSON-LD
            for script in soup_hp.find_all("script", type="application/ld+json"):
                try:
                    import json as _json
                    emails = _ti_extract_emails(_json.dumps(_json.loads(script.string or "")))
                    if emails:
                        return _ti_best_email(emails, domain)
                except Exception:
                    pass

            # Footer
            footer = soup_hp.find("footer")
            if footer:
                emails = _ti_extract_emails(footer.get_text())
                if emails:
                    return _ti_best_email(emails, domain)

            # Regex homepage complète
            emails = _ti_extract_emails(html)
            if emails:
                return _ti_best_email(emails, domain)
    except Exception:
        pass

    # 6. Pages /contact, /about, /mentions-legales
    for path in CONTACT_PATHS:
        try:
            r = requests.get(base + path, headers=HEADERS, timeout=5)
            if r.status_code != 200:
                continue
            soup_p = BeautifulSoup(r.text, "html.parser")
            for a in soup_p.find_all("a", href=True):
                if a["href"].startswith("mailto:"):
                    email = a["href"].replace("mailto:", "").split("?")[0].strip().lower()
                    if _ti_is_valid_email(email):
                        return email
            emails = _ti_extract_emails(r.text)
            if emails:
                return _ti_best_email(emails, domain)
            time.sleep(0.3)
        except Exception:
            continue

    return None

def _ti_scrape_fiche(fiche_url: str) -> dict:
    """Visite la fiche tunisieindex et extrait toutes les infos"""
    try:
        r = requests.get(fiche_url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return {}
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(" ", strip=True)

        phone, website, address = None, None, None

        # Téléphone
        p = re.search(r"\(?\+?216\)?[\s\-]?\d{2}[\s\-]?\d{3}[\s\-]?\d{3}", text)
        if p:
            phone = p.group(0).strip()

        # Site web (premier lien externe non tunisieindex)
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("http") and "tunisieindex" not in href:
                website = href
                break

        # Adresse
        for kw in ["Adresse :", "adresse :"]:
            if kw in text:
                idx = text.index(kw) + len(kw)
                address = text[idx:idx+100].strip().split("  ")[0].strip()
                break

        # Email via pipeline complet
        email = _ti_get_email(soup, text, website)

        return {"phone": phone, "website": website, "address": address, "email": email}
    except Exception as e:
        logger.debug(f"[TI fiche] Erreur {fiche_url}: {e}")
        return {}


def _scrape_pages_jaunes(keywords, location, sector, max_leads):
    """Scrape tunisieindex.com — visite chaque fiche pour email/téléphone/site"""
    leads = []
    session = requests.Session()
    session.trust_env = True

    path = None
    loc_lower = (location or "").lower().strip()
    kw_lower  = (keywords or "").lower().strip()
    sec_lower = (sector or "").lower().strip()

    detected_region = None
    for key, url_path in TUNISIEINDEX_REGIONS.items():
        if key in loc_lower:
            path = url_path
            detected_region = key.capitalize()
            break

    if not path:
        for key, url_path in TUNISIEINDEX_CATEGORIES.items():
            if key in kw_lower or key in sec_lower:
                path = url_path
                break

    if not path:
        path = "/annuaire-entreprises/services-aux-entreprises-15/"

    url = TUNISIEINDEX_BASE + path
    logger.info(f"[Pages Jaunes] Scraping {url}")

    try:
        r = session.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            raise Exception(f"Status {r.status_code}")

        soup = BeautifulSoup(r.text, "html.parser")

        company_links = []
        seen_names = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if not href.startswith("http"):
                href = TUNISIEINDEX_BASE + href
            if "/entreprises/" in href and re.search(r"-\d+\.html$", href):
                name = a.get_text(strip=True)
                if name and 3 < len(name) < 120 and name not in seen_names:
                    seen_names.add(name)
                    company_links.append((name, href))

        logger.info(f"[Pages Jaunes] {len(company_links)} fiches trouvées")

        region = detected_region or location or _guess_region_from_path(path) or "Tunisie"
        detected_sector = sector or _guess_sector_from_path(path)

        # Visiter chaque fiche pour récupérer email, téléphone, site web
        for name, href in company_links[:max_leads]:
            logger.info(f"[Pages Jaunes] Fiche : {name}")
            fiche = _ti_scrape_fiche(href)
            leads.append({
                "company":      name,
                "phone":        fiche.get("phone"),
                "website":      fiche.get("website"),   # vrai site de l'entreprise
                "address":      fiche.get("address"),
                "email":        fiche.get("email"),
                "region":       region,
                "sector":       detected_sector,
                "source":       "scraping",
                "scraping_url": href,
            })
            time.sleep(0.5)  # politesse

        logger.info(f"[Pages Jaunes] {len(leads)} leads construits")

    except Exception as e:
        logger.error(f"[Pages Jaunes] Erreur: {e}")
        logger.info("[Pages Jaunes] Fallback Import CSV")
        leads = _scrape_from_csv(keywords, location, sector, max_leads)

    return leads[:max_leads]


def _guess_region_from_path(path: str) -> str:
    """Extrait la région depuis le path tunisieindex (ex: Gouvernorat-TUNIS Tunis)"""
    mapping = {
        "TUNIS":    "Tunis",
        "SFAX":     "Sfax",
        "SOUSSE":   "Sousse",
        "ARIANA":   "Ariana",
        "MONASTIR": "Monastir",
        "BIZERTE":  "Bizerte",
        "NABEUL":   "Nabeul",
        "GABES":    "Gabès",
    }
    for key, val in mapping.items():
        if key in path.upper():
            return val
    return None

def _guess_sector_from_path(path: str) -> str:
    mapping = {
        "informatique": "Informatique & Tech",
        "restauration": "Restauration & Hôtellerie",
        "banques":      "Finance & Comptabilité",
        "sante":        "Santé",
        "immobilier":   "Immobilier",
        "commerce":     "Commerce & Distribution",
        "transport":    "Transport & Logistique",
        "enseignement": "Education & Formation",
    }
    for key, val in mapping.items():
        if key in path:
            return val
    return "Services aux entreprises"


# SOURCE 2b — TELECONTACT.MA (anciennement pagesjaunes.ma)

TC_BASE = "https://www.telecontact.ma"

TC_CATEGORIES = {
    "informatique":  "informatique",
    "finance":       "banques",
    "assurance":     "assurances",
    "immobilier":    "immobilier",
    "construction":  "construction",
    "transport":     "transport",
    "education":     "enseignement",
    "restaurant":    "restaurants",
    "industrie":     "industrie",
    "commerce":      "commerce",
    "services":      "services-aux-entreprises",
    "sante":         "sante",
    "conseil":       "conseil-et-management",
    "comptabilite":  "expertise-comptable",
    "juridique":     "avocats",
    "pub":           "publicite-et-communication",
    "recrutement":   "recrutement",
}

TC_SECTOR_MAP = {
    "informatique":             "Informatique & Tech",
    "banques":                  "Finance & Comptabilité",
    "assurances":               "Finance & Comptabilité",
    "immobilier":               "Immobilier",
    "construction":             "Construction & BTP",
    "transport":                "Transport & Logistique",
    "enseignement":             "Education & Formation",
    "restaurants":              "Restauration & Hôtellerie",
    "industrie":                "Industrie & Production",
    "commerce":                 "Commerce & Distribution",
    "services-aux-entreprises": "Services aux entreprises",
    "sante":                    "Santé",
    "conseil-et-management":    "Services aux entreprises",
    "expertise-comptable":      "Finance & Comptabilité",
    "avocats":                  "Juridique",
    "publicite-et-communication": "Marketing & Communication",
    "recrutement":              "Services aux entreprises",
}

NAV_WORDS = {
    "accueil", "connexion", "inscription", "recherche", "contact",
    "mentions", "plan du site", "annuaire", "suivant", "précédent",
    "telecontact", "page", "résultats", "voir plus",
}


def _tc_scrape_fiche(fiche_url: str) -> dict:
    """Visite une fiche telecontact.ma et extrait téléphone, site web, email, adresse"""
    try:
        r = requests.get(fiche_url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return {}
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(" ", strip=True)

        phone, website, address = None, None, None

        # Téléphone via balise tel: (le plus fiable sur telecontact.ma)
        for a in soup.find_all("a", href=True):
            if a["href"].startswith("tel:"):
                raw = a["href"].replace("tel:", "").strip()
                if raw:
                    phone = raw
                    break

        # Fallback regex téléphone marocain
        if not phone:
            p = re.search(
                r"(?:\+212[\s\-]?|0)(?:5|6|7)[\s\-]?\d{2}[\s\-]?\d{2}[\s\-]?\d{2}[\s\-]?\d{2}",
                text
            )
            if p:
                phone = p.group(0).strip()

        # Site web : premier lien externe (pas telecontact, pas réseaux sociaux)
        skip_domains = ("telecontact.ma", "facebook.", "instagram.", "twitter.",
                        "linkedin.", "youtube.", "tiktok.", "google.")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("http") and not any(d in href for d in skip_domains):
                website = href
                break

        # Adresse via itemprop ou balises structurées
        for sel in ["[itemprop='address']", ".adresse", ".address", "address"]:
            tag = soup.select_one(sel)
            if tag:
                address = tag.get_text(" ", strip=True)[:150]
                break

        # Fallback adresse : cherche "Adresse" dans le texte
        if not address:
            m = re.search(r"Adresse\s*:?\s*(.{10,150}?)(?:\s{2,}|\n|Tel|Email|Site)", text)
            if m:
                address = m.group(1).strip()

        # Email : uniquement mailto: dans la fiche (pas de visite site web — trop lent)
        email = None
        for a in soup.find_all("a", href=True):
            if a["href"].startswith("mailto:"):
                e = a["href"].replace("mailto:", "").split("?")[0].strip().lower()
                if _ti_is_valid_email(e):
                    email = e
                    break
        if not email:
            emails = _ti_extract_emails(text)
            if emails:
                email = _ti_best_email(emails, "")
        return {"phone": phone, "website": website, "address": address, "email": email}

    except Exception as e:
        logger.debug(f"[TC] Fiche erreur {fiche_url}: {e}")
        return {}


def _tc_city_from_url(url: str) -> str:
    """Extrait la ville depuis l'URL telecontact /annonceur/slug/id/casablanca.php"""
    m = re.search(r"/annonceur/[^/]+/\d+/([^/.]+)\.php", url)
    if m:
        city = m.group(1).replace("-", " ").title()
        return city
    return "Maroc"


def _scrape_pages_jaunes_maroc(keywords, location, sector, max_leads):
    """
    Scrape telecontact.ma (annuaire marocain, ex-pagesjaunes.ma).
    Stratégie : liste nationale par secteur (pagination), filtre optionnel par ville.
    5000+ entreprises par secteur disponibles.
    """
    leads = []
    session = requests.Session()
    session.trust_env = True

    kw_lower  = (keywords or "").lower().strip()
    sec_lower = (sector or "").lower().strip()
    loc_clean = (location or "").strip()

    # Choisir le slug catégorie
    category_slug = "services-aux-entreprises"
    for key, slug in TC_CATEGORIES.items():
        if key in kw_lower or key in sec_lower:
            category_slug = slug
            break

    detected_sector = sector or TC_SECTOR_MAP.get(category_slug, "Services aux entreprises")

    # Normaliser la ville pour filtrer (optionnel)
    city_filter = loc_clean.lower() if loc_clean else None
    city_filter_slug = ""
    if city_filter:
        city_filter_slug = city_filter
        city_filter_slug = city_filter_slug.replace("é","e").replace("è","e").replace("ê","e")
        city_filter_slug = city_filter_slug.replace("à","a").replace("â","a")
        city_filter_slug = city_filter_slug.replace("ô","o").replace("ù","u").replace("û","u")
        city_filter_slug = re.sub(r"[^a-z0-9]+", "-", city_filter_slug).strip("-")

    company_links = []  # list of (name, url)
    seen_urls = set()
    seen_names = set()

    # Calculer les pages nécessaires (~20 résultats/page)
    pages_needed = (max_leads // 15) + 2

    for page_num in range(1, pages_needed + 1):
        if len(company_links) >= max_leads:
            break

        list_url = f"{TC_BASE}/maroc/{category_slug}.html&page={page_num}"
        logger.info(f"[TC] Page {page_num}: {list_url}")

        try:
            r = session.get(list_url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                logger.warning(f"[TC] {list_url} {r.status_code}")
                break

            soup = BeautifulSoup(r.text, "html.parser")

            for a in soup.find_all("a", href=True):
                href = a["href"]
                if not href.startswith("http"):
                    href = TC_BASE + href

                # Pattern fiche telecontact.ma : /annonceur/slug/id/ville.php
                if not re.search(r"/annonceur/[^/]+/\d+/[^/]+\.php$", href):
                    continue
                if href in seen_urls:
                    continue

                # Filtre par ville si demandé
                if city_filter_slug:
                    url_city = re.search(r"/annonceur/[^/]+/\d+/([^/]+)\.php$", href)
                    if url_city and city_filter_slug not in url_city.group(1):
                        continue

                name = a.get_text(strip=True)
                if not name or len(name) < 2:
                    # Chercher dans le parent
                    parent = a.find_parent(["div", "li", "article", "td"])
                    if parent:
                        for tag in parent.find_all(["h2", "h3", "h4", "strong"]):
                            t = tag.get_text(strip=True)
                            if t and len(t) > 2 and t.lower() not in NAV_WORDS:
                                name = t
                                break

                if not name or len(name) < 2:
                    continue
                if name.lower() in NAV_WORDS:
                    continue
                if name in seen_names:
                    continue

                seen_urls.add(href)
                seen_names.add(name)
                company_links.append((name, href))

            time.sleep(1)

        except Exception as e:
            logger.warning(f"[TC] Erreur page {page_num}: {e}")
            break

    logger.info(f"[TC] {len(company_links)} fiches collectées pour secteur={category_slug}")

    if not company_links:
        logger.warning(f"[TC] Aucune fiche — fallback Overpass")
        return _scrape_overpass(keywords, "Maroc", sector, max_leads)

    # Visiter chaque fiche
    for name, href in company_links[:max_leads]:
        city = _tc_city_from_url(href)
        logger.info(f"[TC] {name} ({city})")
        fiche = _tc_scrape_fiche(href)
        leads.append({
            "company":      name,
            "phone":        fiche.get("phone"),
            "website":      fiche.get("website"),
            "address":      fiche.get("address"),
            "email":        fiche.get("email"),
            "region":       city,
            "sector":       detected_sector,
            "source":       "pages_jaunes_maroc",
            "scraping_url": href,
        })
        time.sleep(0.5)

    logger.info(f"[TC] {len(leads)} leads construits")
    return leads[:max_leads]


# SOURCE 3 — SOCIETE.COM

def _scrape_societe_com(keywords, location, sector, max_leads):
    """Scrape societe.com — registre des entreprises françaises/tunisiennes"""
    leads = []
    query = keywords or sector or "informatique"
    city  = location or "Tunis"

    try:
        # Recherche sur societe.com
        search_url = f"https://www.societe.com/cgi-bin/search?champs={requests.utils.quote(query)}&ville={requests.utils.quote(city)}"
        r = requests.get(search_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")

        # Lignes de résultats
        rows = soup.select(".company-item, .search-result, tr[class*='result'], .ent-ligne")
        if not rows:
            rows = soup.select("table tr")[1:] # skip header

        for row in rows[:max_leads]:
            name    = _text(row, ["td:first-child", ".denomination", ".nom", "strong", "b"])
            address = _text(row, [".adresse", ".address", "td:nth-child(3)"])
            siren   = _text(row, [".siren", "[class*='siren']", "td:nth-child(2)"])
            if not name or len(name) < 2: continue
            leads.append({
                "company": name.strip(),
                "phone":   None,
                "website": None,
                "address": address,
                "region":  city,
                "sector":  sector or "Services aux entreprises",
                "source":  "scraping",
                "description": f"SIREN: {siren}" if siren else None,
            })

        logger.info(f"[Societe.com] {len(leads)} leads")

    except Exception as e:
        logger.error(f"[Societe.com] Erreur: {e}")
        logger.info("[Societe.com] Fallback vers Overpass")
        leads = _scrape_overpass(keywords, location, sector, max_leads)

    return leads[:max_leads]


# SOURCE 4 — LINKEDIN (Playwright réel via linkedin_scraper)

SESSION_FILE = "linkedin_session.json"

def linkedin_session_exists() -> bool:
    import os
    return os.path.exists(SESSION_FILE)

def _scrape_linkedin_simulation(keywords, location, sector, max_leads):
    """
    Scraping LinkedIn via Playwright + linkedin_scraper.
    Nécessite une session LinkedIn créée au préalable (linkedin_session.json).
    Si pas de session fallback Overpass B2B.
    """
    import asyncio

    if not linkedin_session_exists():
        logger.warning("[LinkedIn] Pas de session LinkedIn — fallback Overpass B2B")
        return _scrape_linkedin_fallback(keywords, location, sector, max_leads)

    try:
        results = asyncio.run(_scrape_linkedin_async(keywords, location, sector, max_leads))
        if results:
            return results
    except Exception as e:
        logger.error(f"[LinkedIn] Erreur Playwright: {e}")

    logger.info("[LinkedIn] Fallback Overpass B2B")
    return _scrape_linkedin_fallback(keywords, location, sector, max_leads)


async def _scrape_linkedin_async(keywords, location, sector, max_leads):
    """Scraping LinkedIn companies via Playwright"""
    import asyncio
    from app.linkedin_scraper.core.browser import BrowserManager
    from app.linkedin_scraper.scrapers.company import CompanyScraper

    leads = []
    search_query = keywords or sector or "entreprise"
    search_url = (
        f"https://www.linkedin.com/search/results/companies/"
        f"?keywords={requests.utils.quote(search_query)}"
        f"&geoUrn=%5B%22105146636%22%5D"  # Tunisia geo ID
    )

    async with BrowserManager(headless=True) as browser:
        await browser.load_session(SESSION_FILE)
        page = browser.page

        # Aller sur la page de recherche
        await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        # Extraire les liens des entreprises
        company_links = await page.eval_on_selector_all(
            "a[href*='/company/']",
            "els => [...new Set(els.map(e => e.href))].filter(h => h.includes('/company/'))"
        )
        company_links = list(set(company_links))[:max_leads]
        logger.info(f"[LinkedIn] {len(company_links)} entreprises trouvées")

        scraper = CompanyScraper(page)
        for url in company_links:
            try:
                company = await scraper.scrape(url)
                leads.append({
                    "company":     company.name,
                    "website":     company.website,
                    "sector":      company.industry or sector or "Services aux entreprises",
                    "region":      company.headquarters or location,
                    "description": company.about_us[:200] if company.about_us else None,
                    "company_type": _map_company_size(company.company_size),
                    "source":      "scraping",
                })
                await page.wait_for_timeout(2000)  # respecter rate limit
            except Exception as e:
                logger.warning(f"[LinkedIn] Erreur scraping {url}: {e}")
                continue

    return leads


def _map_company_size(size_str):
    if not size_str: return "PME"
    s = str(size_str).lower()
    if any(x in s for x in ["10,001", "5,001", "1,001"]): return "Grande entreprise"
    if any(x in s for x in ["201", "501"]): return "PME"
    return "Startup"


def _scrape_linkedin_fallback(keywords, location, sector, max_leads):
    """Fallback : Overpass API avec tags office (B2B)"""
    logger.info("[LinkedIn] Mode fallback Overpass B2B")
    lat, lon = _geocode(location or "Tunis")
    time.sleep(1)
    query = f"""[out:json][timeout:25];
(
  node["office"](around:12000,{lat},{lon});
  way["office"](around:12000,{lat},{lon});
);
out center tags;"""
    data = _overpass_request(query)
    if not data:
        return []

    leads = []
    for el in data.get("elements", []):
        t = el.get("tags", {})
        name = t.get("name") or t.get("name:fr")
        if not name: continue
        leads.append({
            "company": name,
            "phone":   t.get("phone") or t.get("contact:phone"),
            "website": t.get("website") or t.get("contact:website"),
            "address": t.get("addr:street"),
            "region":  t.get("addr:city") or location,
            "sector":  _detect_sector("", "", t.get("office",""), ""),
            "source":  "scraping",
        })
        if len(leads) >= max_leads: break
    logger.info(f"[LinkedIn fallback] {len(leads)} entreprises B2B")
    return leads


# SOURCE 5 — IMPORT CSV (fichiers locaux scraping/data/)

# Cherche le dossier scraping/data/ depuis la racine du projet
CSV_DATA_DIRS = [
    os.path.join(os.path.dirname(__file__), "..", "..", "scraping", "data"),
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "scraping", "data"),
    r"C:\Users\Narjess\Downloads\vfinal\leadpilot\scraping\data",
    r"C:\Users\Narjess\Downloads\Scrappe",
]

# Mapping souple des colonnes CSV champs Lead
COLUMN_ALIASES = {
    "company":  ["company", "nom", "name", "raison_sociale", "entreprise", "société", "societe", "Company", "Nom"],
    "email":    ["email", "mail", "e-mail", "Email", "EMAIL", "courriel"],
    "phone":    ["phone", "tel", "telephone", "téléphone", "mobile", "Phone", "Téléphone"],
    "website":  ["website", "web", "site", "url", "Website", "Site"],
    "address":  ["address", "adresse", "Adresse", "Address"],
    "sector":   ["sector", "secteur", "activité", "activite", "Secteur", "Activité"],
    "region":   ["region", "ville", "city", "location", "Region", "Ville", "City"],
}

def _find_col(header_row, field):
    """Trouve le nom de colonne CSV qui correspond à un champ Lead"""
    for alias in COLUMN_ALIASES.get(field, []):
        if alias in header_row:
            return alias
    return None

def _scrape_from_csv(keywords, location, sector, max_leads):
    """
    Lit les fichiers CSV dans scraping/data/ et retourne des leads filtrés.
    Filtre par keywords/sector/location si fournis.
    """
    leads = []

    # Trouver le dossier data
    data_dir = None
    for d in CSV_DATA_DIRS:
        if os.path.isdir(d):
            data_dir = d
            break

    if not data_dir:
        logger.error("[CSV] Dossier scraping/data/ introuvable")
        return []

    # Lister tous les CSV du dossier
    csv_files = glob.glob(os.path.join(data_dir, "*.csv"))
    logger.info(f"[CSV] {len(csv_files)} fichiers CSV trouvés dans {data_dir}")

    for csv_path in csv_files:
        if len(leads) >= max_leads:
            break
        # Détecter l'encodage via BOM
        with open(csv_path, "rb") as _fb:
            raw_bytes = _fb.read()  # lire tout le fichier en binaire
        if raw_bytes[:3] == b"\xef\xbb\xbf":
            encoding = "utf-8-sig"
        elif raw_bytes[:2] in (b"\xff\xfe", b"\xfe\xff"):
            encoding = "utf-16"
        else:
            # Pas de BOM — essayer de décoder tout le fichier
            encoding = "latin-1"  # fallback ultime (accepte tous les bytes)
            for enc in ("utf-8", "cp1252", "latin-1"):
                try:
                    raw_bytes.decode(enc)
                    encoding = enc
                    break
                except (UnicodeDecodeError, LookupError):
                    continue

        try:
            with open(csv_path, encoding=encoding, errors="replace") as f:
                reader = csv.DictReader(f)
                header = reader.fieldnames or []

                # Mapper les colonnes
                col = {field: _find_col(header, field) for field in COLUMN_ALIASES}

                for row in reader:
                    if len(leads) >= max_leads:
                        break

                    company = row.get(col["company"]) if col["company"] else None
                    if not company or str(company).strip() in ("", "nan", "None"):
                        continue
                    company = str(company).strip()

                    row_sector  = (row.get(col["sector"])  or "").strip() if col["sector"]  else ""
                    row_region  = (row.get(col["region"])  or "").strip() if col["region"]  else ""

                    # Filtre optionnel par keywords (cherche dans nom + secteur)
                    if keywords:
                        kw_lower = keywords.lower()
                        if (kw_lower not in company.lower()
                                and kw_lower not in row_sector.lower()):
                            continue

                    # Filtre optionnel par sector
                    if sector and sector.lower() not in row_sector.lower():
                        continue

                    # Filtre optionnel par location
                    if location and location.lower() not in row_region.lower():
                        continue

                    leads.append({
                        "company": company,
                        "email":   (row.get(col["email"])   or None) if col["email"]   else None,
                        "phone":   (row.get(col["phone"])   or None) if col["phone"]   else None,
                        "website": (row.get(col["website"]) or None) if col["website"] else None,
                        "address": (row.get(col["address"]) or None) if col["address"] else None,
                        "sector":  row_sector or sector or "Services aux entreprises",
                        "region":  row_region or location or "Tunisie",
                        "source":  "scraping",
                    })

        except Exception as e:
            logger.warning(f"[CSV] Erreur lecture {csv_path}: {e}")
            continue

    logger.info(f"[CSV] {len(leads)} leads extraits des fichiers CSV")
    return leads[:max_leads]


# UTILITAIRES

def _text(tag, selectors):
    for sel in selectors:
        try:
            el = tag.select_one(sel)
            if el and el.get_text(strip=True):
                return el.get_text(strip=True)
        except Exception:
            pass
    return None

def _attr(tag, selector, attr):
    try:
        el = tag.select_one(selector)
        if el:
            val = el.get(attr, "")
            if val and val.startswith("http"):
                return val
    except Exception:
        pass
    return None

def _clean_phone(phone):
    if not phone: return None
    digits = re.sub(r"[^\d+]", "", str(phone))
    return digits if len(digits) >= 8 else None


# SOURCE — FOURSQUARE PLACES API v3 (monde entier)

import json as _json

FS_API_KEY = os.environ.get("FOURSQUARE_API_KEY", "")
FS_BASE    = "https://api.foursquare.com/v3/places"

# Mapping secteur catégorie Foursquare
FS_CATEGORY_MAP = {
    "restaurant":    "13065",   # Food
    "cafe":          "13032",
    "hotel":         "19014",   # Hotel
    "pharmacie":     "15014",   # Pharmacy
    "banque":        "11010",   # Bank
    "supermarche":   "17069",   # Supermarket
    "garage":        "11025",   # Auto repair
    "informatique":  "11102",   # Tech company
    "medecin":       "15039",   # Doctor
    "dentiste":      "15034",
    "gym":           "18008",   # Gym
    "ecole":         "12058",   # School
    "universite":    "12060",
    "hopital":       "15011",   # Hospital
    "librairie":     "17024",
}


def _scrape_foursquare(keywords, location, sector, max_leads):
    """
    Foursquare Places API v3 — 1000 appels/jour gratuits.
    Couverture mondiale : Algérie, Égypte, Tunisie, Maroc, France...
    """
    if not FS_API_KEY:
        logger.error("[FS] FOURSQUARE_API_KEY manquant dans .env")
        return []

    leads      = []
    seen_ids   = set()
    seen_names = set()

    kw_lower = (keywords or "").lower().strip()
    detected_sector = sector or keywords or "Services"

    # Résoudre la catégorie
    category_id = None
    for key, cid in FS_CATEGORY_MAP.items():
        if key in kw_lower:
            category_id = cid
            break

    headers = {
        "Authorization": FS_API_KEY,
        "Accept":        "application/json",
    }

    # Foursquare limite à 50 par appel paginer avec cursor
    cursor = None
    calls  = 0
    max_calls = (max_leads // 50) + 2

    logger.info(f"[FS] location={location} | kw={keywords} | max={max_leads}")

    while len(leads) < max_leads and calls < max_calls:
        params = {
            "query":   keywords or sector or "entreprise",
            "near":    location,
            "limit":   50,
            "fields":  "name,location,tel,website,categories,description,hours",
        }
        if category_id:
            params["categories"] = category_id
        if cursor:
            params["cursor"] = cursor

        try:
            r = requests.get(
                f"{FS_BASE}/search",
                headers=headers,
                params=params,
                timeout=15,
            )
            calls += 1

            if r.status_code == 401:
                logger.error("[FS] Clé API invalide ou expirée")
                break
            if r.status_code == 429:
                logger.warning("[FS] Limite atteinte — pause 60s")
                time.sleep(60)
                continue
            if r.status_code != 200:
                logger.warning(f"[FS] Status {r.status_code}")
                break

            data    = r.json()
            results = data.get("results", [])
            cursor  = data.get("context", {}).get("geo_bounds", {})
            # Foursquare v3 n'a pas de curseur paginé sur /search — on s'arrête après 1 appel par near
            cursor = None

            if not results:
                logger.info("[FS] Aucun résultat")
                break

            for place in results:
                if len(leads) >= max_leads:
                    break

                fsq_id = place.get("fsq_id", "")
                if fsq_id in seen_ids:
                    continue
                seen_ids.add(fsq_id)

                name = place.get("name", "").strip()
                if not name or len(name) < 2:
                    continue
                name_key = name.lower()
                if name_key in seen_names:
                    continue
                seen_names.add(name_key)

                loc     = place.get("location", {})
                address = ", ".join(filter(None, [
                    loc.get("address"),
                    loc.get("locality"),
                    loc.get("region"),
                    loc.get("country"),
                ]))
                region  = loc.get("locality") or loc.get("region") or location

                phone   = _clean_phone(place.get("tel"))
                website = place.get("website")

                cats    = place.get("categories", [])
                cat_name = cats[0].get("name", "") if cats else detected_sector

                desc = place.get("description", "") or ""

                leads.append({
                    "company":     name,
                    "phone":       phone,
                    "website":     website,
                    "address":     address,
                    "region":      region,
                    "sector":      cat_name or detected_sector,
                    "source":      "foursquare",
                    "description": desc[:300] if desc else None,
                    "email":       None,
                })

            logger.info(f"[FS] Appel {calls} : {len(results)} résultats | Total : {len(leads)}")
            time.sleep(0.5)

        except Exception as e:
            logger.error(f"[FS] Erreur appel {calls} : {e}")
            break

    logger.info(f"[FS] Total collecté : {len(leads)} leads")
    return leads


# SOURCE — KOMPASS.COM (annuaire B2B 70+ pays)

KP_BASE = "https://fr.kompass.com"

# Codes pays Kompass (ISO 2 lettres)
KP_COUNTRY_CODES = {
    "algerie":       "DZ",
    "algérie":       "DZ",
    "tunisie":       "TN",
    "maroc":         "MA",
    "france":        "FR",
    "belgique":      "BE",
    "espagne":       "ES",
    "italie":        "IT",
    "allemagne":     "DE",
    "egypte":        "EG",
    "égypte":        "EG",
    "senegal":       "SN",
    "sénégal":       "SN",
    "emirats":       "AE",
    "arabie saoudite":"SA",
    "qatar":         "QA",
    "nigeria":       "NG",
    "kenya":         "KE",
    "afrique du sud":"ZA",
}

# Codes activité Kompass (NACE simplifié)
KP_ACTIVITY_MAP = {
    "informatique":    "IT",
    "it":              "IT",
    "logiciel":        "IT",
    "construction":    "F",
    "btp":             "F",
    "transport":       "H",
    "logistique":      "H",
    "agroalimentaire": "C10",
    "agriculture":     "A",
    "industrie":       "C",
    "chimie":          "C20",
    "textile":         "C13",
    "sante":           "Q",
    "santé":           "Q",
    "energie":         "D",
    "énergie":         "D",
    "finance":         "K",
    "commerce":        "G",
    "services":        "N",
    "education":       "P",
}


def _scrape_kompass(keywords, location, sector, max_leads):
    """
    Scrape fr.kompass.com — annuaire B2B 70+ pays.
    URL : /searchCompanies/?text={kw}&country={CC}&page={n}
    ~20 résultats par page, fiche détail pour chaque entreprise.
    """
    leads   = []
    session = requests.Session()

    kw_lower  = (keywords or "").lower().strip()
    loc_lower = (location or "").lower().strip()
    sec_lower = (sector   or "").lower().strip()

    # Résoudre code pays
    country_code = "TN"  # défaut Tunisie
    for key, code in KP_COUNTRY_CODES.items():
        if key in loc_lower:
            country_code = code
            break

    detected_sector = sector or keywords or "Services aux entreprises"
    search_text     = keywords or sector or "entreprise"

    seen_urls  = set()
    seen_names = set()
    pages_needed = (max_leads // 20) + 2

    logger.info(f"[KP] pays={country_code} | kw={search_text} | pages={pages_needed}")

    for page_num in range(1, pages_needed + 1):
        if len(leads) >= max_leads:
            break

        list_url = (
            f"{KP_BASE}/searchCompanies/"
            f"?text={requests.utils.quote(search_text)}"
            f"&country={country_code}"
            f"&page={page_num}"
        )

        logger.info(f"[KP] Page {page_num} : {list_url}")

        try:
            r = session.get(list_url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                logger.warning(f"[KP] {r.status_code} sur page {page_num}")
                time.sleep(3)
                continue

            soup = BeautifulSoup(r.text, "html.parser")

            # Liens vers les fiches entreprises
            # Kompass : /c/{slug}/{id}/
            company_links = soup.find_all(
                "a", href=re.compile(r"^/c/[^/]+/[a-zA-Z]{2}\d+/")
            )

            if not company_links:
                # Fallback : chercher liens avec /c/ et un ID numérique
                company_links = soup.find_all(
                    "a", href=re.compile(r"/c/[^/]+/[A-Z]{2}\d+")
                )

            if not company_links:
                logger.info(f"[KP] Aucune fiche trouvée page {page_num}, arrêt.")
                break

            for link in company_links:
                if len(leads) >= max_leads:
                    break

                href = link.get("href", "")
                if not href.startswith("http"):
                    href = KP_BASE + href
                if href in seen_urls:
                    continue
                seen_urls.add(href)

                name = link.get_text(strip=True)
                if not name or len(name) < 2:
                    parent = link.find_parent(["div", "li", "article"])
                    if parent:
                        for tag in parent.find_all(["h2", "h3", "strong"]):
                            t = tag.get_text(strip=True)
                            if t and len(t) > 2:
                                name = t
                                break

                if not name or len(name) < 2:
                    continue
                name_key = name.lower().strip()
                if name_key in seen_names:
                    continue
                seen_names.add(name_key)

                lead = _scrape_kompass_detail(session, href, name, detected_sector, location or country_code)
                if lead:
                    leads.append(lead)
                    logger.info(f"[KP] Lead {len(leads)} : {lead.get('company')}")

            time.sleep(1.5)

        except Exception as e:
            logger.error(f"[KP] Erreur page {page_num} : {e}")
            time.sleep(3)
            continue

    logger.info(f"[KP] Total collecté : {len(leads)} leads")
    return leads


def _scrape_kompass_detail(session, url, fallback_name, sector, country):
    """Scraper la fiche détail d'une entreprise Kompass."""
    try:
        r = session.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None

        soup = BeautifulSoup(r.text, "html.parser")

        # Nom entreprise
        company = None
        for sel in ["h1.company-name", "h1", "[itemprop='name']", ".companyName"]:
            el = soup.select_one(sel)
            if el:
                t = el.get_text(strip=True)
                if t and len(t) > 1:
                    company = t
                    break
        company = company or fallback_name

        # Téléphone
        phone = None
        tel_el = soup.find("a", href=re.compile(r"^tel:"))
        if tel_el:
            phone = _clean_phone(tel_el["href"].replace("tel:", ""))
        if not phone:
            for el in soup.find_all(string=re.compile(r"^\+?\d[\d\s\-\.\(\)]{7,}$")):
                p = _clean_phone(el.strip())
                if p:
                    phone = p
                    break

        # Site web
        website = None
        for el in soup.find_all("a", href=True):
            href = el.get("href", "")
            text = el.get_text(strip=True).lower()
            if (href.startswith("http") and "kompass" not in href
                    and any(w in text for w in ["site", "web", "www", "visiter"])):
                website = href
                break
        if not website:
            web_el = soup.select_one("[itemprop='url']")
            if web_el:
                website = web_el.get("href") or web_el.get_text(strip=True)

        # Adresse
        address = None
        region  = None
        addr_el = soup.find(attrs={"itemprop": "address"})
        if addr_el:
            address = addr_el.get_text(separator=" ", strip=True)
        if not address:
            for sel in [".address", ".localisation", "[class*='addr']"]:
                el = soup.select_one(sel)
                if el:
                    address = el.get_text(separator=" ", strip=True)
                    break

        if address:
            parts = [p.strip() for p in address.split(",") if p.strip()]
            region = parts[-1] if parts else country
        else:
            region = country

        # Description (activité principale)
        description = None
        for sel in [".companyDescription", ".activity", "[itemprop='description']",
                    ".company-description", "p.description"]:
            el = soup.select_one(sel)
            if el:
                description = el.get_text(strip=True)[:500]
                break

        # Effectif (bonus)
        employees = None
        for el in soup.find_all(string=re.compile(r"\d+\s*(employés|salariés|employees)", re.I)):
            employees = el.strip()
            break

        if not company or len(company) < 2:
            return None

        return {
            "company":     company,
            "phone":       phone,
            "website":     website,
            "address":     address,
            "region":      region,
            "sector":      sector,
            "description": (description or "") + (f" | Effectif : {employees}" if employees else ""),
            "source":      "kompass",
            "email":       None,
        }

    except Exception as e:
        logger.error(f"[KP] Erreur fiche {url} : {e}")
        return None


# SOURCE — EUROPAGES.FR (annuaire B2B multi-pays)

EP_BASE = "https://www.europages.fr"

# Mapping pays (location) code pays Europages
EP_COUNTRY_MAP = {
    "tunisie":       "tunisie",
    "maroc":         "maroc",
    "algerie":       "algerie",
    "algérie":       "algerie",
    "france":        "france",
    "allemagne":     "allemagne",
    "belgique":      "belgique",
    "espagne":       "espagne",
    "italie":        "italie",
    "egypte":        "egypte",
    "égypte":        "egypte",
    "senegal":       "senegal",
    "sénégal":       "senegal",
    "cote d'ivoire": "cote-d-ivoire",
    "dubai":         "emirats-arabes-unis",
    "emirats":       "emirats-arabes-unis",
}

# Mapping secteur slug Europages
EP_SECTOR_MAP = {
    "informatique":      "informatique-et-telecom",
    "it":                "informatique-et-telecom",
    "telecom":           "informatique-et-telecom",
    "btp":               "construction-et-btp",
    "construction":      "construction-et-btp",
    "agroalimentaire":   "agroalimentaire",
    "agriculture":       "agriculture-sylviculture-et-peche",
    "transport":         "transport-et-logistique",
    "logistique":        "transport-et-logistique",
    "industrie":         "industrie",
    "chimie":            "chimie-et-materiaux",
    "textile":           "textile-et-habillement",
    "sante":             "sante-et-cosmetique",
    "santé":             "sante-et-cosmetique",
    "energie":           "energie-et-environnement",
    "énergie":           "energie-et-environnement",
    "finance":           "finance-et-assurance",
    "services":          "services-aux-entreprises",
    "commerce":          "commerce-de-gros",
    "import export":     "import-export",
}


def _scrape_europages(keywords, location, sector, max_leads):
    """
    Scrape europages.fr — annuaire B2B couvrant 70+ pays.
    URL pattern : /entreprises/{secteur-slug}/{pays}.html
    Pagination   : /entreprises/{secteur-slug}/{pays}/pg-{N}.html
    ~20 résultats par page.
    """
    leads = []
    session = requests.Session()

    kw_lower  = (keywords or "").lower().strip()
    sec_lower = (sector   or "").lower().strip()
    loc_lower = (location or "").lower().strip()

    # Résoudre slug secteur
    sector_slug = "services-aux-entreprises"
    for key, slug in EP_SECTOR_MAP.items():
        if key in kw_lower or key in sec_lower:
            sector_slug = slug
            break

    # Résoudre slug pays
    country_slug = ""
    for key, slug in EP_COUNTRY_MAP.items():
        if key in loc_lower:
            country_slug = slug
            break

    detected_sector = sector or sector_slug.replace("-", " ").title()
    detected_country = location or country_slug or "International"

    seen_urls  = set()
    seen_names = set()
    pages_needed = (max_leads // 20) + 2

    logger.info(f"[EP] secteur={sector_slug} | pays={country_slug} | pages={pages_needed}")

    for page_num in range(1, pages_needed + 1):
        if len(leads) >= max_leads:
            break

        # Construire l'URL de liste
        if country_slug:
            if page_num == 1:
                list_url = f"{EP_BASE}/entreprises/{sector_slug}/{country_slug}.html"
            else:
                list_url = f"{EP_BASE}/entreprises/{sector_slug}/{country_slug}/pg-{page_num}.html"
        else:
            if page_num == 1:
                list_url = f"{EP_BASE}/entreprises/{sector_slug}.html"
            else:
                list_url = f"{EP_BASE}/entreprises/{sector_slug}/pg-{page_num}.html"

        logger.info(f"[EP] Page {page_num}: {list_url}")

        try:
            r = session.get(list_url, headers=HEADERS, timeout=15)
            if r.status_code == 404:
                logger.warning(f"[EP] 404 sur {list_url}")
                break
            if r.status_code != 200:
                logger.warning(f"[EP] {r.status_code} sur {list_url}")
                time.sleep(2)
                continue

            soup = BeautifulSoup(r.text, "html.parser")

            # Chercher les fiches entreprises
            # Europages utilise des liens /annuaire/{slug}-EPXXXXXX.html
            company_cards = soup.find_all("a", href=re.compile(r"/annuaire/.*-EP\d+\.html"))

            if not company_cards:
                # Fallback : chercher tout lien /annuaire/
                company_cards = soup.find_all("a", href=re.compile(r"/annuaire/[^\"]+\.html"))

            if not company_cards:
                logger.info(f"[EP] Aucune fiche trouvée page {page_num}, arrêt.")
                break

            for card in company_cards:
                if len(leads) >= max_leads:
                    break

                href = card.get("href", "")
                if not href.startswith("http"):
                    href = EP_BASE + href
                if href in seen_urls:
                    continue
                seen_urls.add(href)

                # Nom de l'entreprise depuis le texte du lien ou balise titre
                name = card.get_text(strip=True)
                if not name or len(name) < 2:
                    parent = card.find_parent(["div", "li", "article"])
                    if parent:
                        for tag in parent.find_all(["h2", "h3", "h4", "strong"]):
                            t = tag.get_text(strip=True)
                            if t and len(t) > 2:
                                name = t
                                break

                if not name or len(name) < 2:
                    continue
                name_key = name.lower().strip()
                if name_key in seen_names:
                    continue
                seen_names.add(name_key)

                # Scraper la fiche individuelle
                lead = _scrape_europages_detail(session, href, name, detected_sector, detected_country)
                if lead:
                    leads.append(lead)
                    logger.info(f"[EP] Lead {len(leads)}: {lead.get('company')}")

            time.sleep(1.5)

        except Exception as e:
            logger.error(f"[EP] Erreur page {page_num}: {e}")
            time.sleep(3)
            continue

    logger.info(f"[EP] Total collecté : {len(leads)} leads")
    return leads


def _scrape_europages_detail(session, url, fallback_name, sector, country):
    """Scraper la fiche détail d'une entreprise Europages."""
    try:
        r = session.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None

        soup = BeautifulSoup(r.text, "html.parser")

        # Nom entreprise
        company = None
        for sel in ["h1", ".company-name", "[itemprop='name']"]:
            el = soup.select_one(sel)
            if el:
                company = el.get_text(strip=True)
                break
        company = company or fallback_name

        # Téléphone
        phone = None
        for el in soup.find_all(["a", "span"], href=re.compile(r"^tel:"), string=True):
            phone = _clean_phone(el.get_text(strip=True))
            if phone:
                break
        if not phone:
            tel_el = soup.find("a", href=re.compile(r"^tel:"))
            if tel_el:
                phone = _clean_phone(tel_el["href"].replace("tel:", ""))

        # Site web
        website = None
        for el in soup.find_all("a", href=True):
            href = el.get("href", "")
            if href.startswith("http") and "europages" not in href and len(href) > 10:
                text = el.get_text(strip=True).lower()
                if any(w in text for w in ["site", "web", "www", "visiter"]):
                    website = href
                    break

        # Adresse / région
        address = None
        region  = None
        addr_el = soup.find(["span", "div", "p"], attrs={"itemprop": "address"})
        if addr_el:
            address = addr_el.get_text(separator=" ", strip=True)
        if not address:
            addr_el = soup.select_one(".address, .localisation, [class*='address']")
            if addr_el:
                address = addr_el.get_text(separator=" ", strip=True)

        # Région = ville extraite de l'adresse ou du pays
        if address:
            parts = [p.strip() for p in address.split(",") if p.strip()]
            region = parts[-1] if parts else country
        else:
            region = country

        # Description
        description = None
        for sel in [".description", ".company-description", "[itemprop='description']", "p.intro"]:
            el = soup.select_one(sel)
            if el:
                description = el.get_text(strip=True)[:500]
                break

        if not company or len(company) < 2:
            return None

        return {
            "company":     company,
            "phone":       phone,
            "website":     website,
            "address":     address,
            "region":      region,
            "sector":      sector,
            "source":      "europages",
            "description": description,
            "email":       None,
        }

    except Exception as e:
        logger.error(f"[EP] Erreur fiche {url}: {e}")
        return None
