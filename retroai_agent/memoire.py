"""
memoire.py - MEMOIRE PERSISTANTE entre les sessions.

Probleme resolu (demande utilisateur) : chaque conversation repartait de
zero — l'agent ne se "rappelait" d'aucun detail d'une session a l'autre.

Fonctionnement :
    - un fichier local memoire.json (gitignore : donnees perso) contient une
      liste de FAITS courts {texte, date} ;
    - l'outil `remember` permet au MODELE d'y ajouter un fait quand
      l'utilisateur partage une preference, une decision, un detail durable
      ("retiens que je prefere le francais", "mon projet s'appelle X") ;
    - au demarrage de chaque conversation, les faits sont INJECTES dans le
      message systeme -> l'agent se souvient, sans aucun outil a appeler ;
    - /memory permet de voir et d'oublier (tout ou un fait precis).

Volontairement simple : une liste plafonnee (les plus recents gagnent),
pas de base de donnees, pas d'embeddings — la philosophie BAZIZ.IA.
"""

from __future__ import annotations

import json
import os
from datetime import date

FICHIER = "memoire.json"

# Plafond : garde la memoire courte (elle part dans CHAQUE message systeme,
# donc dans chaque appel API). Au-dela, les faits les PLUS ANCIENS sortent.
MAX_FAITS = 50
MAX_TEXTE = 300


def charger(chemin: str = FICHIER) -> list[dict]:
    """Liste des faits memorises ([] si aucun fichier / fichier illisible)."""
    try:
        with open(chemin, encoding="utf-8") as f:
            faits = json.load(f)
        return faits if isinstance(faits, list) else []
    except (OSError, ValueError):
        return []


def _sauver(faits: list[dict], chemin: str) -> None:
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(faits, f, ensure_ascii=False, indent=2)
        f.write("\n")


def ajouter(texte: str, chemin: str = FICHIER) -> str:
    """
    Memorise un fait (appele par l'outil `remember`). Retourne le message a
    renvoyer au modele. Doublon exact ignore ; plafond FIFO applique.
    """
    texte = " ".join(str(texte).split()).strip()
    if not texte:
        return "Error: empty memory."
    texte = texte[:MAX_TEXTE]
    faits = charger(chemin)
    if any(f.get("texte", "").lower() == texte.lower() for f in faits):
        return "Already remembered."
    faits.append({"texte": texte, "date": date.today().isoformat()})
    faits = faits[-MAX_FAITS:]
    try:
        _sauver(faits, chemin)
    except OSError as exc:
        return f"Error: could not save the memory ({exc})."
    return f"Remembered: {texte}"


def oublier(index: int, chemin: str = FICHIER) -> bool:
    """Supprime le fait numero 'index' (1-base, comme affiche). True si OK."""
    faits = charger(chemin)
    if not (1 <= index <= len(faits)):
        return False
    faits.pop(index - 1)
    try:
        _sauver(faits, chemin)
        return True
    except OSError:
        return False


def vider(chemin: str = FICHIER) -> None:
    """Oublie tout."""
    try:
        os.remove(chemin)
    except OSError:
        pass


def texte_pour_prompt(chemin: str = FICHIER) -> str:
    """
    Bloc a injecter dans le message systeme ("" si memoire vide) : c'est lui
    qui fait que l'agent SE SOUVIENT d'une session a l'autre.
    """
    faits = charger(chemin)
    if not faits:
        return ""
    lignes = "\n".join(f"- {f.get('texte', '')}" for f in faits)
    return (
        "MEMORY - facts you saved in past sessions (treat them as true "
        "unless the user contradicts them):\n" + lignes
    )
