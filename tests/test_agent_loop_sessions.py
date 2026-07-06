"""
Tests d'integration AgentLoop <-> sessions.py (multi-conversations) :
sauvegarde automatique (id/titre generes une seule fois), /reset qui
detache la session (au lieu de l'ecraser), et reprise via charger_session_id.
"""

from retroai_agent import sessions
from retroai_agent.agent_loop import AgentLoop
from retroai_agent.api_client import ApiClient
from retroai_agent.config import Config


def _agent() -> AgentLoop:
    config = Config(
        api_key="x", base_url="u", model="m",
        enable_thinking=False, shell_timeout=5, auto_safe_commands=False,
    )
    return AgentLoop(ApiClient(config), config)


def test_session_neuve_sans_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    agent = _agent()
    assert agent.session_id is None
    assert agent.session_titre is None


def test_premiere_sauvegarde_genere_id_et_titre_stables(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    agent = _agent()
    agent.historique.append({"role": "user", "content": "ecris un jeu de snake"})

    agent.sauver_session()
    id1, titre1 = agent.session_id, agent.session_titre
    assert id1 is not None
    assert titre1 == "ecris un jeu de snake"

    # Un 2e tour de la MEME session ne doit PAS changer l'id ni le titre,
    # et doit ecraser le MEME fichier (pas de doublon).
    agent.historique.append({"role": "assistant", "content": "ok !"})
    agent.sauver_session()
    assert agent.session_id == id1
    assert agent.session_titre == titre1
    assert len(sessions.lister()) == 1


def test_reset_detache_la_session_sans_effacer_le_disque(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    agent = _agent()
    agent.historique.append({"role": "user", "content": "premiere conversation"})
    agent.sauver_session()
    ancien_id = agent.session_id

    agent.reset()  # /reset ou /new
    assert agent.session_id is None
    assert agent.session_titre is None

    # L'ancienne session doit encore exister intacte sur disque.
    ancienne = sessions.charger(ancien_id)
    assert ancienne is not None
    assert ancienne["historique"][-1]["content"] == "premiere conversation"

    # Si on envoie un nouveau message puis sauvegarde -> une SESSION DIFFERENTE
    # est creee (l'ancienne n'est pas ecrasee par la nouvelle conversation vide).
    agent.historique.append({"role": "user", "content": "deuxieme conversation"})
    agent.sauver_session()
    assert agent.session_id != ancien_id
    assert len(sessions.lister()) == 2


def test_charger_session_id_restaure_l_etat(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    historique = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "vieux message"},
        {"role": "assistant", "content": "vieille reponse"},
    ]
    sessions.sauver("ancienne-id", historique, titre="Vieux titre")

    agent = _agent()
    assert agent.charger_session_id("ancienne-id") is True
    assert agent.historique == historique
    assert agent.session_id == "ancienne-id"
    assert agent.session_titre == "Vieux titre"
    assert agent.tour_incomplet is False  # toujours remis a False


def test_charger_session_id_inexistante_ne_modifie_rien(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    agent = _agent()
    agent.historique.append({"role": "user", "content": "en cours"})
    avant = list(agent.historique)

    assert agent.charger_session_id("id-qui-n-existe-pas") is False
    assert agent.historique == avant  # inchange
