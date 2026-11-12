# Bez cache /local i JS

Integracja dla Home Assistant, która wyłącza 31-dniowy cache przeglądarki dla własnych plików frontendu: wszystkiego z `/local/` oraz plików `.js` dodawanych przez integracje (karty, panele, skrypty). Pliki samego Home Assistanta nadal są cache'owane.

*English summary at the bottom.*

---

## Po co to jest

Home Assistant wysyła dla plików z `/local/` (folder `www`) oraz dla plików rejestrowanych przez integracje nagłówek:

```
Cache-Control: public, max-age=2678400
```

To 31 dni. Wartość jest wpisana na sztywno w kodzie HA (`homeassistant/components/http/static.py`, stała `CACHE_HEADER`) i nie da się jej zmienić w `configuration.yaml`.

Skutek: po zmianie własnej karty, panelu (`panel_custom`) albo skryptu w `www` przeglądarka i aplikacja mobilna Home Assistant (Companion) dalej używają starej wersji. Pomaga dopiero ręczne czyszczenie cache na każdym urządzeniu (w aplikacji: Ustawienia → Aplikacja → Rozwiązywanie problemów → Zresetuj cache frontendu) albo zmiana adresu pliku (`?v=...`).

Reguły w Cloudflare albo reverse proxy (np. Nginx Proxy Manager) rozwiązują to tylko dla ruchu, który przez nie przechodzi. Połączenie lokalne w domu (np. `https://twoj-adres:8123`) omija je i nadal dostaje 31 dni. Ta integracja zmienia nagłówek **w samym Home Assistancie**, więc działa przy każdym sposobie łączenia: lokalnie, przez internet, przez VPN i bez internetu.

## Co dokładnie robi

| Pliki | Nagłówek po instalacji |
|---|---|
| `/local/...` (cały folder `www`, w tym karty z HACS / Marketplace w `/local/community/`) | `Cache-Control: no-cache` |
| pliki `.js` i `.mjs` rejestrowane przez integracje poza `/local` (np. `/browser_mod.js`) | `Cache-Control: no-cache` |
| pliki samego HA: `/frontend_latest/`, `/frontend_es5/`, `/static/` | bez zmian (31 dni) |
| inne pliki spoza `/local` (obrazki, czcionki itp.) | bez zmian (31 dni) |

`no-cache` **nie oznacza** pobierania pliku za każdym razem od nowa. Przeglądarka pyta serwer, czy plik się zmienił (`If-Modified-Since`), i gdy nie, dostaje krótką odpowiedź `304 Not Modified`. Ruch i czas ładowania praktycznie się nie zmieniają, a po zmianie pliku nowa wersja jest widoczna od razu po odświeżeniu strony.

## Jak to działa (technicznie)

Home Assistant serwuje pliki statyczne na dwa sposoby, oba w komponencie `http`:

1. **Foldery** (`/local`, foldery integracji) przez klasę `CachingStaticResource` (`components/http/static.py`). Nagłówek ustawia jej metoda `_handle`.
2. **Pojedyncze pliki** (np. `/browser_mod.js`) przez funkcję `_serve_file_with_cache_headers` (`components/http/server.py`), podpinaną jako `functools.partial` do trasy.

Integracja przy starcie:

1. Podmienia `CachingStaticResource._handle` na wersję, która po wygenerowaniu odpowiedzi ustawia `no-cache` dla `/local` i plików `.js`/`.mjs`, z pominięciem `/frontend_latest`, `/frontend_es5` i `/static`.
2. Podmienia `_serve_file_with_cache_headers` w module `server` na wersję, która dla plików `.js`/`.mjs` zwraca `no-cache`, a dla pozostałych woła oryginał. Dzięki temu obejmuje też pliki rejestrowane przez integracje uruchamiane później.
3. Przechodzi po trasach już zarejestrowanych w `hass.http.app.router` i podpina im nowe funkcje. Jest to konieczne, bo aiohttp zapamiętuje funkcję obsługi w chwili tworzenia trasy, więc sama podmiana w klasie nie obejmuje tras utworzonych wcześniej (np. `/local`).

Po starcie w logu pojawia się ostrzeżenie (poziom WARNING, żeby było widoczne przy domyślnym `logger: default: warning`):

```
bez_cache_local: aktywne, podpieto tras: foldery N, pliki M
```

## Bezpieczeństwo i zgodność

- To **podmiana wewnętrznych funkcji Home Assistanta** (monkeypatch). Nie zmienia żadnych plików HA na dysku, działa tylko w pamięci do restartu.
- Jeśli w przyszłej wersji HA nazwy tych funkcji się zmienią, integracja **niczego nie zepsuje**. Zapisze ostrzeżenie w logu (`brak CachingStaticResource._handle` lub `brak _serve_file_with_cache_headers`) i nie zrobi nic, a wtedy wraca zwykły cache na 31 dni.
- Błędy przy ustawianiu nagłówka są łapane i logowane, nie trafiają do przeglądarki.
- Przetestowane na: Home Assistant **2026.11.1**, aiohttp **3.14.5**, Python 3.14 (Home Assistant OS, x86-64). Po każdej aktualizacji HA warto sprawdzić działanie (sekcja „Sprawdzenie”).

## Instalacja

### A. Przez Marketplace (HA 2026.11+) albo HACS

1. **Ustawienia → Marketplace → Dodaj z linku** (w HACS: ⋮ → Custom repositories).
2. Adres: `https://github.com/casper255/ha-bez-cache-local`, typ: **Integracja**.
3. Zainstaluj „Bez cache /local i JS”.

Do dodawania z linku Marketplace wymaga połączonego konta GitHub i zaakceptowania ostrzeżenia o projektach społeczności.

### B. Ręcznie

Skopiuj folder `custom_components/bez_cache_local` do `/config/custom_components/`.

### Włączenie (w obu przypadkach)

W `configuration.yaml` dopisz:

```yaml
bez_cache_local:
```

i **zrestartuj Home Assistant**. Integracja nie ma żadnych opcji ani konfiguracji w interfejsie.

Po pierwszym uruchomieniu zresetuj jeden raz cache na urządzeniach, które już mają zapisane stare pliki (przeglądarka: twarde odświeżenie; aplikacja: Rozwiązywanie problemów → Zresetuj cache frontendu). Pliki zapisane przed instalacją przeglądarka trzyma do 31 dni. Później nie jest to już potrzebne.

## Sprawdzenie

Z dowolnego komputera w sieci (podmień adres):

```bash
for u in /local/community/lovelace-mushroom/mushroom.js /browser_mod.js /frontend_latest/core.js; do
  echo "$u: $(curl -sk -o /dev/null -D - "https://TWOJ-HA:8123$u" | grep -i '^cache-control')"
done
```

Oczekiwany wynik:
- pliki z `/local/` i `.js` integracji: `Cache-Control: no-cache`,
- `/frontend_latest/...`: `Cache-Control: public, max-age=2678400`.

Pliki `core.js` i `mushroom.js` mają u ciebie inne nazwy i ścieżki. Weź dowolny plik z listy zasobów dashboardu (Ustawienia → Dashboardy → ⋮ → Zasoby) i dowolny plik z `/frontend_latest/` widoczny w źródle strony.

W logu (Ustawienia → System → Logi) powinien być wpis `bez_cache_local: aktywne, podpieto tras: ...`.

## Odinstalowanie

1. Usuń linię `bez_cache_local:` z `configuration.yaml`.
2. Zrestartuj HA (wraca zwykły cache na 31 dni).
3. Odinstaluj integrację w Marketplace / HACS albo usuń folder `custom_components/bez_cache_local`.

## Rozwiązywanie problemów

| Objaw | Przyczyna / co zrobić |
|---|---|
| Brak wpisu `aktywne` w logu | Brak `bez_cache_local:` w `configuration.yaml` albo HA nie był restartowany. |
| W logu `brak CachingStaticResource._handle` / `brak _serve_file_with_cache_headers` | Nowa wersja HA zmieniła kod wewnętrzny. Integracja nic nie robi; zgłoś problem w Issues. |
| Nagłówek nadal `max-age=2678400` dla jakiegoś pliku `.js` | Sprawdź, czy plik nie leży w `/frontend_latest`, `/frontend_es5` lub `/static` (te są celowo pomijane). Jeśli nie, zgłoś adres pliku w Issues. |
| Przez Cloudflare / proxy inny nagłówek niż lokalnie | Proxy może nadpisywać `Cache-Control` własnymi regułami. Integracja działa na nagłówku wysyłanym przez HA. |
| Mimo `no-cache` stara wersja na jednym urządzeniu | To plik zapisany przed instalacją integracji. Jednorazowo zresetuj cache na tym urządzeniu. |

## Historia wersji

- **1.0.2**: obsługa pojedynczych plików rejestrowanych przez integracje (`_serve_file_with_cache_headers`), także tych rejestrowanych po starcie integracji.
- **1.0.1**: podpinanie tras utworzonych przed startem integracji (aiohttp zapamiętuje funkcję obsługi przy tworzeniu trasy).
- **1.0.0**: pierwsza wersja (nie działała dla tras utworzonych przed startem).

---

## English summary

Home Assistant serves `/local/` (the `www` folder) and integration-registered frontend files with a hard-coded `Cache-Control: public, max-age=2678400` (31 days), so browsers and the Companion app keep stale custom cards and panels. Proxy rules (Cloudflare, NPM) do not help for direct local connections.

This integration patches, in memory, the two places Home Assistant uses to serve static files (`CachingStaticResource._handle` for folders and `_serve_file_with_cache_headers` for single files) and re-binds the already-registered aiohttp routes. Result: `/local/*` and integration `.js`/`.mjs` files get `Cache-Control: no-cache` (still answered with `304 Not Modified` when unchanged). Home Assistant's own files (`/frontend_latest`, `/frontend_es5`, `/static`) keep their long cache.

Install via Marketplace/HACS custom repository or copy `custom_components/bez_cache_local`, add `bez_cache_local:` to `configuration.yaml`, restart. If a future HA version renames the patched internals, the integration only logs a warning and does nothing. Tested on Home Assistant 2026.11.1 / aiohttp 3.14.5.
