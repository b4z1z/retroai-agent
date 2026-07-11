"""Tests du client API : parsing du flux SSE (streaming) et helpers."""

import pytest
import requests

from retroai_agent.api_client import (
    ApiClient,
    ApiError,
    StreamingInterrompu,
    TimeoutApiError,
    _est_saturation,
    _extraire_image_base64,
)


class _FluxFactice:
    """Simule une reponse requests en mode stream (iter_lines)."""

    status_code = 200

    def __init__(self, lignes):
        self._lignes = lignes

    def iter_lines(self, decode_unicode=True):
        yield from self._lignes


class _FluxQuiCoupe:
    """Flux SSE qui emet 'lignes' puis leve une coupure reseau (read timeout)
    en pleine iteration, comme un serveur qui stalle."""

    status_code = 200
    text = ""

    def __init__(self, lignes):
        self._lignes = lignes

    def iter_lines(self, decode_unicode=True):
        yield from self._lignes
        raise requests.exceptions.ConnectionError("Read timed out.")


def test_lire_flux_texte_raisonnement_et_outils():
    lignes = [
        # raisonnement (thinking) streame
        'data: {"choices":[{"delta":{"reasoning_content":"je "}}]}',
        'data: {"choices":[{"delta":{"reasoning_content":"reflechis"}}]}',
        # reponse en 2 fragments
        'data: {"choices":[{"delta":{"content":"Bon"}}]}',
        'data: {"choices":[{"delta":{"content":"jour"},"finish_reason":null}]}',
        "",  # ligne vide (separateur SSE) -> ignoree
        "event: ping",  # ligne non-data non-JSON -> ignoree
        # tool_call fragmente sur 2 lignes
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"a",'
        '"function":{"name":"read_file","arguments":"{\\"pa"}}]}}]}',
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,'
        '"function":{"arguments":"th\\":\\"x\\"}"}}]},"finish_reason":"tool_calls"}]}',
        "data: [DONE]",
        'data: {"choices":[{"delta":{"content":"APRES-DONE"}}]}',  # jamais lu
    ]
    recu = []
    res = ApiClient._lire_flux(
        _FluxFactice(lignes), lambda frag, pense=False: recu.append((frag, pense))
    )
    message = res["choices"][0]["message"]

    # Le contenu ne contient QUE la reponse (pas le raisonnement).
    assert message["content"] == "Bonjour"
    # Le raisonnement a bien ete streame avec le drapeau True.
    assert ("je ", True) in recu and ("reflechis", True) in recu
    assert ("Bon", False) in recu
    # tool_calls reconstruit depuis les fragments.
    (outil,) = message["tool_calls"]
    assert outil["function"]["name"] == "read_file"
    assert outil["function"]["arguments"] == '{"path":"x"}'
    assert res["choices"][0]["finish_reason"] == "tool_calls"
    # [DONE] stoppe la lecture.
    assert "APRES-DONE" not in message["content"]


def test_lire_flux_sans_callback():
    lignes = ['data: {"choices":[{"delta":{"content":"ok"}}]}', "data: [DONE]"]
    res = ApiClient._lire_flux(_FluxFactice(lignes), None)
    assert res["choices"][0]["message"]["content"] == "ok"


def test_est_modele_introuvable():
    """Reproduit le 404 reel : deploiement kimi casse cote NVIDIA alors que
    le modele etait encore liste au catalogue."""
    from retroai_agent.api_client import (
        _est_modele_introuvable, _message_modele_introuvable,
    )
    reel = ('{"status":404,"title":"Not Found","detail":"Function '
            "'23d4f03a-b8a6-4adb-a183-7daa083a09cc': Not found for account "
            "'UNswZ6yevGCkOJl2zmoIsoLrM2dEhf1NzxNsYQoZGuc'\"}")
    assert _est_modele_introuvable(reel)
    assert not _est_modele_introuvable('{"detail":"route not found"}')  # pas une function
    assert not _est_modele_introuvable("")

    message = _message_modele_introuvable("moonshotai/kimi-k2.6")
    assert "moonshotai/kimi-k2.6" in message
    assert "NVIDIA_MODEL" in message          # dit QUOI faire
    assert "not a bug" in message             # rassure : pas un bug de l'app


def test_est_saturation():
    vrai = (
        '{"message":"ResourceExhausted: Worker local total request limit '
        'reached (33/32)","type":"internal_server_error","code":500}'
    )
    assert _est_saturation(vrai)
    assert not _est_saturation('{"message":"internal error"}')
    assert not _est_saturation("")


def test_extraire_image_base64_formats():
    assert _extraire_image_base64({"artifacts": [{"base64": "AAA"}]}) == "AAA"
    assert _extraire_image_base64({"data": [{"b64_json": "BBB"}]}) == "BBB"
    assert _extraire_image_base64({"image": "CCC"}) == "CCC"
    with pytest.raises(ApiError):
        _extraire_image_base64({"foo": 1})


# --------------------------------------------------------------------------- #
#  REGRESSION - crash reel : le streaming SSE peut couper un emoji en 2       #
#  moitiees de paire UTF-16, chacune arrivant dans une ligne "data:" distincte#
#  (donc decodee separement par json.loads()). Le contenu reconstitue via    #
#  simple concatenation contenait alors un "surrogate isole" invalide, qui    #
#  faisait planter sessions.sauver() plus tard (UnicodeEncodeError). _lire_   #
#  flux() doit desormais reparer ca AVANT de renvoyer le message.            #
# --------------------------------------------------------------------------- #
def test_lire_flux_repare_un_emoji_coupe_en_deux_par_le_streaming():
    lignes = [
        'data: {"choices":[{"delta":{"content":"Le site "}}]}',
        # L'emoji U+1F30C est coupe : sa moitie haute arrive dans CETTE ligne...
        'data: {"choices":[{"delta":{"content":"\\ud83c"}}]}',
        # ...et sa moitie basse arrive dans la ligne SSE SUIVANTE.
        'data: {"choices":[{"delta":{"content":"\\udf0c est pret !"}}]}',
        "data: [DONE]",
    ]
    resultat = ApiClient._lire_flux(_FluxFactice(lignes), None)
    contenu = resultat["choices"][0]["message"]["content"]

    assert "\U0001F30C" in contenu   # le vrai emoji est recupere, aucune perte
    assert contenu.encode("utf-8")  # ne doit PAS lever UnicodeEncodeError
    assert all(not (0xD800 <= ord(c) <= 0xDFFF) for c in contenu)


def test_lire_flux_repare_un_surrogate_orphelin_sans_planter():
    """Si la moitie basse n'arrive jamais (flux coupe net), pas de crash."""
    lignes = [
        'data: {"choices":[{"delta":{"content":"Texte "}}]}',
        'data: {"choices":[{"delta":{"content":"\\ud83c"}}]}',
        "data: [DONE]",
    ]
    resultat = ApiClient._lire_flux(_FluxFactice(lignes), None)
    contenu = resultat["choices"][0]["message"]["content"]

    assert contenu.encode("utf-8")  # ne leve pas, meme sans reassemblage possible
    assert all(not (0xD800 <= ord(c) <= 0xDFFF) for c in contenu)


# --------------------------------------------------------------------------- #
#  REGRESSION - coupure reseau EN PLEIN STREAMING (read timeout) : vecu en    #
#  reel avec deepseek-v4-flash surcharge. Si rien n'a encore ete affiche, on  #
#  doit pouvoir relancer proprement ; sinon on remonte pour /continue.        #
# --------------------------------------------------------------------------- #
def test_lire_flux_coupure_avant_tout_output_est_rejouable():
    """Rien n'a ete streame avant la coupure -> deja_streame False."""
    flux = _FluxQuiCoupe([])  # coupe immediatement, aucun morceau
    with pytest.raises(StreamingInterrompu) as info:
        ApiClient._lire_flux(flux, lambda *a, **k: None)
    assert info.value.deja_streame is False


def test_lire_flux_coupure_apres_contenu_final_non_rejouable():
    """La REPONSE FINALE (content) a deja ete affichee -> deja_streame True
    (rejouer dupliquerait la vraie reponse a l'ecran)."""
    flux = _FluxQuiCoupe(['data: {"choices":[{"delta":{"content":"Deja vu"}}]}'])
    recu = []
    with pytest.raises(StreamingInterrompu) as info:
        ApiClient._lire_flux(flux, lambda frag, pense=False: recu.append(frag))
    assert info.value.deja_streame is True
    assert "Deja vu" in recu  # a bien ete affiche avant la coupure


def test_lire_flux_coupure_pendant_raisonnement_reste_rejouable():
    """Cas FREQUENT deepseek : le timeout tombe pendant le THINKING. Le
    raisonnement est jetable -> deja_streame False, on peut relancer proprement."""
    flux = _FluxQuiCoupe([
        'data: {"choices":[{"delta":{"reasoning_content":"je reflechis..."}}]}',
    ])
    penses = []
    with pytest.raises(StreamingInterrompu) as info:
        ApiClient._lire_flux(
            flux, lambda frag, pense=False: penses.append((frag, pense))
        )
    assert info.value.deja_streame is False   # raisonnement ne bloque PAS
    assert ("je reflechis...", True) in penses  # il a bien defile a l'ecran


class _SessionFactice:
    """Simule requests.Session.post : renvoie des reponses fixees dans l'ordre."""

    def __init__(self, reponses):
        self._reponses = list(reponses)
        self.appels = 0

    def post(self, *args, **kwargs):
        self.appels += 1
        return self._reponses.pop(0)


def _client_stream():
    from retroai_agent.config import Config
    cfg = Config(api_key="x", base_url="u", model="m", enable_thinking=False,
                 shell_timeout=5, auto_safe_commands=False, stream=True)
    return ApiClient(cfg)


def test_chat_stream_reessaie_apres_coupure_sans_output(monkeypatch):
    """Coupure avant tout output -> nouvel appel POST automatique, ca reussit."""
    monkeypatch.setattr("retroai_agent.api_client.time.sleep", lambda _s: None)
    bon_flux = _FluxFactice([
        'data: {"choices":[{"delta":{"content":"Reponse OK"}}]}',
        "data: [DONE]",
    ])
    client = _client_stream()
    client.session = _SessionFactice([_FluxQuiCoupe([]), bon_flux])

    res = client._chat_stream({"model": "m"}, on_texte=None)

    assert res["choices"][0]["message"]["content"] == "Reponse OK"
    assert client.session.appels == 2  # 1 coupure + 1 reessai reussi


def test_chat_stream_ne_reessaie_pas_si_deja_affiche(monkeypatch):
    """Si du texte etait deja apparu, on NE relance PAS (eviter le doublon) :
    on remonte un TimeoutApiError -> l'utilisateur reprend via /continue."""
    monkeypatch.setattr("retroai_agent.api_client.time.sleep", lambda _s: None)
    client = _client_stream()
    client.session = _SessionFactice([
        _FluxQuiCoupe(['data: {"choices":[{"delta":{"content":"Debut"}}]}']),
    ])

    with pytest.raises(TimeoutApiError):
        client._chat_stream({"model": "m"}, on_texte=lambda *a, **k: None)
    assert client.session.appels == 1  # aucun reessai


# --------------------------------------------------------------------------- #
#  503 "server at capacity" est TRANSITOIRE (vecu en reel avec deepseek-      #
#  v4-flash) : l'appel suivant quelques secondes plus tard passe. Le client   #
#  doit donc REESSAYER avec backoff, pas abandonner au 1er 503.               #
# --------------------------------------------------------------------------- #
_TXT_503 = ('{"message":"ResourceExhausted: Worker local total request limit '
           'reached (33/32)","type":"internal_server_error","code":500}')


class _Reponse503:
    status_code = 503
    text = _TXT_503


class _Reponse200Json:
    status_code = 200

    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


def _client_simple():
    from retroai_agent.config import Config
    cfg = Config(api_key="x", base_url="u", model="m", enable_thinking=False,
                 shell_timeout=5, auto_safe_commands=False, stream=False)
    return ApiClient(cfg)


def test_chat_simple_reessaie_sur_503_sature(monkeypatch):
    monkeypatch.setattr("retroai_agent.api_client.time.sleep", lambda _s: None)
    bon = _Reponse200Json(
        {"choices": [{"message": {"role": "assistant", "content": "OK"}}]}
    )
    client = _client_simple()
    client.session = _SessionFactice([_Reponse503(), _Reponse503(), bon])

    res = client._chat_simple({"model": "m"})

    assert res["choices"][0]["message"]["content"] == "OK"
    assert client.session.appels == 3  # 2x 503 retentes + 1 succes


def test_chat_stream_reessaie_sur_503_sature(monkeypatch):
    monkeypatch.setattr("retroai_agent.api_client.time.sleep", lambda _s: None)
    bon_flux = _FluxFactice([
        'data: {"choices":[{"delta":{"content":"OK"}}]}', "data: [DONE]",
    ])
    client = _client_stream()
    client.session = _SessionFactice([_Reponse503(), bon_flux])

    res = client._chat_stream({"model": "m"}, on_texte=None)

    assert res["choices"][0]["message"]["content"] == "OK"
    assert client.session.appels == 2  # 1x 503 retente + 1 succes


def test_chat_simple_503_persistant_finit_par_abandonner(monkeypatch):
    """Si le 503 ne se debloque jamais, on rend le message clair (pas de boucle
    infinie)."""
    from retroai_agent.api_client import BACKOFF_DELAIS
    monkeypatch.setattr("retroai_agent.api_client.time.sleep", lambda _s: None)
    client = _client_simple()
    client.session = _SessionFactice(
        [_Reponse503() for _ in range(len(BACKOFF_DELAIS) + 1)]
    )

    with pytest.raises(ApiError) as info:
        client._chat_simple({"model": "m"})
    assert "capacity" in str(info.value).lower() or "limit" in str(info.value).lower()
    assert client.session.appels == len(BACKOFF_DELAIS) + 1
