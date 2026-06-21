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

from .api_client import ApiClient, ApiError
from .config import Config


# Dossier ou sont enregistrees les images generees (ignore par git).
DOSSIER_IMAGES = "generated_images"


def _nettoyer_base64(b64: str) -> str:
    """Retire un eventuel prefixe data-URI (data:image/png;base64,XXXX)."""
    if b64.startswith("data:") and "," in b64:
        return b64.split(",", 1)[1]
    return b64


def creer_image(client: ApiClient, config: Config, description: str) -> str:
    """
    Genere une image depuis 'description', l'enregistre en PNG et retourne
    le chemin du fichier. Leve ApiError si la generation ou l'ecriture echoue.
    """
    b64 = _nettoyer_base64(client.generer_image(description))

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
