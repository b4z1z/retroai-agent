"""Tests de files.py : /add-file (lecture) et /compose (editeur temporaire)."""

import os
import sys

from retroai_agent import files


# --------------------------------------------------------------------------- #
#  lire_fichier_texte (/add-file)                                             #
# --------------------------------------------------------------------------- #
def test_lecture_fichier_ok(tmp_path):
    p = tmp_path / "code.py"
    p.write_text("print('hi')\n", encoding="utf-8")
    contenu, erreur = files.lire_fichier_texte(str(p))
    assert erreur == ""
    assert "print('hi')" in contenu


def test_fichier_absent(tmp_path):
    _, erreur = files.lire_fichier_texte(str(tmp_path / "nope.txt"))
    assert "not found" in erreur.lower()


def test_fichier_binaire_rejete(tmp_path):
    p = tmp_path / "img.bin"
    p.write_bytes(b"\x00\x01\xff\xfe\x00")
    _, erreur = files.lire_fichier_texte(str(p))
    assert "binary" in erreur.lower()


def test_guillemets_autour_du_chemin(tmp_path):
    """Chemin colle avec guillemets (copier-coller Windows) -> nettoye."""
    p = tmp_path / "a.txt"
    p.write_text("data", encoding="utf-8")
    contenu, erreur = files.lire_fichier_texte(f'"{p}"')
    assert erreur == "" and contenu == "data"


def test_troncature_gros_fichier(tmp_path):
    p = tmp_path / "gros.txt"
    p.write_text("x" * (files.MAX_CHARS_FICHIER + 50), encoding="utf-8")
    contenu, erreur = files.lire_fichier_texte(str(p))
    assert erreur == ""
    assert "truncated" in contenu


def test_message_fichier_contient_chemin_et_consigne(tmp_path):
    p = tmp_path / "demo.asm"
    p.write_text("mov ax, 1", encoding="utf-8")
    msg = files.construire_message_fichier(str(p), "mov ax, 1", "ameliore")
    assert msg.startswith("ameliore")
    assert os.path.abspath(str(p)) in msg          # chemin complet -> write_file
    assert "write_file" in msg                     # consigne de sauvegarde
    assert "```" in msg and "mov ax, 1" in msg     # bloc delimite


# --------------------------------------------------------------------------- #
#  composer_dans_editeur (/compose)                                           #
# --------------------------------------------------------------------------- #
def _installer_faux_editeur(tmp_path, monkeypatch):
    """
    Cree un faux editeur (script Python) qui simule un utilisateur ecrivant
    sous la ligne d'instructions, avec les pieges de notepad : BOM + CRLF.
    """
    script = tmp_path / "faux_editeur.py"
    script.write_text(
        "import sys\n"
        "p = sys.argv[1]\n"
        "with open(p, 'r', encoding='utf-8') as f:\n"
        "    marqueur = f.readline().rstrip('\\n')\n"
        "texte = marqueur + '\\r\\nhello\\r\\nmov ax, 1  ; commentaire\\r\\n'\n"
        "with open(p, 'wb') as f:\n"
        "    f.write(b'\\xef\\xbb\\xbf' + texte.encode('utf-8'))\n",
        encoding="utf-8",
    )
    # Chemins en slashes avant : shlex.split (mode posix) mange les backslashes.
    editeur = f"{sys.executable} {script}".replace("\\", "/")
    monkeypatch.setenv("EDITOR", editeur)


def test_compose_marqueur_bom_et_crlf(tmp_path, monkeypatch):
    _installer_faux_editeur(tmp_path, monkeypatch)
    texte = files.composer_dans_editeur()
    # Marqueur retire, BOM avale, CRLF normalises, contenu intact.
    assert texte == "hello\nmov ax, 1  ; commentaire"
    assert files.MARQUEUR_COMPOSE not in texte


def test_compose_editeur_introuvable(monkeypatch):
    monkeypatch.setenv("EDITOR", "editeur-qui-n-existe-pas-xyz")
    assert files.composer_dans_editeur() is None


def test_editeur_par_defaut(monkeypatch):
    monkeypatch.delenv("EDITOR", raising=False)
    monkeypatch.delenv("VISUAL", raising=False)
    attendu = "notepad" if sys.platform.startswith("win") else "nano"
    assert files._editeur_par_defaut() == attendu
    monkeypatch.setenv("EDITOR", "code -w")
    assert files._editeur_par_defaut() == "code -w"
