"""
safety.py - Garde-fous et validations des actions sensibles.

Philosophie : SECURISE PAR DEFAUT.
    - Toute action a risque eleve (ecriture fichier, commande shell) DOIT
      passer par une confirmation interactive explicite de l'utilisateur.
    - La reponse par defaut (Entree seule) est TOUJOURS "non".
    - Aucun mode "toujours accepter" n'est propose par defaut.

Ce module ne fait qu'AFFICHER et DEMANDER. Il n'execute rien lui-meme :
ce sont les outils (tools.py) qui agissent, apres avoir recu le feu vert.
"""

from __future__ import annotations

import re

from . import ui


# Motifs de commandes shell jugees particulierement destructrices.
# Leur presence n'interdit pas l'execution, mais declenche un AVERTISSEMENT
# renforce avant la confirmation habituelle.
MOTIFS_DANGEREUX = [
    (r"\brm\s+-[a-z]*r[a-z]*f", "Forced recursive delete (rm -rf)"),
    (r"\bmkfs\b", "Filesystem formatting (mkfs)"),
    (r"\bdd\b", "Low-level disk write (dd)"),
    (r":\(\)\s*\{.*\|.*&\s*\}", "Fork bomb"),
    (r">\s*/dev/sd[a-z]", "Direct write to a disk (/dev/sdX)"),
    (r"\bchmod\s+-R\b", "Recursive permission change (chmod -R)"),
    (r"\bshutdown\b|\breboot\b", "Machine shutdown or reboot"),
    (r"\bmv\b.*\s+/\b", "Move to the root directory /"),
]


# --------------------------------------------------------------------------- #
#  Liste blanche : commandes shell LECTURE SEULE pouvant etre auto-executees  #
#  (uniquement si l'option AUTO_SAFE_COMMANDS est activee, et sous conditions  #
#  strictes verifiees par est_commande_sure()).                               #
# --------------------------------------------------------------------------- #
COMMANDES_SURES = {
    "ls", "pwd", "echo", "cat", "head", "tail", "wc", "date", "whoami",
    "hostname", "df", "du", "uname", "env", "printenv", "which", "file",
    "stat", "tree", "id", "uptime", "free", "ps", "basename", "dirname",
    "realpath", "grep", "find", "cut", "uniq", "nl", "tac", "column",
}

# Caracteres qui peuvent transformer une commande douce en commande dangereuse
# (redirections, pipes, sous-shell, substitution, chainage...).
METACARACTERES_DANGEREUX = set(">|<&;$`(){}\n")

# Flags de "find" qui EXECUTENT ou SUPPRIMENT -> jamais auto.
FIND_FLAGS_DANGEREUX = ("-exec", "-execdir", "-delete", "-fprint", "-fls", "-ok")


def est_commande_sure(commande: str) -> bool:
    """
    Retourne True UNIQUEMENT si la commande peut etre auto-executee sans
    risque : premier mot dans la liste blanche, AUCUN metacaractere
    (>, |, ;, &, $, (), backtick...), et pas de flag dangereux pour find.

    Au moindre doute -> False (on redemandera confirmation).
    """
    if not commande or not commande.strip():
        return False

    # 1. Aucun metacaractere (bloque redirections, pipes, $(...), chainage...).
    if any(c in METACARACTERES_DANGEREUX for c in commande):
        return False

    # 2. Le premier mot doit etre dans la liste blanche (nom simple, pas de /).
    premier = commande.split()[0]
    if premier not in COMMANDES_SURES:
        return False

    # 3. find : refuser les flags qui executent / suppriment.
    if premier == "find":
        bas = commande.lower()
        if any(flag in bas for flag in FIND_FLAGS_DANGEREUX):
            return False

    return True


def detecter_danger(commande: str) -> str | None:
    """
    Analyse une commande shell et retourne une description du danger
    si un motif sensible est detecte, sinon None.
    """
    for motif, description in MOTIFS_DANGEREUX:
        if re.search(motif, commande):
            return description
    return None


def demander_confirmation(
    titre: str, details: str = "", dangereux: bool = False, categorie: str = ""
) -> bool:
    """
    Affiche l'action proposee et demande une confirmation y/n.

    'categorie' ("edit" / "command") permet d'adapter l'astuce sur les modes
    (quel auto-accept sauterait CETTE confirmation).

    Retourne True UNIQUEMENT si l'utilisateur tape explicitement "y" (ou "o").
    Toute autre saisie, y compris Entree seule, retourne False (refus).
    """
    ui.panneau_confirmation(titre, details, dangereux=dangereux)
    # Rappel discret et CONTEXTUEL : quel mode auto sauterait cette confirmation.
    ui.astuce_modes(categorie)

    try:
        reponse = ui.lire_oui_non("Confirm?", categorie=categorie)
    except EOFError:
        # Pas d'entree disponible (stdin ferme) => refus par securite.
        ui.info("→ Refused (no confirmation).")
        return False
    # NB : on NE capture PAS KeyboardInterrupt ici. Ctrl+C sur une confirmation
    # doit STOPPER tout le tour (comme le bouton stop) et non refuser juste
    # cette action puis relancer le modele en boucle. On le laisse remonter.

    accepte = reponse in ("y", "o", "yes", "oui")
    if accepte:
        ui.succes("→ Approved.")
    else:
        ui.info("→ Refused.")
    return accepte
