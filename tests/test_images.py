"""
Tests de images.py : detection des chemins d'images + construction du
contenu multimodal. On cree de vrais petits PNG dans un dossier temporaire
(fixture tmp_path de pytest) pour que os.path.isfile reponde True.
"""

import struct
import zlib

from retroai_agent import images


def _creer_png(chemin) -> None:
    """Ecrit un petit PNG rouge valide a l'emplacement donne."""
    largeur = hauteur = 4
    brut = b"".join(b"\x00" + b"\xff\x00\x00" * largeur for _ in range(hauteur))

    def bloc(typ, data):
        return (struct.pack(">I", len(data)) + typ + data
                + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF))

    png = (
        b"\x89PNG\r\n\x1a\n"
        + bloc(b"IHDR", struct.pack(">IIBBBBB", largeur, hauteur, 8, 2, 0, 0, 0))
        + bloc(b"IDAT", zlib.compress(brut))
        + bloc(b"IEND", b"")
    )
    chemin.write_bytes(png)


def test_detecte_un_chemin_image_existant(tmp_path):
    img = tmp_path / "photo.png"
    _creer_png(img)
    chemins = images.extraire_chemins_images(f"describe {img}")
    assert str(img) in chemins


def test_ponctuation_collee_ne_casse_pas_la_detection(tmp_path):
    # Bug rencontre lors du dev : "photo.png?" -> doit quand meme etre detecte.
    img = tmp_path / "photo.png"
    _creer_png(img)
    chemins = images.extraire_chemins_images(f"what is in {img}?")
    assert str(img) in chemins


def test_fichier_inexistant_est_ignore():
    assert images.extraire_chemins_images("describe nope.png") == []


def test_sans_image_retourne_le_texte(tmp_path):
    contenu, jointes = images.construire_contenu("just text, no image")
    assert contenu == "just text, no image"
    assert jointes == []


def test_avec_image_retourne_contenu_multimodal(tmp_path):
    img = tmp_path / "photo.png"
    _creer_png(img)
    contenu, jointes = images.construire_contenu(f"see {img}")
    assert isinstance(contenu, list)
    assert jointes == ["photo.png"]
    assert any(bloc.get("type") == "image_url" for bloc in contenu)
    assert any(bloc.get("type") == "text" for bloc in contenu)
