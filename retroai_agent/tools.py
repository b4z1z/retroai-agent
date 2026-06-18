"""
tools.py - Definition (JSON Schema) et implementation des 4 outils.

Ce module contient deux choses :
    1. TOOLS_SCHEMA : la description des outils au format OpenAI/JSON Schema,
       envoyee a l'API pour que le modele sache quels outils existent.
    2. Les fonctions Python qui executent reellement chaque outil, plus un
       dictionnaire TOOLS qui fait le lien "nom d'outil" -> fonction.

Regles de risque (cahier des charges) :
    - read_file / list_directory : risque FAIBLE, pas de confirmation.
    - write_file / run_shell_command : risque ELEVE, confirmation OBLIGATOIRE
      via safety.demander_confirmation().

Chaque fonction retourne TOUJOURS une chaine de caracteres (le resultat
texte qui sera renvoye au modele), meme en cas d'erreur : on ne laisse
jamais une exception remonter et casser la boucle de l'agent.
"""

from __future__ import annotations

import os
import subprocess

from .config import Config
from . import safety
from . import ui


# Limite de taille pour read_file (cahier des charges).
MAX_CHARS_LECTURE = 50_000


# --------------------------------------------------------------------------- #
#  1. Schemas JSON envoyes a l'API                                            #
# --------------------------------------------------------------------------- #
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Lit et retourne le contenu d'un fichier texte.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Chemin du fichier a lire.",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Ecrit (ou ecrase) un fichier avec le contenu fourni. "
                "Demande une confirmation a l'utilisateur."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Chemin du fichier a ecrire.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Contenu a ecrire dans le fichier.",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "Liste les fichiers et dossiers d'un repertoire avec leur taille.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Chemin du repertoire (par defaut: dossier courant).",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell_command",
            "description": (
                "Execute une commande shell et retourne sa sortie. "
                "Demande une confirmation a l'utilisateur."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "La commande shell a executer.",
                    }
                },
                "required": ["command"],
            },
        },
    },
]


# --------------------------------------------------------------------------- #
#  2. Implementation des outils                                               #
#     Signature commune : (args: dict, config: Config) -> str                 #
# --------------------------------------------------------------------------- #
def _outil_read_file(args: dict, config: Config) -> str:
    path = args.get("path", "")
    ui.action_outil("read_file", path)

    if not path:
        return "Erreur : aucun chemin fourni."
    if not os.path.exists(path):
        return f"Erreur : fichier introuvable -> {path}"
    if os.path.isdir(path):
        return f"Erreur : '{path}' est un dossier, pas un fichier."

    try:
        with open(path, "r", encoding="utf-8") as f:
            contenu = f.read()
    except UnicodeDecodeError:
        return f"Erreur : '{path}' semble etre un fichier binaire (illisible en texte)."
    except OSError as exc:
        return f"Erreur de lecture : {exc}"

    if len(contenu) > MAX_CHARS_LECTURE:
        contenu = (
            contenu[:MAX_CHARS_LECTURE]
            + f"\n\n[... tronque : fichier > {MAX_CHARS_LECTURE} caracteres ...]"
        )
    return contenu


def _outil_write_file(args: dict, config: Config) -> str:
    path = args.get("path", "")
    content = args.get("content", "")
    ui.action_outil("write_file", path)

    if not path:
        return "Erreur : aucun chemin fourni."

    # Apercu pour que l'utilisateur sache ce qu'il valide.
    apercu = content[:300] + ("..." if len(content) > 300 else "")
    details = (
        f"Fichier : {path}\n"
        f"Taille  : {len(content)} caracteres\n"
        f"Apercu  :\n{apercu}"
    )

    # CONFIRMATION OBLIGATOIRE (risque eleve).
    if not safety.demander_confirmation("Ecrire un fichier", details):
        return "Action annulee par l'utilisateur (write_file refuse)."

    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except OSError as exc:
        return f"Erreur d'ecriture : {exc}"

    return f"Fichier ecrit avec succes : {path} ({len(content)} caracteres)."


def _outil_list_directory(args: dict, config: Config) -> str:
    path = args.get("path") or "."
    ui.action_outil("list_directory", path)

    if not os.path.exists(path):
        return f"Erreur : repertoire introuvable -> {path}"
    if not os.path.isdir(path):
        return f"Erreur : '{path}' n'est pas un repertoire."

    try:
        entrees = sorted(os.listdir(path))
    except OSError as exc:
        return f"Erreur de lecture du repertoire : {exc}"

    if not entrees:
        return f"(Repertoire vide : {path})"

    lignes = [f"Contenu de {path} :"]
    for nom in entrees:
        chemin = os.path.join(path, nom)
        if os.path.isdir(chemin):
            lignes.append(f"  [DIR]  {nom}/")
        else:
            try:
                taille = os.path.getsize(chemin)
            except OSError:
                taille = 0
            lignes.append(f"  [FILE] {nom}  ({taille} octets)")
    return "\n".join(lignes)


def _outil_run_shell_command(args: dict, config: Config) -> str:
    command = args.get("command", "")
    ui.action_outil("run_shell_command", command)

    if not command:
        return "Erreur : aucune commande fournie."

    # Avertissement renforce si la commande matche un motif dangereux.
    danger = safety.detecter_danger(command)
    details = f"Commande : {command}"
    if danger:
        details += f"\n!! ATTENTION : {danger} !!"

    # CONFIRMATION OBLIGATOIRE dans 100% des cas (risque eleve).
    if not safety.demander_confirmation(
        "Executer une commande shell", details, dangereux=bool(danger)
    ):
        return "Action annulee par l'utilisateur (commande refusee)."

    try:
        resultat = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=config.shell_timeout,
        )
    except subprocess.TimeoutExpired:
        return f"Erreur : commande interrompue (timeout {config.shell_timeout}s depasse)."
    except OSError as exc:
        return f"Erreur d'execution : {exc}"

    sortie = []
    if resultat.stdout:
        sortie.append("[stdout]\n" + resultat.stdout)
    if resultat.stderr:
        sortie.append("[stderr]\n" + resultat.stderr)
    sortie.append(f"[code de sortie] {resultat.returncode}")
    return "\n".join(sortie)


# --------------------------------------------------------------------------- #
#  3. Table de routage : nom d'outil -> fonction                              #
# --------------------------------------------------------------------------- #
TOOLS = {
    "read_file": _outil_read_file,
    "write_file": _outil_write_file,
    "list_directory": _outil_list_directory,
    "run_shell_command": _outil_run_shell_command,
}


def executer_outil(nom: str, args: dict, config: Config) -> str:
    """
    Aiguille vers la bonne fonction d'outil et retourne son resultat (str).
    Si l'outil n'existe pas, retourne un message d'erreur (jamais d'exception).
    """
    fonction = TOOLS.get(nom)
    if fonction is None:
        return f"Erreur : outil inconnu '{nom}'."
    return fonction(args, config)
