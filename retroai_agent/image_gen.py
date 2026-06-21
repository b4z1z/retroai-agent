"""
image_gen.py - Generation d'images (text-to-image) via NVIDIA NIM.

Commande /create-image : l'utilisateur decrit ce qu'il veut, on demande au
modele de generation d'images (FLUX par defaut, configurable) de la creer,
puis on enregistre le PNG dans un dossier local et on retourne son chemin.

A NOTER : le modele de CHAT (kimi-k2.6) ne sait pas creer d'images ; c'est
un modele SEPARE (config.image_model), appele avec la MEME cle API NVIDIA.
"""

from __future__ import annotations

import base64
import os
import subprocess
import sys
import time

import requests

from .api_client import ApiClient, ApiError, QuotaError
from .config import Config


# Dossier ou sont enregistrees les images generees (ignore par git).
DOSSIER_IMAGES = "generated_images"

# Endpoint Google Gemini (Nano Banana) pour la generation d'images.
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)


def label_modele(config: Config) -> str:
    """Libelle lisible du modele de generation courant (pour l'affichage)."""
    if config.image_provider == "gemini":
        return f"Nano Banana ({config.gemini_model}) · Google"
    return f"FLUX.1 ({config.image_model}) · NVIDIA"


def _extraire_gemini_base64(data: dict) -> str:
    """Extrait l'image base64 de la reponse Gemini (parts[].inlineData.data)."""
    for candidat in data.get("candidates") or []:
        parts = (candidat.get("content") or {}).get("parts") or []
        for part in parts:
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                return inline["data"]
    raise ApiError("The Gemini response did not contain any image.")


def _generer_gemini(config: Config, prompt: str) -> str:
    """Genere une image via l'API Gemini et retourne sa donnee base64."""
    if not config.gemini_api_key:
        raise ApiError(
            "No Gemini API key set. Use /image to choose a Gemini model "
            "and enter your key."
        )
    url = GEMINI_URL.format(model=config.gemini_model)
    headers = {
        "x-goog-api-key": config.gemini_api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
    }
    try:
        reponse = requests.post(url, headers=headers, json=payload, timeout=120)
    except requests.exceptions.RequestException as exc:
        raise ApiError(f"Network error (Gemini): {exc}") from exc

    # 429 = quota / palier gratuit epuise (ou rate limit) -> erreur dediee.
    if reponse.status_code == 429:
        raise QuotaError(
            "Gemini free-tier limit reached (quota exhausted, HTTP 429)."
        )
    if reponse.status_code != 200:
        raise ApiError(
            f"HTTP error {reponse.status_code} from Gemini:\n{reponse.text[:500]}"
        )
    try:
        data = reponse.json()
    except ValueError as exc:
        raise ApiError("Unreadable Gemini response (invalid JSON).") from exc
    return _extraire_gemini_base64(data)


def _nettoyer_base64(b64: str) -> str:
    """Retire un eventuel prefixe data-URI (data:image/png;base64,XXXX)."""
    if b64.startswith("data:") and "," in b64:
        return b64.split(",", 1)[1]
    return b64


def creer_image(client: ApiClient, config: Config, description: str) -> str:
    """
    Genere une image depuis 'description', l'enregistre en PNG et retourne
    le chemin du fichier. Selon config.image_provider, utilise FLUX (NVIDIA)
    ou Nano Banana (Gemini). Leve ApiError si la generation/ecriture echoue.
    """
    if config.image_provider == "gemini":
        brut = _generer_gemini(config, description)
    else:
        brut = client.generer_image(description)
    b64 = _nettoyer_base64(brut)

    try:
        donnees = base64.b64decode(b64)
    except (ValueError, TypeError) as exc:
        raise ApiError("The image data returned by the API is invalid.") from exc

    try:
        os.makedirs(DOSSIER_IMAGES, exist_ok=True)
        nom = f"baziz_{time.strftime('%Y%m%d_%H%M%S')}.png"
        chemin = os.path.join(DOSSIER_IMAGES, nom)
        with open(chemin, "wb") as f:
            f.write(donnees)
    except OSError as exc:
        raise ApiError(f"Could not save the generated image: {exc}") from exc

    return chemin


def ouvrir_image(chemin: str) -> bool:
    """
    Ouvre l'image avec la visionneuse par defaut du systeme (multiplateforme).
    Retourne True si la commande a pu etre lancee, False sinon (echec
    silencieux : ne pas planter si aucune visionneuse n'est disponible).
    """
    try:
        if sys.platform.startswith("win"):
            os.startfile(chemin)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", chemin])
        else:  # Linux / autres Unix
            subprocess.Popen(["xdg-open", chemin])
        return True
    except Exception:
        return False
