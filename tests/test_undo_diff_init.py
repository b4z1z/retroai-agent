"""
Trois filets de securite / contexte :
  - /undo  : corbeille.py sauve l'etat AVANT chaque write_file -> restauration
             (ou suppression si l'agent venait de CREER le fichier) ;
  - DIFF   : ecraser un fichier existant montre ce qui CHANGE (+/-), pas juste
             le nouveau contenu -> l'utilisateur approuve en connaissance ;
  - /init  : BAZIZ.md est injecte au demarrage de chaque conversation.
"""

from __future__ import annotations

import os

from retroai_agent import agent_loop, corbeille, tools, ui
from retroai_agent.agent_loop import AgentLoop
from retroai_agent.config import Config

CFG = Config(api_key="x", base_url="u", model="m", enable_thinking=False,
             shell_timeout=5, auto_safe_commands=False)


# --------------------------------------------------------------------- #
#  /undo                                                                #
# --------------------------------------------------------------------- #
def test_undo_restaure_une_version_ecrasee(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fichier = tmp_path / "code.py"
    fichier.write_text("version 1", encoding="utf-8")

    corbeille.sauvegarder(str(fichier))          # ce que fait write_file
    fichier.write_text("version 2", encoding="utf-8")

    message = corbeille.restaurer(0)
    assert "Restored" in message
    assert fichier.read_text(encoding="utf-8") == "version 1"
    assert corbeille.lister() == []              # entree consommee


def test_undo_supprime_un_fichier_cree(tmp_path, monkeypatch):
    """Annuler la CREATION d'un fichier = le supprimer."""
    monkeypatch.chdir(tmp_path)
    nouveau = tmp_path / "nouveau.txt"

    corbeille.sauvegarder(str(nouveau))          # n'existe pas encore
    nouveau.write_text("contenu", encoding="utf-8")

    message = corbeille.restaurer(0)
    assert "Removed" in message
    assert not nouveau.exists()


def test_undo_en_cascade(tmp_path, monkeypatch):
    """Repeter /undo remonte le temps, ecriture par ecriture."""
    monkeypatch.chdir(tmp_path)
    fichier = tmp_path / "f.txt"
    fichier.write_text("A", encoding="utf-8")
    corbeille.sauvegarder(str(fichier)); fichier.write_text("B", encoding="utf-8")
    corbeille.sauvegarder(str(fichier)); fichier.write_text("C", encoding="utf-8")

    corbeille.restaurer(0)
    assert fichier.read_text(encoding="utf-8") == "B"
    corbeille.restaurer(0)
    assert fichier.read_text(encoding="utf-8") == "A"
    assert corbeille.restaurer(0) is None       # plus rien a annuler


def test_write_file_sauvegarde_avant_ecrasement(tmp_path, monkeypatch):
    """Le vrai outil write_file doit alimenter la corbeille (mode auto-edit
    pour eviter la confirmation interactive)."""
    monkeypatch.chdir(tmp_path)
    from retroai_agent import modes
    monkeypatch.setattr(modes, "auto_edits", lambda: True)
    monkeypatch.setattr(modes, "est_plan", lambda: False)
    (tmp_path / "x.txt").write_text("ancien", encoding="utf-8")

    tools.executer_outil(
        "write_file", {"path": "x.txt", "content": "nouveau"}, CFG)

    assert (tmp_path / "x.txt").read_text(encoding="utf-8") == "nouveau"
    assert len(corbeille.lister()) == 1
    corbeille.restaurer(0)
    assert (tmp_path / "x.txt").read_text(encoding="utf-8") == "ancien"


def test_write_file_contenu_identique_ne_fait_rien(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "y.txt").write_text("pareil", encoding="utf-8")
    resultat = tools.executer_outil(
        "write_file", {"path": "y.txt", "content": "pareil"}, CFG)
    assert "No change" in resultat
    assert corbeille.lister() == []   # rien a annuler : rien n'a change


# --------------------------------------------------------------------- #
#  DIFF                                                                 #
# --------------------------------------------------------------------- #
def test_diff_montre_les_lignes_ajoutees_et_retirees():
    avant = "ligne 1\nligne 2\nligne 3"
    apres = "ligne 1\nligne DEUX\nligne 3\nligne 4"
    diff = ui.diff_texte(avant, apres)
    assert "+2 line(s)" in diff and "-1 line(s)" in diff
    assert "-ligne 2" in diff
    assert "+ligne DEUX" in diff
    assert "+ligne 4" in diff


def test_diff_tronque_les_gros_changements():
    avant = ""
    apres = "\n".join(f"ligne {i}" for i in range(200))
    diff = ui.diff_texte(avant, apres, max_lignes=10)
    assert "more diff lines" in diff


# --------------------------------------------------------------------- #
#  /init (BAZIZ.md)                                                     #
# --------------------------------------------------------------------- #
def test_baziz_md_injecte_dans_le_systeme(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "BAZIZ.md").write_text(
        "# Project\nUn jeu de cartes en Python.", encoding="utf-8")

    agent = AgentLoop(client=None, config=CFG)
    agent.reset()

    systeme = agent.historique[0]["content"]
    assert "PROJECT CONTEXT" in systeme
    assert "Un jeu de cartes en Python." in systeme


def test_sans_baziz_md_rien_n_est_injecte(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    agent = AgentLoop(client=None, config=CFG)
    agent.reset()
    assert "PROJECT CONTEXT" not in agent.historique[0]["content"]


def test_backups_gitignore():
    racine = os.path.join(os.path.dirname(__file__), "..")
    with open(os.path.join(racine, ".gitignore"), encoding="utf-8") as f:
        assert ".baziz_backups" in f.read()
