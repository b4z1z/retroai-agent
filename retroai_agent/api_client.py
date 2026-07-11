"""
api_client.py - Couche transport vers l'API NVIDIA NIM.

Responsabilite UNIQUE : envoyer une requete HTTP a l'endpoint
chat/completions et rendre la reponse. Ce module ne connait RIEN
aux outils ni a la logique de conversation (cela appartient a
agent_loop.py). Il reste "bete" : il envoie ce qu'on lui donne.

Robustesse geree ici :
    - retry avec backoff exponentiel sur HTTP 429 (Rate Limit) : 5s, 10s, 20s
    - timeout reseau (evite de geler le client sur un vieux PC)
    - messages d'erreur clairs pour les autres codes HTTP / JSON invalide
"""

from __future__ import annotations

import json
import time

import requests

from .config import Config
from . import thinking


# Delais d'attente (secondes) entre chaque nouvelle tentative apres un 429.
# 3 valeurs => 3 reessais maximum, soit 4 tentatives au total.
BACKOFF_DELAIS = [5, 10, 20]

# Le delai max d'UNE requete HTTP est desormais dans la config
# (config.request_timeout, defaut 300s, via REQUEST_TIMEOUT).


class ApiError(Exception):
    """Erreur levee quand l'appel API echoue de maniere non recuperable."""


class QuotaError(ApiError):
    """
    Quota / palier gratuit epuise (HTTP 429 RESOURCE_EXHAUSTED).
    Sous-classe d'ApiError -> les 'except ApiError' existants la capturent
    aussi, mais l'appelant peut la traiter specifiquement (proposer FLUX...).
    """


class TimeoutApiError(ApiError):
    """
    La requete a depasse le delai. Sous-classe d'ApiError ; l'appelant peut
    decider de NE PAS reessayer (relancer ne ferait que re-attendre aussi
    longtemps pour une generation deja longue).
    """


class StreamingInterrompu(ApiError):
    """
    Coupure reseau PENDANT la lecture du flux SSE (ex. read timeout : le
    serveur stalle, vecu en reel avec deepseek-v4-flash surcharge).

    Porte 'deja_streame' : si RIEN n'a encore ete affiche a l'ecran, on peut
    relancer l'appel proprement (aucune duplication). Si du texte etait deja
    apparu, relancer le re-afficherait -> on laisse plutot /continue reprendre.
    """

    def __init__(self, message: str, *, deja_streame: bool) -> None:
        super().__init__(message)
        self.deja_streame = deja_streame


# Message court et clair : limite NIM atteinte. Couvre les deux cas possibles
# (capacite du worker saturee OU quota d'utilisation epuise) car le client ne
# peut pas les distinguer de facon fiable.
MSG_SATURATION = (
    "NVIDIA request limit reached: the server is at capacity OR your usage "
    "limit is exhausted. Wait a bit and try again, or switch model / API key."
)


def _reparer_texte(texte: str) -> str:
    """
    Repare un texte pouvant contenir des "surrogates isoles" invalides
    (U+D800-U+DFFF). Cause : en streaming SSE, un emoji/caractere multi-
    octets peut etre COUPE EN DEUX par le decoupage en morceaux (chaque
    moitie de la paire UTF-16 arrivant dans un fragment JSON distinct,
    decode independamment) -> le caractere reconstitue est invalide et fait
    planter toute ecriture UTF-8 stricte plus tard (session, prochain appel
    API...) avec "UnicodeEncodeError: ... surrogates not allowed".

    Scan CARACTERE PAR CARACTERE (pas de tentative globale encode/decode sur
    toute la chaine : un seul orphelin ferait alors echouer - et remplacer en
    bloc - des paires par ailleurs valides plus loin dans le meme texte) :
      - une paire haute+basse ADJACENTE est RECOMBINEE en le vrai caractere
        d'origine (aucune perte, c'est le cas le plus courant) ;
      - un surrogate qui reste isole (jamais suivi/precede de son binome) est
        remplace par le caractere de remplacement Unicode - mieux vaut perdre
        1 glyphe que planter et perdre toute la conversation.
    Sans effet sur un texte deja propre (idempotent).
    """
    resultat = []
    i, n = 0, len(texte)
    while i < n:
        code = ord(texte[i])
        if 0xD800 <= code <= 0xDBFF:  # moitie HAUTE d'une paire
            if i + 1 < n:
                code2 = ord(texte[i + 1])
                if 0xDC00 <= code2 <= 0xDFFF:  # moitie BASSE valide juste apres
                    vrai = 0x10000 + (code - 0xD800) * 0x400 + (code2 - 0xDC00)
                    resultat.append(chr(vrai))
                    i += 2
                    continue
            resultat.append("\ufffd")  # orpheline -> neutralisee
            i += 1
            continue
        if 0xDC00 <= code <= 0xDFFF:  # moitie BASSE isolee (pas de haute avant)
            resultat.append("\ufffd")
            i += 1
            continue
        resultat.append(texte[i])
        i += 1
    return "".join(resultat)


def _est_modele_introuvable(texte: str) -> bool:
    """
    Vrai si une reponse 404 signifie "le MODELE configure n'est pas/plus
    disponible" (vecu en reel : kimi-k2.6 encore liste au catalogue, mais son
    deploiement NVIDIA cassé -> {"status":404,...,"detail":"Function '...':
    Not found for account '...'"}). Sans ce mapping, l'utilisateur recoit un
    dump JSON cryptique qui ressemble a un bug de l'app alors que c'est une
    indisponibilite cote NVIDIA.
    """
    t = (texte or "").lower()
    return "function" in t and "not found" in t


def _message_modele_introuvable(modele: str) -> str:
    return (
        f"The configured model ({modele}) is currently NOT available on "
        "NVIDIA's side (404 Function not found) - this is not a bug in "
        "BAZIZ.IA and usually temporary. Options: try again later, or switch "
        "model: edit NVIDIA_MODEL in .env then /restart. Your API key is fine."
    )


def _est_saturation(texte: str) -> bool:
    """
    Vrai si une reponse 5xx traduit une SATURATION TRANSITOIRE du worker NIM
    (ex. 'ResourceExhausted: Worker local total request limit reached (33/32)').
    Ce cas est reessayable, contrairement a une vraie erreur serveur.
    """
    t = (texte or "").lower()
    return (
        "resourceexhausted" in t
        or "resource_exhausted" in t
        or "request limit reached" in t
        or "total request limit" in t
    )


def _extraire_image_base64(data: dict) -> str:
    """
    Extrait la chaine base64 de l'image depuis la reponse de l'API genai.
    Tolerant a plusieurs formats possibles (l'endpoint NVIDIA peut renvoyer
    'artifacts', le style OpenAI 'data[].b64_json', ou un champ direct).
    """
    # Format NVIDIA genai (Stability/FLUX) : {"artifacts":[{"base64": "..."}]}
    artifacts = data.get("artifacts")
    if isinstance(artifacts, list) and artifacts:
        b64 = artifacts[0].get("base64") or artifacts[0].get("b64_json")
        if b64:
            return b64
    # Format style OpenAI : {"data":[{"b64_json": "..."}]}
    bloc = data.get("data")
    if isinstance(bloc, list) and bloc:
        b64 = bloc[0].get("b64_json") or bloc[0].get("base64")
        if b64:
            return b64
    # Champ direct eventuel.
    for cle in ("image", "b64_json", "base64"):
        if isinstance(data.get(cle), str):
            return data[cle]
    raise ApiError("The image API response did not contain any image data.")


class ApiClient:
    """Client minimaliste pour l'endpoint chat/completions de NVIDIA NIM."""

    def __init__(self, config: Config) -> None:
        self.config = config
        # Une session requests reutilise la connexion TCP entre les appels
        # (plus rapide, surtout sur une machine modeste).
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    # ------------------------------------------------------------------ #
    #  Construction du payload                                            #
    # ------------------------------------------------------------------ #
    def _construire_payload(self, messages: list, tools: list | None) -> dict:
        """
        Assemble le corps JSON envoye a l'API a partir de la config et
        des messages/outils fournis par l'appelant.
        """
        payload: dict = {
            "model": self.config.model,
            "messages": messages,
            "temperature": 0.6,
        }

        # max_tokens : 0 (defaut) = aucune limite, on ne l'envoie PAS (le
        # modele genere jusqu'a son maximum). > 0 = plafond explicite.
        if self.config.max_tokens > 0:
            payload["max_tokens"] = self.config.max_tokens

        # Le mode "thinking" (raisonnement) est pilote par le niveau courant.
        if thinking.est_actif(self.config.thinking_level):
            payload["chat_template_kwargs"] = {"thinking": True}

        # On n'ajoute la cle "tools" que si des outils sont fournis :
        # envoyer "tools": null ou [] peut faire echouer certains endpoints.
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        return payload

    # ------------------------------------------------------------------ #
    #  Appel principal                                                   #
    # ------------------------------------------------------------------ #
    def chat(self, messages: list, tools: list | None = None, on_texte=None) -> dict:
        """
        Envoie la conversation et retourne la reponse au format JSON "classique"
        (meme structure en streaming et non-streaming -> agent_loop inchange).

        Si config.stream est vrai : reponse recue morceau par morceau
        (on_texte(fragment) appele a chaque bout de texte) -> pas de timeout
        sur les longues generations + affichage en direct. Sinon : reponse
        complete d'un coup. Retry/backoff 429 ; leve ApiError/TimeoutApiError.
        """
        payload = self._construire_payload(messages, tools)
        if self.config.stream:
            payload["stream"] = True
            return self._chat_stream(payload, on_texte)
        return self._chat_simple(payload)

    def _chat_simple(self, payload: dict) -> dict:
        """Appel NON-streaming : la reponse complete arrive d'un coup."""
        url = self.config.base_url

        # On tente 1 fois + autant de reessais que de delais de backoff.
        for tentative in range(len(BACKOFF_DELAIS) + 1):
            try:
                reponse = self.session.post(
                    url, json=payload, timeout=self.config.request_timeout
                )
            except requests.exceptions.Timeout as exc:
                raise TimeoutApiError(
                    f"Request timed out ({self.config.request_timeout}s). "
                    "The task may be large — try a lower /think level, raise "
                    "REQUEST_TIMEOUT in .env, or split the request. "
                    "Type /continue to resume."
                ) from exc
            except requests.exceptions.RequestException as exc:
                raise ApiError(f"Network error: {exc}") from exc

            # --- Cas 429 : Rate Limit -> on attend puis on reessaie ------
            if reponse.status_code == 429:
                if tentative < len(BACKOFF_DELAIS):
                    delai = BACKOFF_DELAIS[tentative]
                    print(
                        f"  [API] Rate limit reached (429). "
                        f"Retrying in {delai}s..."
                    )
                    time.sleep(delai)
                    continue  # on retente la boucle
                raise ApiError(
                    "Rate limit (429) still active after "
                    f"{len(BACKOFF_DELAIS)} retries. Giving up."
                )

            # --- Serveur sature (503 "All workers busy" / "Worker local total
            # request limit reached") -> TRANSITOIRE : on reessaie avec backoff
            # (verifie en reel : deepseek-v4-flash renvoie souvent ce 503, et
            # l'appel suivant quelques secondes plus tard passe). Ce n'est
            # qu'apres avoir epuise les reessais qu'on rend un message clair.
            if reponse.status_code >= 500 and _est_saturation(reponse.text):
                if tentative < len(BACKOFF_DELAIS):
                    delai = BACKOFF_DELAIS[tentative]
                    print(
                        f"  [API] Server at capacity (503). "
                        f"Retrying in {delai}s..."
                    )
                    time.sleep(delai)
                    continue
                raise ApiError(MSG_SATURATION)

            # --- Modele indisponible cote NVIDIA (404 Function not found) -
            if reponse.status_code == 404 and _est_modele_introuvable(reponse.text):
                raise ApiError(_message_modele_introuvable(self.config.model))

            # --- Autres erreurs HTTP : pas recuperables ------------------
            if reponse.status_code != 200:
                extrait = reponse.text[:500]
                raise ApiError(
                    f"HTTP error {reponse.status_code} from the NVIDIA API:\n"
                    f"{extrait}"
                )

            # --- Succes : on parse le JSON ------------------------------
            try:
                return reponse.json()
            except ValueError as exc:
                raise ApiError(
                    "Unreadable API response (invalid JSON)."
                ) from exc

        # Ne devrait jamais arriver, mais par securite :
        raise ApiError("Unexpected API call failure.")

    # ------------------------------------------------------------------ #
    #  Appel STREAMING (SSE) : reponse morceau par morceau               #
    # ------------------------------------------------------------------ #
    def _chat_stream(self, payload: dict, on_texte=None) -> dict:
        """
        Appel streaming : on lit le flux SSE, on accumule le texte (et les
        tool_calls), on appelle on_texte(fragment) a chaque morceau de texte,
        puis on renvoie la MEME structure que _chat_simple.
        """
        url = self.config.base_url
        for tentative in range(len(BACKOFF_DELAIS) + 1):
            try:
                reponse = self.session.post(
                    url, json=payload,
                    timeout=self.config.request_timeout, stream=True,
                    headers={"Accept": "text/event-stream"},
                )
            except requests.exceptions.Timeout as exc:
                raise TimeoutApiError(
                    f"Request timed out ({self.config.request_timeout}s). "
                    "Type /continue to resume."
                ) from exc
            except requests.exceptions.RequestException as exc:
                raise ApiError(f"Network error: {exc}") from exc

            if reponse.status_code == 429:
                if tentative < len(BACKOFF_DELAIS):
                    delai = BACKOFF_DELAIS[tentative]
                    print(f"  [API] Rate limit (429). Retrying in {delai}s...")
                    time.sleep(delai)
                    continue
                raise ApiError("Rate limit (429) still active. Giving up.")
            # 503 sature = transitoire -> reessai backoff (cf. _chat_simple).
            if reponse.status_code >= 500 and _est_saturation(reponse.text):
                if tentative < len(BACKOFF_DELAIS):
                    delai = BACKOFF_DELAIS[tentative]
                    print(
                        f"  [API] Server at capacity (503). "
                        f"Retrying in {delai}s..."
                    )
                    time.sleep(delai)
                    continue
                raise ApiError(MSG_SATURATION)
            if reponse.status_code == 404 and _est_modele_introuvable(reponse.text):
                raise ApiError(_message_modele_introuvable(self.config.model))
            if reponse.status_code != 200:
                raise ApiError(
                    f"HTTP error {reponse.status_code} from the NVIDIA API:\n"
                    f"{reponse.text[:500]}"
                )

            try:
                return self._lire_flux(reponse, on_texte)
            except StreamingInterrompu as exc:
                # Coupure reseau en plein flux. Si RIEN n'a encore ete affiche
                # et qu'il reste des tentatives, on relance proprement (nouvel
                # appel POST) : aucune duplication a l'ecran. Sinon (du texte
                # deja apparu, ou plus de tentatives) on remonte l'erreur ->
                # l'utilisateur reprend avec /continue sans rien perdre.
                if not exc.deja_streame and tentative < len(BACKOFF_DELAIS):
                    delai = BACKOFF_DELAIS[tentative]
                    print(
                        f"  [API] Streaming cut before any output "
                        f"(likely an overloaded server). Retrying in {delai}s..."
                    )
                    time.sleep(delai)
                    continue
                raise TimeoutApiError(str(exc)) from exc

        raise ApiError("Unexpected API call failure.")

    @staticmethod
    def _lire_flux(reponse, on_texte) -> dict:
        """
        Lit le flux SSE et reconstruit le message (texte + tool_calls).

        on_texte(fragment, reflexion) est appele pour chaque morceau :
          - reflexion=True  : morceau de RAISONNEMENT (mode thinking) ->
            affiche en direct mais PAS conserve dans l'historique ;
          - reflexion=False : morceau de la REPONSE finale.
        """
        contenu = ""
        outils: dict = {}
        finish = None
        usage = None
        # Vrai des qu'un morceau de la REPONSE FINALE (content) a ete affiche.
        # Sert a decider si une coupure reseau est rejouable : le RAISONNEMENT
        # (thinking) est jetable et non conserve -> le rejouer ne fait que
        # re-afficher une reflexion, sans dupliquer de vraie reponse. Seul le
        # 'content' deja montre a l'ecran interdit un reessai propre. C'est le
        # cas FREQUENT avec un modele de raisonnement lent (deepseek-v4-flash) :
        # le read timeout tombe pendant le long thinking -> on DOIT pouvoir
        # relancer meme si du raisonnement a deja defile.
        a_streame = False
        try:
            for ligne in reponse.iter_lines(decode_unicode=True):
                if not ligne:
                    continue
                if ligne.startswith("data:"):
                    ligne = ligne[5:].strip()
                if ligne == "[DONE]":
                    break
                try:
                    obj = json.loads(ligne)
                except ValueError:
                    continue  # ligne non-JSON (keep-alive...) -> on ignore
                # Comptes de tokens : certains serveurs les envoient dans le
                # dernier morceau du flux -> on les capture s'ils passent
                # (sert au compteur /btw ; sinon estimation cote client).
                if obj.get("usage"):
                    usage = obj["usage"]
                choix = (obj.get("choices") or [{}])[0]
                delta = choix.get("delta") or {}
                # Raisonnement (thinking) streame par NIM : montre en direct
                # pour que l'utilisateur VOIE que le modele travaille.
                frag_pense = delta.get("reasoning_content") or delta.get("reasoning")
                if frag_pense and on_texte:
                    on_texte(frag_pense, True)  # raisonnement : NE bloque PAS le reessai
                frag = delta.get("content")
                if frag:
                    contenu += frag
                    a_streame = True  # vraie reponse affichee -> plus rejouable
                    if on_texte:
                        on_texte(frag, False)
                for tc in (delta.get("tool_calls") or []):
                    idx = tc.get("index", 0)
                    slot = outils.setdefault(
                        idx,
                        {"id": None, "type": "function",
                         "function": {"name": "", "arguments": ""}},
                    )
                    if tc.get("id"):
                        slot["id"] = tc["id"]
                    fonction = tc.get("function") or {}
                    if fonction.get("name"):
                        slot["function"]["name"] += fonction["name"]
                    if fonction.get("arguments"):
                        slot["function"]["arguments"] += fonction["arguments"]
                if choix.get("finish_reason"):
                    finish = choix["finish_reason"]
        except requests.exceptions.RequestException as exc:
            # Coupure reseau en plein flux (souvent un read timeout : le serveur
            # stalle). Rejouable SEULEMENT si rien n'a encore ete affiche.
            raise StreamingInterrompu(
                f"Network error during streaming: {exc}",
                deja_streame=a_streame,
            ) from exc

        message = {"role": "assistant", "content": _reparer_texte(contenu)}
        if outils:
            message["tool_calls"] = [outils[i] for i in sorted(outils)]
        resultat = {"choices": [{"message": message, "finish_reason": finish}]}
        if usage:
            resultat["usage"] = usage
        return resultat

    # ------------------------------------------------------------------ #
    #  Generation d'image (text-to-image) - endpoint genai (FLUX)        #
    # ------------------------------------------------------------------ #
    def generer_image(
        self,
        prompt: str,
        *,
        width: int = 1024,
        height: int = 1024,
        steps: int = 50,
        cfg_scale: float = 3.5,
        seed: int = 0,
    ) -> str:
        """
        Genere une image a partir d'un prompt texte et retourne sa donnee
        base64 (a decoder/sauver par l'appelant). Utilise le modele image de
        la config (FLUX par defaut) sur l'endpoint genai, avec la meme cle API.

        Gere le retry/backoff sur 429 comme chat(). Leve ApiError si echec.
        """
        url = f"{self.config.image_base_url.rstrip('/')}/{self.config.image_model}"
        payload = {
            "prompt": prompt,
            "mode": "base",
            "cfg_scale": cfg_scale,
            "width": width,
            "height": height,
            "seed": seed,
            "steps": steps,
        }

        for tentative in range(len(BACKOFF_DELAIS) + 1):
            try:
                reponse = self.session.post(
                    url, json=payload, timeout=self.config.request_timeout
                )
            except requests.exceptions.Timeout as exc:
                raise TimeoutApiError(
                    f"Image request timed out ({self.config.request_timeout}s)."
                ) from exc
            except requests.exceptions.RequestException as exc:
                raise ApiError(f"Network error: {exc}") from exc

            if reponse.status_code == 429:
                if tentative < len(BACKOFF_DELAIS):
                    delai = BACKOFF_DELAIS[tentative]
                    print(f"  [API] Rate limit (429). Retrying in {delai}s...")
                    time.sleep(delai)
                    continue
                raise ApiError("Rate limit (429) still active. Giving up.")

            # Limite NIM atteinte -> message clair, pas de retry inutile.
            if reponse.status_code >= 500 and _est_saturation(reponse.text):
                raise ApiError(MSG_SATURATION)

            if reponse.status_code != 200:
                raise ApiError(
                    f"HTTP error {reponse.status_code} from the image API:\n"
                    f"{reponse.text[:500]}"
                )

            try:
                data = reponse.json()
            except ValueError as exc:
                raise ApiError("Unreadable image API response (invalid JSON).") from exc
            return _extraire_image_base64(data)

        raise ApiError("Unexpected image API call failure.")
