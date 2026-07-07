"""Tests de sessions.py : multi-conversations (lister/sauver/charger/migrer)."""

import json
import os

import pytest

from retroai_agent import sessions

# Deux moitiees de paire UTF-16 d'un emoji (U+1F30C), telles que produites par
# json.loads() sur 2 lignes SSE separees quand le streaming coupe le
# caractere en deux (voir CRASH REEL rencontre : UnicodeEncodeError lors de
# sessions.sauver() -> "surrogates not allowed").
_SURROGATE_HAUT = json.loads('"\\ud83c"')
_SURROGATE_BAS = json.loads('"\\udf0c"')


def test_generer_id_unique_sur_collision(tmp_path, monkeypatch):
    dossier = str(tmp_path)
    id1 = sessions.generer_id(dossier)
    sessions.sauver(id1, [{"role": "user", "content": "hi"}], dossier=dossier)
    # Force la meme seconde -> generer_id doit renvoyer un id DIFFERENT.
    monkeypatch.setattr(sessions.time, "strftime", lambda fmt: id1)
    id2 = sessions.generer_id(dossier)
    assert id2 != id1
    assert id2.startswith(id1)


def test_sauver_puis_charger_round_trip(tmp_path):
    dossier = str(tmp_path)
    historique = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "Bonjour, code un jeu de ping pong"},
    ]
    sessions.sauver("abc", historique, dossier=dossier)
    donnees = sessions.charger("abc", dossier=dossier)
    assert donnees is not None
    assert donnees["historique"] == historique
    assert donnees["titre"] == "Bonjour, code un jeu de ping pong"
    assert "cree" in donnees and "maj" in donnees


def test_charger_session_absente(tmp_path):
    assert sessions.charger("nope", dossier=str(tmp_path)) is None


def test_charger_fichier_corrompu(tmp_path):
    dossier = str(tmp_path)
    (tmp_path / "cassee.json").write_text("{ pas du json valide", encoding="utf-8")
    assert sessions.charger("cassee", dossier=dossier) is None


def test_sauver_preserve_la_date_de_creation(tmp_path):
    dossier = str(tmp_path)
    sessions.sauver("s1", [{"role": "user", "content": "un"}], dossier=dossier)
    cree_original = sessions.charger("s1", dossier=dossier)["cree"]
    sessions.sauver("s1", [{"role": "user", "content": "deux"}], dossier=dossier)
    donnees = sessions.charger("s1", dossier=dossier)
    assert donnees["cree"] == cree_original          # inchangee
    assert donnees["historique"][0]["content"] == "deux"  # mise a jour


def test_lister_triee_par_maj_decroissant(tmp_path):
    dossier = str(tmp_path)
    sessions.sauver("vieille", [{"role": "user", "content": "a"}], dossier=dossier)
    # Force une date de maj clairement plus ancienne pour "vieille".
    chemin = os.path.join(dossier, "vieille.json")
    donnees = json.loads(open(chemin, encoding="utf-8").read())
    donnees["maj"] = "2020-01-01T00:00:00"
    open(chemin, "w", encoding="utf-8").write(json.dumps(donnees))

    sessions.sauver("recente", [{"role": "user", "content": "b"}], dossier=dossier)

    resultats = sessions.lister(dossier)
    assert [r["id"] for r in resultats] == ["recente", "vieille"]
    assert resultats[0]["nb_messages"] == 1


def test_lister_dossier_absent():
    assert sessions.lister(dossier="ce_dossier_n_existe_pas_xyz") == []


def test_lister_ignore_fichier_corrompu(tmp_path):
    dossier = str(tmp_path)
    sessions.sauver("bonne", [{"role": "user", "content": "ok"}], dossier=dossier)
    (tmp_path / "cassee.json").write_text("pas du json", encoding="utf-8")
    resultats = sessions.lister(dossier)
    assert [r["id"] for r in resultats] == ["bonne"]


def test_deriver_titre_ignore_resultats_outils_et_plan():
    historique = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "[Tool result: read_file]\nblabla"},
        {"role": "user", "content": "vraie question ici"},
    ]
    assert sessions.deriver_titre(historique) == "vraie question ici"


def test_deriver_titre_gere_contenu_multimodal():
    historique = [
        {"role": "user", "content": [
            {"type": "text", "text": "decris cette image"},
            {"type": "image_url", "image_url": {"url": "data:..."}},
        ]},
    ]
    assert sessions.deriver_titre(historique) == "decris cette image"


def test_deriver_titre_par_defaut_si_aucun_message():
    assert sessions.deriver_titre([{"role": "system", "content": "sys"}]) == "New session"


def test_deriver_titre_tronque_les_longs_messages():
    long_texte = "x" * 100
    titre = sessions.deriver_titre([{"role": "user", "content": long_texte}])
    assert len(titre) <= sessions.LONGUEUR_TITRE + 1  # +1 pour l'ellipse
    assert titre.endswith("…")


def test_supprimer(tmp_path):
    dossier = str(tmp_path)
    sessions.sauver("a-virer", [{"role": "user", "content": "x"}], dossier=dossier)
    assert sessions.supprimer("a-virer", dossier=dossier)
    assert sessions.charger("a-virer", dossier=dossier) is None
    assert not sessions.supprimer("deja-partie", dossier=dossier)  # tolerant


def test_migration_ancien_fichier_unique(tmp_path):
    dossier_sessions = str(tmp_path / "sessions")
    chemin_legacy = str(tmp_path / "session_history.json")
    historique = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "vieille conversation avant multi-session"},
    ]
    with open(chemin_legacy, "w", encoding="utf-8") as f:
        json.dump(historique, f)

    id_migre = sessions.migrer_ancienne_session(chemin_legacy, dossier_sessions)
    assert id_migre is not None
    donnees = sessions.charger(id_migre, dossier_sessions)
    assert donnees["historique"] == historique
    assert donnees["titre"] == "vieille conversation avant multi-session"
    # Le fichier legacy a ete renomme (plus present a son emplacement d'origine).
    assert not os.path.exists(chemin_legacy)
    assert os.path.exists(chemin_legacy + ".migrated")


def test_migration_ne_refait_rien_si_deja_faite(tmp_path):
    dossier_sessions = str(tmp_path / "sessions")
    chemin_legacy = str(tmp_path / "session_history.json")
    # Pas de fichier legacy -> rien a migrer.
    assert sessions.migrer_ancienne_session(chemin_legacy, dossier_sessions) is None


def test_migration_fichier_vide_ou_invalide_ignoree(tmp_path):
    dossier_sessions = str(tmp_path / "sessions")
    chemin_legacy = str(tmp_path / "session_history.json")
    with open(chemin_legacy, "w", encoding="utf-8") as f:
        json.dump([], f)  # liste vide -> rien de reel a migrer
    assert sessions.migrer_ancienne_session(chemin_legacy, dossier_sessions) is None
    assert os.path.exists(chemin_legacy)  # pas renomme, rien fait


# --------------------------------------------------------------------------- #
#  REGRESSION - crash reel : emoji coupe en 2 par le streaming SSE ->         #
#  surrogate isole -> UnicodeEncodeError sur sauver() -> plantage TOTAL de    #
#  l'app (traceback + fermeture). Doit desormais etre repare silencieusement. #
# --------------------------------------------------------------------------- #
def test_reparer_texte_recombine_une_paire_adjacente_sans_perte():
    casse = "AVANT" + _SURROGATE_HAUT + _SURROGATE_BAS + "APRES"
    repare = sessions._reparer_texte(casse)
    assert "\U0001F30C" in repare              # le VRAI emoji est recupere
    assert repare.encode("utf-8")              # ne leve pas


def test_reparer_texte_neutralise_un_orphelin_sans_planter():
    casse = "AVANT" + _SURROGATE_HAUT + "APRES"  # jamais reassemble
    repare = sessions._reparer_texte(casse)
    assert all(not (0xD800 <= ord(c) <= 0xDFFF) for c in repare)  # plus de surrogate
    assert repare.encode("utf-8")              # ne leve pas


def test_reparer_texte_ne_touche_pas_un_texte_propre():
    propre = "Bonjour, ça marche très bien ! 🚀"
    assert sessions._reparer_texte(propre) == propre


def test_reparer_recursif_traite_les_structures_imbriquees():
    casse = _SURROGATE_HAUT + _SURROGATE_BAS
    structure = {
        "a": casse,
        "b": [casse, {"c": casse}],
        "d": 42,
        "e": None,
    }
    repare = sessions._reparer_recursif(structure)
    assert "\U0001F30C" in repare["a"]
    assert "\U0001F30C" in repare["b"][0]
    assert "\U0001F30C" in repare["b"][1]["c"]
    assert repare["d"] == 42 and repare["e"] is None  # types non-str intacts


def test_sauver_avec_emoji_casse_ne_plante_jamais(tmp_path):
    """LE crash reel reproduit : sauver() sur un historique contenant un
    surrogate isole ne doit JAMAIS lever d'exception (avant le fix, ceci
    faisait planter TOUTE l'application avec un traceback non rattrape)."""
    dossier = str(tmp_path)
    contenu_casse = (
        "Voici le site " + _SURROGATE_HAUT + _SURROGATE_BAS + " fini, "
        + "et un orphelin ici -> " + _SURROGATE_HAUT
    )
    historique = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "cree le site"},
        {"role": "assistant", "content": contenu_casse},
    ]
    sessions.sauver("crash-repro", historique, dossier=dossier)  # ne doit PAS lever

    donnees = sessions.charger("crash-repro", dossier=dossier)
    assert donnees is not None
    contenu_final = donnees["historique"][2]["content"]
    assert "\U0001F30C" in contenu_final       # l'emoji legitime est recupere
    assert all(not (0xD800 <= ord(c) <= 0xDFFF) for c in contenu_final)  # aucun orphelin


def test_sauver_repare_aussi_le_titre_derive(tmp_path):
    """Le titre est derive de historique AVANT reparation dans le code naif ;
    verifie qu'il est bien lui aussi propre (pas seulement l'historique)."""
    dossier = str(tmp_path)
    premier_message = "besoin d'aide " + _SURROGATE_HAUT + _SURROGATE_BAS
    historique = [{"role": "user", "content": premier_message}]
    sessions.sauver("titre-casse", historique, dossier=dossier)
    donnees = sessions.charger("titre-casse", dossier=dossier)
    assert donnees["titre"].encode("utf-8")  # ne leve pas
    assert "\U0001F30C" in donnees["titre"]
