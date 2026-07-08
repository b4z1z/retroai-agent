"""
Tests d'integration AgentLoop : gestion des tool_calls dont les arguments
sont un JSON mal forme genere par le MODELE lui-meme (bug reel rencontre :
kimi-k2.6 a mal echappe un enorme bloc de code JS dans les arguments de
write_file -> "Invalid \\escape: line 1 column 3292").

Sans fix, la chaine cassee restait stockee telle quelle dans l'historique et
etait renvoyee a l'API a CHAQUE tour suivant -> l'API la rejetait encore et
encore (HTTP 400), empoisonnant la session en PERMANENCE (plus aucun /continue
possible). Le fix remplace les arguments casses par un JSON vide valide des
qu'on detecte l'echec de parsing local.
"""

from __future__ import annotations

import json

from retroai_agent.agent_loop import AgentLoop
from retroai_agent.config import Config


class _FauxClient:
    """Simule ApiClient.chat() : renvoie une sequence de reponses fixee,
    sans aucun appel reseau."""

    def __init__(self, reponses: list[dict]) -> None:
        self._reponses = list(reponses)

    def chat(self, messages, tools=None, on_texte=None):
        return self._reponses.pop(0)


def _agent(reponses: list[dict]) -> AgentLoop:
    config = Config(
        api_key="x", base_url="u", model="m",
        enable_thinking=False, shell_timeout=5, auto_safe_commands=False,
        stream=False,  # simplifie le test : pas besoin de simuler le SSE
    )
    return AgentLoop(_FauxClient(reponses), config)


def _reponse_avec_tool_call_casse() -> dict:
    """Reproduit EXACTEMENT le bug reel : arguments contenant un \\escape
    JSON invalide (\\i n'est pas un escape JSON valide)."""
    arguments_casses = (
        '{"path": "app.js", "content": "/**\\n * HEADER\\n '
        '=========================== */\\inte\\nconst $ = 1;"}'
    )
    return {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "write_file", "arguments": arguments_casses},
                }],
            },
            "finish_reason": "tool_calls",
        }]
    }


def _reponse_finale_sans_outil(texte: str = "Termine.") -> dict:
    return {
        "choices": [{
            "message": {"role": "assistant", "content": texte},
            "finish_reason": "stop",
        }]
    }


def test_arguments_casses_reellement_invalides_localement():
    """Verifie d'abord que le JSON de test reproduit bien une vraie erreur
    de parsing (sinon le test ne teste rien)."""
    arguments_casses = _reponse_avec_tool_call_casse()[
        "choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]
    try:
        json.loads(arguments_casses)
        assert False, "les arguments de test devraient etre invalides"
    except json.JSONDecodeError as exc:
        assert "Invalid" in str(exc) and "escape" in str(exc)


def test_arguments_casses_remplaces_par_json_vide_dans_l_historique(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    agent = _agent([_reponse_avec_tool_call_casse(), _reponse_finale_sans_outil()])

    agent.envoyer("corrige app.js")

    # Retrouve le message assistant qui portait le tool_call casse.
    messages_avec_outils = [
        m for m in agent.historique if m.get("tool_calls")
    ]
    assert len(messages_avec_outils) == 1
    args_stockes = messages_avec_outils[0]["tool_calls"][0]["function"]["arguments"]

    # Les arguments stockes doivent maintenant etre un JSON VALIDE (vide),
    # plus le blob casse original.
    assert args_stockes == "{}"
    json.loads(args_stockes)  # ne leve pas


def test_le_modele_est_informe_de_l_echec_de_parsing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    agent = _agent([_reponse_avec_tool_call_casse(), _reponse_finale_sans_outil()])

    agent.envoyer("corrige app.js")

    resultats = [
        m["content"] for m in agent.historique
        if m.get("role") == "user" and "[Tool result: write_file]" in m.get("content", "")
    ]
    assert len(resultats) == 1
    assert "invalid JSON arguments" in resultats[0]


def test_historique_complet_reste_serialisable_pour_les_tours_suivants(tmp_path, monkeypatch):
    """Le VRAI test de non-regression : apres le fix, tout l'historique (y
    compris l'entree autrefois cassee) doit pouvoir etre renvoye a l'API
    sans jamais re-provoquer la meme erreur -> simule ce que ferait
    requests.post(json=...) sur le tour SUIVANT."""
    monkeypatch.chdir(tmp_path)
    agent = _agent([_reponse_avec_tool_call_casse(), _reponse_finale_sans_outil()])
    agent.envoyer("corrige app.js")

    # Simule le payload du tour suivant : doit etre serialisable, et chaque
    # tool_calls[].function.arguments doit lui-meme rester un JSON valide
    # (c'est PRECISEMENT ce que l'API re-valide et qui plantait avant le fix).
    serialise = json.dumps(agent.historique)  # ne leve jamais (deja le cas avant)
    relu = json.loads(serialise)
    for message in relu:
        for appel in (message.get("tool_calls") or []):
            json.loads(appel["function"]["arguments"])  # ne doit PAS lever


def test_sauvegarde_de_session_ne_replante_plus_non_plus(tmp_path, monkeypatch):
    """L'historique assaini doit aussi se sauvegarder sans souci (le chemin
    qui, avec le blob casse ENCORE present, aurait continue a gonfler le
    fichier de session de plusieurs dizaines de Ko a chaque tour)."""
    monkeypatch.chdir(tmp_path)
    agent = _agent([_reponse_avec_tool_call_casse(), _reponse_finale_sans_outil()])
    agent.envoyer("corrige app.js")

    agent.sauver_session()  # ne leve pas
    from retroai_agent import sessions
    donnees = sessions.charger(agent.session_id)
    assert donnees is not None
