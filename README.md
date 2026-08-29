# Domácí rodinný asistent

Učební projekt: postupně stavíme domácí asistenta pro rodinu.
Dlouhodobý cíl je webová aplikace s dashboardem (data z domácnosti),
kolaborativním nákupním seznamem a ovládáním chytrých zařízení.

Kompletní zadání a roadmapa: [`inputs/plan-domaci-asistent.md`](inputs/plan-domaci-asistent.md)

## Aktuální fáze

Fáze 2 — webové rozhraní (Flask). Fáze 1 — čtení dat ze zařízení čistým Python skriptem.
Zatím **bez webu a bez databáze**.

- [x] Úkol A — čtení stavu Nanoleaf (lokální REST API)
- [x] Úkol B — čtení stavu SolaX (cloud API)

## Struktura

```
devices/
  nanoleaf.py       čtení stavu Nanoleaf panelů
  solax.py          čtení stavu solární elektrárny
web.py              webový server (Flask) — spouští stránku v prohlížeči
templates/
  dashboard.html    vzhled webové stránky (odděleně od logiky)
main.py             vstupní bod konzolové verze
ziskej_token.py     jednorázový pomocník na vygenerování Nanoleaf tokenu
config.py           REÁLNÉ tokeny — není v Gitu!
config.example.py   šablona configu — je v Gitu
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
```

Web (B) a sběrač (C) běží každý ve **svém okně** zároveň: sběrač zapisuje
měření do `asistent.db`, web z ní čte. Obojí zastavíš `Ctrl+C`.

Pokud `config.py` neexistuje (třeba po stažení z GitHubu), vyrob ho kopií šablony:

```powershell
copy config.example.py config.py
```
