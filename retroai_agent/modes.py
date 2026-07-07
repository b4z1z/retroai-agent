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

# Alias en langage naturel -> constante canonique. Necessaire car les
# messages affiches a l'utilisateur (astuce_modes, tuto) citent des mots
# comme "all" ou "edits" (repris des LABELS, ex. "auto-accept edits") : sans
# ces alias, taper exactement ce qui est suggere echouait silencieusement
# (traite comme un refus a une confirmation, ou "Unknown mode" pour /mode).
#
# ATTENTION : PAS d'alias a une seule lettre (ex. "n", "p") : "n" DOIT rester
# reserve au refus d'une confirmation (y/n). Un alias "n"->normal a ete teste
# puis retire immediatement : il interceptait le refus et re-posait la
# question au lieu de traiter "n" comme "non". Ne pas reintroduire ce risque.
ALIAS = {
    "edit": AUTO_EDIT, "edits": AUTO_EDIT,
    "auto-accept-edits": AUTO_EDIT, "accept-edits": AUTO_EDIT,
    "all": AUTO_ALL,
    "auto-accept-all": AUTO_ALL, "accept-all": AUTO_ALL,
}

# Etat courant (module-level).
_courant = NORMAL


def courant() -> str:
    """Retourne le mode courant (constante)."""
    return _courant


def label(mode: str | None = None) -> str:
    """Libelle lisible du mode (courant par defaut)."""
    return LABELS.get(mode or _courant, mode or _courant)


def _normaliser(texte: str) -> str:
    """Minuscules, espaces/underscores -> tirets (ex. 'Auto Accept All' -> 'auto-accept-all')."""
    return (texte or "").strip().lower().replace("_", "-").replace(" ", "-")


def definir(mode: str) -> bool:
    """
    Fixe le mode si 'mode' est une constante canonique (normal/auto-edit/
    plan/auto-all) OU un alias naturel reconnu (voir ALIAS, insensible a la
    casse/aux espaces). Retourne True si applique, False sinon (inchange).
    """
    global _courant
    cle = _normaliser(mode)
    if cle in LABELS:
        _courant = cle
        return True
    if cle in ALIAS:
        _courant = ALIAS[cle]
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
