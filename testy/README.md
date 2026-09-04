# Testy

Automatické kontroly, které se pouštějí před nasazením.

## Jak je spustit

```
.venv\Scripts\python.exe testy\spust.py
```

Vypíše každý test zvlášť a na konci souhrn. Když něco spadne, skončí
návratovým kódem 1 — pozná se to i bez čtení výpisu.

Jeden soubor samostatně:

```
.venv\Scripts\python.exe testy\test_prihlaseni.py
```

## Co který soubor hlídá

| soubor | co ověřuje |
|---|---|
| `test_spojeni.py` | spojení s databází se po bloku `with` zavírá — kvůli téhle chybě 4. 9. 2026 spadl server |
| `test_prihlaseni.py` | strop na počet přihlašovacích pokusů |
| `test_stranky.py` | hlavní stránky odpovídají a nenechávají viset spojení |
| `spolecne.py` | zázemí: dočasná databáze, testovací účet, spouštěč |

## Dvě pravidla, na kterých to stojí

**Žádný test nesahá na `asistent.db`.** `spolecne.py` hned při importu přepne
aplikaci na prázdnou databázi v dočasné složce. Proto se `web` v testech
neimportuje přímo, ale bere se ze `spolecne` — `web.py` si totiž při importu
sám volá `init_db()`, takže při špatném pořadí importů by sáhl na ostrou
databázi dřív, než by ji kdokoliv stihl přepnout.

**Před každým testem se databáze vyprázdní.** Testy tak na sobě nezávisí
a nezáleží na pořadí, v jakém běží.

## Jak přidat další test

Napiš do některého souboru funkci, jejíž jméno začíná na `test_`, a ověřuj
přes `assert`. Spouštěč si ji najde sám, nikam se nezapisuje. Text za
`assert` se ukáže, když test spadne — vyplatí se do něj dát skutečnou
hodnotu, ne jen „nesedí to".

Testy schválně neběží na `pytest`: nic se nemusí instalovat, `requirements.txt`
zůstává jen pro provoz a celý spouštěč je v `spolecne.py` na pár řádcích.
