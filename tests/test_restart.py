"""
Tests de la commande /restart : relance BAZIZ.IA dans un processus Python
NEUF (recharge le code + .env) puis quitte avec le code de sortie de la
nouvelle instance. Aucun vrai processus n'est lance ici (subprocess mocke).
"""

import pytest

from retroai_agent import main as m
from retroai_agent.agent_loop import AgentLoop
from retroai_agent.api_client import ApiClient
from retroai_agent.config import Config


@pytest.fixture(autouse=True)
def _pas_de_vrais_signaux(monkeypatch):
    """Ne modifie jamais le handler SIGINT du processus de test."""
    monkeypatch.setattr(m.signal, "signal", lambda *a, **k: None)


def test_redemarrer_relance_python_m_et_transmet_le_code(monkeypatch):
    appels = {}

    def _faux_call(cmd, *args, **kwargs):
        appels["cmd"] = cmd
        return 7  # code de sortie de la nouvelle instance

    monkeypatch.setattr(m.subprocess, "call", _faux_call)

    with pytest.raises(SystemExit) as exc:
        m._redemarrer()

    # Relance bien "<python> -m retroai_agent.main" (marche quel que soit le
    # mode de lancement d'origine : baziz.ia, python -m, etc.).
    assert appels["cmd"][0] == m.sys.executable
    assert appels["cmd"][1:] == ["-m", "retroai_agent.main"]
    # Et quitte en transmettant le code de sortie de la nouvelle instance.
    assert exc.value.code == 7


def test_dispatch_slash_restart_appelle_le_handler(tmp_path, monkeypatch):
    """Taper /restart a l'invite doit invoquer _redemarrer() (qui quitte)."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "tuto_complete.json").write_text('{"complete": true}',
                                                 encoding="utf-8")

    config = Config(
        api_key="x", base_url="u", model="m",
        enable_thinking=False, shell_timeout=5, auto_safe_commands=False,
    )
    agent = AgentLoop(ApiClient(config), config)

    monkeypatch.setattr(m.ui, "lire_saisie", lambda: "/restart")

    def _faux_redemarrer():
        raise SystemExit(0)

    monkeypatch.setattr(m, "_redemarrer", _faux_redemarrer)

    with pytest.raises(SystemExit):
        m.boucle_cli(agent, "m", pseudo="")


def test_restart_est_documente():
    """/restart doit apparaitre dans le menu ET dans l'aide de l'IA."""
    from retroai_agent import ui, agent_loop
    assert "/restart" in ui.NOMS_COMMANDES
    assert "/restart" in agent_loop.AIDE_LOGICIEL
