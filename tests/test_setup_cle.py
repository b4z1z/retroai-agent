"""
Assistant de premiere configuration (setup_cle) : un nouvel utilisateur SANS
cle est guide (etapes NVIDIA, navigateur, saisie terminal) et la cle finit
AUTOMATIQUEMENT dans .env — plus besoin d'editer le fichier a la main.
"""

from __future__ import annotations

import os

from retroai_agent import setup_cle


def test_cle_plausible():
    assert setup_cle.cle_plausible("nvapi-" + "x" * 60)
    assert not setup_cle.cle_plausible("sk-abcdef1234567890abcdef1234567890")
    assert not setup_cle.cle_plausible("nvapi-court")  # trop courte
    assert not setup_cle.cle_plausible("")


def test_refuse_hors_terminal_interactif(monkeypatch):
    """En CI/tests/pipe (pas un vrai terminal), l'assistant ne se lance pas :
    l'appelant retombe sur le message d'erreur classique."""
    monkeypatch.setattr(setup_cle.sys.stdin, "isatty", lambda: False)
    assert setup_cle.assistant_cle() is None


def _interactif(monkeypatch, reponses):
    """Prepare un faux terminal interactif + une sequence de saisies."""
    monkeypatch.setattr(setup_cle.sys.stdin, "isatty", lambda: True)
    file_reponses = list(reponses)
    monkeypatch.setattr(
        setup_cle.ui, "demander_texte", lambda invite: file_reponses.pop(0)
    )
    monkeypatch.setattr(setup_cle.ui, "panneau_setup_cle", lambda url: None)
    # Jamais de vrai navigateur pendant les tests.
    monkeypatch.setattr(setup_cle.webbrowser, "open", lambda url: True)


def test_cle_valide_ecrite_dans_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    bonne_cle = "nvapi-" + "a" * 60
    _interactif(monkeypatch, ["n", bonne_cle])  # pas de navigateur, puis cle
    monkeypatch.setattr(setup_cle, "verifier_cle_en_ligne", lambda c: True)

    resultat = setup_cle.assistant_cle(chemin_env=str(tmp_path / ".env"))

    assert resultat == bonne_cle
    contenu = (tmp_path / ".env").read_text(encoding="utf-8")
    assert f"NVIDIA_API_KEY={bonne_cle}" in contenu       # ecrite dans .env
    assert os.environ.get("NVIDIA_API_KEY") == bonne_cle  # effet immediat


def test_mauvaise_forme_puis_bonne_cle(tmp_path, monkeypatch):
    """Une saisie qui ne ressemble pas a une cle -> nouvel essai, sans appel
    reseau inutile ; la 2e saisie (valide) est enregistree."""
    monkeypatch.chdir(tmp_path)
    bonne_cle = "nvapi-" + "b" * 60
    _interactif(monkeypatch, ["n", "pas-une-cle", bonne_cle])
    appels = []

    def verif(cle):
        appels.append(cle)
        return True

    monkeypatch.setattr(setup_cle, "verifier_cle_en_ligne", verif)
    resultat = setup_cle.assistant_cle(chemin_env=str(tmp_path / ".env"))

    assert resultat == bonne_cle
    assert appels == [bonne_cle]  # la forme invalide n'a PAS ete testee en ligne


def test_cle_rejetee_par_nvidia_puis_abandon(tmp_path, monkeypatch):
    """Cle refusee (401) a chaque essai -> abandon propre, rien d'ecrit."""
    monkeypatch.chdir(tmp_path)
    cle = "nvapi-" + "c" * 60
    _interactif(monkeypatch, ["n", cle, cle, cle])
    monkeypatch.setattr(setup_cle, "verifier_cle_en_ligne", lambda c: False)

    resultat = setup_cle.assistant_cle(chemin_env=str(tmp_path / ".env"))

    assert resultat is None
    assert not (tmp_path / ".env").exists()


def test_hors_ligne_enregistre_quand_meme(tmp_path, monkeypatch):
    """Reseau indisponible (None) : on ne bloque pas l'utilisateur, la cle
    plausible est enregistree quand meme."""
    monkeypatch.chdir(tmp_path)
    cle = "nvapi-" + "d" * 60
    _interactif(monkeypatch, ["n", cle])
    monkeypatch.setattr(setup_cle, "verifier_cle_en_ligne", lambda c: None)

    assert setup_cle.assistant_cle(chemin_env=str(tmp_path / ".env")) == cle
    assert "NVIDIA_API_KEY" in (tmp_path / ".env").read_text(encoding="utf-8")


def test_saisie_vide_annule(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _interactif(monkeypatch, ["n", ""])
    assert setup_cle.assistant_cle(chemin_env=str(tmp_path / ".env")) is None
