"""
Tableau de bord /stats : chiffres DERIVES des fichiers locaux (sessions,
plugins, memoire) — aucune telemetrie, aucun nouveau suivi.
"""

from __future__ import annotations

import json

from retroai_agent import stats
from retroai_agent import memoire


def _session(tmp_path, nom, historique, cree="2026-07-01", maj="2026-07-02"):
    dossier = tmp_path / "sessions"
    dossier.mkdir(exist_ok=True)
    (dossier / f"{nom}.json").write_text(json.dumps({
        "id": nom, "titre": f"Chat {nom}", "cree": cree, "maj": maj,
        "historique": historique,
    }), encoding="utf-8")
    return str(dossier)


def _appel(nom_outil):
    return {"role": "assistant", "content": "", "tool_calls": [
        {"id": "1", "type": "function",
         "function": {"name": nom_outil, "arguments": "{}"}}]}


def test_agregation_complete(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    dossier = _session(tmp_path, "a", [
        {"role": "user", "content": "bonjour"},          # 7 chars
        _appel("read_file"),
        {"role": "assistant", "content": "voici"},       # 5 chars
    ], cree="2026-07-01", maj="2026-07-01")
    _session(tmp_path, "b", [
        {"role": "user", "content": "salut"},
        _appel("read_file"),
        _appel("get_weather"),
    ], cree="2026-06-20", maj="2026-07-05")

    resume = stats.calculer(dossier)

    assert resume["sessions"] == 2
    assert resume["messages"] == 6
    assert resume["messages_utilisateur"] == 2
    assert resume["appels_outils"] == 3
    assert stats.top_outils(resume) == [("read_file", 2), ("get_weather", 1)]
    # Periode d'activite : plus ancienne creation -> derniere maj.
    assert resume["premiere"].startswith("2026-06-20")
    assert resume["derniere"].startswith("2026-07-05")
    # Tokens estimes : ~4 chars/token sur le texte sauvegarde.
    assert resume["tokens_estimes"] == resume["caracteres"] // 4


def test_contenu_multimodal_compte_le_texte(tmp_path, monkeypatch):
    """Un message avec image = liste de blocs : seul le TEXTE est compte
    (pas le base64 de l'image, qui fausserait tout)."""
    monkeypatch.chdir(tmp_path)
    dossier = _session(tmp_path, "img", [
        {"role": "user", "content": [
            {"type": "text", "text": "regarde"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}},
        ]},
    ])
    resume = stats.calculer(dossier)
    assert resume["caracteres"] == len("regarde")


def test_memoire_et_plugins_comptes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    memoire.ajouter("un fait")
    (tmp_path / "plugins").mkdir()
    (tmp_path / "plugins" / "actif.py").write_text("x", encoding="utf-8")
    (tmp_path / "plugins" / "eteint.py.off").write_text("x", encoding="utf-8")
    (tmp_path / "plugins" / "_prive.py").write_text("x", encoding="utf-8")

    resume = stats.calculer(_session(tmp_path, "a", []))

    assert resume["souvenirs"] == 1
    assert resume["plugins"] == (1, 1)   # _prive.py ignore


def test_aucune_session_ne_plante_pas(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    resume = stats.calculer(str(tmp_path / "vide"))
    assert resume["sessions"] == 0
    assert resume["tokens_estimes"] == 0
    assert stats.top_outils(resume) == []
