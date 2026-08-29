# Domácí rodinný asistent

Učební projekt: postupně stavíme domácí asistenta pro rodinu.
Dlouhodobý cíl je webová aplikace s dashboardem (data z domácnosti),
kolaborativním nákupním seznamem a ovládáním chytrých zařízení.

Kompletní zadání a roadmapa: [`inputs/plan-domaci-asistent.md`](inputs/plan-domaci-asistent.md)

## Aktuální fáze

Fáze 1 — čtení dat ze zařízení čistým Python skriptem.
Zatím **bez webu a bez databáze**.

- [x] Úkol A — čtení stavu Nanoleaf (lokální REST API)
- [x] Úkol B — čtení stavu SolaX (cloud API)

## Struktura

```
devices/
  nanoleaf.py       čtení stavu Nanoleaf panelů
  solax.py          čtení stavu solární elektrárny
main.py             vstupní bod, tohle se spouští
ziskej_token.py     jednorázový pomocník na vygenerování Nanoleaf tokenu
config.py           REÁLNÉ tokeny — není v Gitu!
config.example.py   šablona configu — je v Gitu
requirements.txt    seznam potřebných knihoven
```

## Jak to spustit

```powershell
# 1) aktivovat virtuální prostředí
.venv\Scripts\Activate.ps1

# 2) nainstalovat knihovny (stačí jednou, nebo když přibude nová)
pip install -r requirements.txt

# 3) vyplnit reálné údaje v config.py

# 4) spustit
python main.py
```

Pokud `config.py` neexistuje (třeba po stažení z GitHubu), vyrob ho kopií šablony:

```powershell
copy config.example.py config.py
```
