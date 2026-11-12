"""No-cache dla /local/ i plikow .js (poza plikami samego HA)."""
import logging

from aiohttp.hdrs import CACHE_CONTROL
from homeassistant.components.http import static as ha_static

_LOGGER = logging.getLogger(__name__)
POMIN = ("/frontend_latest", "/frontend_es5", "/static")


async def async_setup(hass, config):
    klasa = getattr(ha_static, "CachingStaticResource", None)
    oryg = getattr(klasa, "_handle", None)
    if oryg is None:
        _LOGGER.warning("bez_cache_local: brak CachingStaticResource._handle, nic nie zmieniam")
        return True
    if getattr(oryg, "_bez_cache", False):
        return True

    async def _handle(self, request):
        response = await oryg(self, request)
        try:
            prefix = getattr(self, "_prefix", "")
            if not prefix.startswith(POMIN) and (
                prefix.startswith("/local") or request.path.endswith((".js", ".mjs"))
            ):
                response.headers[CACHE_CONTROL] = "no-cache"
        except Exception:
            _LOGGER.exception("bez_cache_local: blad przy ustawianiu naglowka")
        return response

    _handle._bez_cache = True
    klasa._handle = _handle
    _LOGGER.info("bez_cache_local: aktywne")
    return True
