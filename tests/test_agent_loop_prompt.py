"""
Tests du prompt systeme : la plateforme decrite doit correspondre a la VRAIE
plateforme d'execution (regression : le prompt disait "Linux terminal" en
dur meme sous Windows, poussant l'agent a utiliser des commandes Unix
invalides sous cmd.exe -> tours perdus, confusion, reponse finale vide).
"""

from retroai_agent import agent_loop


def test_windows_decrit_cmd_exe(monkeypatch):
    monkeypatch.setattr(agent_loop.sys, "platform", "win32")
    texte = agent_loop._description_plateforme()
    assert "Windows" in texte
    assert "cmd.exe" in texte
    assert "dir /s /b" in texte              # alternative Windows valide, suggeree
    # "find -name" est cite mais explicitement signale comme NE marchant PAS.
    assert "find -name" in texte
    assert "do NOT work here" in texte


def test_macos(monkeypatch):
    monkeypatch.setattr(agent_loop.sys, "platform", "darwin")
    texte = agent_loop._description_plateforme()
    assert "macOS" in texte


def test_linux_par_defaut(monkeypatch):
    monkeypatch.setattr(agent_loop.sys, "platform", "linux")
    texte = agent_loop._description_plateforme()
    assert "Linux" in texte


def test_systeme_contient_la_description_plateforme():
    """SYSTEME doit inclure la vraie plateforme (pas 'Linux terminal' en dur)."""
    assert agent_loop._description_plateforme() in agent_loop.SYSTEME


def test_systeme_impose_la_persistance_multi_etapes():
    """Regression : l'agent annoncait un plan en N etapes puis s'arretait apres
    l'etape 1. Le prompt doit explicitement lui dire de NE PAS rendre la main
    entre les etapes et de continuer jusqu'a la fin du plan."""
    s = agent_loop.SYSTEME
    assert "KEEP GOING" in s
    assert "next step" in s.lower()
    # L'exception plan mode (lecture seule) doit rester documentee.
    assert "plan mode" in s.lower()
