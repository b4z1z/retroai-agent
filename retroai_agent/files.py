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
        racine.wm_attributes("-topmost", True)
        racine.update()  # applique le -topmost avant d'ouvrir le dialogue
        try:
            racine.focus_force()  # force le focus (sinon dialogue cache derriere)
        except Exception:
            pass
        chemin = filedialog.askopenfilename(
            parent=racine, title="Choose a file to attach"
        )
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
    # Nettoyage : espaces et guillemets autour du chemin (frequents au
    # copier-coller, surtout sous Windows : "C:\\dossier\\fichier.py").
    chemin = (chemin or "").strip().strip('"').strip("'")
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


# Ligne d'instructions placee en tete du fichier temporaire de /compose.
# Tout ce qui est au-dessus (elle comprise) est RETIRE du message envoye.
MARQUEUR_COMPOSE = (
    "=== Write your message BELOW this line. Save and close to send. ==="
)


def composer_dans_editeur(contenu_initial: str = "") -> str | None:
    """
    Ouvre un editeur (notepad/nano/$EDITOR) sur un fichier temporaire pour
    que l'utilisateur ecrive/colle un long bloc tranquillement.

    - Le fichier temp est DEDIE : le fermer ne touche pas aux autres fichiers
      de l'editeur (VS Code : EDITOR="code -w" n'attend que CET onglet).
    - Une ligne d'instructions (MARQUEUR_COMPOSE) est inseree en tete puis
      retiree du resultat.
    - Les fins de ligne Windows (\\r\\n) et un eventuel BOM sont normalises.

    Retourne le texte saisi, "" si vide, ou None si aucun editeur lancable.
    """
    editeur = _editeur_par_defaut()
    fd, chemin = tempfile.mkstemp(suffix=".txt", prefix="baziz_compose_")
    try:
        os.close(fd)
        with open(chemin, "w", encoding="utf-8") as f:
            f.write(MARQUEUR_COMPOSE + "\n" + (contenu_initial or ""))
        try:
            # shlex.split gere un editeur avec arguments (ex. "code -w").
            subprocess.run(shlex.split(editeur) + [chemin])
        except (OSError, ValueError):
            return None  # editeur introuvable / commande invalide
        try:
            # utf-8-sig : avale le BOM que notepad peut ajouter.
            with open(chemin, "r", encoding="utf-8-sig") as f:
                texte = f.read()
        except (OSError, UnicodeDecodeError):
            return ""
        texte = texte.replace("\r\n", "\n").replace("\r", "\n")
        # Retire la ligne d'instructions (et tout ce qui la precede).
        if MARQUEUR_COMPOSE in texte:
            texte = texte.split(MARQUEUR_COMPOSE, 1)[1]
        return texte.strip("\n")
    finally:
        try:
            os.remove(chemin)
        except OSError:
            pass


def construire_message_fichier(chemin: str, contenu: str, message: str) -> str:
    """
    Assemble le message envoye a l'agent : un eventuel texte de l'utilisateur,
    puis le CHEMIN COMPLET du fichier (pour que l'agent puisse l'ecraser avec
    write_file si on lui demande de le modifier) et son contenu.
    """
    chemin_abs = os.path.abspath(chemin)
    entete = message.strip() or "Here is a file for you to look at:"
    return (
        f"{entete}\n\n"
        f"File path: {chemin_abs}\n"
        f"({len(contenu)} characters)\n"
        f"If asked to modify/improve it, save your result with write_file to "
        f"this exact path.\n"
        f"```\n{contenu}\n```"
    )
