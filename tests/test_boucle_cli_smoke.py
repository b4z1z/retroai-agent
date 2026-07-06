"""
Test de fumee bout-en-bout : verifie que boucle_cli() (point d'entree reel de
l'app) s'enchaine sans planter au tout premier lancement -> tuto automatique
-> puis quitte proprement, sans qu'aucun element du branchage /continue,
/sessions, /new, /tuto ne fasse planter l'import ou l'appel.
"""

from retroai_agent import main as m
from retroai_agent.agent_loop import AgentLoop
from retroai_agent.api_client import ApiClient
from retroai_agent.config import Config


def test_premier_lancement_puis_sortie_immediate(tmp_path, monkeypatch, capsys):
    """
    Simule : app jamais lancee avant (pas de marqueur tuto) -> le tuto se
    joue (et se termine tout seul, stdin vide -> EOFError -> skip gere par
    ui.pause) -> puis l'utilisateur quitte (Ctrl-D des la 1ere invite).
    Aucune exception ne doit remonter.
    """
    monkeypatch.chdir(tmp_path)

    config = Config(
        api_key="x", base_url="u", model="m",
        enable_thinking=False, shell_timeout=5, auto_safe_commands=False,
    )
    agent = AgentLoop(ApiClient(config), config)

    # Des l'invite (apres le tuto), l'utilisateur fait Ctrl-D -> quitte.
    monkeypatch.setattr(m.ui, "lire_saisie", lambda: (_ for _ in ()).throw(EOFError))

    m.boucle_cli(agent, "m", pseudo="")  # ne doit lever AUCUNE exception

    sortie = capsys.readouterr().out
    assert "Welcome to BAZIZ.IA" in sortie  # le tuto a bien demarre


def test_lancement_avec_commandes_sessions_puis_sortie(tmp_path, monkeypatch, capsys):
    """
    Variante plus poussee : le tuto est deja marque comme vu (2e lancement),
    l'utilisateur tape /sessions (aucune session -> message vide) puis /new
    puis quitte. Verifie l'enchainement complet des commandes sans crash.
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / "tuto_complete.json").write_text('{"complete": true}', encoding="utf-8")

    config = Config(
        api_key="x", base_url="u", model="m",
        enable_thinking=False, shell_timeout=5, auto_safe_commands=False,
    )
    agent = AgentLoop(ApiClient(config), config)

    saisies = iter(["/sessions", "/new", "/help"])

    def _lire_saisie():
        try:
            return next(saisies)
        except StopIteration:
            raise EOFError

    monkeypatch.setattr(m.ui, "lire_saisie", _lire_saisie)

    m.boucle_cli(agent, "m", pseudo="")  # ne doit lever AUCUNE exception

    sortie = capsys.readouterr().out
    assert "No saved sessions yet" in sortie
    assert "Available commands" in sortie
