# Domácí rodinný asistent

Učební projekt: webová aplikace pro rodinu, která na jednom místě ukazuje
data z domácnosti, drží společný nákupní seznam a ovládá chytrá zařízení.
Staví se postupně a hlavním cílem není hotový produkt, ale pochopit, jak se
takový systém dělá.

Běží nasazená na vlastní doméně, přihlašuje se do ní rodinnými účty.

## Co umí

- **Přehled** — domácí rozcestník s aktuálním stavem
- **Soláry** — výkon a výroba elektrárny, grafy z historie
- **Nanoleaf** — stav panelů i jejich ovládání (vypínač, jas, efekty)
- **Nákup** — společný nákupní seznam pro celou rodinu
- **Správa** — rodinné účty a jejich práva na jednotlivé taby

Data se sbírají do vlastní databáze, dokud běží sběrač. Vzhled má světlý
i tmavý motiv.

## Rychlý start

```
cd /d E:\Claudi\Home_asistant
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe web.py
```

Dashboard pak najdeš na `127.0.0.1:5000`. V druhém okně se spouští sběrač
měření `sber.py`. Celý návod včetně `config.py` je v [`docs/provoz.md`](docs/provoz.md).

> `config.py` s reálnými tokeny a hesly **není v Gitu**. Vyrobíš ho kopií
> `config.example.py`, kde je u každého údaje vysvětlivka.

## Kde je co

| dokument | o čem je |
|---|---|
| [`docs/stav.md`](docs/stav.md) | kde projekt právě je a co se dělá dál |
| [`docs/struktura.md`](docs/struktura.md) | mapa souborů — co je kde a proč |
| [`docs/provoz.md`](docs/provoz.md) | spuštění doma, rozdíly na serveru, zálohy |
| [`docs/dalsi-kroky.md`](docs/dalsi-kroky.md) | věci, na které jsme narazili a odložili je |
| [`docs/zadani-projektu.md`](docs/zadani-projektu.md) | původní zadání a vize (historický dokument) |
