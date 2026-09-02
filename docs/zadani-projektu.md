# Domácí rodinný asistent — projektový plán pro Claude Code

> ## ⚠️ Historický dokument — neaktualizuje se
>
> Tohle je **původní zadání z 29. 8. 2026**, kdy ještě neexistoval žádný
> kód. Zůstává v repozitáři schválně, aby bylo vidět, z čeho se vycházelo
> a jak se to za pár dní posunulo.
>
> **Neplatí z něj hlavně vize a roadmapa.** Roadmapa je v podstatě
> vyčerpaná a 2. 9. 2026 se změnilo i zadání: z aplikace pro jednu rodinu
> se stává osobní asistent pro kohokoliv. Co platí dnes:
>
> | co hledáš | kde to je |
> |---|---|
> | co je hotové | [`stav.md`](stav.md) |
> | kam to míří a v jakém pořadí | [`plan.md`](plan.md) |
> | zásady, které se nesmí porušit | [`struktura.md`](struktura.md) |
>
> Pravidla pro spolupráci hned pod tímhle rámečkem **platí dál** — ta se
> změnou zadání nikam nezmizela.

## Kontext pro Claude Code

Tohle je učební projekt. Uživatel je začátečník v programování (zná základy Pythonu:
proměnné, cykly, funkce), učí se stavět software praxí. Hlavním cílem **není** mít
rychle hotový produkt, ale postupně pochopit, jak se takový systém staví.

**Pravidla pro spolupráci:**
- Nepiš celá řešení najednou bez vysvětlení. Postupuj po malých krocích, vysvětluj proč, ne jen jak.
- Nepředbíhej fáze roadmapy níže — i kdyby "šlo" rovnou přidat databázi nebo web, nedělej to,
  dokud na to nepřijde řada.
- Než zavedeš nový koncept nebo knihovnu, kterou uživatel ještě nepoužil, krátce vysvětli, co dělá a proč.
- Komentuj kód tak, aby z něj bylo poznat, co se děje a proč.
- Menší funkční kus je lepší než rozpracovaný velký kus.

## Vize celého projektu (dlouhodobý cíl, pro kontext)

Webová aplikace pro rodinu s přihlašováním na rodinné profily, dostupná odkudkoliv
(ne jen v domácí síti), se třemi taby:

1. **Dashboard** — trendy a data z domácnosti v čase (grafy)
2. **Nákup** — kolaborativní nákupní seznam (rodina přidává položky, máma je pak
   na jednom místě v obchodě odškrtává)
3. **Ovládání** — ovládání chytrých zařízení (světla apod.) — *zatím se nebuduje, jen se čte stav*

Volitelný budoucí "capstone" nápad: automatické předání nákupního seznamu do Rohlíku.
Rohlík nemá oficiální veřejné API — existují jen komunitní reverzně-inženýrská řešení
(např. GitHub projekt HA-RohlikCZ), která se přihlašují přímo přes uživatelský účet.
Tohle nechat na úplný konec, je to nejnejistější a nejnáročnější část.

## Technologické rozhodnutí

- **Python** jako hlavní jazyk (backend, hardware, čtení API) — kvůli kontinuitě mezi webem a hardwarem
- Web později přes **Flask** (mikroframework — jednodušší na pochopení než Django/FastAPI)
- Databáze později **SQLite**
- Frontend zprvu jednoduché Flask šablony, JS/React až v pozdější fázi
- Vzdálený přístup později přes tunel (Cloudflare Tunnel / Tailscale), ne přes veřejný port-forwarding

## Roadmapa (koncepční pořadí učení — NE stav rozpracovanosti)

Číslování níže ukazuje, v jakém pořadí dávají jednotlivé dovednosti smysl, ne co už je hotové.

1. Python do hloubky + Git — *nahrazeno rovnou praktickým milestonem níže (uživatel už zná
   základy Pythonu, takže formální CLI to-do cvičení přeskakujeme a tuhle fázi odbudeme
   přímo na reálném projektu)*
2. Web základy (Flask) — data dostanou webové rozhraní
3. Databáze (SQLite)
4. Přihlašování / rodinné účty
5. Ovládání zařízení (výstupy, ne jen čtení)
6. Propojení hardware + web (dashboard naživo)
7. Vzdálený přístup / hosting
8. Rozšíření, hezčí frontend
9. (Volitelně) Rohlík capstone

## Stav projektu na začátku (historické)

> **Tahle sekce je zamrazená.** Popisuje start projektu z 29. 8. 2026, kdy
> ještě neexistoval žádný kód. Aktuální stav a to, co se dělá teď, je
> v [`stav.md`](stav.md) — tady se nic neaktualizuje, ať zůstane vidět,
> z čeho se vycházelo.

**Status: úplný začátek, nic není postavené.** Tohle je první kód, který v tomto projektu
vznikne — neočekávej existující repozitář, soubory ani žádnou předchozí práci. Založ
všechno od nuly podle sekce "Nastavení projektu" níže.

**Cíl:** naučit se vzorec "zavolat API zařízení → dostat JSON → vytáhnout zajímavá data
→ hezky vypsat" na dvou reálných zařízeních, která uživatel doma má. Zatím bez webu,
bez databáze — čistý Python skript.

### Nastavení projektu

- Založit Git repozitář, README
- Virtuální prostředí (venv), requirements.txt
- Struktura:
```
home-assistant-project/
  devices/
    nanoleaf.py
    solax.py
  main.py
  requirements.txt
  README.md
  .gitignore
```

### Bezpečnostní poznámka

Tokeny a přihlašovací údaje **nikdy nepatří přímo v kódu ani v Gitu**. Uložit je do
odděleného konfiguračního souboru (např. `config.py` nebo `.env`) a ten hned na začátku
přidat do `.gitignore`. Dobrá příležitost vysvětlit uživateli proč (a co se stane, když
to člověk omylem nahraje na veřejný GitHub).

### Úkol A — Nanoleaf reader

- Nanoleaf má lokální REST API přímo v zařízení (žádný cloud potřeba)
- Token se generuje podržením tlačítka napájení 5–7s (nebo v appce: nastavení zařízení →
  "Connect to API")
- Použít knihovnu `requests` přímo (ne hotový `nanoleafapi` wrapper) — cílem je pochopit
  HTTP volání, ne zabalit ho do černé skříňky
- Funkce `get_nanoleaf_status(ip, token)` → vrátí dict se stavem (zapnuto/vypnuto, jas,
  aktuální efekt)
- Akceptační kritérium: spuštění skriptu vytiskne aktuální stav světla v pokoji

### Úkol B — SolaX reader

- SolaX Cloud API — potřeba: registrace na SolaX Cloud, vygenerovaný Token, sériové
  číslo Wi-Fi modulu měniče
- Funkce `get_solax_status(token, wifi_sn)` → vrátí dict s aktuálním výkonem, denní/celkovou
  výrobou
- Akceptační kritérium: spuštění skriptu vytiskne aktuální výkon solárů

### Co v této fázi neřešit

- Neukládat data do databáze (přijde ve fázi 3)
- Nedělat webové rozhraní (přijde ve fázi 2)
- Neřešit ovládání zařízení (přijde ve fázi 5)
- Nezavádět Flask, SQLAlchemy, autentizaci apod.
