"""
sessions.py - Multi-conversations : plusieurs historiques sauvegardes,
listables et reprenables (facon Claude Code --resume).

Chaque conversation est un fichier JSON independant dans le dossier
sessions/ (local, ignore par git) :
    sessions/<id>.json = {
        "id": "20260706_201530",
        "titre": "Pingpong asm improvements",   # derive du 1er message user
        "cree": "2026-07-06T20:15:30",
        "maj":  "2026-07-06T20:20:11",
        "historique": [...]                     # meme format qu'avant
    }

Avant cette fonctionnalite, une SEULE conversation etait sauvegardee dans
session_history.json (liste brute de messages). migrer_ancienne_session()
recupere cet ancien fichier (s'il existe) dans le nouveau systeme, sans
perte, puis le renomme pour ne pas re-migrer a chaque lancement.
"""

from __future__ import annotations

import json
import os
import time


DOSSIER_SESSIONS = "sessions"
CHEMIN_LEGACY = "session_history.json"

# Longueur max du titre affiche (derive du 1er message utilisateur).
LONGUEUR_TITRE = 48


def _horodatage() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def generer_id(dossier: str = DOSSIER_SESSIONS) -> str:
    """
    Nouvel identifiant unique, base sur l'horodatage (lisible et triable).
    Ajoute un suffixe si une collision existe deja (rare : meme seconde).
    """
    base = time.strftime("%Y%m%d_%H%M%S")
    candidat = base
    suffixe = 2
    while os.path.exists(os.path.join(dossier, f"{candidat}.json")):
        candidat = f"{base}_{suffixe}"
        suffixe += 1
    return candidat


def _chemin(id_session: str, dossier: str = DOSSIER_SESSIONS) -> str:
    return os.path.join(dossier, f"{id_session}.json")


def _extraire_texte(contenu) -> str:
    """
    Extrait un texte lisible du contenu d'un message, qu'il soit une simple
    chaine ou une liste multimodale (texte + image_url, voir images.py).
    """
    if isinstance(contenu, str):
        return contenu
    if isinstance(contenu, list):
        for bloc in contenu:
            if isinstance(bloc, dict) and bloc.get("type") == "text":
                return bloc.get("text", "")
    return ""


def deriver_titre(historique: list[dict]) -> str:
    """
    Construit un titre court a partir du premier message utilisateur (le
    message systeme est ignore). Retourne "New session" si aucun trouve.
    """
    for message in historique:
        if message.get("role") != "user":
            continue
        texte = _extraire_texte(message.get("content", "")).strip()
        texte = " ".join(texte.split())  # aplati les retours a la ligne
        if not texte:
            continue
        if texte.startswith("[Tool result:") or texte.startswith("[Plan mode"):
            continue  # pas un vrai message utilisateur -> continue de chercher
        if len(texte) > LONGUEUR_TITRE:
            texte = texte[:LONGUEUR_TITRE].rstrip() + "…"
        return texte
    return "New session"


def sauver(
    id_session: str,
    historique: list[dict],
    titre: str | None = None,
    dossier: str = DOSSIER_SESSIONS,
) -> None:
    """
    Enregistre (ou met a jour) une session sur disque. Preserve la date de
    creation d'origine si le fichier existe deja. Echec silencieux si
    l'ecriture est impossible (disque plein, permissions...).
    """
    chemin = _chemin(id_session, dossier)
    cree = _horodatage()
    if os.path.exists(chemin):
        try:
            with open(chemin, "r", encoding="utf-8") as f:
                cree = json.load(f).get("cree", cree)
        except (OSError, ValueError):
            pass

    donnees = {
        "id": id_session,
        "titre": titre or deriver_titre(historique),
        "cree": cree,
        "maj": _horodatage(),
        "historique": historique,
    }
    try:
        os.makedirs(dossier, exist_ok=True)
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump(donnees, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def charger(id_session: str, dossier: str = DOSSIER_SESSIONS) -> dict | None:
    """Charge une session complete (id/titre/cree/maj/historique), ou None."""
    chemin = _chemin(id_session, dossier)
    if not os.path.exists(chemin):
        return None
    try:
        with open(chemin, "r", encoding="utf-8") as f:
            donnees = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(donnees, dict) or not isinstance(donnees.get("historique"), list):
        return None
    return donnees


def lister(dossier: str = DOSSIER_SESSIONS) -> list[dict]:
    """
    Retourne les metadonnees de toutes les sessions (id/titre/cree/maj/
    nb_messages), triees par date de mise a jour DECROISSANTE (la plus
    recente d'abord). Fichiers corrompus ignores silencieusement.
    """
    if not os.path.isdir(dossier):
        return []
    resultats = []
    for nom in os.listdir(dossier):
        if not nom.endswith(".json"):
            continue
        donnees = charger(nom[: -len(".json")], dossier)
        if donnees is None:
            continue
        resultats.append({
            "id": donnees.get("id", nom[: -len(".json")]),
            "titre": donnees.get("titre", "New session"),
            "cree": donnees.get("cree", ""),
            "maj": donnees.get("maj", ""),
            "nb_messages": len(donnees.get("historique", [])),
        })
    resultats.sort(key=lambda s: s["maj"], reverse=True)
    return resultats


def supprimer(id_session: str, dossier: str = DOSSIER_SESSIONS) -> bool:
    """Supprime une session. Retourne True si un fichier a bien ete efface."""
    chemin = _chemin(id_session, dossier)
    try:
        os.remove(chemin)
        return True
    except OSError:
        return False


def migrer_ancienne_session(
    chemin_legacy: str = CHEMIN_LEGACY, dossier: str = DOSSIER_SESSIONS
) -> str | None:
    """
    Recupere l'ancien fichier unique session_history.json (avant le multi-
    session) dans le nouveau systeme, SANS PERTE : il est importe comme une
    session normale puis renomme en '.migrated' pour ne plus etre re-traite
    au prochain lancement. Ne fait rien si le fichier n'existe pas (deja
    migre, ou installation neuve). Retourne le nouvel id, ou None.
    """
    if not os.path.exists(chemin_legacy):
        return None
    try:
        with open(chemin_legacy, "r", encoding="utf-8") as f:
            historique = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(historique, list) or not historique:
        return None

    id_session = generer_id(dossier)
    sauver(id_session, historique, dossier=dossier)
    try:
        os.replace(chemin_legacy, chemin_legacy + ".migrated")
    except OSError:
        pass  # migration deja faite en memoire ; tant pis si le rename echoue
    return id_session
