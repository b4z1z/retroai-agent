"""
tuto.py - Tutoriel terminal interactif (onboarding au 1er lancement).

Guide rapide (~1 minute) en plusieurs ecrans courts pour decouvrir les
commandes et le fonctionnement de BAZIZ.IA. NE FAIT AUCUN APPEL API (100%
hors-ligne, instantane, toujours disponible meme sans cle/reseau).

Se joue automatiquement une seule fois (marque via un fichier local, voir
CHEMIN_MARQUEUR) puis reste accessible a la demande via la commande /tuto.
On peut quitter le tour a tout moment en tapant 'skip' ou via Ctrl+C/Ctrl+D.
"""

from __future__ import annotations

import json
import os

from . import ui


CHEMIN_MARQUEUR = "tuto_complete.json"

# Chaque etape : (titre, lignes de contenu). Volontairement court : le but
# est un tour rapide, pas un manuel complet (/help reste la reference).
ETAPES = [
    ("Welcome to BAZIZ.IA", [
        "BAZIZ.IA is an autonomous terminal agent (any NVIDIA NIM model).",
        "It can read/write files, run shell commands, generate images, and more.",
        "This quick tour takes about a minute — replay it anytime with /tuto.",
    ]),
    ("Talking to the agent", [
        "Just type your request at the prompt and press Enter.",
        'Example: "list the files in this folder and summarize them".',
    ]),
    ("Slash commands: sessions", [
        "/continue    resume an interrupted task, or your last session",
        "/sessions    list all saved conversations and switch between them",
        "/new         start a brand-new session (the old one stays saved)",
    ]),
    ("Slash commands: files & images", [
        "/add-file      attach a file's content for the agent to analyze",
        "/create-image  generate an image from a text description",
        "/add-image, /paste   send an existing image for the agent to look at",
        "/image         choose the image generation model (FLUX / Nano Banana)",
    ]),
    ("Approval modes", [
        "normal              every file write / command is confirmed (default)",
        "auto-accept edits   file writes run without asking",
        "plan                read-only: the agent only plans, changes nothing",
        "auto-accept all     nothing is confirmed — use with care",
        "",
        "At the main prompt: press Shift+Tab, or type /mode, to switch.",
        "During a (y/n) confirmation: type 'm' (or Shift+Tab) right there.",
        "('m' alone only works during a confirmation — at the main prompt,",
        " anything you type is a real message sent to the agent.)",
    ]),
    ("Reasoning effort — /think", [
        "low · medium · high · highx · ultra — how hard the model thinks.",
        "'ultra' is tuned for the best code quality (slower, more thorough).",
    ]),
    ("You're all set!", [
        "Type /help anytime to see the full list of commands.",
        "Type /tuto to replay this tour whenever you like.",
    ]),
]


def _deja_vu(chemin: str = CHEMIN_MARQUEUR) -> bool:
    """Vrai si le tutoriel a deja ete montre au moins une fois."""
    return os.path.exists(chemin)


def _marquer_vu(chemin: str = CHEMIN_MARQUEUR) -> None:
    """Enregistre que le tutoriel a ete montre (echec silencieux si impossible)."""
    try:
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump({"complete": True}, f)
    except OSError:
        pass


def jouer(force: bool = False, chemin_marqueur: str = CHEMIN_MARQUEUR) -> None:
    """
    Joue le tutoriel etape par etape.

    - Au tout premier lancement (force=False) : ne joue que s'il n'a jamais
      ete vu ; marque comme vu DES LE DEBUT (pas seulement a la fin), pour
      ne jamais re-harceler l'utilisateur meme s'il quitte au milieu.
    - Avec force=True (commande /tuto) : le rejoue toujours, sans toucher
      au marqueur (une relecture volontaire ne doit rien changer d'autre).
    """
    if not force and _deja_vu(chemin_marqueur):
        return
    if not force:
        _marquer_vu(chemin_marqueur)

    total = len(ETAPES)
    for i, (titre, lignes) in enumerate(ETAPES, start=1):
        ui.panneau_info(titre, lignes, etape=f"Step {i}/{total}")
        try:
            reponse = ui.pause()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if "skip" in reponse:
            return
