"""
profile.py - Profil utilisateur optionnel (personnalisation de l'experience).

Au TOUT PREMIER lancement, on demande a l'utilisateur s'il souhaite partager
son nom et quelques infos de base. Son choix est enregistre dans un fichier
JSON local pour ne plus reposer la question aux lancements suivants.

Principe de respect de la vie privee :
    - Rien n'est demande sans consentement explicite (defaut = non).
    - Les infos restent LOCALES (fichier user_profile.json, ignore par git).
    - L'utilisateur peut tout ignorer (Entree vide = champ saute).
"""

from __future__ import annotations

import json
import os


# Fichier local ou est stocke le profil (ignore par .gitignore).
CHEMIN_PROFIL = "user_profile.json"


def profil_existe(chemin: str = CHEMIN_PROFIL) -> bool:
    """Vrai si un profil (ou un refus) a deja ete enregistre."""
    return os.path.exists(chemin)


def charger_profil(chemin: str = CHEMIN_PROFIL) -> dict:
    """Lit le profil JSON. Retourne {} si absent ou illisible."""
    if not os.path.exists(chemin):
        return {}
    try:
        with open(chemin, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def sauver_profil(profil: dict, chemin: str = CHEMIN_PROFIL) -> None:
    """Enregistre le profil au format JSON (echec silencieux si non ecrivable)."""
    try:
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump(profil, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def _demander(question: str) -> str:
    """Pose une question ; retourne '' si l'utilisateur ignore ou interrompt."""
    try:
        return input(f"  {question} ").strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def creer_profil_interactif() -> dict:
    """Collecte les infos de l'utilisateur (toutes optionnelles)."""
    print("  (Leave blank and press Enter to skip a question.)")
    profil: dict = {}

    pseudo = _demander("Your nickname:")
    if pseudo:
        profil["pseudo"] = pseudo

    role = _demander("What do you do? (job, studies, level...):")
    if role:
        profil["role"] = role

    prefs = _demander("Preferences or info to remember (optional):")
    if prefs:
        profil["preferences"] = prefs

    return profil


def initialiser_profil(chemin: str = CHEMIN_PROFIL) -> dict:
    """
    Au premier lancement uniquement : demande le consentement puis,
    si accepte, collecte les infos. Le choix est memorise pour ne plus
    redemander ensuite. Retourne le profil (eventuellement vide).
    """
    # Deja configure (profil rempli OU refus enregistre) -> on recharge.
    if profil_existe(chemin):
        return charger_profil(chemin)

    # --- Premier lancement : demande de consentement -------------------
    print()
    print("  Welcome! Would you like to set a nickname and a few basic")
    print("  details to personalize your experience?")
    print("  (Everything stays local on your machine, nothing is sent anywhere.)")
    try:
        reponse = input("  Share this info? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        reponse = ""

    if reponse in ("y", "o", "yes", "oui"):
        profil = creer_profil_interactif()
        profil["partage"] = True
        print("  Thanks! Your preferences have been saved.")
    else:
        # On memorise le refus pour ne plus reposer la question.
        profil = {"partage": False}
        print("  No problem, no information will be saved.")

    sauver_profil(profil, chemin)
    return profil


def profil_en_texte(profil: dict) -> str:
    """
    Transforme le profil en bloc de texte injecte dans le message systeme,
    pour que l'agent personnalise ses reponses. Retourne '' si rien a dire.
    """
    if not profil or not profil.get("partage"):
        return ""

    morceaux = []
    if profil.get("pseudo"):
        morceaux.append(f"The user's nickname is {profil['pseudo']}.")
    if profil.get("role"):
        morceaux.append(f"Their activity: {profil['role']}.")
    if profil.get("preferences"):
        morceaux.append(f"Preferences to remember: {profil['preferences']}.")

    if not morceaux:
        return ""

    return (
        "Information about the user (use it to personalize your answers and "
        "address them by their nickname when it feels natural):\n"
        + " ".join(morceaux)
    )
