"""
images.py - Support des images en entree (multimodal / vision).

Detecte les chemins d'images dans le message de l'utilisateur, les encode
en base64 (data-URI) et construit le contenu "multimodal" attendu par
l'API au format OpenAI : une liste de blocs {text} + {image_url}.

Le modele moonshotai/kimi-k2.6 via NVIDIA NIM supporte la vision : un
message dont le "content" est une liste mixant texte et images est accepte.

Usage : l'utilisateur mentionne un chemin d'image dans son message, par ex.
    "describe photo.png"   ou   "what is in @captures/img.jpg ?"
"""

from __future__ import annotations

import base64
import os


# Extensions reconnues comme images, et leur type MIME.
MIME_PAR_EXTENSION = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}

# Garde-fou : on n'encode pas une image plus grosse que ca (octets).
MAX_OCTETS = 8 * 1024 * 1024  # 8 Mo


def _nettoyer(token: str) -> str:
    """
    Nettoie un token pour en extraire un chemin : retire les guillemets,
    parentheses, le prefixe '@', et la PONCTUATION de fin (ex. "photo.png?"
    ou "photo.png," -> "photo.png") qui sinon casse la detection.
    """
    token = token.strip()
    token = token.lstrip("@(\"'")
    token = token.rstrip("\"')?!.,;:")
    return token


def extraire_chemins_images(texte: str) -> list[str]:
    """
    Retourne la liste des chemins d'images EXISTANTS mentionnes dans le texte.
    Un token est retenu s'il a une extension d'image connue ET pointe vers
    un fichier reel (os.path.isfile).
    """
    chemins = []
    for token in texte.split():
        chemin = _nettoyer(token)
        if not chemin:
            continue
        ext = os.path.splitext(chemin)[1].lower()
        if ext in MIME_PAR_EXTENSION and os.path.isfile(chemin):
            chemins.append(chemin)
    return chemins


def encoder_image(chemin: str) -> str | None:
    """
    Lit une image et la retourne en data-URI base64, ou None si echec
    (fichier illisible, trop gros...).
    """
    try:
        if os.path.getsize(chemin) > MAX_OCTETS:
            return None
        with open(chemin, "rb") as f:
            donnees = f.read()
    except OSError:
        return None

    ext = os.path.splitext(chemin)[1].lower()
    mime = MIME_PAR_EXTENSION.get(ext, "image/png")
    b64 = base64.b64encode(donnees).decode()
    return f"data:{mime};base64,{b64}"


def choisir_image_dialogue() -> str | None:
    """
    Ouvre une fenetre de selection de fichier (gestionnaire de fichiers
    natif) pour choisir une image. Retourne le chemin choisi, ou None si
    annule / si l'interface graphique n'est pas disponible.

    Utilise tkinter (inclus dans la bibliotheque standard Python ; sous
    Linux il faut parfois installer python3-tk).
    """
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        return None
    try:
        racine = tk.Tk()
        racine.withdraw()                      # cache la fenetre principale
        racine.attributes("-topmost", True)    # passe au premier plan
        chemin = filedialog.askopenfilename(
            title="Choose an image",
            filetypes=[
                ("Images", "*.png *.jpg *.jpeg *.gif *.webp *.bmp"),
                ("All files", "*.*"),
            ],
        )
        racine.destroy()
        return chemin or None
    except Exception:
        return None


def image_depuis_presse_papiers() -> str | None:
    """
    Recupere une image depuis le presse-papiers, l'enregistre dans un
    fichier temporaire et retourne son chemin. Retourne None si le
    presse-papiers ne contient pas d'image (ou si Pillow n'est pas installe).

    Necessite la bibliotheque optionnelle Pillow (pip install pillow).
    """
    try:
        from PIL import ImageGrab
    except ImportError:
        return None
    try:
        image = ImageGrab.grabclipboard()
    except Exception:
        return None
    # grabclipboard() renvoie une Image, une liste de chemins, ou None.
    if image is None or not hasattr(image, "save"):
        return None
    try:
        import tempfile
        chemin = os.path.join(tempfile.gettempdir(), "baziz_paste.png")
        image.save(chemin, "PNG")
        return chemin
    except Exception:
        return None


def construire_contenu(texte: str, chemins_explicites: list[str] | None = None):
    """
    Construit le 'content' du message utilisateur.

    Retourne un couple (contenu, images_jointes) :
      - sans image  -> (texte: str, [])
      - avec images -> (liste multimodale, [noms d'images attachees])

    chemins_explicites : images ajoutees explicitement (via /paste,
    /add-image) en plus de celles detectees dans le texte.

    Si des chemins sont detectes mais qu'aucune image n'a pu etre encodee,
    on retombe sur le texte simple.
    """
    chemins = extraire_chemins_images(texte)
    for chemin in (chemins_explicites or []):
        if chemin and chemin not in chemins:
            chemins.append(chemin)
    if not chemins:
        return texte, []

    blocs = [{"type": "text", "text": texte}]
    attachees = []
    for chemin in chemins:
        uri = encoder_image(chemin)
        if uri:
            blocs.append({"type": "image_url", "image_url": {"url": uri}})
            attachees.append(os.path.basename(chemin))

    if not attachees:
        return texte, []
    return blocs, attachees
