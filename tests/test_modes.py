"""Tests des modes d'approbation (Shift+Tab / /mode)."""

import pytest

from retroai_agent import modes


@pytest.fixture(autouse=True)
def _reset_mode():
    """Chaque test part du mode normal et le restaure (etat global)."""
    modes.definir(modes.NORMAL)
    yield
    modes.definir(modes.NORMAL)


def test_cycle_ordre_complet():
    assert modes.cycler() == modes.AUTO_EDIT
    assert modes.cycler() == modes.PLAN
    assert modes.cycler() == modes.AUTO_ALL
    assert modes.cycler() == modes.NORMAL  # retour au depart


def test_definir_valide_et_invalide():
    assert modes.definir(modes.PLAN)
    assert modes.courant() == modes.PLAN
    assert not modes.definir("n-existe-pas")
    assert modes.courant() == modes.PLAN  # inchange


def test_normal_ne_couvre_rien():
    assert not modes.auto_edits()
    assert not modes.auto_tout()
    assert not modes.est_plan()


def test_auto_edit_couvre_les_ecritures_seulement():
    modes.definir(modes.AUTO_EDIT)
    assert modes.auto_edits()
    assert not modes.auto_tout()


def test_auto_all_couvre_tout():
    modes.definir(modes.AUTO_ALL)
    assert modes.auto_edits()
    assert modes.auto_tout()


def test_plan_est_lecture_seule():
    modes.definir(modes.PLAN)
    assert modes.est_plan()
    assert not modes.auto_edits()
