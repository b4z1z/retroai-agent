"""
Memoire persistante entre sessions : l'outil remember sauve des faits dans
memoire.json, et chaque NOUVELLE conversation les recoit dans son message
systeme — l'agent "se rappelle des details" d'une session a l'autre.
"""

from __future__ import annotations

import os

from retroai_agent import memoire
from retroai_agent import tools
from retroai_agent.agent_loop import AgentLoop
from retroai_agent.config import Config

CFG = Config(api_key="x", base_url="u", model="m", enable_thinking=False,
             shell_timeout=5, auto_safe_commands=False)


def test_ajouter_charger_oublier_vider(tmp_path):
    chemin = str(tmp_path / "memoire.json")

    assert memoire.ajouter("Prefere le francais", chemin).startswith("Remembered")
    assert memoire.ajouter("Projet: BAZIZ.IA", chemin).startswith("Remembered")
    # Doublon exact (casse ignoree) -> pas de duplication.
    assert memoire.ajouter("prefere le francais", chemin) == "Already remembered."
    assert len(memoire.charger(chemin)) == 2

    assert memoire.oublier(1, chemin) is True
    assert [f["texte"] for f in memoire.charger(chemin)] == ["Projet: BAZIZ.IA"]
    assert memoire.oublier(99, chemin) is False  # index invalide -> propre

    memoire.vider(chemin)
    assert memoire.charger(chemin) == []
    assert memoire.ajouter("", chemin).startswith("Error")  # vide refuse


def test_plafond_garde_les_plus_recents(tmp_path):
    chemin = str(tmp_path / "memoire.json")
    for i in range(memoire.MAX_FAITS + 10):
        memoire.ajouter(f"fait numero {i}", chemin)
    faits = memoire.charger(chemin)
    assert len(faits) == memoire.MAX_FAITS
    assert faits[-1]["texte"] == f"fait numero {memoire.MAX_FAITS + 9}"
    assert faits[0]["texte"] == "fait numero 10"  # les plus anciens sortis


def test_injection_dans_le_message_systeme(tmp_path, monkeypatch):
    """La nouvelle conversation DEMARRE avec les souvenirs des sessions
    passees (c'est le coeur de la demande utilisateur)."""
    monkeypatch.chdir(tmp_path)
    memoire.ajouter("L'utilisateur s'appelle BAZIZ")

    agent = AgentLoop(client=None, config=CFG)
    agent.reset()

    systeme = agent.historique[0]["content"]
    assert "MEMORY - facts you saved in past sessions" in systeme
    assert "L'utilisateur s'appelle BAZIZ" in systeme


def test_memoire_vide_n_injecte_rien(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    agent = AgentLoop(client=None, config=CFG)
    agent.reset()
    assert "MEMORY - facts you saved" not in agent.historique[0]["content"]


def test_outil_remember_branche(tmp_path, monkeypatch):
    """remember est un outil du COEUR : declare au schema (le modele le
    voit) et route vers memoire.ajouter."""
    monkeypatch.chdir(tmp_path)
    noms = [s["function"]["name"] for s in tools.TOOLS_SCHEMA]
    assert "remember" in noms

    resultat = tools.executer_outil("remember", {"fact": "Aime le foot"}, CFG)
    assert resultat.startswith("Remembered")
    assert os.path.exists("memoire.json")
    assert memoire.charger()[0]["texte"] == "Aime le foot"


def test_memoire_json_est_gitignore():
    racine = os.path.join(os.path.dirname(__file__), "..")
    with open(os.path.join(racine, ".gitignore"), encoding="utf-8") as f:
        assert "memoire.json" in f.read()
