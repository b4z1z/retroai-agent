"""
modes.py - Modes d'approbation des actions (inspire de Claude Code).

L'utilisateur cycle entre les modes avec Shift+Tab (ou la commande /mode).
Le mode courant est un etat GLOBAL simple, lu par tools.py (pour decider
s'il faut confirmer / bloquer une action) et par ui.py (pour l'afficher).

Modes :
    - normal     : tout est confirme (defaut, sur).
    - auto-edit  : ecritures de fichiers auto-approuvees ; shell confirme.
    - auto-all   : TOUT auto-approuve (mode "yolo", a utiliser avec prudence).
    - plan       : lecture seule -> aucune ecriture ni commande ; l'agent
                   doit proposer un plan au lieu d'agir.

Securite : le defaut reste 'normal'. Les modes auto sont un choix EXPLICITE
de l'utilisateur (Shift+Tab), jamais actives tout seuls.
"""

from __future__ import annotations


NORMAL = "normal"
AUTO_EDIT = "auto-edit"
AUTO_ALL = "auto-all"
PLAN = "plan"

# Ordre de defilement avec Shift+Tab.
ORDRE = [NORMAL, AUTO_EDIT, PLAN, AUTO_ALL]

# Libelles lisibles (affichage).
LABELS = {
    NORMAL: "normal",
    AUTO_EDIT: "auto-accept edits",
    PLAN: "plan mode",
    AUTO_ALL: "auto-accept all",
}

# Etat courant (module-level).
_courant = NORMAL


def courant() -> str:
    """Retourne le mode courant (constante)."""
    return _courant


def label(mode: str | None = None) -> str:
    """Libelle lisible du mode (courant par defaut)."""
    return LABELS.get(mode or _courant, mode or _courant)


def definir(mode: str) -> bool:
    """Fixe le mode si valide. Retourne True si applique."""
    global _courant
    if mode in LABELS:
        _courant = mode
        return True
    return False


def cycler() -> str:
    """Passe au mode suivant (Shift+Tab) et le retourne."""
    global _courant
    i = ORDRE.index(_courant) if _courant in ORDRE else 0
    _courant = ORDRE[(i + 1) % len(ORDRE)]
    return _courant


# --- Helpers de decision (lus par tools.py) ------------------------------- #
def auto_edits() -> bool:
    """Vrai si les ecritures de fichiers sont auto-approuvees."""
    return _courant in (AUTO_EDIT, AUTO_ALL)


def auto_tout() -> bool:
    """Vrai si TOUT est auto-approuve (y compris le shell)."""
    return _courant == AUTO_ALL


def est_plan() -> bool:
    """Vrai si on est en mode plan (lecture seule, pas d'action)."""
    return _courant == PLAN
