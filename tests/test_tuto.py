"""Tests de tuto.py : tutoriel interactif au 1er lancement (/tuto)."""

from retroai_agent import tuto, ui


def _sans_pause_ni_panneau(monkeypatch, reponses=None):
    """
    Neutralise l'affichage (panneau_info) et fait repondre ui.pause() avec
    une sequence de reponses fournie (par defaut : toujours Entree = "").
    Retourne la liste des titres d'etapes realmement affiches (pour verifier
    la progression / l'arret anticipe).
    """
    titres_affiches = []
    monkeypatch.setattr(
        ui, "panneau_info",
        lambda titre, lignes, etape="": titres_affiches.append(titre),
    )
    file_reponses = iter(reponses if reponses is not None else [""] * 100)
    monkeypatch.setattr(ui, "pause", lambda *a, **k: next(file_reponses))
    return titres_affiches


def test_premier_lancement_joue_toutes_les_etapes(tmp_path, monkeypatch):
    marqueur = str(tmp_path / "marqueur.json")
    titres = _sans_pause_ni_panneau(monkeypatch)
    tuto.jouer(chemin_marqueur=marqueur)
    assert len(titres) == len(tuto.ETAPES)
    assert titres[0] == tuto.ETAPES[0][0]
    assert titres[-1] == tuto.ETAPES[-1][0]


def test_ne_se_rejoue_pas_tout_seul_une_2e_fois(tmp_path, monkeypatch):
    marqueur = str(tmp_path / "marqueur.json")
    titres = _sans_pause_ni_panneau(monkeypatch)
    tuto.jouer(chemin_marqueur=marqueur)          # 1er lancement : joue
    tuto.jouer(chemin_marqueur=marqueur)          # 2e lancement : ne rejoue pas
    assert len(titres) == len(tuto.ETAPES)         # pas de doublon


def test_force_rejoue_meme_si_deja_vu(tmp_path, monkeypatch):
    marqueur = str(tmp_path / "marqueur.json")
    titres = _sans_pause_ni_panneau(monkeypatch)
    tuto.jouer(chemin_marqueur=marqueur)                  # marque comme vu
    tuto.jouer(force=True, chemin_marqueur=marqueur)      # /tuto : rejoue
    assert len(titres) == 2 * len(tuto.ETAPES)


def test_marque_comme_vu_meme_si_on_quitte_au_milieu(tmp_path, monkeypatch):
    """Sortir tot (skip) ne doit PAS re-declencher le tuto au prochain lancement."""
    marqueur = str(tmp_path / "marqueur.json")
    _sans_pause_ni_panneau(monkeypatch, reponses=["skip"])
    tuto.jouer(chemin_marqueur=marqueur)
    assert tuto._deja_vu(marqueur)

    # Un 2e appel (sans force) ne doit rien rejouer.
    titres = _sans_pause_ni_panneau(monkeypatch)
    tuto.jouer(chemin_marqueur=marqueur)
    assert titres == []


def test_skip_arrete_la_progression(tmp_path, monkeypatch):
    marqueur = str(tmp_path / "marqueur.json")
    # Avance de 2 etapes puis "skip" -> ne doit PAS afficher les suivantes.
    titres = _sans_pause_ni_panneau(monkeypatch, reponses=["", "", "skip"])
    tuto.jouer(chemin_marqueur=marqueur)
    assert len(titres) == 3
    assert titres == [t for t, _ in tuto.ETAPES[:3]]


def test_ctrl_c_arrete_proprement(tmp_path, monkeypatch):
    marqueur = str(tmp_path / "marqueur.json")

    def _pause_qui_interrompt(*a, **k):
        raise KeyboardInterrupt

    monkeypatch.setattr(ui, "panneau_info", lambda *a, **k: None)
    monkeypatch.setattr(ui, "pause", _pause_qui_interrompt)
    tuto.jouer(chemin_marqueur=marqueur)  # ne doit pas lever d'exception
    assert tuto._deja_vu(marqueur)        # quand meme marque comme vu
