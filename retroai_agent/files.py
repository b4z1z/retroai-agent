"""
files.py - Joindre le contenu d'un fichier au message (/add-file).

Permet a l'utilisateur de "deposer" un fichier (n'importe lequel, du moment
qu'il est lisible comme texte) pour que l'agent l'analyse : on lit son contenu
et on l'injecte dans le message envoye au modele.

A ne pas confondre avec /add-image (images, vision) : ici c'est du TEXTE/CODE.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
import tempfile


# Au-dela de cette taille, on tronque (un enorme fichier gonflerait le contexte).
MAX_CHARS_FICHIER = 100_000


def choisir_fichier_dialogue() -> str | None:
    """
    Ouvre un selecteur de fichier natif (tkinter) pour n'importe quel fichier.
    Retourne le chemin choisi, ou None si annule / interface indisponible.
    Sous Linux, tkinter peut necessiter python3-tk.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        return None
    try:
        racine = tk.Tk()
        racine.withdraw()
        racine.attributes("-topmost", True)
        chemin = filedialog.askopenfilename(title="Choose a file to attach")
        racine.destroy()
        return chemin or None
    except Exception:
        return None


def lire_fichier_texte(chemin: str) -> tuple[str, str]:
    """
    Lit un fichier comme texte. Retourne (contenu, erreur) :
      - succes -> (contenu, "")
      - echec  -> ("", message_d_erreur)
    Tronque au-dela de MAX_CHARS_FICHIER.
    """
    if not chemin or not os.path.isfile(chemin):
        return "", f"File not found: {chemin}"
    try:
        with open(chemin, "r", encoding="utf-8") as f:
            contenu = f.read()
    except UnicodeDecodeError:
        return "", "This looks like a binary file (not readable as text)."
    except OSError as exc:
        return "", f"Read error: {exc}"

    if len(contenu) > MAX_CHARS_FICHIER:
        contenu = (
            contenu[:MAX_CHARS_FICHIER]
            + f"\n\n[... truncated: file > {MAX_CHARS_FICHIER} characters ...]"
        )
    return contenu, ""


def _editeur_par_defaut() -> str:
    """
    Choisit l'editeur a lancer pour /compose : $VISUAL ou $EDITOR si definis,
    sinon notepad (Windows) / nano (Linux/macOS).
    """
    editeur = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if editeur:
        return editeur
    if sys.platform.startswith("win"):
        return "notepad"
    return "nano"


def composer_dans_editeur(contenu_initial: str = "") -> str | None:
    """
    Ouvre un editeur (nano/notepad/$EDITOR) sur un fichier temporaire pour
    que l'utilisateur ecrive/colle un long bloc tranquillement (sans encombrer
    la ligne de saisie). Retourne le texte saisi, "" si vide, ou None si aucun
    editeur n'a pu etre lance.
    """
    editeur = _editeur_par_defaut()
    fd, chemin = tempfile.mkstemp(suffix=".txt", prefix="baziz_compose_")
    try:
        os.close(fd)
        if contenu_initial:
            with open(chemin, "w", encoding="utf-8") as f:
                f.write(contenu_initial)
        try:
            # shlex.split gere un editeur avec arguments (ex. "code -w").
            subprocess.run(shlex.split(editeur) + [chemin])
        except (OSError, ValueError):
            return None  # editeur introuvable / commande invalide
        try:
            with open(chemin, "r", encoding="utf-8") as f:
                return f.read()
        except (OSError, UnicodeDecodeError):
            return ""
    finally:
        try:
            os.remove(chemin)
        except OSError:
            pass


def construire_message_fichier(chemin: str, contenu: str, message: str) -> str:
    """
    Assemble le message envoye a l'agent : un eventuel texte de l'utilisateur,
    puis le nom du fichier et son contenu dans un bloc delimite.
    """
    nom = os.path.basename(chemin)
    entete = message.strip() or "Here is a file for you to look at:"
    return (
        f"{entete}\n\n"
        f"File: {nom} ({len(contenu)} characters)\n"
        f"```\n{contenu}\n```"
    )
