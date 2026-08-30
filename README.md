# Domácí rodinný asistent

Učební projekt: postupně stavíme domácí asistenta pro rodinu.
Dlouhodobý cíl je webová aplikace s dashboardem (data z domácnosti),
kolaborativním nákupním seznamem a ovládáním chytrých zařízení.

Kompletní zadání a roadmapa: [`docs/zadani-projektu.md`](docs/zadani-projektu.md)

## Aktuální fáze

**Fáze 7 — nasazení na server.** Fáze 1–4 jsou hotové a aplikace už umí
běžet v produkčním režimu; zbývá ji rozběhnout na skutečném serveru.

- [x] Fáze 1 — čtení Nanoleaf (lokální REST API) a SolaX (lokálně z Wi-Fi dongle)
- [x] Fáze 2 — webový dashboard (Flask + šablona + CSS ve třech vrstvách)
- [x] Fáze 3, krok 1 — databáze umí uložit a přečíst měření
- [x] Fáze 3, krok 2 — `sber.py` plní databázi sám
- [x] Fáze 3, krok 3 — grafy z historie na stránce
- [x] Fáze 4 — přihlašování (účty, hashovaná hesla, zamčený dashboard)
- [x] Nákupní seznam — společný pro rodinu (přidávání, odškrtávání, úklid)
- [x] Správa uživatelů — účty a práva na jednotlivé taby
- [x] Příprava na produkci, blok 1 — zabezpečená cookie, ProxyFix, gunicorn
- [ ] **Fáze 7 — nasazení na cloudový server  ← DALŠÍ KROK**
- [ ] Fáze 5 — ovládání zařízení (zapínání Nanoleaf)

Data se sbírají do `asistent.db`, dokud běží `sber.py`.

## Struktura

```
devices/
  nanoleaf.py       čtení stavu Nanoleaf panelů
  solax.py          čtení stavu solární elektrárny
web.py              webový server (Flask) — spouští stránku v prohlížeči
static/
  style.css         vzhled (barvy jako proměnné, světlý i tmavý motiv)
  motiv.js          přepínač motivu (jediný JavaScript v projektu)
templates/
  zaklad.html       společná kostra všech stránek (hlavička, navigace)
  motiv_skript.html nastavení motivu před vykreslením (proti blikání)
  makra.html        znovupoužitelné kousky (graf, tabulka)
  prehled.html      tab Přehled
  solary.html       tab Soláry
  nanoleaf.html     tab Nanoleaf
  nakup.html        tab Nákup
  sprava.html       tab Správa (účty a práva)
  prihlaseni.html   přihlašovací stránka
main.py             vstupní bod konzolové verze
sber.py             sběrač měření (plní databázi)
database.py         práce s databází (SQLite)
graf.py             převod dat na souřadnice pro SVG graf
sprava_uctu.py      zakládání a mazání rodinných účtů
ziskej_token.py     jednorázový pomocník na vygenerování Nanoleaf tokenu
config.py           REÁLNÉ tokeny — není v Gitu!
config.example.py   šablona configu — je v Gitu
docs/
  zadani-projektu.md  zadání a roadmapa projektu
requirements.txt    seznam potřebných knihoven
```

## Jak to spustit

Návod je pro **cmd** (příkazový řádek). `.venv\Scripts\python.exe` je Python
z virtuálního prostředí — použít ho přímo je jednodušší než venv aktivovat.

```
:: přepnout se do složky projektu (i mezi disky, díky /d)
cd /d E:\Claudi\Home_asistant

:: knihovny stačí nainstalovat jednou (nebo když přibude nová)
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Pak podle toho, co chceš:

```
:: A) rychlý výpis stavu do konzole (nic neběží dál)
.venv\Scripts\python.exe main.py

:: B) webový dashboard — necháš běžet, otevřeš 127.0.0.1:5000 v prohlížeči
.venv\Scripts\python.exe web.py

:: C) sběrač měření — necháš běžet v samostatném okně, plní databázi
.venv\Scripts\python.exe sber.py

:: D) správa rodinných účtů (přidat/smazat uživatele)
.venv\Scripts\python.exe sprava_uctu.py
```

Web (B) a sběrač (C) běží každý ve **svém okně** zároveň: sběrač zapisuje
měření do `asistent.db`, web z ní čte. Obojí zastavíš `Ctrl+C`.

Pokud `config.py` neexistuje (třeba po stažení z GitHubu), vyrob ho kopií šablony:

```
copy config.example.py config.py
```

V `config.py` pak doplň vlastní `SECRET_KEY` — tím Flask podepisuje
přihlašovací cookie. Vygeneruješ ho takhle:

```
.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
```

Každý počítač i server má svůj vlastní klíč, nekopíruje se mezi nimi.

## Doma vs. na serveru

Ten samý kód poběží na dvou místech a chová se na každém trochu jinak.
Rozhoduje o tom proměnná prostředí `ASISTENT_PRODUKCE` — nastavení, které
kód dostane zvenku od systému, místo aby ho měl napsané v sobě:

- **doma** není nastavená vůbec → dashboard jede přes `http://127.0.0.1:5000`
  a přihlašovací cookie nemá příznak `Secure` (jinak by přes `http://` vůbec
  nešlo se přihlásit)
- **na serveru** (`ASISTENT_PRODUKCE=1`) → cookie se posílá jen po HTTPS
  a aplikace věří hlavičkám od reverzní proxy (Caddy), takže vidí skutečnou
  adresu návštěvníka a skládá odkazy s `https://`

Cookie je v obou případech `HttpOnly` (nepřečte ji JavaScript na stránce)
a `SameSite=Lax` (neodešle se, když na web odkáže cizí formulář).

Na serveru aplikaci nespouští `python web.py`, ale **gunicorn** — vestavěný
server Flasku je jen na vývoj. Například:

```
ASISTENT_PRODUKCE=1 gunicorn -w 2 -b 127.0.0.1:8000 web:app
```

Gunicorn je v `requirements.txt` označený `sys_platform != "win32"`, takže
se na Windows neinstaluje a doma nepřekáží.

První účet založený v prázdné databázi dostane automaticky **všechna práva**.
Bez toho by na čerstvém serveru nikdo neměl přístup do Správy a nešlo by
práva nikomu přidělit.
