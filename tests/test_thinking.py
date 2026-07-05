"""Tests des niveaux de reflexion (/think)."""

from retroai_agent import thinking


def test_low_desactive_le_raisonnement():
    assert not thinking.est_actif("low")
    assert "concisely" in thinking.consigne("low")


def test_les_autres_niveaux_activent_le_raisonnement():
    for niveau in ("medium", "high", "highx", "ultra"):
        assert thinking.est_actif(niveau), niveau


def test_medium_sans_consigne():
    assert thinking.consigne("medium") == ""


def test_ultra_oriente_qualite_du_code():
    consigne = thinking.consigne("ultra")
    assert "CODE QUALITY" in consigne
    assert "runnable" in consigne


def test_niveau_inconnu_retombe_sur_defaut():
    assert thinking.normaliser("bogus") == thinking.DEFAUT
    assert thinking.normaliser("") == thinking.DEFAUT
    assert thinking.normaliser("  ULTRA ") == "ultra"  # casse/espaces toleres


def test_descriptions_completes():
    for niveau in thinking.NIVEAUX:
        assert niveau in thinking.DESCRIPTIONS
