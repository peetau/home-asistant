# Provoz

Jak projekt rozběhnout doma a čím se to liší na serveru.

## Příprava

Návod je pro **cmd** (příkazový řádek). `.venv\Scripts\python.exe` je Python
z virtuálního prostředí — použít ho přímo je jednodušší než venv aktivovat.

```
:: přepnout se do složky projektu (i mezi disky, díky /d)
cd /d E:\Claudi\Home_asistant

:: knihovny stačí nainstalovat jednou (nebo když přibude nová)
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### `config.py`

Pokud `config.py` neexistuje (třeba po stažení z GitHubu), vyrob ho kopií
šablony — v Gitu schválně není, protože drží reálné tokeny:

```
copy config.example.py config.py
```

Pak v něm doplň:

- **tokeny a IP** k Nanoleafu a SolaXu (token panelů vygeneruje
  `ziskej_token.py`)
- **`SECRET_KEY`** — tím Flask podepisuje přihlašovací cookie. Vygeneruješ
  ho takhle a každý počítač i server má svůj vlastní, nekopíruje se:

  ```
  .venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
  ```

- **`POCASI_LAT` / `POCASI_LON` / `POCASI_MISTO`** — poloha pro předpověď na
  přihlašovací stránce. Souřadnice se nikde nevypisují, návštěvník uvidí jen
  název místa.
- **`ZALOHY_SLOZKA`** — má smysl jen na serveru, viz [Zálohy](#zálohy) níž.

Každý údaj má v `config.example.py` u sebe vysvětlivku.

## Spuštění

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
měření do `asistent.db`, web z ní čte. Obojí zastavíš `Ctrl+C`. Data se
sbírají jen tak dlouho, dokud `sber.py` běží.

## Doma vs. na serveru

Ten samý kód běží na dvou místech a chová se na každém trochu jinak.
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

**První účet** založený v prázdné databázi dostane automaticky **všechna
práva**. Bez toho by na čerstvém serveru nikdo neměl přístup do Správy
a nešlo by práva nikomu přidělit.

## Zálohy

Zálohuje se jen na serveru. `ZALOHY_SLOZKA` v configu říká, kde leží
zabalené kopie databáze (`*.db.gz`) — výchozí je `~/zalohy`.

Doma tahle složka neexistuje a **je to v pořádku**: indikátor pak ukáže
„neznámo“, ne chybu.

## Indikátory na přihlašovací stránce

Nad formulářem svítí dvě tečky — sběr dat a záloha. Mají tři stavy:

| stav | sběr dat | záloha |
|---|---|---|
| v pořádku | poslední měření mladší než 15 minut | nejnovější záloha mladší než 48 hodin |
| problém | poslední měření starší | záloha starší |
| neznámo | databáze nedostupná nebo prázdná | složka záloh neexistuje |

Do šablony jde **jen** slovo „ok“ / „problém“ / „neznámo“ — žádné časy,
čísla ani chybové hlášky. Tuhle stránku vidí kdokoliv na internetu, takže
majiteli barevná tečka stačí a kolemjdoucímu neřekne nic použitelného.
Vedle tečky je vždycky i slovní popisek, aby barva nebyla jediným nositelem
informace.
