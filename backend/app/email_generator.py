import os
import sys
import json
import time
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import pandas as pd

load_dotenv()

DATABASE_URL       = os.getenv("DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql+psycopg2://").replace("postgresql://", "postgresql+psycopg2://")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
GROQ_API_KEY       = os.getenv("GROQ_API_KEY")
BREVO_API_KEY      = os.getenv("BREVO_API_KEY")
FROM_EMAIL         = os.getenv("FROM_EMAIL", "contact@leadNova .tn")
FROM_NAME          = os.getenv("FROM_NAME", "LeadNova ")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('email_generator.log', encoding='utf-8')
    ]
)
logger = logging.getLogger("leadNova .email_generator")

# MODÈLES OPENROUTER 
OPENROUTER_MODELS = [
    "openai/gpt-oss-120b:free",
    "openai/gpt-oss-20b:free",
    "z-ai/glm-4.5-air:free",
]

# MODÈLES GROQ 
GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "gemma2-9b-it",
]

# PROMPTS PAR SEGMENT
SEGMENT_PROMPTS = {
    "Chaud":  {
        "subject_hint": "proposition de valeur directe et urgente",
        "tone": "direct, confiant, orienté ROI",
        "cta": "Planifier un appel de 15 minutes cette semaine",
        "context": "Ce prospect est chaud : profil complet, joignable, score élevé. Email de prospection direct.",
    },
    "Prêts à Acheter": {
        "subject_hint": "contenu utile ou ressource gratuite",
        "tone": "éducatif, empathique, sans pression",
        "cta": "Télécharger notre guide gratuit ou répondre à cet email",
        "context": "Ce prospect est prêt à acheter : l'intéresser avec de la valeur avant de vendre. Email nurturing.",
    },
    "Froid": {
        "subject_hint": "question ouverte ou statistique surprenante du secteur",
        "tone": "curieux, léger, non commercial",
        "cta": "Juste répondre OUI ou NON à cette question",
        "context": "Ce prospect est froid : objectif = obtenir une réponse, pas vendre. Email très court.",
    },
    "À Risque": {
        "subject_hint": "offre de diagnostic gratuit ou audit rapide",
        "tone": "utile, sans engagement, rassurant",
        "cta": "Audit gratuit de 30 minutes sans engagement",
        "context": "Ce prospect a un profil incomplet. Proposer quelque chose de gratuit pour le qualifier.",
    },
}

# PROMPTS PAR SECTEUR — couvre tous les secteurs de la base
# Chaque secteur contient un contexte général + une adaptation par segment CRM
SECTOR_PROMPTS = {
    "Informatique & Tech": {
        "angle": "automatisation des processus de vente et gain de temps développeur",
        "pain_point": "trop de temps perdu sur la prospection manuelle, pipeline mal qualifié",
        "value_prop": "LeadNova  identifie et contacte automatiquement vos meilleurs prospects B2B",
        "vocabulary": "utilise des termes tech : pipeline, automation, API, ROI, conversion rate",
        "tone_extra": "parle tech-to-tech, sois direct et concis, évite le jargon commercial classique",
        "segment_context": {
            "Chaud":           "Ce prospect tech est prêt à adopter un nouvel outil — parle ROI immédiat et gain de temps mesurable.",
            "Prêts à Acheter": "Ce prospect tech veut se documenter avant de décider — propose une comparaison ou un benchmark technique.",
            "Froid":           "Ce prospect tech est prudent — pose une question précise sur son process de prospection actuel.",
            "À Risque":        "Ce prospect tech manque de données — propose un audit gratuit de son pipeline commercial.",
        },
    },
    "Marketing & Communication": {
        "angle": "acquisition de nouveaux clients et optimisation des campagnes B2B",
        "pain_point": "difficulté à trouver des prospects B2B qualifiés pour leurs propres clients",
        "value_prop": "LeadNova  génère des leads B2B qualifiés avec scoring IA pour vos campagnes",
        "vocabulary": "utilise : leads qualifiés, taux de conversion, nurturing, funnel, campagne ciblée",
        "tone_extra": "montre que tu comprends le métier d'agence, parle résultats mesurables",
        "segment_context": {
            "Chaud":           "Cette agence cherche activement à améliorer ses résultats — propose un appel pour montrer comment LeadNova  booste leurs campagnes.",
            "Prêts à Acheter": "Cette agence s'informe — partage des résultats concrets de campagnes B2B automatisées.",
            "Froid":           "Cette agence n'a pas encore entendu parler de nous — pose une question sur leur principal défi d'acquisition B2B.",
            "À Risque":        "Cette agence a un profil incomplet — propose un diagnostic gratuit de leur stratégie de prospection.",
        },
    },
    "Finance & Comptabilité": {
        "angle": "réduction du temps de prospection et amélioration du portefeuille clients",
        "pain_point": "développement commercial chronophage qui prend du temps sur le cœur de métier",
        "value_prop": "LeadNova  automatise l'acquisition de nouveaux clients PME pour les cabinets",
        "vocabulary": "utilise : portefeuille clients, prospection ciblée, cabinet, gestion de la relation client",
        "tone_extra": "sois formel et professionnel, mets en avant la fiabilité et les données chiffrées",
        "segment_context": {
            "Chaud":           "Ce cabinet cherche à développer son portefeuille — propose un appel centré sur le ROI et les données chiffrées.",
            "Prêts à Acheter": "Ce cabinet s'informe sur les solutions de prospection — envoie des chiffres concrets sur le gain de temps.",
            "Froid":           "Ce cabinet n'est pas encore convaincu — pose une question sur combien de temps il consacre à la prospection par semaine.",
            "À Risque":        "Ce cabinet a peu d'informations disponibles — propose un audit gratuit de leur approche commerciale.",
        },
    },
    "Services aux entreprises": {
        "angle": "développement commercial B2B et fidélisation clients",
        "pain_point": "manque de visibilité sur les prospects les plus susceptibles de convertir",
        "value_prop": "LeadNova  priorise vos prospects B2B selon leur probabilité d'achat grâce à l'IA",
        "vocabulary": "utilise : prospects qualifiés, développement commercial, relation client, B2B",
        "tone_extra": "ton consultif, montre une compréhension des enjeux business de leur secteur",
        "segment_context": {
            "Chaud":           "Ce prestataire B2B est en phase active de développement — propose un appel centré sur l'acquisition rapide de nouveaux clients.",
            "Prêts à Acheter": "Ce prestataire réfléchit à optimiser sa prospection — propose un guide sur la qualification des leads B2B.",
            "Froid":           "Ce prestataire n'est pas encore en mode prospection — demande-lui quel est son principal canal d'acquisition aujourd'hui.",
            "À Risque":        "Ce prestataire manque de visibilité — propose un diagnostic gratuit de son positionnement commercial B2B.",
        },
    },
    "Immobilier": {
        "angle": "ciblage d'entreprises cherchant des locaux professionnels ou en expansion",
        "pain_point": "difficulté à identifier les entreprises en croissance ayant des besoins immobiliers",
        "value_prop": "LeadNova  identifie les PME et startups en phase de croissance = futurs clients",
        "vocabulary": "utilise : locaux professionnels, entreprises en croissance, portefeuille, transaction",
        "tone_extra": "sois précis sur les opportunités business, évite le ton promotionnel immobilier résidentiel",
        "segment_context": {
            "Chaud":           "Cette agence immobilière cherche activement de nouveaux clients professionnels — propose un appel pour montrer comment cibler les entreprises en croissance.",
            "Prêts à Acheter": "Cette agence s'intéresse aux solutions B2B — partage des exemples de PME en croissance identifiées par LeadNova .",
            "Froid":           "Cette agence n'a pas encore exploré la cible B2B — pose une question sur la part des entreprises dans leur portefeuille actuel.",
            "À Risque":        "Cette agence manque de données — propose un audit gratuit de leur portefeuille de prospects professionnels.",
        },
    },
    "Construction & BTP": {
        "angle": "acquisition de contrats B2B et développement du carnet de commandes",
        "pain_point": "dépendance aux appels d'offres publics et difficulté à prospecter le privé",
        "value_prop": "LeadNova  identifie les entreprises ayant des projets de construction ou rénovation",
        "vocabulary": "utilise : carnet de commandes, maître d'ouvrage, appel d'offres, contrat",
        "tone_extra": "sois concret et orienté résultats, parle chiffre d'affaires et contrats",
        "segment_context": {
            "Chaud":           "Cette entreprise BTP cherche à diversifier ses contrats privés — propose un appel centré sur les nouveaux donneurs d'ordre identifiables.",
            "Prêts à Acheter": "Cette entreprise BTP réfléchit à réduire sa dépendance aux appels d'offres — partage des exemples de marchés privés détectés.",
            "Froid":           "Cette entreprise BTP est encore hésitante — demande-lui quelle part de son CA vient du privé versus le public.",
            "À Risque":        "Cette entreprise BTP a un profil flou — propose un audit gratuit de son positionnement commercial privé.",
        },
    },
    "Transport & Logistique": {
        "angle": "développement de nouveaux partenariats B2B et contrats transport",
        "pain_point": "recherche de nouveaux chargeurs et partenaires commerciaux B2B",
        "value_prop": "LeadNova  identifie les entreprises ayant des besoins logistiques récurrents",
        "vocabulary": "utilise : chargeurs, fret, partenariat, contrat cadre, flux logistique",
        "tone_extra": "sois efficace et orienté service, mets en avant la fiabilité",
        "segment_context": {
            "Chaud":           "Ce transporteur cherche à développer son réseau de chargeurs — propose un appel pour identifier ensemble les prospects les plus actifs.",
            "Prêts à Acheter": "Ce transporteur s'informe sur les solutions B2B — partage des données sur les entreprises avec des flux logistiques importants.",
            "Froid":           "Ce transporteur n'est pas encore convaincu — demande-lui combien de nouveaux chargeurs il cherche à recruter cette année.",
            "À Risque":        "Ce transporteur manque de visibilité commerciale — propose un audit gratuit de son réseau de prospects chargeurs.",
        },
    },
    "Education & Formation": {
        "angle": "partenariats B2B avec des entreprises pour la formation continue",
        "pain_point": "difficulté à trouver des entreprises cherchant à former leurs équipes",
        "value_prop": "LeadNova  cible les PME et grandes entreprises avec des budgets formation",
        "vocabulary": "utilise : formation professionnelle, plan de développement des compétences, certification",
        "tone_extra": "sois institutionnel et rassurant, met en avant la pédagogie et les certifications",
        "segment_context": {
            "Chaud":           "Cet organisme de formation cherche à signer de nouveaux contrats B2B — propose un appel pour identifier les entreprises avec des budgets formation disponibles.",
            "Prêts à Acheter": "Cet organisme réfléchit à développer sa clientèle B2B — partage des informations sur les entreprises ciblant la montée en compétences.",
            "Froid":           "Cet organisme n'a pas encore structuré son approche B2B — pose une question sur ses principaux canaux d'acquisition actuels.",
            "À Risque":        "Cet organisme a peu de données — propose un audit gratuit de son positionnement auprès des entreprises.",
        },
    },
    "Santé": {
        "angle": "développement de partenariats B2B et acquisition de nouveaux patients ou clients professionnels",
        "pain_point": "développement de la clientèle chronophage qui empiète sur le temps médical",
        "value_prop": "LeadNova  identifie les cliniques, cabinets et structures de santé cherchant à développer leur activité",
        "vocabulary": "utilise : réseau médical, partenariat clinique, patientèle, spécialité, prise en charge",
        "tone_extra": "sois formel et discret, utilise un vocabulaire médical et professionnel, mets en avant la confiance",
        "segment_context": {
            "Chaud":           "Cette structure de santé cherche à développer son activité — propose un appel court centré sur l'acquisition de nouveaux partenariats médicaux.",
            "Prêts à Acheter": "Cette structure s'informe sur les solutions de développement — partage des cas concrets d'établissements ayant élargi leur réseau.",
            "Froid":           "Cette structure n'est pas encore en mode développement actif — pose une question sur ses principaux canaux d'orientation de patients.",
            "À Risque":        "Cette structure a un profil incomplet — propose un diagnostic gratuit de son positionnement dans le réseau de santé local.",
        },
    },
    "Juridique": {
        "angle": "développement du portefeuille clients et acquisition de nouveaux dossiers",
        "pain_point": "manque de visibilité sur les entreprises ayant des besoins juridiques actifs",
        "value_prop": "LeadNova  identifie les PME et startups ayant des besoins en conseil juridique ou contentieux",
        "vocabulary": "utilise : portefeuille clients, dossiers, conseil juridique, contentieux, conformité",
        "tone_extra": "sois très formel et professionnel, évite tout ton commercial agressif, privilégie la discrétion",
        "segment_context": {
            "Chaud":           "Ce cabinet juridique cherche à développer son portefeuille clients — propose un appel pour montrer comment LeadNova  identifie des entreprises avec des besoins juridiques actifs.",
            "Prêts à Acheter": "Ce cabinet s'interroge sur sa stratégie de développement — partage des exemples de PME cherchant un accompagnement juridique.",
            "Froid":           "Ce cabinet n'a pas encore structuré sa prospection — demande-lui quel type de dossiers il souhaite développer prioritairement.",
            "À Risque":        "Ce cabinet a peu de données disponibles — propose un audit discret et gratuit de son positionnement commercial.",
        },
    },
    "Sécurité": {
        "angle": "acquisition de contrats de sécurité B2B avec des entreprises et sites industriels",
        "pain_point": "difficulté à prospecter de nouveaux sites industriels et commerciaux privés",
        "value_prop": "LeadNova  identifie les entreprises et sites industriels cherchant des prestataires de sécurité",
        "vocabulary": "utilise : gardiennage, télésurveillance, site industriel, contrat de sécurité, ronde",
        "tone_extra": "sois direct et orienté contrat, mets en avant la fiabilité, la réactivité et l'expérience terrain",
        "segment_context": {
            "Chaud":           "Cette entreprise de sécurité cherche à développer son portefeuille de sites — propose un appel pour identifier ensemble les cibles prioritaires.",
            "Prêts à Acheter": "Cette entreprise de sécurité réfléchit à sa stratégie commerciale — partage des données sur les sites industriels sans prestataire identifié.",
            "Froid":           "Cette entreprise de sécurité n'est pas encore en prospection active — demande-lui combien de nouveaux contrats elle cherche à signer cette année.",
            "À Risque":        "Cette entreprise de sécurité a un profil flou — propose un audit gratuit de son positionnement commercial sur sa zone géographique.",
        },
    },
    "Management & Conseil": {
        "angle": "acquisition de nouveaux mandats et développement du portefeuille clients stratégiques",
        "pain_point": "difficulté à identifier les entreprises ayant un besoin actif de conseil ou d'accompagnement",
        "value_prop": "LeadNova  détecte les PME et startups en phase de transformation cherchant un accompagnement stratégique",
        "vocabulary": "utilise : mandat, accompagnement stratégique, transformation, pilotage, gouvernance, performance",
        "tone_extra": "sois consultatif et élégant, parle en termes de valeur ajoutée, de performance et d'impact",
        "segment_context": {
            "Chaud":           "Ce cabinet de conseil cherche à accroître son portefeuille — propose un appel centré sur les entreprises en phase de transformation identifiables.",
            "Prêts à Acheter": "Ce cabinet réfléchit à développer sa prospection — partage des exemples de mandats générés via la détection de signaux d'affaires.",
            "Froid":           "Ce cabinet n'a pas encore structuré son approche — demande-lui quel type de missions il cherche à développer en priorité.",
            "À Risque":        "Ce cabinet a peu de données — propose un audit gratuit de son positionnement et de son attractivité auprès des dirigeants.",
        },
    },
    "Architecture & Urbanisme": {
        "angle": "acquisition de nouveaux projets et développement du réseau maîtres d'ouvrage",
        "pain_point": "dépendance aux appels d'offres publics et difficulté à prospecter les maîtres d'ouvrage privés",
        "value_prop": "LeadNova  identifie les promoteurs et entreprises ayant des projets de construction ou rénovation",
        "vocabulary": "utilise : maître d'ouvrage, programme, CCTP, conception, réalisation, permis de construire",
        "tone_extra": "sois précis et technique, mets en avant la qualité des réalisations et la démarche créative",
        "segment_context": {
            "Chaud":           "Ce cabinet d'architecture cherche à décrocher de nouveaux projets privés — propose un appel pour identifier ensemble les maîtres d'ouvrage actifs.",
            "Prêts à Acheter": "Ce cabinet réfléchit à réduire sa dépendance aux appels d'offres — partage des exemples de projets privés détectés en amont.",
            "Froid":           "Ce cabinet n'a pas encore exploré la prospection privée — demande-lui quelle part de ses projets vient du secteur privé.",
            "À Risque":        "Ce cabinet a peu de visibilité — propose un audit gratuit de son positionnement auprès des maîtres d'ouvrage privés.",
        },
    },
    "Commerce & Distribution": {
        "angle": "développement du réseau de distribution et acquisition de nouveaux revendeurs B2B",
        "pain_point": "difficulté à identifier de nouveaux revendeurs, distributeurs ou clients grossistes",
        "value_prop": "LeadNova  cartographie les distributeurs et revendeurs potentiels pour élargir votre réseau",
        "vocabulary": "utilise : réseau de distribution, grossiste, revendeur, point de vente, marge, référencement",
        "tone_extra": "sois commercial et orienté volume, parle marges, référencement et potentiel de vente",
        "segment_context": {
            "Chaud":           "Ce distributeur cherche à élargir son réseau de revendeurs — propose un appel pour identifier ensemble les points de vente non encore couverts.",
            "Prêts à Acheter": "Ce distributeur réfléchit à sa stratégie d'expansion — partage des données sur les revendeurs potentiels dans sa zone.",
            "Froid":           "Ce distributeur n'est pas encore en mode expansion — demande-lui combien de nouveaux points de vente il prévoit d'ouvrir cette année.",
            "À Risque":        "Ce distributeur a peu de données — propose un audit gratuit de la couverture de son réseau de distribution actuel.",
        },
    },
    "Industrie & Production": {
        "angle": "acquisition de nouveaux donneurs d'ordre et développement des contrats de sous-traitance",
        "pain_point": "dépendance à un nombre limité de donneurs d'ordre et difficulté à diversifier le portefeuille",
        "value_prop": "LeadNova  identifie de nouveaux donneurs d'ordre industriels cherchant des sous-traitants qualifiés",
        "vocabulary": "utilise : donneur d'ordre, sous-traitance, capacité de production, cahier des charges, certification",
        "tone_extra": "sois technique et orienté capacités, parle qualité, délais, certifications et normes",
        "segment_context": {
            "Chaud":           "Cet industriel cherche à diversifier ses donneurs d'ordre — propose un appel pour identifier ensemble les nouveaux marchés accessibles.",
            "Prêts à Acheter": "Cet industriel réfléchit à réduire sa dépendance — partage des exemples de donneurs d'ordre identifiés dans son secteur.",
            "Froid":           "Cet industriel n'est pas encore en démarche active — demande-lui combien de donneurs d'ordre représentent aujourd'hui plus de 50% de son CA.",
            "À Risque":        "Cet industriel a peu de données — propose un audit gratuit de sa dépendance commerciale et de ses opportunités de diversification.",
        },
    },
    "Agriculture & Alimentaire": {
        "angle": "développement de nouveaux débouchés B2B et partenariats avec acheteurs professionnels",
        "pain_point": "difficulté à trouver de nouveaux acheteurs professionnels et partenaires de distribution",
        "value_prop": "LeadNova  identifie les acheteurs professionnels, GMS et exportateurs potentiels pour vos produits",
        "vocabulary": "utilise : producteur, filière, acheteur professionnel, GMS, circuit court, export, traçabilité",
        "tone_extra": "sois pragmatique et orienté terrain, parle volumes, prix, logistique et traçabilité",
        "segment_context": {
            "Chaud":           "Ce producteur cherche à développer ses débouchés B2B — propose un appel pour identifier ensemble les acheteurs professionnels accessibles.",
            "Prêts à Acheter": "Ce producteur réfléchit à diversifier ses canaux de distribution — partage des données sur les GMS et acheteurs actifs dans sa région.",
            "Froid":           "Ce producteur vend encore en circuit court uniquement — demande-lui s'il a déjà envisagé la distribution B2B à plus grande échelle.",
            "À Risque":        "Ce producteur a peu de visibilité commerciale — propose un audit gratuit de ses canaux de vente et des opportunités B2B.",
        },
    },
    "Energie & Environnement": {
        "angle": "acquisition de contrats B2B pour l'installation de solutions énergétiques",
        "pain_point": "difficulté à identifier les entreprises cherchant à réduire leur facture énergétique",
        "value_prop": "LeadNova  identifie les entreprises investissant dans la transition énergétique et la RSE",
        "vocabulary": "utilise : transition énergétique, audit énergétique, économies d'énergie, RSE, certification ISO",
        "tone_extra": "sois expert et orienté impact, parle économies financières mesurables et engagement environnemental",
        "segment_context": {
            "Chaud":           "Cette entreprise énergie cherche à signer de nouveaux contrats B2B — propose un appel centré sur les entreprises avec des projets RSE actifs.",
            "Prêts à Acheter": "Cette entreprise réfléchit à sa stratégie commerciale — partage des données sur les PME investissant dans la transition énergétique.",
            "Froid":           "Cette entreprise n'a pas encore structuré sa prospection B2B — demande-lui quel type de clients elle cible prioritairement.",
            "À Risque":        "Cette entreprise a peu de données — propose un audit gratuit de son positionnement sur le marché de la transition énergétique.",
        },
    },
    "Tourisme & Loisirs": {
        "angle": "développement des partenariats B2B et acquisition de groupes clients entreprises",
        "pain_point": "difficulté à attirer et fidéliser des clients B2B pour les séminaires et événements",
        "value_prop": "LeadNova  identifie les entreprises avec des budgets événementiels et team building disponibles",
        "vocabulary": "utilise : team building, séminaire, événement d'entreprise, forfait groupe, expérience",
        "tone_extra": "sois chaleureux et inspirant, mets en avant les expériences uniques et la qualité de service",
        "segment_context": {
            "Chaud":           "Cet acteur du tourisme cherche à développer sa clientèle B2B — propose un appel pour identifier les entreprises avec des budgets team building.",
            "Prêts à Acheter": "Cet acteur réfléchit à ses offres B2B — partage des exemples d'entreprises cherchant des destinations pour leurs séminaires.",
            "Froid":           "Cet acteur n'a pas encore développé son offre B2B — demande-lui quelle part de son CA vient des groupes entreprises.",
            "À Risque":        "Cet acteur a peu de visibilité — propose un audit gratuit de son positionnement auprès des entreprises.",
        },
    },
    "Tourisme & Voyages": {
        "angle": "développement des partenariats B2B et acquisition de groupes clients entreprises",
        "pain_point": "difficulté à attirer et fidéliser des clients B2B pour les séminaires et voyages d'affaires",
        "value_prop": "LeadNova  identifie les entreprises avec des budgets voyages d'affaires et incentive",
        "vocabulary": "utilise : voyage d'affaires, incentive, séminaire, forfait groupe, déplacement professionnel",
        "tone_extra": "sois chaleureux et inspirant, mets en avant le service premium et la personnalisation",
        "segment_context": {
            "Chaud":           "Cette agence de voyages cherche à développer sa clientèle corporate — propose un appel pour identifier les entreprises avec des budgets voyages d'affaires.",
            "Prêts à Acheter": "Cette agence réfléchit à ses offres corporate — partage des exemples d'entreprises cherchant des prestataires voyages.",
            "Froid":           "Cette agence n'a pas encore développé son offre B2B — demande-lui si elle a déjà travaillé avec des groupes entreprises.",
            "À Risque":        "Cette agence a peu de données — propose un audit gratuit de son positionnement sur le marché corporate.",
        },
    },
    "Mode & Accessoires": {
        "angle": "développement du réseau de revendeurs professionnels et distribution B2B",
        "pain_point": "difficulté à identifier de nouveaux revendeurs et distributeurs multimarques",
        "value_prop": "LeadNova  cartographie les boutiques et revendeurs potentiels pour étendre votre distribution",
        "vocabulary": "utilise : revendeur, boutique multimarque, collection, wholesale, marché cible, référencement",
        "tone_extra": "sois élégant et inspirant, parle tendances, collections, image de marque et potentiel commercial",
        "segment_context": {
            "Chaud":           "Cette marque cherche à étendre son réseau de distribution — propose un appel pour identifier ensemble les boutiques non encore référencées.",
            "Prêts à Acheter": "Cette marque réfléchit à sa stratégie wholesale — partage des données sur les boutiques multimarques actives dans sa cible.",
            "Froid":           "Cette marque n'a pas encore développé son réseau — demande-lui combien de points de vente elle vise pour la prochaine collection.",
            "À Risque":        "Cette marque a peu de visibilité — propose un audit gratuit de la couverture de son réseau de distribution actuel.",
        },
    },
    "Restauration & Hôtellerie": {
        "angle": "acquisition de clients B2B pour les déjeuners d'affaires, séminaires et événements d'entreprise",
        "pain_point": "difficulté à attirer des entreprises pour privatiser l'espace ou organiser des événements professionnels",
        "value_prop": "LeadNova  identifie les entreprises cherchant des espaces pour leurs événements professionnels",
        "vocabulary": "utilise : déjeuner d'affaires, séminaire, salle de réunion, privatisation, team building, buffet",
        "tone_extra": "sois accueillant et commercial, mets en avant l'expérience gastronomique, le cadre et le service",
        "segment_context": {
            "Chaud":           "Cet établissement cherche à développer sa clientèle B2B — propose un appel pour identifier les entreprises avec des événements à organiser.",
            "Prêts à Acheter": "Cet établissement réfléchit à ses offres corporate — partage des exemples d'entreprises cherchant des salles de réunion ou espaces événementiels.",
            "Froid":           "Cet établissement n'a pas encore structuré son offre B2B — demande-lui si il dispose d'une salle privatisable pour les événements d'entreprise.",
            "À Risque":        "Cet établissement a peu de données — propose un audit gratuit de son positionnement auprès des entreprises locales.",
        },
    },
    "Culture & Musées": {
        "angle": "développement des partenariats mécénat et événements culturels avec des entreprises",
        "pain_point": "difficulté à convaincre des entreprises d'investir dans la culture via le mécénat",
        "value_prop": "LeadNova  identifie les entreprises avec des budgets RSE et mécénat culturel disponibles",
        "vocabulary": "utilise : mécénat, partenariat culturel, RSE, valorisation, rayonnement, patrimoine, sponsoring",
        "tone_extra": "sois culturel et élégant, mets en avant le rayonnement, la valorisation d'image et l'impact social",
        "segment_context": {
            "Chaud":           "Cet acteur culturel cherche des partenaires mécènes — propose un appel pour identifier les entreprises avec des budgets RSE disponibles.",
            "Prêts à Acheter": "Cet acteur culturel réfléchit à ses partenariats — partage des exemples d'entreprises ayant valorisé leur image via le mécénat culturel.",
            "Froid":           "Cet acteur culturel n'a pas encore développé ses partenariats entreprises — demande-lui s'il a déjà travaillé avec des mécènes privés.",
            "À Risque":        "Cet acteur culturel a peu de données — propose un audit gratuit de son potentiel de partenariats avec le secteur privé.",
        },
    },
    "Culture & Patrimoine": {
        "angle": "développement des partenariats mécénat et valorisation du patrimoine avec des entreprises",
        "pain_point": "difficulté à mobiliser des entreprises autour de la préservation et valorisation du patrimoine",
        "value_prop": "LeadNova  identifie les entreprises sensibles à la RSE et au rayonnement culturel territorial",
        "vocabulary": "utilise : mécénat, patrimoine, valorisation, RSE, sponsoring, rayonnement culturel",
        "tone_extra": "sois culturel et institutionnel, mets en avant l'impact territorial et la valorisation d'image",
        "segment_context": {
            "Chaud":           "Cet acteur du patrimoine cherche des partenaires entreprises — propose un appel pour identifier les mécènes potentiels dans la région.",
            "Prêts à Acheter": "Cet acteur réfléchit à ses partenariats — partage des exemples de valorisation d'image via le mécénat patrimonial.",
            "Froid":           "Cet acteur n'a pas encore développé ses partenariats privés — demande-lui s'il a déjà bénéficié de soutien d'entreprises locales.",
            "À Risque":        "Cet acteur a peu de visibilité — propose un audit gratuit de son potentiel de partenariats avec le secteur privé.",
        },
    },
}

DEFAULT_SECTOR_PROMPT = {
    "angle": "développement commercial et acquisition de nouveaux clients B2B",
    "pain_point": "temps perdu en prospection non qualifiée",
    "value_prop": "LeadNova  automatise votre prospection B2B avec l'intelligence artificielle",
    "vocabulary": "utilise un vocabulaire business professionnel",
    "tone_extra": "sois professionnel et orienté valeur",
    "segment_context": {
        "Chaud":           "Ce prospect est prêt — propose un appel rapide pour démontrer la valeur de LeadNova .",
        "Prêts à Acheter": "Ce prospect s'informe — partage des exemples concrets de résultats obtenus.",
        "Froid":           "Ce prospect est hésitant — pose une question simple sur son processus de prospection actuel.",
        "À Risque":        "Ce prospect manque de données — propose un audit gratuit sans engagement.",
    },
}

# GÉNÉRATION EMAIL VIA OPENROUTER
SENDER_COMPANY = "LeadNova "

def build_prompt(lead: dict, segment: str, version: str = "A",
                 user_subject: str = None, user_cta: str = None, user_tone: str = None) -> str:
    hints     = SEGMENT_PROMPTS.get(segment, SEGMENT_PROMPTS["Froid"])
    company   = lead.get("company") or "votre entreprise"
    sector    = lead.get("sector") or "votre secteur"
    region    = lead.get("region") or "Tunisie"
    ctype     = lead.get("company_type") or "entreprise"
    firstname = lead.get("first_name") or ""

    # Paramètres utilisateur ou fallback automatique par segment
    # Personnalisation prénom dans l'objet 
    firstname_hint = f" — si possible inclure le prénom '{firstname}' dans l'objet" if firstname else ""
    subject_instruction = (
        f"Utilise EXACTEMENT cet objet : \"{user_subject}\""
        if user_subject
        else f"Génère un objet accrocheur ({hints['subject_hint']}{firstname_hint})"
    )
    cta_instruction  = user_cta  or hints["cta"]
    tone_instruction = user_tone or hints["tone"]

    variation = ""
    if version == "B":
        variation = "Version B : reformule l'accroche différemment, varie le CTA, garde le même objet."

    # Personnalisation par secteur + contexte spécifique segment×secteur
    sp = SECTOR_PROMPTS.get(sector, DEFAULT_SECTOR_PROMPT)
    segment_sector_context = sp.get("segment_context", {}).get(segment, hints["context"])

    return f"""Tu es un expert en prospection B2B tunisien. Génère un email commercial personnalisé.

Données du prospect :
- Entreprise : {company}
- Secteur : {sector}
- Région : {region}
- Type d'entreprise : {ctype}
- Prénom contact : {firstname or 'Non disponible'}
- Segment CRM : {segment}

Contexte secteur ({sector}) — adapte TOUT ton email à ce contexte :
- Angle d'approche : {sp['angle']}
- Pain point typique de ce secteur : {sp['pain_point']}
- Proposition de valeur adaptée : {sp['value_prop']}
- Vocabulaire métier à utiliser : {sp['vocabulary']}
- Ton spécifique secteur : {sp['tone_extra']}

Contexte segment × secteur (très important) :
- {segment_sector_context}

Consignes générales :
- Objet : {subject_instruction}
- Ton global : {tone_instruction}
- CTA (appel à l'action) : {cta_instruction}
- Longueur corps : 100-150 mots maximum
- Langue : français professionnel
- Tu représentes la société **LeadPNova ** — utilise TOUJOURS ce nom exact
- INTERDIT d'écrire : [Votre Entreprise], [Votre Société], [Votre Prénom], [Nom], [Poste], [Téléphone], [Email], [lien], [URL]
- JAMAIS de lien, d'URL ou de lien de réservation dans l'email — utilise uniquement "Répondez à cet email"
- Termine TOUJOURS par cette signature exacte :
  Cordialement,
  L'équipe LeadNova 
  contact@leadNova t.tn | www.leadNova .tn
- Personnalise avec le nom de l'entreprise ET son secteur spécifique
{variation}

Réponds UNIQUEMENT en JSON valide :
{{"subject": "...", "body": "..."}}"""


def generate_email_openrouter(lead: dict, segment: str, version: str = "A",
                               user_subject: str = None, user_cta: str = None, user_tone: str = None) -> dict:
    if not OPENROUTER_API_KEY:
        logger.error("OPENROUTER_API_KEY manquante dans .env")
        return {}

    prompt = build_prompt(lead, segment, version, user_subject, user_cta, user_tone)

    for model in OPENROUTER_MODELS:
        try:
            r = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://leadnova .tn",
                    "X-Title": "LeadNova ",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": 400,
                },
                timeout=25,
            )
            data = r.json()

            if "choices" not in data:
                err = data.get("error", {}).get("message", "?")
                logger.warning(f" {model}: {err}")
                continue

            content = data["choices"][0]["message"]["content"].strip()
            content = content.replace("```json", "").replace("```", "").strip()

            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                import re
                match = re.search(r'\{.*\}', content, re.DOTALL)
                if match:
                    result = json.loads(match.group(0))
                else:
                    continue

            if result.get("subject") and result.get("body"):
                logger.info(f"   {model} | v{version} | objet: {result['subject'][:50]}")
                return result

        except Exception as e:
            logger.error(f" {model} erreur: {e}")
            continue

    logger.warning(" Tous les modèles OpenRouter épuisés — tentative Groq...")
    return _generate_email_groq(prompt)


def _generate_email_groq(prompt: str) -> dict:
    """Fallback Groq quand tous les modèles OpenRouter ont échoué."""
    if not GROQ_API_KEY:
        logger.error(" GROQ_API_KEY manquante — aucun fallback disponible")
        return {}

    for model in GROQ_MODELS:
        try:
            r = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": 400,
                },
                timeout=20,
            )
            data = r.json()

            if "choices" not in data:
                err = data.get("error", {}).get("message", "?")
                logger.warning(f" Groq {model}: {err}")
                continue

            content = data["choices"][0]["message"]["content"].strip()
            content = content.replace("```json", "").replace("```", "").strip()

            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                import re
                match = re.search(r'\{.*\}', content, re.DOTALL)
                if match:
                    result = json.loads(match.group(0))
                else:
                    continue

            if result.get("subject") and result.get("body"):
                logger.info(f"   [GROQ] {model} | objet: {result['subject'][:50]}")
                return result

        except Exception as e:
            logger.error(f" Groq {model} erreur: {e}")
            continue

    logger.error(" Groq épuisé — aucun modèle disponible")
    return {}


def generate_text_openrouter(prompt: str, max_tokens: int = 1800) -> str:
    """Appel générique à OpenRouter, retourne du texte brut (pas de JSON)."""
    if not OPENROUTER_API_KEY:
        return ""
    for model in OPENROUTER_MODELS:
        try:
            r = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://leadnova .tn",
                    "X-Title": "LeadNova ",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.6,
                    # large budget : les modèles "reasoning" consomment des tokens
                    # de réflexion avant de produire la réponse finale
                    "max_tokens": max_tokens,
                    "reasoning": {"exclude": True},
                },
                timeout=45,
            )
            data = r.json()
            if "choices" not in data:
                continue
            content = (data["choices"][0]["message"].get("content") or "").strip()
            content = content.replace("```", "").strip()
            if content:
                return content
        except Exception as e:
            logger.error(f"OpenRouter texte erreur {model}: {e}")
            continue

    logger.warning(" OpenRouter texte épuisé — tentative Groq...")
    if not GROQ_API_KEY:
        return ""
    for model in GROQ_MODELS:
        try:
            r = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.6,
                    "max_tokens": max_tokens,
                },
                timeout=45,
            )
            data = r.json()
            if "choices" not in data:
                continue
            content = (data["choices"][0]["message"].get("content") or "").strip()
            content = content.replace("```", "").strip()
            if content:
                logger.info(f"   [GROQ texte] {model}")
                return content
        except Exception as e:
            logger.error(f"Groq texte erreur {model}: {e}")
            continue
    return ""


# ENVOI VIA BREVO
def send_email_brevo(to_email: str, to_name: str, subject: str, body: str, lead_id: int = None,
                     cta_text: str = None, cta_link: str = None) -> bool:
    if not BREVO_API_KEY:
        logger.warning(" BREVO_API_KEY manquante — envoi ignoré")
        return False

    from urllib.parse import quote
    base_url = os.environ.get("APP_BASE_URL", "http://127.0.0.1:8000")

    pixel = ""
    cta_button = ""
    if lead_id:
        pixel = f'<img src="{base_url}/campaigns/track/open?lead_id={lead_id}" width="1" height="1" style="display:none" alt=""/>'
        if cta_text:
            dest = cta_link or "https://leadnova.io"
            tracked = f'{base_url}/campaigns/track/click?lead_id={lead_id}&url={quote(dest, safe="")}'
            cta_button = (
                f'<div style="margin:24px 0;">'
                f'<a href="{tracked}" style="display:inline-block;background:#6366f1;color:#fff;'
                f'text-decoration:none;font-weight:600;font-size:14px;padding:12px 24px;border-radius:8px;">'
                f'{cta_text}</a></div>'
            )

    try:
        r = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={
                "api-key": BREVO_API_KEY,
                "Content-Type": "application/json",
            },
            json={
                "sender": {"name": FROM_NAME, "email": FROM_EMAIL},
                "to": [{"email": to_email, "name": to_name}],
                "subject": subject,
                "textContent": body,
                "htmlContent": f"<p>{body.replace(chr(10), '<br>')}</p>{cta_button}{pixel}",
            },
            timeout=15,
        )
        if r.status_code in (200, 201):
            logger.info(f" Envoyé à {to_email}")
            return True
        else:
            logger.error(f" Brevo erreur {r.status_code}: {r.text[:200]}")
            return False
    except Exception as e:
        logger.error(f" Brevo exception: {e}")
        return False


# SAUVEGARDE EMAIL EN BASE (colonnes email_sent_*)
def save_email_to_db(engine, lead_id: int, subject_a: str, body_a: str,
                     subject_b: str, body_b: str, sent: bool, ab_version: str = None):
    with engine.connect() as conn:
        conn.execute(text("""
            UPDATE leads SET
                email_subject_a  = :sa,
                email_body_a     = :ba,
                email_subject_b  = :sb,
                email_body_b     = :bb,
                email_sent       = :sent,
                email_sent_at    = :ts,
                ab_version       = :ab
            WHERE id = :id
        """), {
            "sa": subject_a, "ba": body_a,
            "sb": subject_b, "bb": body_b,
            "sent": sent,
            "ts": datetime.utcnow() if sent else None,
            "ab": ab_version,
            "id": lead_id,
        })
        conn.commit()


# PIPELINE PRINCIPAL
def generate_emails(segment: str = None, limit: int = 50, dry_run: bool = True,
                    user_subject: str = None, user_cta: str = None, user_tone: str = None,
                    sector: str = None, region: str = None, lead_ids: list = None,
                    regenerate: bool = False, user_cta_link: str = None,
                    campaign_id: int = None):
    logger.info("=" * 55)
    logger.info("LeadNova — Email Generator")
    logger.info(f"Segment : {segment or 'TOUS'} | Limite : {limit} | Dry-run : {dry_run}")
    logger.info(f"OpenRouter : {'' if OPENROUTER_API_KEY else ' '}")
    logger.info(f"Brevo      : {'' if BREVO_API_KEY else ' (dry-run forcé)'}")
    logger.info("=" * 55)

    if not OPENROUTER_API_KEY:
        logger.error("OPENROUTER_API_KEY manquante — arrêt")
        return

    engine = create_engine(DATABASE_URL)

    # Requête leads avec email
    where_clauses = ["email IS NOT NULL", "email != ''"]

    # Si des sociétés spécifiques sont sélectionnées ignorer les autres filtres
    if lead_ids:
        ids_str = ",".join(str(i) for i in lead_ids)
        where_clauses.append(f"id IN ({ids_str})")
    else:
        if segment:
            where_clauses.append(f"segment = '{segment}'")
        if sector:
            where_clauses.append(f"sector = '{sector}'")
        if region:
            where_clauses.append(f"region ILIKE '%{region}%'")

    # Si regenerate=True regénère même les leads déjà générés
    if not regenerate:
        where_clauses.append("(email_sent IS NULL OR email_sent = FALSE)")

    query = f"""
        SELECT id, company, first_name, last_name, email,
               sector, region, company_type, segment, lead_score
        FROM leads
        WHERE {' AND '.join(where_clauses)}
        ORDER BY lead_score DESC NULLS LAST
        LIMIT {limit}
    """

    df = pd.read_sql(query, engine)
    logger.info(f" {len(df)} leads à traiter")

    if len(df) == 0:
        logger.info("Aucun lead éligible.")
        return

    sent_count = generated_count = error_count = 0
    total = len(df)

    # Initialiser le suivi de progression dans Redis
    _redis = None
    if campaign_id:
        try:
            import redis as redis_lib
            _redis = redis_lib.Redis(host='localhost', port=6379, db=0, decode_responses=True)
            _redis.setex(f"gen_progress:{campaign_id}", 7200, json.dumps({
                "status": "running", "generated": 0, "sent": 0, "errors": 0, "total": total
            }))
        except Exception:
            _redis = None

    for idx, (_, row) in enumerate(df.iterrows()):
        lead = row.to_dict()
        seg  = lead.get("segment") or segment or "Froid"
        name = f"{lead.get('first_name') or ''} {lead.get('last_name') or ''}".strip() or lead.get("company") or "Contact"

        # A/B Testing 50/50 indices pairs A, impairs B
        ab_version = "A" if idx % 2 == 0 else "B"

        logger.info(f"\n[{idx+1}/{total}] {lead.get('company')} | {seg} | v={ab_version} | score={lead.get('lead_score')}")

        # Générer  2 ver
        email_a = generate_email_openrouter(lead, seg, version="A",
                    user_subject=user_subject, user_cta=user_cta, user_tone=user_tone)
        time.sleep(0.5)
        email_b = generate_email_openrouter(lead, seg, version="B",
                    user_subject=user_subject, user_cta=user_cta, user_tone=user_tone)
        time.sleep(0.5)

        if not email_a:
            error_count += 1
            if _redis and campaign_id:
                try:
                    _redis.setex(f"gen_progress:{campaign_id}", 7200, json.dumps({
                        "status": "running", "generated": generated_count, "sent": sent_count,
                        "errors": error_count, "total": total
                    }))
                except Exception:
                    pass
            continue

        generated_count += 1

        # Choisir la version à envoyer selon l'assignation A/B
        email_to_send = email_a if ab_version == "A" else (email_b or email_a)

        if dry_run:
            logger.info(f"   [DRY-RUN] Version assignée : {ab_version}")
            logger.info(f"   [DRY-RUN] Objet A : {email_a.get('subject')}")
            logger.info(f"   [DRY-RUN] Objet B : {email_b.get('subject') if email_b else 'N/A'}")
        else:
            sent = send_email_brevo(
                to_email=lead["email"],
                to_name=name,
                subject=email_to_send["subject"],
                body=email_to_send["body"],
                lead_id=int(lead["id"]),
                cta_text=user_cta or "En savoir plus",
                cta_link=user_cta_link,
            )
            if sent:
                sent_count += 1
                logger.info(f" Envoyé version {ab_version} à {lead['email']}")

        # Sauvegarder en base avec la version assignée
        try:
            save_email_to_db(
                engine=engine,
                lead_id=int(lead["id"]),
                subject_a=email_a.get("subject", ""),
                body_a=email_a.get("body", ""),
                subject_b=email_b.get("subject", "") if email_b else "",
                body_b=email_b.get("body", "") if email_b else "",
                sent=not dry_run,
                ab_version=ab_version,
            )
        except Exception as e:
            logger.warning(f" Sauvegarde DB échouée: {e}")

        # Mise à jour progression Redis
        if _redis and campaign_id:
            try:
                _redis.setex(f"gen_progress:{campaign_id}", 7200, json.dumps({
                    "status": "running", "generated": generated_count, "sent": sent_count,
                    "errors": error_count, "total": total
                }))
            except Exception:
                pass

    logger.info(f"\n{'='*55}")
    logger.info(f"Terminé !")
    logger.info(f"   Générés  : {generated_count}")
    logger.info(f"   Envoyés  : {sent_count}")
    logger.info(f"   Erreurs  : {error_count}")

    # Marquer la progression comme terminée dans Redis
    if _redis and campaign_id:
        try:
            _redis.setex(f"gen_progress:{campaign_id}", 3600, json.dumps({
                "status": "done", "generated": generated_count, "sent": sent_count,
                "errors": error_count, "total": total
            }))
        except Exception:
            pass

    if dry_run:
        logger.info("   Mode dry-run — aucun email envoyé")
    else:
        try:
            from app.routers.notifications import push_notification
            push_notification("camp", "Campagne terminée",
                f"{sent_count} emails envoyés · {generated_count} générés")
        except Exception as e:
            logger.error(f"[NOTIF] {e}")


# CLI
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="LeadNova  Email Generator")
    parser.add_argument("--segment", choices=["Chaud", "Prêts à Acheter", "Froid", "À Risque"],
                        help="Segment cible")
    parser.add_argument("--all", action="store_true", help="Tous les segments")
    parser.add_argument("--limit", type=int, default=50, help="Nombre max de leads")
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Générer sans envoyer (défaut: True)")
    parser.add_argument("--send", action="store_true",
                        help="Envoyer réellement via Brevo (désactive dry-run)")
    args = parser.parse_args()

    dry = not args.send

    if args.all:
        for seg in ["Chaud", "Prêts à Acheter", "À Risque", "Froid"]:
            generate_emails(segment=seg, limit=args.limit // 4, dry_run=dry)
    else:
        generate_emails(segment=args.segment, limit=args.limit, dry_run=dry)
