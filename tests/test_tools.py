"""Tests de tools.py : write_file (creation dossiers, modes d'approbation)."""

import os
import sys

import pytest

from retroai_agent import modes, safety, tools
from retroai_agent.config import Config


@pytest.fixture(autouse=True)
def _reset_mode():
    """Chaque test part du mode normal et le restaure (etat global)."""
    modes.definir(modes.NORMAL)
    yield
    modes.definir(modes.NORMAL)


@pytest.fixture
def config():
    return Config(
        api_key="x", base_url="u", model="m",
        enable_thinking=True, shell_timeout=5, auto_safe_commands=False,
    )


def test_write_file_cree_les_dossiers_manquants(tmp_path, config, monkeypatch):
    """
    BUG CORRIGE : ecrire dans un NOUVEAU dossier (ex. un nouveau projet)
    echouait auparavant (FileNotFoundError), forcant une commande shell
    (mkdir) que le mode auto-edit ne couvre pas -> cassait le flux "sans
    confirmation". write_file doit desormais creer les dossiers lui-meme.
    """
    monkeypatch.setattr(safety, "demander_confirmation", lambda *a, **k: True)
    chemin = tmp_path / "nouveau_projet" / "sous_dossier" / "fichier.asm"
    resultat = tools._outil_write_file(
        {"path": str(chemin), "content": "mov ax, 1"}, config
    )
    assert "successfully" in resultat
    assert chemin.is_file()
    assert chemin.read_text(encoding="utf-8") == "mov ax, 1"


def test_write_file_dossier_deja_existant_ok(tmp_path, config, monkeypatch):
    monkeypatch.setattr(safety, "demander_confirmation", lambda *a, **k: True)
    chemin = tmp_path / "fichier.txt"  # pas de sous-dossier
    resultat = tools._outil_write_file({"path": str(chemin), "content": "x"}, config)
    assert "successfully" in resultat
    assert chemin.is_file()


def test_write_file_auto_edit_saute_la_confirmation(tmp_path, config, monkeypatch):
    """En mode auto-edit, demander_confirmation ne doit JAMAIS etre appelee."""
    def _echoue(*a, **k):
        raise AssertionError("demander_confirmation appelee alors qu'auto-edit "
                              "aurait du l'eviter")
    monkeypatch.setattr(safety, "demander_confirmation", _echoue)
    modes.definir(modes.AUTO_EDIT)
    chemin = tmp_path / "auto" / "fichier.txt"
    resultat = tools._outil_write_file({"path": str(chemin), "content": "x"}, config)
    assert "successfully" in resultat
    assert chemin.is_file()


def test_write_file_mode_normal_demande_confirmation(tmp_path, config, monkeypatch):
    appele = {"oui": False}

    def _confirme(*a, **k):
        appele["oui"] = True
        return True

    monkeypatch.setattr(safety, "demander_confirmation", _confirme)
    chemin = tmp_path / "fichier.txt"
    tools._outil_write_file({"path": str(chemin), "content": "x"}, config)
    assert appele["oui"] is True


def test_write_file_refus_n_ecrit_rien(tmp_path, config, monkeypatch):
    monkeypatch.setattr(safety, "demander_confirmation", lambda *a, **k: False)
    chemin = tmp_path / "fichier.txt"
    resultat = tools._outil_write_file({"path": str(chemin), "content": "x"}, config)
    assert "cancelled" in resultat.lower()
    assert not chemin.exists()


def test_write_file_mode_plan_bloque_sans_toucher_au_disque(tmp_path, config):
    modes.definir(modes.PLAN)
    chemin = tmp_path / "fichier.txt"
    resultat = tools._outil_write_file({"path": str(chemin), "content": "x"}, config)
    assert "Blocked" in resultat
    assert not chemin.exists()


# --------------------------------------------------------------------------- #
#  REGRESSION - sortie shell accentuee illisible (mojibake) sous Windows :    #
#  cmd.exe ecrit dans le CODEPAGE OEM de la console (souvent cp850), mais     #
#  subprocess.run(text=True) decodait en UTF-8 -> "chemin d'accès" devenait   #
#  "chemin d'accŠs" (0xE8 lu comme 0x160). L'agent voyait alors des messages  #
#  d'erreur illisibles au lieu du vrai message.                              #
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(not sys.platform.startswith("win"), reason="specifique a Windows/cmd.exe")
def test_run_shell_command_accents_corrects_sous_windows(config):
    modes.definir(modes.AUTO_ALL)
    resultat = tools._outil_run_shell_command(
        {"command": "dir /XYZ-inexistant-flag"}, config
    )
    # Le mot "param" (de "paramètre") doit etre suivi du VRAI "è" (U+00E8),
    # pas d'un caractere mojibake comme "Š" (U+0160).
    i = resultat.find("param")
    assert i != -1, resultat
    assert ord(resultat[i + 5]) == 0xE8
