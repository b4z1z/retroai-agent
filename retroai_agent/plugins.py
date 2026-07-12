"""
plugins.py - Systeme de PLUGINS : ajouter des outils a l'agent SANS toucher
au coeur du logiciel.

Contrat d'un plugin (1 fichier .py dans le dossier plugins/, ~30 lignes) :

    OUTIL = {                     # schema JSON envoye au modele
        "name": "get_weather",
        "description": "...",
        "parameters": {"type": "object", "properties": {...}, "required": [...]},
    }
    DANGEREUX = False             # optionnel (defaut False). True -> l'outil
                                  # passe par la confirmation y/n, comme le shell.
    def executer(args: dict, config) -> str:
        ...retourne le TEXTE que verra le modele...

Regles de robustesse :
    - un plugin CASSE (erreur d'import, contrat invalide) est IGNORE avec un
      message clair au demarrage : il ne plante JAMAIS l'application ;
    - un plugin ne peut pas ECRASER un outil du coeur (collision de nom) ;
    - une exception pendant l'execution devient une chaine "Error: ..."
      renvoyee au modele (meme philosophie que tools.py).

Chargement au DEMARRAGE (main.py appelle activer()). Apres l'ajout d'un
fichier plugin, /restart recharge tout.
"""

from __future__ import annotations

import glob
import importlib.util
import os

from . import safety

DOSSIER = "plugins"

# Etat module : plugins charges (nom -> infos) et erreurs de chargement.
_REGISTRE: dict[str, dict] = {}
_ERREURS: list[str] = []


def _valider(module, fichier: str) -> dict:
    """Verifie le contrat d'un module plugin et retourne ses infos."""
    outil = getattr(module, "OUTIL", None)
    if not isinstance(outil, dict):
        raise ValueError("missing OUTIL dict")
    for cle in ("name", "description", "parameters"):
        if not outil.get(cle):
            raise ValueError(f"OUTIL is missing '{cle}'")
    executer = getattr(module, "executer", None)
    if not callable(executer):
        raise ValueError("missing executer(args, config) function")
    return {
        "nom": outil["name"],
        "description": outil["description"],
        "schema": {"type": "function", "function": outil},
        "dangereux": bool(getattr(module, "DANGEREUX", False)),
        "fichier": fichier,
        "executer": executer,
    }


def charger(dossier: str = DOSSIER) -> tuple[int, list[str]]:
    """
    Scanne dossier/*.py, importe et valide chaque plugin. Remplit le registre
    (vide d'abord : rechargeable). Retourne (nb_charges, erreurs).
    Les fichiers commencant par '_' sont ignores (brouillons, __init__...).
    """
    _REGISTRE.clear()
    _ERREURS.clear()
    if not os.path.isdir(dossier):
        return 0, []
    for chemin in sorted(glob.glob(os.path.join(dossier, "*.py"))):
        nom_fichier = os.path.basename(chemin)
        if nom_fichier.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location(
                f"baziz_plugin_{nom_fichier[:-3]}", chemin
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            infos = _valider(module, chemin)
            if infos["nom"] in _REGISTRE:
                raise ValueError(f"duplicate tool name '{infos['nom']}'")
            _REGISTRE[infos["nom"]] = infos
        except Exception as exc:  # un plugin casse n'arrete JAMAIS le boot
            _ERREURS.append(f"{nom_fichier}: {exc}")
    return len(_REGISTRE), list(_ERREURS)


def activer(dossier: str = DOSSIER) -> tuple[int, list[str]]:
    """
    Charge les plugins ET fusionne leurs schemas dans tools.TOOLS_SCHEMA
    (c'est ce que voit le modele). Idempotent : les schemas plugins
    precedents sont retires avant re-fusion ; une collision avec un outil du
    COEUR (read_file...) est refusee.
    """
    from . import tools  # import paresseux (tools importe deja plugins)

    noms_coeur = set(tools.TOOLS)
    nb, erreurs = charger(dossier)

    # Retire les schemas plugins d'une eventuelle activation precedente.
    tools.TOOLS_SCHEMA[:] = [
        s for s in tools.TOOLS_SCHEMA
        if s["function"]["name"] in noms_coeur
    ]
    for nom in list(_REGISTRE):
        if nom in noms_coeur:
            _ERREURS.append(
                f"{os.path.basename(_REGISTRE[nom]['fichier'])}: "
                f"'{nom}' collides with a core tool"
            )
            del _REGISTRE[nom]
            nb -= 1
            continue
        tools.TOOLS_SCHEMA.append(_REGISTRE[nom]["schema"])
    return nb, list(_ERREURS)


def executer(nom: str, args: dict, config) -> str:
    """
    Execute le plugin 'nom' (appele par tools.executer_outil en repli).
    Confirmation y/n prealable si DANGEREUX (categorie 'command' : couverte
    par le mode auto-all, pas par auto-edit — comme le shell).
    """
    infos = _REGISTRE.get(nom)
    if infos is None:
        return f"Error: unknown tool '{nom}'."
    if infos["dangereux"]:
        details = f"plugin: {nom}\narguments: {args}"
        if not safety.demander_confirmation(
            f"Run plugin '{nom}'", details, categorie="command"
        ):
            return "Refused by user."
    try:
        return str(infos["executer"](args, config))
    except Exception as exc:
        return f"Error: plugin '{nom}' failed: {exc}"


def liste() -> list[dict]:
    """Infos d'affichage pour /plugins (sans les callables)."""
    return [
        {k: infos[k] for k in ("nom", "description", "fichier", "dangereux")}
        for infos in _REGISTRE.values()
    ]


def erreurs() -> list[str]:
    return list(_ERREURS)
