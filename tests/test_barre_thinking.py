"""
Jauge du niveau de reflexion (/think) : une barre qui se remplit d'un cran
par niveau (low = 1/5 ... ultra = 5/5), visible dans le selecteur ET dans la
confirmation apres changement.
"""

from retroai_agent import ui
from retroai_agent import thinking


def test_barre_se_remplit_d_un_cran_par_niveau():
    attendu = {
        "low":    "█░░░░",
        "medium": "██░░░",
        "high":   "███░░",
        "highx":  "████░",
        "ultra":  "█████",
    }
    for niveau, barre in attendu.items():
        assert ui.barre_thinking(niveau) == barre


def test_barre_niveau_inconnu_retombe_sur_le_defaut():
    # normaliser() ramene tout inconnu au DEFAUT (medium) -> 2 crans.
    assert ui.barre_thinking("n_importe_quoi") == "██░░░"


def test_niveau_thinking_affiche_barre_et_description(capsys):
    ui.niveau_thinking("high")
    sortie = capsys.readouterr().out
    assert "███" in sortie                      # la jauge est visible
    assert "high" in sortie
    assert thinking.DESCRIPTIONS["high"].split(",")[0] in sortie
