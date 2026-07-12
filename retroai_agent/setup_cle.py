"""
setup_cle.py - Assistant de PREMIERE CONFIGURATION (cle API NVIDIA).

Probleme resolu : avant, un nouvel utilisateur sans .env recevait juste une
erreur seche ("NVIDIA_API_KEY is missing") et devait lire le README, creer le
fichier et le remplir a la main. Desormais, au premier lancement sans cle,
un assistant le guide de bout en bout :

    1. affiche les etapes (compte NVIDIA gratuit, generation de la cle),
    2. propose d'OUVRIR build.nvidia.com dans le navigateur,
    3. laisse COLLER la cle directement dans le terminal,
    4. la VERIFIE en ligne (GET /v1/models : gratuit, aucune inference),
    5. l'ECRIT dans .env automatiquement (config.set_env_value).

L'utilisateur est operationnel sans jamais editer un fichier.
"""

from __future__ import annotations

import sys
import webbrowser

from . import ui
from .config import set_env_value


URL_NVIDIA = "https://build.nvidia.com/"
URL_VERIF = "https://integrate.api.nvidia.com/v1/models"

# Nombre d'essais de saisie avant d'abandonner proprement.
MAX_ESSAIS = 3


def cle_plausible(cle: str) -> bool:
    """Controle de FORME uniquement (le vrai test est en ligne) : les cles
    NVIDIA commencent par 'nvapi-' et sont longues."""
    return cle.startswith("nvapi-") and len(cle) >= 30


def verifier_cle_en_ligne(cle: str, timeout: int = 15):
    """
    Teste la cle avec GET /v1/models (liste du catalogue : GRATUIT, aucune
    inference, aucun credit consomme).

    Retourne True (valide), False (rejetee 401/403), ou None (reseau
    indisponible / reponse inattendue -> on ne BLOQUE pas l'utilisateur
    hors-ligne, on enregistre quand meme).
    """
    try:
        import requests
        reponse = requests.get(
            URL_VERIF, headers={"Authorization": f"Bearer {cle}"},
            timeout=timeout,
        )
        if reponse.status_code == 200:
            return True
        if reponse.status_code in (401, 403):
            return False
        return None
    except Exception:
        return None


def assistant_cle(chemin_env: str = ".env") -> str | None:
    """
    Guide l'utilisateur pas a pas et retourne la cle enregistree,
    ou None s'il abandonne (Ctrl+C, saisie vide, essais epuises).

    Ne se lance JAMAIS hors d'un terminal interactif (tests, CI, pipes) :
    dans ce cas on retourne None et l'appelant affiche l'erreur classique.
    """
    try:
        if not sys.stdin.isatty():
            return None
    except Exception:
        return None

    ui.panneau_setup_cle(URL_NVIDIA)

    # Proposer d'ouvrir le navigateur (Enter = oui).
    try:
        reponse = ui.demander_texte(
            "Open build.nvidia.com in your browser now? (Y/n):"
        ).lower()
    except (EOFError, KeyboardInterrupt):
        ui.info("\nSetup cancelled.")
        return None
    if reponse in ("", "y", "yes", "o", "oui"):
        try:
            webbrowser.open(URL_NVIDIA)
            ui.info("Browser opened — come back here once you have the key.")
        except Exception:
            ui.info(f"Could not open a browser — go to {URL_NVIDIA} manually.")

    # Saisie de la cle (quelques essais, avec verification en ligne).
    for essai in range(MAX_ESSAIS):
        try:
            cle = ui.demander_texte("Paste your API key (nvapi-…):")
        except (EOFError, KeyboardInterrupt):
            ui.info("\nSetup cancelled.")
            return None
        cle = cle.strip().strip('"').strip("'")
        if not cle:
            ui.info("Setup cancelled (empty input).")
            return None
        if not cle_plausible(cle):
            ui.erreur(
                "That does not look like an NVIDIA key (it should start "
                "with 'nvapi-'). Please copy the FULL key and try again."
            )
            continue

        ui.info("Checking the key with NVIDIA…")
        verdict = verifier_cle_en_ligne(cle)
        if verdict is False:
            ui.erreur(
                "NVIDIA rejected this key (unauthorized). Double-check that "
                "you copied it entirely, or generate a new one."
            )
            continue
        if verdict is None:
            ui.info(
                "Could not verify the key right now (offline or NVIDIA "
                "unreachable) — saving it anyway."
            )

        set_env_value("NVIDIA_API_KEY", cle, chemin_env)
        ui.succes(
            "Key saved to .env — you are all set! It will be reused "
            "automatically at every launch."
        )
        return cle

    ui.erreur(
        f"Too many attempts ({MAX_ESSAIS}). Run the app again when you have "
        f"your key, or put it in .env yourself (see .env.example)."
    )
    return None
