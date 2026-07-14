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
import sys

from .config import Config
from . import safety
from . import ui
from . import modes
from . import corbeille


def _encodage_console() -> str:
    """
    Encodage reellement utilise par le shell natif pour stdout/stderr.

    Sous Windows, subprocess(shell=True) invoque cmd.exe, qui ecrit dans le
    CODEPAGE OEM DE LA CONSOLE (souvent cp850/cp437 sur une machine
    francophone), PAS en UTF-8. subprocess.run(text=True) sans encoding
    explicite decode pourtant en UTF-8 (encodage prefere de Python) -> tout
    accent dans un message d'erreur devient du mojibake (ex. "chemin
    d'accŠs" au lieu de "chemin d'accès" - verifie : 0x160 au lieu de 0xE8).
    Recuperer le VRAI codepage OEM via l'API Windows (GetOEMCP) et decoder
    avec corrige ca. Ailleurs (Linux/macOS), l'encodage prefere convient.
    """
    if sys.platform.startswith("win"):
        try:
            import ctypes
            return f"cp{ctypes.windll.kernel32.GetOEMCP()}"
        except Exception:
            return "cp850"  # repli raisonnable (le plus courant sous Windows)
    import locale
    return locale.getpreferredencoding(False) or "utf-8"


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
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": (
                "Save a SHORT lasting fact to your persistent memory: it "
                "survives across sessions and is shown to you at the start "
                "of every future conversation. Use it when the user shares "
                "a durable preference, decision, name or detail (e.g. "
                "'retiens que...', 'je prefere...', 'mon projet s'appelle "
                "...'). One short sentence per fact."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "fact": {
                        "type": "string",
                        "description": "The fact to remember (one short sentence).",
                    }
                },
                "required": ["fact"],
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

    # Le fichier existe deja -> on montre un DIFF (ce qui change vraiment)
    # plutot qu'un simple apercu du nouveau contenu : l'utilisateur approuve
    # en VOYANT les modifications, pas en devinant. Nouveau fichier -> apercu.
    existant = None
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as f:
                existant = f.read()
        except OSError:
            existant = None

    if existant is not None:
        if existant == content:
            return f"No change: {path} already has exactly this content."
        details = (
            f"File:    {path}  (existing — showing what CHANGES)\n"
            f"{ui.diff_texte(existant, content)}"
        )
    else:
        LIMITE_APERCU = 1500
        apercu = content[:LIMITE_APERCU] + (
            f"\n… (+{len(content) - LIMITE_APERCU} more characters)"
            if len(content) > LIMITE_APERCU else ""
        )
        details = (
            f"File:    {path}  (new file)\n"
            f"Size:    {len(content)} characters, "
            f"{content.count(chr(10)) + 1} lines\n"
            f"Preview:\n{apercu}"
        )

    # Modes auto-edit / auto-all : ecriture auto-approuvee, sinon confirmation.
    if modes.auto_edits():
        ui.info(f"(auto-accept edits — writing {path} without confirmation)")
    elif not safety.demander_confirmation("Write a file", details, categorie="edit"):
        return "Action cancelled by the user (write_file refused)."

    # FILET /undo : on sauve l'etat AVANT d'ecraser (ou on note la creation).
    corbeille.sauvegarder(path)

    try:
        # Cree le(s) dossier(s) parent(s) manquants (meme niveau de risque que
        # l'ecriture elle-meme, deja couvert par la confirmation/auto-edit
        # ci-dessus). Sans ca, ecrire dans un NOUVEAU dossier echoue et force
        # une commande shell (mkdir) -> pas couverte par auto-edit, ce qui
        # cassait l'experience "sans confirmation" au milieu d'une tache.
        dossier = os.path.dirname(path)
        if dossier:
            os.makedirs(dossier, exist_ok=True)
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
            "Run a shell command", details, dangereux=bool(danger),
            categorie="command",
        ):
            return "Action cancelled by the user (command refused)."

    try:
        resultat = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            encoding=_encodage_console(),
            errors="replace",  # ne plante jamais sur un octet imprevu
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
def _outil_remember(args: dict, config: Config) -> str:
    """Memoire persistante : risque FAIBLE (petit fichier local memoire.json,
    plafonne), pas de confirmation — comme read/list."""
    from . import memoire
    fait = args.get("fact", "")
    ui.action_outil("remember", fait[:60])
    return memoire.ajouter(fait)


TOOLS = {
    "read_file": _outil_read_file,
    "write_file": _outil_write_file,
    "list_directory": _outil_list_directory,
    "run_shell_command": _outil_run_shell_command,
    "remember": _outil_remember,
}


def executer_outil(nom: str, args: dict, config: Config) -> str:
    """
    Aiguille vers la bonne fonction d'outil et retourne son resultat (str).
    Outils du COEUR d'abord, puis PLUGINS (plugins.py) en repli. Si l'outil
    n'existe nulle part, message d'erreur (jamais d'exception).
    """
    fonction = TOOLS.get(nom)
    if fonction is None:
        from . import plugins  # import paresseux (plugins importe tools)
        return plugins.executer(nom, args, config)
    return fonction(args, config)
