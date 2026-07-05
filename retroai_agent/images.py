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

# Reduction des grandes images avant envoi : si la plus grande dimension
# depasse cette valeur (pixels), on redimensionne (via Pillow si dispo).
# Gain : moins de base64 -> messages plus legers, moins de tokens, plus rapide.
MAX_DIMENSION = 1568


def _est_url(token: str) -> bool:
    """Vrai si le token est une URL d'image distante (http/https)."""
    return token.startswith("http://") or token.startswith("https://")


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
    Retourne la liste des images mentionnees dans le texte. On retient :
      - les URLs http(s) avec une extension d'image connue ;
      - les chemins locaux pointant vers un fichier reel (os.path.isfile).
    """
    chemins = []
    for token in texte.split():
        chemin = _nettoyer(token)
        if not chemin:
            continue
        ext = os.path.splitext(chemin)[1].lower()
        if ext not in MIME_PAR_EXTENSION:
            continue
        if _est_url(chemin) or os.path.isfile(chemin):
            chemins.append(chemin)
    return chemins


def _reduire_si_grande(chemin: str) -> tuple[bytes, str] | None:
    """
    Si Pillow est dispo ET que l'image depasse MAX_DIMENSION, la redimensionne
    et renvoie (octets_reduits, mime). Sinon renvoie None (-> on lira le
    fichier brut). Echec silencieux : on retombe sur le fichier d'origine.
    """
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        import io
        with Image.open(chemin) as img:
            if max(img.size) <= MAX_DIMENSION:
                return None  # deja assez petite, pas la peine de re-encoder
            img.thumbnail((MAX_DIMENSION, MAX_DIMENSION))
            tampon = io.BytesIO()
            # JPEG = bien plus leger pour une photo ; mais il ne gere pas la
            # transparence -> on garde PNG si l'image a un canal alpha.
            if img.mode in ("RGBA", "LA", "P"):
                img.convert("RGBA").save(tampon, format="PNG", optimize=True)
                return tampon.getvalue(), "image/png"
            img.convert("RGB").save(tampon, format="JPEG", quality=85)
            return tampon.getvalue(), "image/jpeg"
    except Exception:
        return None


def encoder_image(chemin: str) -> str | None:
    """
    Transforme une image en quelque chose d'envoyable a l'API :
      - URL distante (http/https) -> renvoyee telle quelle (l'API la recupere) ;
      - fichier local -> data-URI base64 (reduit avant si trop grand), ou None
        en cas d'echec (illisible, trop gros...).
    """
    # URL distante : pas d'encodage, on passe l'URL directement.
    if _est_url(chemin):
        return chemin

    # Tentative de reduction (Pillow) pour alleger les grandes images.
    reduit = _reduire_si_grande(chemin)
    if reduit is not None:
        donnees, mime = reduit
    else:
        try:
            if os.path.getsize(chemin) > MAX_OCTETS:
                return None
            with open(chemin, "rb") as f:
                donnees = f.read()
        except OSError:
            return None
        ext = os.path.splitext(chemin)[1].lower()
        mime = MIME_PAR_EXTENSION.get(ext, "image/png")

    # Filet de securite : meme apres reduction, on refuse l'enorme.
    if len(donnees) > MAX_OCTETS:
        return None
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
        racine.wm_attributes("-topmost", True) # passe au premier plan
        racine.update()                        # applique avant d'ouvrir
        try:
            racine.focus_force()               # evite le dialogue cache derriere
        except Exception:
            pass
        chemin = filedialog.askopenfilename(
            parent=racine,
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


def alleger_pour_disque(historique: list[dict]) -> list[dict]:
    """
    Renvoie une COPIE de l'historique allegee pour la sauvegarde sur disque.

    Les data-URIs base64 (souvent plusieurs Mo) sont remplaces par une note
    texte courte -> session_history.json reste petit et lisible. Les URLs
    distantes (deja courtes) sont conservees telles quelles. L'historique en
    memoire n'est PAS modifie (l'image reste visible le temps de la session).
    """
    copie: list[dict] = []
    for message in historique:
        contenu = message.get("content")
        if not isinstance(contenu, list):
            copie.append(message)  # texte simple : rien a alleger
            continue

        blocs = []
        for bloc in contenu:
            url = (bloc.get("image_url") or {}).get("url", "") \
                if isinstance(bloc, dict) and bloc.get("type") == "image_url" else ""
            if url.startswith("data:"):
                blocs.append({"type": "text", "text": "[image omitted from saved history]"})
            else:
                blocs.append(bloc)
        nouveau = dict(message)
        nouveau["content"] = blocs
        copie.append(nouveau)
    return copie
