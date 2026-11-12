# Bez cache /local i JS

Integracja dla Home Assistant. Pliki z `/local/` i pliki `.js` (karty, panele) dostaja naglowek `Cache-Control: no-cache` zamiast 31 dni. Pliki samego HA (`/frontend_latest`, `/frontend_es5`, `/static`) zostaja z cache.

Wlaczenie: w `configuration.yaml` dopisz `bez_cache_local:` i zrestartuj HA.
