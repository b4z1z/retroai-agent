"""
Historique de SAISIE persistant (fleche HAUT retrouve les messages des
lancements precedents, comme Claude Code). La PromptSession ne se cree que
dans une vraie console -> on teste ici la CONFIGURATION (constantes, imports,
gitignore), pas l'interaction terminal elle-meme.
"""

import os

from retroai_agent import ui


def test_fichier_historique_declare():
    assert ui.FICHIER_HISTORIQUE_SAISIE == "input_history.txt"


def test_imports_prompt_toolkit_historique():
    """Si prompt_toolkit est present, les classes d'historique/suggestion
    doivent etre importees (sinon _obtenir_session leverait NameError et on
    perdrait silencieusement l'auto-completion ET l'historique)."""
    if not ui.PTK_DISPO:  # environnement sans prompt_toolkit : rien a verifier
        return
    assert hasattr(ui, "FileHistory")
    assert hasattr(ui, "AutoSuggestFromHistory")


def test_historique_saisie_est_gitignore():
    """Donnees personnelles : le fichier d'historique ne doit JAMAIS partir
    sur GitHub (meme regle que user_profile.json / sessions/)."""
    racine = os.path.join(os.path.dirname(__file__), "..")
    with open(os.path.join(racine, ".gitignore"), encoding="utf-8") as f:
        assert "input_history.txt" in f.read()
