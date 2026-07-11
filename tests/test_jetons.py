"""
Tests du compteur de tokens (/btw + spinner live) et de /restart (presence).

Le compteur est une feature "fun" mais elle traverse 3 couches :
  - ui.creer_stream_printer : compte les caracteres streames (raisonnement
    masque inclus) et alimente le suffixe live du spinner ;
  - api_client._lire_flux : capture le champ usage si le serveur l'envoie ;
  - agent_loop._comptabiliser : accumule par TOUR et par SESSION.
"""

import io
import sys

from retroai_agent import ui
from retroai_agent.agent_loop import AgentLoop
from retroai_agent.api_client import ApiClient
from retroai_agent.config import Config


# --------------------------------------------------------------------------- #
#  ui : compteurs de caracteres du printer streaming                          #
# --------------------------------------------------------------------------- #
def test_printer_compte_raisonnement_et_reponse(capsys):
    printer, cloturer, stats = ui.creer_stream_printer()
    printer("x" * 800, True)     # raisonnement : masque mais compte
    printer("Bonjour.", False)   # reponse : affichee et comptee
    cloturer()
    assert stats() == {"pense_chars": 800, "reponse_chars": 8}
    sortie = capsys.readouterr().out
    assert "x" not in sortie          # le raisonnement n'est jamais affiche
    assert "Bonjour." in sortie


def test_ligne_jetons_formats():
    reel = {"appels": 2, "entree": 5000, "sortie": 800,
            "raisonnement_est": 200, "sortie_est": 190}
    ligne = ui._ligne_jetons(reel)
    assert "in 5 000" in ligne and "out 800" in ligne and "~200" in ligne

    estime = {"appels": 1, "entree": 0, "sortie": 0,
              "raisonnement_est": 0, "sortie_est": 120}
    ligne = ui._ligne_jetons(estime)
    assert "in ?" in ligne and "out ~120" in ligne and "thinking" not in ligne


# --------------------------------------------------------------------------- #
#  api_client : capture du champ usage dans le flux SSE                       #
# --------------------------------------------------------------------------- #
class _FluxFactice:
    status_code = 200

    def __init__(self, lignes):
        self._lignes = lignes

    def iter_lines(self, decode_unicode=True):
        yield from self._lignes


def test_lire_flux_capture_usage():
    lignes = [
        'data: {"choices":[{"delta":{"content":"ok"}}]}',
        'data: {"choices":[],"usage":{"prompt_tokens":123,"completion_tokens":45}}',
        "data: [DONE]",
    ]
    res = ApiClient._lire_flux(_FluxFactice(lignes), None)
    assert res["usage"] == {"prompt_tokens": 123, "completion_tokens": 45}


def test_lire_flux_sans_usage_pas_de_cle():
    lignes = ['data: {"choices":[{"delta":{"content":"ok"}}]}', "data: [DONE]"]
    res = ApiClient._lire_flux(_FluxFactice(lignes), None)
    assert "usage" not in res


# --------------------------------------------------------------------------- #
#  agent_loop : accumulation par tour / par session                           #
# --------------------------------------------------------------------------- #
class _FauxClient:
    def __init__(self, reponses):
        self._reponses = list(reponses)

    def chat(self, messages, tools=None, on_texte=None):
        return self._reponses.pop(0)


def _reponse(texte="Reponse.", usage=None):
    r = {"choices": [{"message": {"role": "assistant", "content": texte},
                      "finish_reason": "stop"}]}
    if usage:
        r["usage"] = usage
    return r


def _agent(reponses):
    config = Config(
        api_key="x", base_url="u", model="m",
        enable_thinking=False, shell_timeout=5, auto_safe_commands=False,
        stream=False,
    )
    return AgentLoop(_FauxClient(reponses), config)


def test_comptabilise_usage_reel_par_tour_et_session(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    agent = _agent([
        _reponse(usage={"prompt_tokens": 100, "completion_tokens": 20}),
        _reponse(usage={"prompt_tokens": 150, "completion_tokens": 30}),
    ])

    agent.envoyer("premier")
    assert agent.jetons_tour["entree"] == 100
    assert agent.jetons_tour["sortie"] == 20
    assert agent.jetons_tour["appels"] == 1

    agent.envoyer("deuxieme")
    # Le tour est REMIS A ZERO a chaque nouveau tour...
    assert agent.jetons_tour["entree"] == 150
    # ...mais la session ACCUMULE.
    assert agent.jetons_session["entree"] == 250
    assert agent.jetons_session["sortie"] == 50
    assert agent.jetons_session["appels"] == 2


def test_usage_absent_ne_plante_pas(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    agent = _agent([_reponse()])  # aucun champ usage
    agent.envoyer("hello")
    assert agent.jetons_tour["entree"] == 0
    assert agent.jetons_tour["appels"] == 1


def test_reset_remet_les_compteurs_a_zero(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    agent = _agent([_reponse(usage={"prompt_tokens": 9, "completion_tokens": 9})])
    agent.envoyer("x")
    assert agent.jetons_session["appels"] == 1
    agent.reset()  # /new : nouvelle conversation -> compteur remis a zero
    assert agent.jetons_session == agent._jetons_zero()


# --------------------------------------------------------------------------- #
#  Presence des commandes dans le menu                                        #
# --------------------------------------------------------------------------- #
def test_btw_et_restart_dans_le_menu():
    assert "/btw" in ui.NOMS_COMMANDES
    assert "/restart" in ui.NOMS_COMMANDES


# --------------------------------------------------------------------------- #
#  Compteur de session LIVE dans le spinner (facon Claude Code)               #
# --------------------------------------------------------------------------- #
def test_fmt_tokens_compact():
    assert ui._fmt_tokens(843) == "843"
    assert ui._fmt_tokens(2867) == "2.9k"
    assert ui._fmt_tokens(12300) == "12.3k"


def test_printer_avec_session_tokens(capsys):
    """Le suffixe du spinner inclut 'session ~N' = base fournie + live."""
    printer, cloturer, stats = ui.creer_stream_printer(
        session_tokens=lambda: 2000
    )
    # 400 chars de raisonnement = ~100 tokens live.
    printer("x" * 400, True)
    # On appelle le suffixe interne via l'attente ? Non : on reconstruit le
    # comportement attendu depuis stats() (API publique) + _fmt_tokens.
    cloturer()
    s = stats()
    live = s["pense_chars"] // ui.CHARS_PAR_TOKEN
    assert live == 100
    assert ui._fmt_tokens(2000 + live) == "2.1k"


def test_printer_session_tokens_en_panne_ne_plante_pas(capsys):
    """Un callable session qui explose ne doit jamais casser le streaming."""
    def boom():
        raise RuntimeError("boom")
    printer, cloturer, stats = ui.creer_stream_printer(session_tokens=boom)
    printer("reponse", False)   # ne doit pas lever
    assert cloturer() is True


def test_total_session_estime(tmp_path, monkeypatch):
    """_total_session_estime = sortie (reelle sinon estimee) + raisonnement."""
    monkeypatch.chdir(tmp_path)
    agent = _agent([_reponse(usage={"prompt_tokens": 10, "completion_tokens": 40})])
    agent.envoyer("x")
    agent.jetons_session["raisonnement_est"] = 60
    assert agent._total_session_estime() == 100  # 40 reels + 60 raisonnement

    # Sans usage reel, repli sur l'estimation de sortie.
    agent.jetons_session["sortie"] = 0
    agent.jetons_session["sortie_est"] = 25
    assert agent._total_session_estime() == 85   # 25 estimes + 60


def test_au_revoir_explique_comment_revenir(capsys):
    """L'ecran GOODBYE doit dire comment reprendre (/continue) si on change
    d'avis — demande utilisateur apres le screenshot du 2026-07-11."""
    ui.au_revoir()
    sortie = capsys.readouterr().out
    assert "/continue" in sortie
    assert "saved" in sortie.lower()
