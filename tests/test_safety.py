"""
Tests de safety.py : detection de commandes dangereuses + liste blanche.
C'est le code le plus CRITIQUE (securite) -> a tester en priorite.
"""

from retroai_agent import safety


# --- detecter_danger : repere les commandes destructrices ------------------ #
def test_detecter_danger_signale_les_dangereuses():
    assert safety.detecter_danger("rm -rf /home/user") is not None
    assert safety.detecter_danger("sudo reboot") is not None
    assert safety.detecter_danger("dd if=/dev/zero of=/dev/sda") is not None
    assert safety.detecter_danger("mkfs.ext4 /dev/sdb") is not None


def test_detecter_danger_laisse_passer_les_sures():
    assert safety.detecter_danger("ls -la") is None
    assert safety.detecter_danger("cat fichier.txt") is None
    assert safety.detecter_danger("echo bonjour") is None


# --- est_commande_sure : liste blanche pour l'auto-execution --------------- #
def test_commandes_lecture_seule_sont_sures():
    for cmd in ["ls -la", "pwd", "echo hello", "cat file.txt",
                "find . -name x.py", "grep -i foo file", "head -n 5 f"]:
        assert safety.est_commande_sure(cmd) is True, cmd


def test_redirections_pipes_chainage_substitution_bloques():
    # Le PIEGE : une commande "douce" rendue dangereuse par les metacaracteres.
    for cmd in ["echo x > fichier", "cat a | grep b", "ls ; rm x",
                "ls && rm x", "echo $(rm -rf ~)", "cat `whoami`"]:
        assert safety.est_commande_sure(cmd) is False, cmd


def test_find_destructeur_est_bloque():
    assert safety.est_commande_sure("find . -delete") is False
    assert safety.est_commande_sure("find / -exec rm {} +") is False


def test_hors_liste_blanche_et_vide_refuses():
    assert safety.est_commande_sure("rm -rf /") is False
    assert safety.est_commande_sure("python script.py") is False
    assert safety.est_commande_sure("") is False
    assert safety.est_commande_sure("   ") is False
