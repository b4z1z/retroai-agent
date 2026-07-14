"""
corbeille.py - Filet de securite des ecritures (/undo).

Avant CHAQUE write_file qui ecrase un fichier existant, l'ancienne version
est copiee dans .baziz_backups/ (dossier local, gitignore). La commande
/undo restaure la derniere ecriture — ou n'importe laquelle dans la liste.

Volontairement simple : un dossier + un index JSON, plafonne. Pas de git,
pas de diff binaire : la philosophie BAZIZ.IA.
"""

from __future__ import annotations

import json
import os
import shutil
import time

DOSSIER = ".baziz_backups"
INDEX = os.path.join(DOSSIER, "index.json")

# Plafond : au-dela, les sauvegardes les PLUS ANCIENNES sont supprimees.
MAX_SAUVEGARDES = 30


def _charger_index(dossier: str = DOSSIER) -> list[dict]:
    try:
        with open(os.path.join(dossier, "index.json"), encoding="utf-8") as f:
            entrees = json.load(f)
        return entrees if isinstance(entrees, list) else []
    except (OSError, ValueError):
        return []


def _sauver_index(entrees: list[dict], dossier: str = DOSSIER) -> None:
    try:
        os.makedirs(dossier, exist_ok=True)
        with open(os.path.join(dossier, "index.json"), "w",
                  encoding="utf-8") as f:
            json.dump(entrees, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def sauvegarder(chemin: str, dossier: str = DOSSIER) -> None:
    """
    Copie la version ACTUELLE de 'chemin' dans la corbeille (a appeler AVANT
    de l'ecraser). Un fichier qui n'existe pas encore est enregistre comme
    "creation" (undo = le supprimer). Ne leve JAMAIS : une sauvegarde ratee
    ne doit pas empecher l'ecriture demandee par l'utilisateur.
    """
    try:
        entrees = _charger_index(dossier)
        existait = os.path.isfile(chemin)
        copie = None
        if existait:
            os.makedirs(dossier, exist_ok=True)
            copie = os.path.join(
                dossier, f"{int(time.time() * 1000)}_{os.path.basename(chemin)}")
            shutil.copyfile(chemin, copie)
        entrees.append({
            "chemin": os.path.abspath(chemin),
            "copie": copie,               # None = le fichier n'existait pas
            "date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "creation": not existait,
        })
        # Plafond : on jette les plus anciennes (et leurs copies).
        while len(entrees) > MAX_SAUVEGARDES:
            vieille = entrees.pop(0)
            if vieille.get("copie"):
                try:
                    os.remove(vieille["copie"])
                except OSError:
                    pass
        _sauver_index(entrees, dossier)
    except Exception:
        pass  # jamais bloquant


def lister(dossier: str = DOSSIER) -> list[dict]:
    """Sauvegardes, de la PLUS RECENTE a la plus ancienne."""
    return list(reversed(_charger_index(dossier)))


def restaurer(index: int = 0, dossier: str = DOSSIER) -> str | None:
    """
    Restaure la sauvegarde numero 'index' de lister() (0 = la plus recente).
    Une "creation" est annulee en SUPPRIMANT le fichier cree.
    Retourne un message decrivant l'action, ou None si rien a restaurer.
    L'entree est consommee (retiree de l'index) : /undo repetable en cascade.
    """
    entrees = _charger_index(dossier)
    if not entrees:
        return None
    position = len(entrees) - 1 - index      # index 0 = derniere entree
    if not (0 <= position < len(entrees)):
        return None
    entree = entrees[position]
    chemin = entree["chemin"]
    try:
        if entree.get("creation"):
            if os.path.isfile(chemin):
                os.remove(chemin)
            message = f"Removed {os.path.basename(chemin)} (it was created by me)."
        else:
            copie = entree.get("copie")
            if not copie or not os.path.isfile(copie):
                return None
            shutil.copyfile(copie, chemin)
            try:
                os.remove(copie)
            except OSError:
                pass
            message = f"Restored {os.path.basename(chemin)} to its previous version."
    except OSError as exc:
        return f"Error: could not undo ({exc})."
    entrees.pop(position)
    _sauver_index(entrees, dossier)
    return message
