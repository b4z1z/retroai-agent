"""Tests des modes d'approbation (Shift+Tab / /mode)."""

import io
import sys

import pytest

from retroai_agent import modes, ui


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


# --------------------------------------------------------------------------- #
#  Alias en langage naturel (modes.definir) : "all", "edits", etc. — ce sont  #
#  exactement les mots affiches par astuce_modes()/le tutoriel, ils doivent   #
#  donc fonctionner tels quels quand l'utilisateur les tape.                  #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("texte,attendu", [
    ("all", modes.AUTO_ALL),
    ("ALL", modes.AUTO_ALL),
    (" All ", modes.AUTO_ALL),
    ("auto-accept-all", modes.AUTO_ALL),
    ("auto accept all", modes.AUTO_ALL),
    ("edit", modes.AUTO_EDIT),
    ("edits", modes.AUTO_EDIT),
    ("auto accept edits", modes.AUTO_EDIT),
    ("auto-edit", modes.AUTO_EDIT),   # constante canonique, doit marcher aussi
    ("plan", modes.PLAN),
    ("normal", modes.NORMAL),
])
def test_alias_naturels_reconnus(texte, attendu):
    assert modes.definir(texte) is True
    assert modes.courant() == attendu


@pytest.mark.parametrize("mot", ["n", "y", "yes", "no", "oui", "non", "o", ""])
def test_reponses_oui_non_jamais_interceptees_comme_mode(mot):
    """
    REGRESSION CRITIQUE : un alias 'n' -> normal a brievement existe et
    interceptait le refus d'une confirmation (l'utilisateur ne pouvait plus
    taper 'n' pour refuser). Aucun mot de reponse y/n ne doit JAMAIS etre
    reconnu comme nom de mode, quoi qu'on ajoute plus tard a ALIAS.
    """
    assert modes.definir(mot) is False
    assert modes.courant() == modes.NORMAL  # inchange


# --------------------------------------------------------------------------- #
#  Changement de mode PENDANT une confirmation (taper 'm' / '/mode')          #
#  Doit marcher meme sans Shift+Tab (terminal-independant).                   #
# --------------------------------------------------------------------------- #
def _repondre(entrees: str, invite: str, categorie: str) -> str:
    """Simule la saisie de plusieurs lignes a lire_oui_non (pas un vrai TTY)."""
    ancien = sys.stdin
    sys.stdin = io.StringIO(entrees)
    try:
        return ui.lire_oui_non(invite, categorie=categorie)
    finally:
        sys.stdin = ancien


def test_un_seul_m_couvre_une_confirmation_edit():
    """1 cran ('m') -> auto-edit, qui couvre deja les ecritures -> approuve direct."""
    rep = _repondre("m\n", "Write a file?", "edit")
    assert modes.courant() == modes.AUTO_EDIT
    assert rep == "y"


def test_alias_slash_mode_fonctionne_aussi():
    """'/mode' doit avoir le meme effet que 'm' (alias tape a la confirmation)."""
    rep = _repondre("/mode\n", "Write a file?", "edit")
    assert modes.courant() == modes.AUTO_EDIT
    assert rep == "y"


def test_cycle_jusqu_a_couvrir_une_commande():
    """auto-edit ne couvre PAS les commandes -> il faut cycler jusqu'a auto-all."""
    rep = _repondre("m\nm\nm\n", "Run a shell command?", "command")
    assert modes.courant() == modes.AUTO_ALL
    assert rep == "y"


def test_mode_non_couvrant_repose_la_question():
    """Un cran qui ne couvre pas l'action -> la confirmation est reposee."""
    rep = _repondre("m\nn\n", "Run a shell command?", "command")
    assert modes.courant() == modes.AUTO_EDIT  # cycle applique
    assert rep == "n"                          # la 2e ligne a bien ete lue


def test_reponse_normale_sans_cycler():
    rep = _repondre("y\n", "Write a file?", "edit")
    assert modes.courant() == modes.NORMAL  # inchange
    assert rep == "y"


def test_taper_le_nom_du_mode_directement_bascule_dessus():
    """
    BUG REPRODUIT PUIS CORRIGE : l'utilisateur voit l'astuce ("... (or 'all')")
    et tape logiquement 'all' -> avant le fix, ce n'etait reconnu par rien et
    etait traite comme un REFUS. Doit desormais basculer direct sur ce mode.
    """
    rep = _repondre("all\n", "Write a file?", "edit")
    assert modes.courant() == modes.AUTO_ALL
    assert rep == "y"  # auto-all couvre 'edit' -> approuve tout de suite


def test_taper_edits_bascule_sur_auto_edit():
    rep = _repondre("edits\n", "Write a file?", "edit")
    assert modes.courant() == modes.AUTO_EDIT
    assert rep == "y"


def test_taper_all_ne_couvre_pas_une_commande_a_lui_seul_si_deja_couvert():
    """Sanity check : 'all' couvre AUSSI les commandes (auto-all = tout)."""
    rep = _repondre("all\n", "Run a shell command?", "command")
    assert modes.courant() == modes.AUTO_ALL
    assert rep == "y"


def test_taper_n_reste_un_refus_meme_apres_le_fix_des_alias():
    """Non-regression : 'n' doit TOUJOURS etre un refus, jamais un mode."""
    rep = _repondre("n\n", "Write a file?", "edit")
    assert modes.courant() == modes.NORMAL  # rien n'a change
    assert rep == "n"
