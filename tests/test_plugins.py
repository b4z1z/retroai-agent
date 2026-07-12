"""
Systeme de plugins : chargement, validation, isolation des erreurs, fusion
dans le schema, dispatch via tools.executer_outil, confirmation DANGEREUX,
et validite des 2 plugins exemples livres.
"""

from __future__ import annotations

import os
import textwrap

from retroai_agent import plugins
from retroai_agent import tools
from retroai_agent import safety
from retroai_agent.config import Config


CFG = Config(api_key="x", base_url="u", model="m", enable_thinking=False,
             shell_timeout=5, auto_safe_commands=False)

PLUGIN_VALIDE = '''
OUTIL = {
    "name": "dire_bonjour",
    "description": "Say hello",
    "parameters": {"type": "object", "properties": {
        "nom": {"type": "string"}}, "required": ["nom"]},
}
def executer(args, config):
    return "Bonjour " + args["nom"] + " !"
'''

PLUGIN_DANGEREUX = '''
OUTIL = {
    "name": "outil_risque",
    "description": "Does something risky",
    "parameters": {"type": "object", "properties": {}},
}
DANGEREUX = True
def executer(args, config):
    return "boom done"
'''


def _dossier(tmp_path, fichiers: dict) -> str:
    d = tmp_path / "plugins"
    d.mkdir(exist_ok=True)
    for nom, code in fichiers.items():
        (d / nom).write_text(textwrap.dedent(code), encoding="utf-8")
    return str(d)


def test_chargement_et_execution(tmp_path):
    dossier = _dossier(tmp_path, {"bonjour.py": PLUGIN_VALIDE})
    nb, erreurs = plugins.activer(dossier)
    try:
        assert (nb, erreurs) == (1, [])
        # Present dans le schema envoye au modele.
        noms = [s["function"]["name"] for s in tools.TOOLS_SCHEMA]
        assert "dire_bonjour" in noms
        # Dispatch via le MEME chemin que les outils du coeur.
        assert tools.executer_outil(
            "dire_bonjour", {"nom": "BAZIZ"}, CFG) == "Bonjour BAZIZ !"
    finally:
        plugins.activer(str(tmp_path / "vide_inexistant"))  # nettoie le schema


def test_plugin_casse_ignore_sans_planter(tmp_path):
    dossier = _dossier(tmp_path, {
        "ok.py": PLUGIN_VALIDE,
        "casse.py": "import n_existe_pas_du_tout\n",
        "sans_contrat.py": "x = 1\n",
        "_brouillon.py": "raise RuntimeError('jamais importe')\n",
    })
    nb, erreurs = plugins.activer(dossier)
    try:
        assert nb == 1                        # seul le valide est charge
        assert len(erreurs) == 2              # casse + sans_contrat signales
        assert any("casse.py" in e for e in erreurs)
        assert any("sans_contrat.py" in e for e in erreurs)
    finally:
        plugins.activer(str(tmp_path / "vide_inexistant"))


def test_collision_avec_outil_du_coeur_refusee(tmp_path):
    usurpateur = PLUGIN_VALIDE.replace("dire_bonjour", "read_file")
    dossier = _dossier(tmp_path, {"usurpateur.py": usurpateur})
    nb, erreurs = plugins.activer(dossier)
    try:
        assert nb == 0
        assert any("collides" in e for e in erreurs)
        # read_file du coeur intact.
        assert tools.TOOLS["read_file"] is not None
    finally:
        plugins.activer(str(tmp_path / "vide_inexistant"))


def test_dangereux_passe_par_la_confirmation(tmp_path, monkeypatch):
    dossier = _dossier(tmp_path, {"risque.py": PLUGIN_DANGEREUX})
    plugins.activer(dossier)
    try:
        appels = []

        def fausse_confirmation(titre, details, categorie=""):
            appels.append((titre, categorie))
            return False  # l'utilisateur refuse

        monkeypatch.setattr(plugins.safety, "demander_confirmation",
                            fausse_confirmation)
        resultat = tools.executer_outil("outil_risque", {}, CFG)

        assert resultat == "Refused by user."
        assert appels and appels[0][1] == "command"  # meme categorie que shell
    finally:
        plugins.activer(str(tmp_path / "vide_inexistant"))


def test_exception_du_plugin_devient_message_erreur(tmp_path):
    plante = PLUGIN_VALIDE.replace(
        'return "Bonjour " + args["nom"] + " !"', 'raise ValueError("aie")')
    dossier = _dossier(tmp_path, {"plante.py": plante})
    plugins.activer(dossier)
    try:
        resultat = tools.executer_outil("dire_bonjour", {"nom": "x"}, CFG)
        assert resultat.startswith("Error: plugin 'dire_bonjour' failed")
        assert "aie" in resultat
    finally:
        plugins.activer(str(tmp_path / "vide_inexistant"))


def test_outil_inconnu_reste_une_erreur_propre():
    assert tools.executer_outil("nexiste_pas", {}, CFG) == \
        "Error: unknown tool 'nexiste_pas'."


# ----------------------------------------------------------------------- #
#  Les 2 plugins exemples LIVRES doivent respecter le contrat.            #
# ----------------------------------------------------------------------- #
def test_plugins_exemples_livres_valides():
    racine = os.path.join(os.path.dirname(__file__), "..", "plugins")
    nb, erreurs = plugins.charger(racine)
    assert erreurs == []
    assert nb == 2
    noms = {p["nom"] for p in plugins.liste()}
    assert noms == {"get_weather", "calculate"}


def test_calculatrice_exacte_et_sure():
    racine = os.path.join(os.path.dirname(__file__), "..", "plugins")
    plugins.charger(racine)
    assert plugins.executer("calculate",
                            {"expression": "17*23 - 19*21"}, CFG) \
        == "17*23 - 19*21 = -8"
    # Toute tentative hors math est refusee proprement (pas d'eval sauvage).
    assert plugins.executer(
        "calculate", {"expression": "__import__('os').getcwd()"}, CFG
    ).startswith("Error:")
    assert plugins.executer(
        "calculate", {"expression": "1/0"}, CFG) == "Error: division by zero."
