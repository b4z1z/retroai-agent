"""
Gestion des plugins (menu /plugins) : desactiver/reactiver (renommage
*.py.off), supprimer, installation depuis le marketplace (telechargement
mocke + validation du contrat AVANT de garder le fichier), catalogue.
Tout s'applique A CHAUD via plugins.activer() — aucun restart.
"""

from __future__ import annotations

import os
import textwrap

from retroai_agent import plugins
from retroai_agent import tools
from retroai_agent.config import Config

CFG = Config(api_key="x", base_url="u", model="m", enable_thinking=False,
             shell_timeout=5, auto_safe_commands=False)

CODE_VALIDE = textwrap.dedent('''
    OUTIL = {
        "name": "outil_test",
        "description": "test",
        "parameters": {"type": "object", "properties": {}},
    }
    def executer(args, config):
        return "ok"
''')


def _dossier(tmp_path):
    d = tmp_path / "plugins"
    d.mkdir(exist_ok=True)
    return d


def test_desactiver_puis_reactiver_a_chaud(tmp_path):
    d = _dossier(tmp_path)
    fichier = d / "outil.py"
    fichier.write_text(CODE_VALIDE, encoding="utf-8")
    try:
        nb, _ = plugins.activer(str(d))
        assert nb == 1

        # DESACTIVER : le fichier devient .py.off et sort du schema.
        assert plugins.desactiver_fichier(str(fichier)) is None
        nb, _ = plugins.activer(str(d))
        assert nb == 0
        assert plugins.lister_desactives(str(d)) == [str(fichier) + ".off"]
        noms = [s["function"]["name"] for s in tools.TOOLS_SCHEMA]
        assert "outil_test" not in noms

        # REACTIVER : retour a la normale.
        assert plugins.reactiver_fichier(str(fichier) + ".off") is None
        nb, _ = plugins.activer(str(d))
        assert nb == 1
        assert plugins.lister_desactives(str(d)) == []
    finally:
        plugins.activer(str(tmp_path / "inexistant"))


def test_supprimer_fichier(tmp_path):
    d = _dossier(tmp_path)
    fichier = d / "jetable.py"
    fichier.write_text(CODE_VALIDE, encoding="utf-8")
    assert plugins.supprimer_fichier(str(fichier)) is None
    assert not fichier.exists()
    # Supprimer un fichier absent -> message d'erreur, pas d'exception.
    assert plugins.supprimer_fichier(str(fichier)).startswith("Could not")


class _ReponseHTTP:
    def __init__(self, texte, code=200):
        self.text = texte
        self.status_code = code


def test_installer_valide_avant_de_garder(tmp_path, monkeypatch):
    d = _dossier(tmp_path)
    import requests
    monkeypatch.setattr(requests, "get",
                        lambda url, timeout=0: _ReponseHTTP(CODE_VALIDE))

    probleme = plugins.installer(
        {"nom": "outil_test", "fichier": "outil.py", "url": "https://x/o.py"},
        dossier=str(d),
    )
    assert probleme is None
    assert (d / "outil.py").exists()


def test_installer_rejette_un_plugin_invalide(tmp_path, monkeypatch):
    d = _dossier(tmp_path)
    import requests
    monkeypatch.setattr(requests, "get",
                        lambda url, timeout=0: _ReponseHTTP("x = 1\n"))

    probleme = plugins.installer(
        {"nom": "casse", "fichier": "casse.py", "url": "https://x/c.py"},
        dossier=str(d),
    )
    assert probleme is not None and "Invalid plugin" in probleme
    assert not (d / "casse.py").exists()   # rien de casse ne persiste


def test_installer_echec_reseau_propre(tmp_path, monkeypatch):
    d = _dossier(tmp_path)
    import requests
    monkeypatch.setattr(requests, "get",
                        lambda url, timeout=0: _ReponseHTTP("nope", 404))
    probleme = plugins.installer(
        {"nom": "x", "fichier": "x.py", "url": "https://x/x.py"},
        dossier=str(d),
    )
    assert probleme == "Download failed (HTTP 404)."


def test_catalogue_parse_et_filtre(monkeypatch):
    import requests
    registre = ('{"plugins": ['
                '{"nom":"a","fichier":"a.py","url":"https://x/a.py"},'
                '{"nom":"sans_url","fichier":"b.py"}]}')
    monkeypatch.setattr(requests, "get",
                        lambda url, timeout=0: _ReponseHTTP(registre))
    entrees, erreur = plugins.catalogue("https://x/registry.json")
    assert erreur is None
    assert [e["nom"] for e in entrees] == ["a"]  # l'entree incomplete filtree


def test_catalogue_hors_ligne(monkeypatch):
    import requests

    def boom(url, timeout=0):
        raise OSError("no network")
    monkeypatch.setattr(requests, "get", boom)
    entrees, erreur = plugins.catalogue("https://x/registry.json")
    assert entrees == [] and "Could not reach" in erreur


def test_catalogue_inline_du_site_synchronise_avec_registry_json():
    """Le site embarque le catalogue DANS index.html (pour marcher meme en
    double-clic, ou file:// bloque fetch) : ce bloc inline doit rester la
    COPIE EXACTE de registry.json (la source de verite lue par l'app)."""
    import json
    racine = os.path.join(os.path.dirname(__file__), "..", "marketplace")
    with open(os.path.join(racine, "registry.json"), encoding="utf-8") as f:
        source = json.load(f)
    with open(os.path.join(racine, "index.html"), encoding="utf-8") as f:
        html = f.read()
    debut = html.index("var REGISTRY =") + len("var REGISTRY =")
    fin = html.index("/* REGISTRY-END */")
    copie = json.loads(html[debut:fin].strip().rstrip(";"))
    assert copie == source


def test_registre_du_depot_coherent():
    """Le registry.json LIVRE doit etre un JSON valide dont chaque entree a
    nom/fichier/url, et chaque fichier reference existe dans marketplace/."""
    import json
    racine = os.path.join(os.path.dirname(__file__), "..", "marketplace")
    with open(os.path.join(racine, "registry.json"), encoding="utf-8") as f:
        data = json.load(f)
    assert data["plugins"], "registre vide"
    for entree in data["plugins"]:
        assert entree["nom"] and entree["fichier"] and entree["url"]
        assert os.path.exists(os.path.join(racine, "plugins", entree["fichier"]))
        assert entree["url"].endswith("marketplace/plugins/" + entree["fichier"])
