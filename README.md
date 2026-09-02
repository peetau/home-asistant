# Domácí asistent

Učební projekt: webová aplikace, která na jednom místě ukazuje to podstatné,
drží sdílené nákupní seznamy a umí ovládat chytrá zařízení. Staví se
postupně a hlavním cílem není hotový produkt, ale pochopit, jak se takový
systém dělá.

Běží nasazená na vlastní doméně.

> **Zadání se 2. 9. 2026 změnilo.** Z nástěnky jedné domácnosti se stává
> osobní asistent, který se má dát k dispozici i lidem mimo rodinu.
> Soláry a Nanoleaf jsou zařízení jednoho konkrétního domu, takže
> přestávají být jádrem a stávají se doplňkem — jádrem jsou **Přehled**
> a **Nákup**. Proč, co z toho plyne a co se musí stihnout dřív, je
> v [`docs/plan.md`](docs/plan.md). Název aplikace tuhle změnu ještě
> nedohnal.

## Co umí

- **Přehled** — pozdrav, datum se svátkem a počasí pro každého; pod tím
  karty zařízení a nákupní seznamy podle práv
- **Nákup** — sdílené seznamy s pozvánkami na kód, cenami u koupených
  položek a vyúčtováním, kdo komu co vrátí
- **Soláry** — výkon a výroba elektrárny, diagram toku energie, grafy
- **Nanoleaf** — stav panelů i jejich ovládání (vypínač, jas, efekty)
- **Správa** — účty a jejich práva na jednotlivé taby

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
| [`docs/stav.md`](docs/stav.md) | co je hotové a co aplikace umí |
| [`docs/plan.md`](docs/plan.md) | **kam to míří a v jakém pořadí** |
| [`docs/struktura.md`](docs/struktura.md) | mapa souborů — co je kde a proč |
| [`docs/provoz.md`](docs/provoz.md) | spuštění doma, rozdíly na serveru, zálohy |
| [`docs/dalsi-kroky.md`](docs/dalsi-kroky.md) | odložené věci a jak je udělat |
| [`docs/zadani-projektu.md`](docs/zadani-projektu.md) | původní zadání a vize (historický dokument) |

Stav se vede **jen** ve `stav.md` a plán **jen** v `plan.md` — README je
neopakuje, jinak by si to dřív nebo později začalo protiřečit.
