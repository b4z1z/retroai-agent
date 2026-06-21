"""
Tests de config.py : validation de la cle, valeurs par defaut, conversions.
On utilise monkeypatch pour controler les variables d'environnement, et un
dotenv_path inexistant pour ne PAS lire le vrai .env du projet.
"""

import pytest

from retroai_agent import config

_PAS_DE_ENV = "__inexistant__.env"


def test_cle_manquante_leve_systemexit(monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    with pytest.raises(SystemExit):
        config.load_config(dotenv_path=_PAS_DE_ENV)


def test_valeurs_par_defaut(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    for var in ("NVIDIA_MODEL", "NVIDIA_BASE_URL", "SHELL_TIMEOUT",
                "ENABLE_THINKING", "AUTO_SAFE_COMMANDS"):
        monkeypatch.delenv(var, raising=False)

    cfg = config.load_config(dotenv_path=_PAS_DE_ENV)
    assert cfg.api_key == "nvapi-test"
    assert cfg.model == "moonshotai/kimi-k2.6"
    assert cfg.shell_timeout == 30
    assert cfg.enable_thinking is True
    assert cfg.auto_safe_commands is False


def test_conversion_bool_et_int(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    monkeypatch.setenv("ENABLE_THINKING", "false")
    monkeypatch.setenv("SHELL_TIMEOUT", "5")
    monkeypatch.setenv("AUTO_SAFE_COMMANDS", "true")

    cfg = config.load_config(dotenv_path=_PAS_DE_ENV)
    assert cfg.enable_thinking is False
    assert cfg.shell_timeout == 5
    assert cfg.auto_safe_commands is True


def test_timeout_invalide_retombe_sur_defaut(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    monkeypatch.setenv("SHELL_TIMEOUT", "abc")  # pas un entier
    cfg = config.load_config(dotenv_path=_PAS_DE_ENV)
    assert cfg.shell_timeout == 30
