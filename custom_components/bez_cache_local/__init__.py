"""No-cache dla /local/ i plikow .js (poza plikami samego HA)."""
import functools
import logging
import types

from aiohttp import web
from aiohttp.hdrs import CACHE_CONTROL
from homeassistant.components.http import server as ha_server
from homeassistant.components.http import static as ha_static

_LOGGER = logging.getLogger(__name__)
POMIN = ("/frontend_latest", "/frontend_es5", "/static")
JS = (".js", ".mjs")


async def async_setup(hass, config):
    # 1) foldery (StaticResource): /local/... oraz .js spoza plikow HA
    klasa = getattr(ha_static, "CachingStaticResource", None)
    oryg = getattr(klasa, "_handle", None)
    nowy_handle = None
    if oryg is None:
        _LOGGER.warning("bez_cache_local: brak CachingStaticResource._handle")
    elif getattr(oryg, "_bez_cache", False):
        nowy_handle = oryg
    else:
        async def _handle(self, request):
            response = await oryg(self, request)
            try:
                prefix = getattr(self, "_prefix", "")
                if not prefix.startswith(POMIN) and (
                    prefix.startswith("/local") or request.path.endswith(JS)
                ):
                    response.headers[CACHE_CONTROL] = "no-cache"
            except Exception:
                _LOGGER.exception("bez_cache_local: blad przy ustawianiu naglowka")
            return response

        _handle._bez_cache = True
        klasa._handle = _handle
        nowy_handle = _handle

    # 2) pojedyncze pliki (np. /browser_mod.js, /crowdsec-card/crowdsec-card.js)
    oryg_plik = getattr(ha_server, "_serve_file_with_cache_headers", None)
    nowy_plik = None
    if oryg_plik is None:
        _LOGGER.warning("bez_cache_local: brak _serve_file_with_cache_headers")
    elif getattr(oryg_plik, "_bez_cache", False):
        nowy_plik = oryg_plik
        oryg_plik = oryg_plik._oryg
    else:
        async def _plik(path, request):
            if str(path).endswith(JS):
                return web.FileResponse(path, headers={CACHE_CONTROL: "no-cache"})
            return await oryg_plik(path, request)

        _plik._bez_cache = True
        _plik._oryg = oryg_plik
        ha_server._serve_file_with_cache_headers = _plik  # pliki rejestrowane pozniej
        nowy_plik = _plik

    # 3) trasy utworzone przed startem integracji - podpinamy nowe funkcje
    foldery = pliki = 0
    try:
        for res in hass.http.app.router.resources():
            for route in res:
                h = route.handler
                if nowy_handle and klasa and isinstance(res, klasa):
                    route._handler = types.MethodType(nowy_handle, res)
                    foldery += 1
                elif nowy_plik and isinstance(h, functools.partial) and h.func is oryg_plik:
                    route._handler = functools.partial(nowy_plik, *h.args, **h.keywords)
                    pliki += 1
    except Exception:
        _LOGGER.exception("bez_cache_local: blad przy podpinaniu tras")
    _LOGGER.warning("bez_cache_local: aktywne, podpieto tras: foldery %s, pliki %s", foldery, pliki)
    return True
