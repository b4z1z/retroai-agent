"""
Robustesse aux TOURS VIDES (bug reel : deepseek-v4-flash sous charge renvoie
par intermittence une completion totalement vide -> ni contenu, ni tool_calls,
finish_reason null). Avant, l'agent abandonnait aussitot avec "(empty
response)". Desormais il reessaie jusqu'a MAX_TOURS_VIDES fois : le tour
suivant reussit presque toujours.
"""

from __future__ import annotations

from retroai_agent.agent_loop import AgentLoop
from retroai_agent.config import Config


class _FauxClient:
    """Renvoie une sequence de reponses fixee (aucun reseau)."""

    def __init__(self, reponses: list[dict]) -> None:
        self._reponses = list(reponses)
        self.appels = 0

    def chat(self, messages, tools=None, on_texte=None):
        self.appels += 1
        return self._reponses.pop(0)


def _agent(reponses: list[dict]) -> AgentLoop:
    config = Config(
        api_key="x", base_url="u", model="m",
        enable_thinking=False, shell_timeout=5, auto_safe_commands=False,
        stream=False,
    )
    return AgentLoop(_FauxClient(reponses), config)


def _vide() -> dict:
    """Tour degenere : pas de contenu, pas d'outil, finish_reason null."""
    return {"choices": [{"message": {"role": "assistant", "content": ""},
                         "finish_reason": None}]}


def _final(texte: str = "Voici le plan.") -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": texte},
                         "finish_reason": "stop"}]}


def test_reessaie_apres_tours_vides_puis_reussit(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    agent = _agent([_vide(), _vide(), _final("Reponse reelle.")])

    resultat = agent.envoyer("ameliore le projet aether")

    # La vraie reponse finit par sortir, pas un "(empty response)".
    assert resultat == "Reponse reelle."
    # Les 2 tours vides ne sont PAS enregistres dans l'historique.
    assistants = [m for m in agent.historique if m.get("role") == "assistant"]
    assert len(assistants) == 1
    assert assistants[0]["content"] == "Reponse reelle."
    # 3 appels API au total (2 vides retentes + 1 reussi).
    assert agent.client.appels == 3


def test_abandonne_avec_message_clair_si_toujours_vide(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Plus de tours vides que la limite -> message d'aide explicite.
    vides = [_vide() for _ in range(AgentLoop.MAX_TOURS_VIDES + 1)]
    agent = _agent(vides)

    resultat = agent.envoyer("salut")

    assert "empty response" in resultat.lower()
    assert "NVIDIA_MODEL" in resultat  # dit QUOI faire
    # On a bien tente MAX_TOURS_VIDES + 1 fois avant d'abandonner.
    assert agent.client.appels == AgentLoop.MAX_TOURS_VIDES + 1
