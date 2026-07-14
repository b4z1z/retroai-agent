"""
Commande /model : gestion du modele de CHAT.
- Le modele de BASE est celui de la config (nemotron) et il RESTE tant que
  l'utilisateur ne le change pas.
- Un changement s'applique A CHAUD (config.model, relu a chaque appel API)
  ET persiste dans .env (survit aux relances).
- Annuler / choisir le modele courant ne change rien.
"""

from __future__ import annotations

import os

from retroai_agent import main as main_mod
from retroai_agent import ui
from retroai_agent.agent_loop import AgentLoop
from retroai_agent.config import Config


class _FauxClient:
    def chat(self, *a, **k):  # jamais appele dans ces tests
        raise AssertionError("no API call expected")


def _agent(tmp_path, monkeypatch) -> AgentLoop:
    monkeypatch.chdir(tmp_path)
    config = Config(
        api_key="x", base_url="u", model="nvidia/nemotron-3-ultra-550b-a55b",
        enable_thinking=False, shell_timeout=5, auto_safe_commands=False,
        stream=False,
    )
    return AgentLoop(_FauxClient(), config)


def test_changement_applique_a_chaud_et_persiste(tmp_path, monkeypatch):
    agent = _agent(tmp_path, monkeypatch)
    # Le selecteur a fleches renvoie directement un modele de la liste.
    monkeypatch.setattr(ui, "selecteur",
                        lambda *a, **k: "deepseek-ai/deepseek-v4-flash")

    main_mod._menu_modele(agent)

    # A CHAUD : le prochain appel API partira sur le nouveau modele.
    assert agent.config.model == "deepseek-ai/deepseek-v4-flash"
    # PERSISTANT : ecrit dans .env + os.environ (survit aux relances).
    assert os.environ.get("NVIDIA_MODEL") == "deepseek-ai/deepseek-v4-flash"
    assert "NVIDIA_MODEL=deepseek-ai/deepseek-v4-flash" in (
        (tmp_path / ".env").read_text(encoding="utf-8")
    )


def test_esc_annule_sans_repli_numerote(tmp_path, monkeypatch):
    """BUG REEL corrige : Esc dans le selecteur renvoyait None, confondu
    avec 'selecteur indisponible' -> le repli NUMEROTE s'affichait au lieu
    d'annuler. Desormais Esc (ui.ANNULE) annule NET : aucun repli."""
    agent = _agent(tmp_path, monkeypatch)
    monkeypatch.setattr(ui, "selecteur", lambda *a, **k: ui.ANNULE)

    def interdit(invite):
        raise AssertionError("le repli numerote ne doit PAS s'afficher")
    monkeypatch.setattr(ui, "demander_texte", interdit)

    main_mod._menu_modele(agent)

    assert agent.config.model == "nvidia/nemotron-3-ultra-550b-a55b"
    assert not (tmp_path / ".env").exists()


def test_choisir_esc_vs_indisponible(tmp_path, monkeypatch):
    """_choisir : ANNULE -> None direct ; None (indisponible) -> repli."""
    monkeypatch.chdir(tmp_path)
    options = [("a", "Option A"), ("b", "Option B")]

    monkeypatch.setattr(ui, "selecteur", lambda *a, **k: ui.ANNULE)
    monkeypatch.setattr(ui, "demander_texte",
                        lambda invite: (_ for _ in ()).throw(
                            AssertionError("pas de repli sur Esc")))
    assert main_mod._choisir("T", "t", options) is None

    monkeypatch.setattr(ui, "selecteur", lambda *a, **k: None)
    monkeypatch.setattr(ui, "demander_texte", lambda invite: "2")
    assert main_mod._choisir("T", "t", options) == "b"  # repli numerote OK


def test_annulation_ne_change_rien(tmp_path, monkeypatch):
    agent = _agent(tmp_path, monkeypatch)
    monkeypatch.setattr(ui, "selecteur", lambda *a, **k: None)  # Esc / pas de TTY
    # Le repli numerote demande alors une saisie : Enter = garder.
    monkeypatch.setattr(ui, "demander_texte", lambda invite: "")

    main_mod._menu_modele(agent)

    assert agent.config.model == "nvidia/nemotron-3-ultra-550b-a55b"
    assert not (tmp_path / ".env").exists()  # rien ecrit


def test_choisir_le_modele_courant_ne_reecrit_pas(tmp_path, monkeypatch):
    agent = _agent(tmp_path, monkeypatch)
    monkeypatch.setattr(ui, "selecteur",
                        lambda *a, **k: "nvidia/nemotron-3-ultra-550b-a55b")

    main_mod._menu_modele(agent)

    assert agent.config.model == "nvidia/nemotron-3-ultra-550b-a55b"
    assert not (tmp_path / ".env").exists()  # pas d'ecriture inutile


def test_saisie_custom(tmp_path, monkeypatch):
    agent = _agent(tmp_path, monkeypatch)
    monkeypatch.setattr(ui, "selecteur", lambda *a, **k: "__custom__")
    monkeypatch.setattr(ui, "demander_texte",
                        lambda invite: "qwen/qwen3.5-122b-a10b")

    main_mod._menu_modele(agent)

    assert agent.config.model == "qwen/qwen3.5-122b-a10b"
    assert "NVIDIA_MODEL=qwen/qwen3.5-122b-a10b" in (
        (tmp_path / ".env").read_text(encoding="utf-8")
    )


def test_repli_numerote_sans_selecteur(tmp_path, monkeypatch):
    """Sans prompt_toolkit/TTY : choix par numero, comme /image."""
    agent = _agent(tmp_path, monkeypatch)
    monkeypatch.setattr(ui, "selecteur", lambda *a, **k: None)
    monkeypatch.setattr(ui, "demander_texte", lambda invite: "3")  # llama

    main_mod._menu_modele(agent)

    assert agent.config.model == "meta/llama-3.3-70b-instruct"


def test_modele_de_base_en_tete_de_liste():
    """Le modele de BASE de l'app (defaut config) est la 1re option du menu."""
    assert main_mod.MODELES_CHAT[0][0] == "nvidia/nemotron-3-ultra-550b-a55b"
    assert "/model" in ui.NOMS_COMMANDES