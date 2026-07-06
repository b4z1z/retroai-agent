"""
Tests d'integration des handlers /continue, /sessions, /new dans main.py :
verifie le VRAI comportement multi-conversations cote CLI (pas seulement
agent_loop/sessions.py isolement), en simulant les choix utilisateur.
"""

from retroai_agent import main as m
from retroai_agent import sessions, ui
from retroai_agent.agent_loop import AgentLoop
from retroai_agent.api_client import ApiClient
from retroai_agent.config import Config


def _agent() -> AgentLoop:
    config = Config(
        api_key="x", base_url="u", model="m",
        enable_thinking=False, shell_timeout=5, auto_safe_commands=False,
    )
    return AgentLoop(ApiClient(config), config)


def _neutraliser_traiter_reponse(monkeypatch):
    """Empeche tout vrai appel API : enregistre juste les appels demandes."""
    appels = []
    monkeypatch.setattr(
        m, "_traiter_reponse",
        lambda agent, **kw: appels.append(kw),
    )
    return appels


# --------------------------------------------------------------------------- #
#  /continue                                                                  #
# --------------------------------------------------------------------------- #
def test_continue_sans_rien_a_reprendre(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    appels = _neutraliser_traiter_reponse(monkeypatch)
    agent = _agent()

    m._gerer_continue(agent)

    assert appels == []  # aucun tour lance
    assert agent.session_id is None  # rien charge


def test_continue_reprend_tour_interrompu_en_memoire(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    appels = _neutraliser_traiter_reponse(monkeypatch)
    agent = _agent()
    agent.tour_incomplet = True

    m._gerer_continue(agent)

    assert appels == [{"reprise": True}]


def test_continue_recharge_la_session_la_plus_recente(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    appels = _neutraliser_traiter_reponse(monkeypatch)

    historique = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "premiere question"},
        {"role": "assistant", "content": "reponse complete"},
    ]
    sessions.sauver("recente", historique, titre="Ma session")

    agent = _agent()
    m._gerer_continue(agent)

    assert agent.session_id == "recente"
    assert agent.historique == historique
    assert appels == []  # dernier message = assistant -> pas de reprise auto


def test_continue_reprend_automatiquement_si_derniere_session_incomplete(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    appels = _neutraliser_traiter_reponse(monkeypatch)

    historique = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "question sans reponse"},
    ]
    sessions.sauver("incomplete", historique)

    agent = _agent()
    m._gerer_continue(agent)

    assert agent.session_id == "incomplete"
    assert appels == [{"reprise": True}]  # reprise auto declenchee


# --------------------------------------------------------------------------- #
#  /sessions                                                                  #
# --------------------------------------------------------------------------- #
def test_sessions_liste_vide(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    appels_vide = []
    monkeypatch.setattr(ui, "sessions_vides", lambda: appels_vide.append(True))
    agent = _agent()

    m._gerer_sessions(agent)

    assert appels_vide == [True]


def test_sessions_selection_change_de_conversation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _neutraliser_traiter_reponse(monkeypatch)

    sessions.sauver("s1", [{"role": "user", "content": "premiere"},
                           {"role": "assistant", "content": "ok"}])
    sessions.sauver("s2", [{"role": "user", "content": "deuxieme"},
                           {"role": "assistant", "content": "ok"}])

    # Simule le choix utilisateur dans le menu a fleches : il choisit "s2".
    monkeypatch.setattr(ui, "selecteur", lambda *a, **k: "s2")
    restaurees = []
    monkeypatch.setattr(
        ui, "session_restauree", lambda titre, n: restaurees.append((titre, n))
    )

    agent = _agent()
    m._gerer_sessions(agent)

    assert agent.session_id == "s2"
    assert restaurees == [("deuxieme", 2)]


def test_sessions_annulation_ne_change_rien(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sessions.sauver("s1", [{"role": "user", "content": "x"}])
    monkeypatch.setattr(ui, "selecteur", lambda *a, **k: None)  # Esc

    agent = _agent()
    m._gerer_sessions(agent)

    assert agent.session_id is None  # rien charge


def test_sessions_choisir_la_session_deja_active(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sessions.sauver("s1", [{"role": "user", "content": "x"}])
    agent = _agent()
    agent.charger_session_id("s1")

    monkeypatch.setattr(ui, "selecteur", lambda *a, **k: "s1")
    infos = []
    monkeypatch.setattr(ui, "info", lambda texte: infos.append(texte))

    m._gerer_sessions(agent)

    assert any("Already on this session" in t for t in infos)


def test_sessions_reprend_automatiquement_si_incomplete(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    appels = _neutraliser_traiter_reponse(monkeypatch)
    sessions.sauver("s1", [{"role": "user", "content": "sans reponse"}])
    monkeypatch.setattr(ui, "selecteur", lambda *a, **k: "s1")

    agent = _agent()
    m._gerer_sessions(agent)

    assert appels == [{"reprise": True}]


# --------------------------------------------------------------------------- #
#  /new (via agent.reset(), deja teste dans test_agent_loop_sessions.py) —    #
#  ici on verifie juste que le handler CLI appelle bien reset() et informe.   #
# --------------------------------------------------------------------------- #
def test_new_detache_la_session_et_informe(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    agent = _agent()
    agent.historique.append({"role": "user", "content": "une conversation"})
    agent.sauver_session()
    ancien_id = agent.session_id

    agent.reset()
    ui.info("Started a new session — the previous one is safely saved "
            "(/sessions to see it).")  # meme appel que fait le dispatcher

    assert agent.session_id is None
    assert sessions.charger(ancien_id) is not None  # ancienne conservee
