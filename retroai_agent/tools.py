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
from . import modes


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
        return "Error: no path provided."
    if not os.path.exists(path):
        return f"Error: file not found -> {path}"
    if os.path.isdir(path):
        return f"Error: '{path}' is a directory, not a file."

    try:
        with open(path, "r", encoding="utf-8") as f:
            contenu = f.read()
    except UnicodeDecodeError:
        return f"Error: '{path}' looks like a binary file (not readable as text)."
    except OSError as exc:
        return f"Read error: {exc}"

    if len(contenu) > MAX_CHARS_LECTURE:
        contenu = (
            contenu[:MAX_CHARS_LECTURE]
            + f"\n\n[... truncated: file > {MAX_CHARS_LECTURE} characters ...]"
        )
    return contenu


def _outil_write_file(args: dict, config: Config) -> str:
    path = args.get("path", "")
    content = args.get("content", "")
    ui.action_outil("write_file", path)

    if not path:
        return "Error: no path provided."

    # Mode PLAN : lecture seule -> on refuse d'ecrire et on invite a planifier.
    if modes.est_plan():
        return (
            "Blocked: plan mode is active (read-only). Do NOT write files. "
            "Present a step-by-step plan and wait for the user to approve."
        )

    # Apercu pour que l'utilisateur sache ce qu'il valide.
    apercu = content[:300] + ("..." if len(content) > 300 else "")
    details = (
        f"File:    {path}\n"
        f"Size:    {len(content)} characters\n"
        f"Preview:\n{apercu}"
    )

    # Modes auto-edit / auto-all : ecriture auto-approuvee, sinon confirmation.
    if modes.auto_edits():
        ui.info(f"(auto-accept edits — writing {path} without confirmation)")
    elif not safety.demander_confirmation("Write a file", details):
        return "Action cancelled by the user (write_file refused)."

    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except OSError as exc:
        return f"Write error: {exc}"

    return f"File written successfully: {path} ({len(content)} characters)."


def _outil_list_directory(args: dict, config: Config) -> str:
    path = args.get("path") or "."
    ui.action_outil("list_directory", path)

    if not os.path.exists(path):
        return f"Error: directory not found -> {path}"
    if not os.path.isdir(path):
        return f"Error: '{path}' is not a directory."

    try:
        entrees = sorted(os.listdir(path))
    except OSError as exc:
        return f"Directory read error: {exc}"

    if not entrees:
        return f"(Empty directory: {path})"

    lignes = [f"Contents of {path}:"]
    for nom in entrees:
        chemin = os.path.join(path, nom)
        if os.path.isdir(chemin):
            lignes.append(f"  [DIR]  {nom}/")
        else:
            try:
                taille = os.path.getsize(chemin)
            except OSError:
                taille = 0
            lignes.append(f"  [FILE] {nom}  ({taille} bytes)")
    return "\n".join(lignes)


def _outil_run_shell_command(args: dict, config: Config) -> str:
    command = args.get("command", "")
    ui.action_outil("run_shell_command", command)

    if not command:
        return "Error: no command provided."

    # Mode PLAN : lecture seule -> on refuse d'executer et on invite a planifier.
    if modes.est_plan():
        return (
            "Blocked: plan mode is active (read-only). Do NOT run commands. "
            "Present a step-by-step plan and wait for the user to approve."
        )

    # Avertissement renforce si la commande matche un motif dangereux.
    danger = safety.detecter_danger(command)

    # Auto-execution sans confirmation si :
    #  - mode auto-all (TOUT approuve), OU
    #  - option auto_safe_commands ET commande lecture seule sure.
    auto = modes.auto_tout() or (
        config.auto_safe_commands and safety.est_commande_sure(command)
    )

    if auto:
        if modes.auto_tout():
            ui.info("(auto-accept all — running without confirmation)")
        else:
            ui.info("(safe read-only command — running without confirmation)")
    else:
        # CONFIRMATION OBLIGATOIRE (risque eleve / option desactivee).
        details = f"Command: {command}"
        if danger:
            details += f"\n!! WARNING: {danger} !!"
        if not safety.demander_confirmation(
            "Run a shell command", details, dangereux=bool(danger)
        ):
            return "Action cancelled by the user (command refused)."

    try:
        resultat = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=config.shell_timeout,
        )
    except subprocess.TimeoutExpired:
        return f"Error: command interrupted (timeout {config.shell_timeout}s exceeded)."
    except OSError as exc:
        return f"Execution error: {exc}"

    sortie = []
    if resultat.stdout:
        sortie.append("[stdout]\n" + resultat.stdout)
    if resultat.stderr:
        sortie.append("[stderr]\n" + resultat.stderr)
    sortie.append(f"[exit code] {resultat.returncode}")
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
        return f"Error: unknown tool '{nom}'."
    return fonction(args, config)
