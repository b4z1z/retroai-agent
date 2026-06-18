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
    (r"\brm\s+-[a-z]*r[a-z]*f", "Suppression recursive forcee (rm -rf)"),
    (r"\bmkfs\b", "Formatage de systeme de fichiers (mkfs)"),
    (r"\bdd\b", "Ecriture disque bas niveau (dd)"),
    (r":\(\)\s*\{.*\|.*&\s*\}", "Fork bomb"),
    (r">\s*/dev/sd[a-z]", "Ecriture directe sur un disque (/dev/sdX)"),
    (r"\bchmod\s+-R\b", "Changement recursif de permissions (chmod -R)"),
    (r"\bshutdown\b|\breboot\b", "Arret ou redemarrage de la machine"),
    (r"\bmv\b.*\s+/\b", "Deplacement vers la racine /"),
]


def detecter_danger(commande: str) -> str | None:
    """
    Analyse une commande shell et retourne une description du danger
    si un motif sensible est detecte, sinon None.
    """
    for motif, description in MOTIFS_DANGEREUX:
        if re.search(motif, commande):
            return description
    return None


def demander_confirmation(titre: str, details: str = "", dangereux: bool = False) -> bool:
    """
    Affiche l'action proposee et demande une confirmation y/n.

    Retourne True UNIQUEMENT si l'utilisateur tape explicitement "y" (ou "o").
    Toute autre saisie, y compris Entree seule, retourne False (refus).
    """
    ui.panneau_confirmation(titre, details, dangereux=dangereux)

    try:
        reponse = ui.lire_oui_non("Confirmer ?")
    except (EOFError, KeyboardInterrupt):
        # Pas d'entree disponible ou interruption => on refuse par securite.
        ui.info("→ Refuse (aucune confirmation).")
        return False

    accepte = reponse in ("y", "o", "yes", "oui")
    if accepte:
        ui.succes("→ Accepte.")
    else:
        ui.info("→ Refuse.")
    return accepte
