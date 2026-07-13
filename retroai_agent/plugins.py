"""
plugins.py - Systeme de PLUGINS : ajouter des outils a l'agent SANS toucher
au coeur du logiciel.

Contrat d'un plugin (1 fichier .py dans le dossier plugins/, ~30 lignes) :

    OUTIL = {                     # schema JSON envoye au modele
        "name": "get_weather",
        "description": "...",
        "parameters": {"type": "object", "properties": {...}, "required": [...]},
    }
    DANGEREUX = False             # optionnel (defaut False). True -> l'outil
                                  # passe par la confirmation y/n, comme le shell.
    def executer(args: dict, config) -> str:
        ...retourne le TEXTE que verra le modele...

Regles de robustesse :
    - un plugin CASSE (erreur d'import, contrat invalide) est IGNORE avec un
      message clair au demarrage : il ne plante JAMAIS l'application ;
    - un plugin ne peut pas ECRASER un outil du coeur (collision de nom) ;
    - une exception pendant l'execution devient une chaine "Error: ..."
      renvoyee au modele (meme philosophie que tools.py).

Chargement au DEMARRAGE (main.py appelle activer()). Apres l'ajout d'un
fichier plugin, /restart recharge tout.
"""

from __future__ import annotations

import glob
import importlib.util
import os

from . import safety

DOSSIER = "plugins"

# Etat module : plugins charges (nom -> infos) et erreurs de chargement.
_REGISTRE: dict[str, dict] = {}
_ERREURS: list[str] = []


def _valider(module, fichier: str) -> dict:
    """Verifie le contrat d'un module plugin et retourne ses infos."""
    outil = getattr(module, "OUTIL", None)
    if not isinstance(outil, dict):
        raise ValueError("missing OUTIL dict")
    for cle in ("name", "description", "parameters"):
        if not outil.get(cle):
            raise ValueError(f"OUTIL is missing '{cle}'")
    executer = getattr(module, "executer", None)
    if not callable(executer):
        raise ValueError("missing executer(args, config) function")
    return {
        "nom": outil["name"],
        "description": outil["description"],
        "schema": {"type": "function", "function": outil},
        "dangereux": bool(getattr(module, "DANGEREUX", False)),
        "fichier": fichier,
        "executer": executer,
    }


def charger(dossier: str = DOSSIER) -> tuple[int, list[str]]:
    """
    Scanne dossier/*.py, importe et valide chaque plugin. Remplit le registre
    (vide d'abord : rechargeable). Retourne (nb_charges, erreurs).
    Les fichiers commencant par '_' sont ignores (brouillons, __init__...).
    """
    _REGISTRE.clear()
    _ERREURS.clear()
    if not os.path.isdir(dossier):
        return 0, []
    for chemin in sorted(glob.glob(os.path.join(dossier, "*.py"))):
        nom_fichier = os.path.basename(chemin)
        if nom_fichier.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location(
                f"baziz_plugin_{nom_fichier[:-3]}", chemin
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            infos = _valider(module, chemin)
            if infos["nom"] in _REGISTRE:
                raise ValueError(f"duplicate tool name '{infos['nom']}'")
            _REGISTRE[infos["nom"]] = infos
        except Exception as exc:  # un plugin casse n'arrete JAMAIS le boot
            _ERREURS.append(f"{nom_fichier}: {exc}")
    return len(_REGISTRE), list(_ERREURS)


def activer(dossier: str = DOSSIER) -> tuple[int, list[str]]:
    """
    Charge les plugins ET fusionne leurs schemas dans tools.TOOLS_SCHEMA
    (c'est ce que voit le modele). Idempotent : les schemas plugins
    precedents sont retires avant re-fusion ; une collision avec un outil du
    COEUR (read_file...) est refusee.
    """
    from . import tools  # import paresseux (tools importe deja plugins)

    noms_coeur = set(tools.TOOLS)
    nb, erreurs = charger(dossier)

    # Retire les schemas plugins d'une eventuelle activation precedente.
    tools.TOOLS_SCHEMA[:] = [
        s for s in tools.TOOLS_SCHEMA
        if s["function"]["name"] in noms_coeur
    ]
    for nom in list(_REGISTRE):
        if nom in noms_coeur:
            _ERREURS.append(
                f"{os.path.basename(_REGISTRE[nom]['fichier'])}: "
                f"'{nom}' collides with a core tool"
            )
            del _REGISTRE[nom]
            nb -= 1
            continue
        tools.TOOLS_SCHEMA.append(_REGISTRE[nom]["schema"])
    return nb, list(_ERREURS)


def executer(nom: str, args: dict, config) -> str:
    """
    Execute le plugin 'nom' (appele par tools.executer_outil en repli).
    Confirmation y/n prealable si DANGEREUX (categorie 'command' : couverte
    par le mode auto-all, pas par auto-edit — comme le shell).
    """
    infos = _REGISTRE.get(nom)
    if infos is None:
        return f"Error: unknown tool '{nom}'."
    if infos["dangereux"]:
        details = f"plugin: {nom}\narguments: {args}"
        if not safety.demander_confirmation(
            f"Run plugin '{nom}'", details, categorie="command"
        ):
            return "Refused by user."
    try:
        return str(infos["executer"](args, config))
    except Exception as exc:
        return f"Error: plugin '{nom}' failed: {exc}"


# --------------------------------------------------------------------------- #
#  Publication vers le MARKETPLACE (menu /plugins > Publish)                  #
#                                                                             #
#  Flux : copier le fichier dans marketplace/plugins/ + ajouter l'entree au   #
#  registry.json + REGENERER le bloc inline d'index.html (le site). Ensuite   #
#  main fait git add/commit/push -> Vercel redeploie AUTOMATIQUEMENT.         #
# --------------------------------------------------------------------------- #
RACINE_MARKETPLACE = "marketplace"

# Publication par IDENTITE GIT (modele Pull Request GitHub) :
#  - le PROPRIETAIRE (email git ci-dessous) publie DIRECTEMENT — ses
#    credentials git sont la vraie autorisation, GitHub refuse le push aux
#    autres de toute facon ;
#  - un CONTRIBUTEUR passe par une Pull Request : GitHub previent le
#    proprietaire PAR EMAIL (notification native), il relit et approuve, la
#    fusion redeploie le site automatiquement.
# (Remplace l'ancien mot de passe applicatif, contournable en editant les
# fichiers ; l'identite git + droits GitHub ne le sont pas.)
# Le proprietaire peut avoir PLUSIEURS identites git (compte GitHub +
# email de config locale). Liste surchargeable via env (emails separes
# par des virgules).
EMAILS_PROPRIETAIRE = {
    e.strip().lower()
    for e in os.environ.get(
        "MARKETPLACE_OWNER_EMAIL",
        "bazizdev07@gmail.com,a.mekouar@esisa.ac.ma",
    ).split(",")
    if e.strip()
}
URL_DEPOT = "https://github.com/b4z1z/retroai-agent"


def est_proprietaire(email: str | None = None) -> bool:
    """
    Vrai si l'identite git courante est celle du proprietaire du marketplace.
    email=None -> lit `git config user.email` (parametre injectable pour les
    tests). En cas de doute (git absent...), on repond False : le parcours
    contributeur (PR) est toujours SUR, jamais bloquant.
    """
    if email is None:
        import subprocess
        try:
            email = subprocess.run(
                ["git", "config", "user.email"],
                capture_output=True, text=True, timeout=10,
            ).stdout.strip()
        except Exception:
            return False
    return bool(email) and email.lower() in EMAILS_PROPRIETAIRE
URL_BRUTE_BASE = ("https://raw.githubusercontent.com/b4z1z/retroai-agent/"
                  "main/marketplace/plugins/")
MARQUEUR_DEBUT = "/* REGISTRY-START */"
MARQUEUR_FIN = "/* REGISTRY-END */"


def synchroniser_site(racine: str = RACINE_MARKETPLACE) -> str | None:
    """
    Regenere le bloc inline `var REGISTRY = ...` d'index.html a partir de
    registry.json (source de verite). Retourne une erreur, ou None si OK.
    C'est ce qui garantit que le SITE montre toujours la meme chose que le
    registre — fini les desynchronisations manuelles.
    """
    import json

    chemin_registre = os.path.join(racine, "registry.json")
    chemin_index = os.path.join(racine, "index.html")
    try:
        with open(chemin_registre, encoding="utf-8") as f:
            registre = json.load(f)
        with open(chemin_index, encoding="utf-8") as f:
            html = f.read()
        debut = html.index(MARQUEUR_DEBUT) + len(MARQUEUR_DEBUT)
        fin = html.index(MARQUEUR_FIN)
        bloc = ("\n  var REGISTRY = "
                + json.dumps(registre, ensure_ascii=False, indent=2)
                + ";\n  ")
        with open(chemin_index, "w", encoding="utf-8") as f:
            f.write(html[:debut] + bloc + html[fin:])
        return None
    except Exception as exc:
        return f"Could not sync the site: {exc}"


def publier(nom: str, auteur: str = "B4Z1Z",
            racine: str = RACINE_MARKETPLACE) -> str | None:
    """
    Publie le plugin CHARGE 'nom' vers le marketplace local (fichiers du
    depot) : copie + entree registre (ou mise a jour) + site resynchronise.
    Le commit/push (qui declenche le deploiement Vercel) est fait par
    l'appelant. Retourne une erreur, ou None si OK.
    """
    import json
    import shutil

    infos = _REGISTRE.get(nom)
    if infos is None:
        return f"Unknown plugin '{nom}' (is it loaded?)."
    fichier = os.path.basename(infos["fichier"])
    try:
        os.makedirs(os.path.join(racine, "plugins"), exist_ok=True)
        shutil.copyfile(infos["fichier"],
                        os.path.join(racine, "plugins", fichier))
        chemin_registre = os.path.join(racine, "registry.json")
        with open(chemin_registre, encoding="utf-8") as f:
            registre = json.load(f)
        entree = {
            "nom": nom,
            "fichier": fichier,
            "description": infos["description"],
            "auteur": auteur,
            "url": URL_BRUTE_BASE + fichier,
            "dangereux": infos["dangereux"],
        }
        existantes = [e for e in registre["plugins"] if e.get("nom") != nom]
        registre["plugins"] = existantes + [entree]
        with open(chemin_registre, "w", encoding="utf-8") as f:
            json.dump(registre, f, ensure_ascii=False, indent=2)
            f.write("\n")
    except Exception as exc:
        return f"Could not publish: {exc}"
    return synchroniser_site(racine)


def liste() -> list[dict]:
    """Infos d'affichage pour /plugins (sans les callables)."""
    return [
        {k: infos[k] for k in ("nom", "description", "fichier", "dangereux")}
        for infos in _REGISTRE.values()
    ]


def erreurs() -> list[str]:
    return list(_ERREURS)


# --------------------------------------------------------------------------- #
#  Gestion : activer / desactiver / supprimer (menu /plugins)                 #
#                                                                             #
#  Un plugin DESACTIVE = son fichier renomme en *.py.off : le chargeur ne     #
#  voit que les .py, donc il disparait du schema au prochain activer().       #
#  Etat visible dans l'explorateur, zero fichier de config supplementaire.    #
# --------------------------------------------------------------------------- #
SUFFIXE_OFF = ".off"


def lister_desactives(dossier: str = DOSSIER) -> list[str]:
    """Chemins des plugins desactives (*.py.off) du dossier."""
    if not os.path.isdir(dossier):
        return []
    return sorted(glob.glob(os.path.join(dossier, f"*.py{SUFFIXE_OFF}")))


def desactiver_fichier(fichier: str) -> str | None:
    """Renomme x.py -> x.py.off. Retourne un message d'erreur, ou None si OK."""
    try:
        os.replace(fichier, fichier + SUFFIXE_OFF)
        return None
    except OSError as exc:
        return f"Could not disable: {exc}"


def reactiver_fichier(fichier_off: str) -> str | None:
    """Renomme x.py.off -> x.py. Retourne un message d'erreur, ou None si OK."""
    if not fichier_off.endswith(SUFFIXE_OFF):
        return "Not a disabled plugin file."
    try:
        os.replace(fichier_off, fichier_off[: -len(SUFFIXE_OFF)])
        return None
    except OSError as exc:
        return f"Could not enable: {exc}"


def supprimer_fichier(fichier: str) -> str | None:
    """Supprime definitivement le fichier du plugin (actif ou desactive)."""
    try:
        os.remove(fichier)
        return None
    except OSError as exc:
        return f"Could not delete: {exc}"


# --------------------------------------------------------------------------- #
#  Marketplace communautaire                                                  #
#                                                                             #
#  Le REGISTRE est un simple JSON heberge sur le depot GitHub (source de      #
#  verite) ; le site vitrine (Vercel) lit le meme fichier. Chaque entree :    #
#  {"nom", "fichier", "description", "auteur", "url", "dangereux"}.           #
# --------------------------------------------------------------------------- #
URL_REGISTRE = os.environ.get(
    "MARKETPLACE_REGISTRY",
    "https://raw.githubusercontent.com/b4z1z/retroai-agent/main/"
    "marketplace/registry.json",
)
URL_SITE = os.environ.get(
    "MARKETPLACE_SITE", "https://retroai-agent.vercel.app"
)


def catalogue(url: str | None = None) -> tuple[list[dict], str | None]:
    """
    Telecharge le registre du marketplace. Retourne (entrees, erreur) :
    erreur est None si tout va bien, sinon un message clair (hors-ligne...).
    """
    import json
    import requests

    try:
        reponse = requests.get(url or URL_REGISTRE, timeout=10)
        if reponse.status_code != 200:
            return [], f"Marketplace replied HTTP {reponse.status_code}."
        entrees = json.loads(reponse.text).get("plugins", [])
        valides = [
            e for e in entrees
            if e.get("nom") and e.get("fichier") and e.get("url")
        ]
        return valides, None
    except Exception as exc:
        return [], f"Could not reach the marketplace ({exc})."


def installer(entree: dict, dossier: str = DOSSIER) -> str | None:
    """
    Telecharge le plugin decrit par 'entree' dans le dossier plugins/, puis
    VALIDE son contrat avant de le garder (un fichier invalide est supprime).
    Retourne un message d'erreur, ou None si OK.
    """
    import requests

    try:
        reponse = requests.get(entree["url"], timeout=15)
        if reponse.status_code != 200:
            return f"Download failed (HTTP {reponse.status_code})."
        code = reponse.text
    except Exception as exc:
        return f"Download failed ({exc})."

    os.makedirs(dossier, exist_ok=True)
    chemin = os.path.join(dossier, os.path.basename(entree["fichier"]))
    try:
        with open(chemin, "w", encoding="utf-8") as f:
            f.write(code)
    except OSError as exc:
        return f"Could not write the plugin file ({exc})."

    # Validation immediate : si le fichier ne respecte pas le contrat, on le
    # retire (pas de plugin casse persistant apres une installation).
    avant_registre = dict(_REGISTRE)
    avant_erreurs = list(_ERREURS)
    try:
        charger(dossier)
        probleme = next(
            (e for e in _ERREURS if os.path.basename(chemin) in e), None
        )
    finally:
        _REGISTRE.clear(); _REGISTRE.update(avant_registre)
        _ERREURS[:] = avant_erreurs
    if probleme:
        try:
            os.remove(chemin)
        except OSError:
            pass
        return f"Invalid plugin, not kept: {probleme}"
    return None
