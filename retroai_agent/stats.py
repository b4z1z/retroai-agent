"""
stats.py - Tableau de bord (/stats) : ce que BAZIZ.IA a fait pour vous.

Tout est DERIVE des fichiers deja presents (aucun nouveau suivi, aucune
telemetrie, rien qui sort de la machine) :
    - sessions/*.json  -> conversations, messages, appels d'outils, volume ;
    - memoire.json     -> faits memorises ;
    - plugins/         -> outils supplementaires installes.

Les tokens sont ESTIMES (~4 caracteres/token, comme le compteur /btw) : les
sessions sur disque ne conservent pas le champ "usage" de l'API.
"""

from __future__ import annotations

import json
import os
from collections import Counter

from . import sessions
from . import memoire

# Meme regle d'estimation que le compteur live du spinner (ui.CHARS_PAR_TOKEN).
CHARS_PAR_TOKEN = 4


def _texte_du_contenu(contenu) -> str:
    """Un contenu peut etre une chaine OU une liste multimodale (texte+image)."""
    if isinstance(contenu, str):
        return contenu
    if isinstance(contenu, list):
        return " ".join(
            bloc.get("text", "")
            for bloc in contenu
            if isinstance(bloc, dict) and bloc.get("type") == "text"
        )
    return ""


def calculer(dossier: str = sessions.DOSSIER_SESSIONS) -> dict:
    """
    Parcourt les sessions sauvegardees et agrege les chiffres du tableau de
    bord. Tolerant : une session illisible est ignoree, jamais d'exception.
    """
    resume = {
        "sessions": 0,
        "messages": 0,
        "messages_utilisateur": 0,
        "appels_outils": 0,
        "outils": Counter(),      # nom d'outil -> nombre d'appels
        "caracteres": 0,
        "premiere": None,         # date de la plus ancienne conversation
        "derniere": None,
        "plus_longue": None,      # (titre, nb_messages)
    }

    for entree in sessions.lister(dossier):
        session = sessions.charger(entree["id"], dossier)
        if not session:
            continue
        historique = session.get("historique") or []
        resume["sessions"] += 1
        resume["messages"] += len(historique)

        for message in historique:
            role = message.get("role")
            if role == "user":
                resume["messages_utilisateur"] += 1
            resume["caracteres"] += len(_texte_du_contenu(message.get("content")))
            for appel in (message.get("tool_calls") or []):
                nom = (appel.get("function") or {}).get("name") or "?"
                resume["outils"][nom] += 1
                resume["appels_outils"] += 1

        cree = session.get("cree") or entree.get("cree")
        maj = session.get("maj") or entree.get("maj")
        if cree and (resume["premiere"] is None or cree < resume["premiere"]):
            resume["premiere"] = cree
        if maj and (resume["derniere"] is None or maj > resume["derniere"]):
            resume["derniere"] = maj

        nb = len(historique)
        if resume["plus_longue"] is None or nb > resume["plus_longue"][1]:
            resume["plus_longue"] = (session.get("titre") or entree["id"], nb)

    resume["tokens_estimes"] = resume["caracteres"] // CHARS_PAR_TOKEN
    resume["souvenirs"] = len(memoire.charger())
    resume["plugins"] = _compter_plugins()
    return resume


def _compter_plugins(dossier: str = "plugins") -> tuple[int, int]:
    """(actifs, desactives) d'apres les fichiers du dossier plugins/."""
    if not os.path.isdir(dossier):
        return (0, 0)
    fichiers = os.listdir(dossier)
    actifs = [
        f for f in fichiers
        if f.endswith(".py") and not f.startswith("_") and f != "README.md"
    ]
    inactifs = [f for f in fichiers if f.endswith(".py.off")]
    return (len(actifs), len(inactifs))


def top_outils(resume: dict, n: int = 5) -> list[tuple[str, int]]:
    """Les n outils les plus utilises (nom, appels)."""
    return resume["outils"].most_common(n)
