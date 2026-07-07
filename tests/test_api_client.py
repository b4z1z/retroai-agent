"""Tests du client API : parsing du flux SSE (streaming) et helpers."""

import pytest

from retroai_agent.api_client import (
    ApiClient,
    ApiError,
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
