# -*- coding: utf-8 -*-
"""
Zázemí pro testy: cesta k projektu, dočasná databáze a spouštěč.

PRAVIDLO, KTERÉ SE NESMÍ PORUŠIT: žádný test nesahá na ostrou databázi.
Proto se hned při importu tohohle souboru přepne `database.DB_SOUBOR` na
prázdný soubor v dočasné složce - a teprve POTOM se smí importovat `web`,
protože ten si při importu sám volá `init_db()`.

Aby to nešlo splést, testy si `web` neimportují samy, ale berou si ho odsud:

    from spolecne import web, database, klient, spust
"""

import gc
import os
import sqlite3
import sys
import tempfile

# Kořen projektu je o složku výš. Počítá se z umístění tohohle souboru,
# ne z toho, odkud testy spustíš - jinak by šly pustit jen z jedné složky
# a na serveru by spadly.
KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if KOREN not in sys.path:
    sys.path.insert(0, KOREN)

import database  # noqa: E402

# Dočasná databáze. Vznikne jednou za spuštění, každý test si ji vyprázdní.
# tempfile.mkdtemp() vyrobí složku, do které nikdo jiný nesahá.
DOCASNA = os.path.join(tempfile.mkdtemp(prefix="asistent-testy-"), "test.db")
database.DB_SOUBOR = DOCASNA

import web  # noqa: E402  (až tady, viz vysvětlení nahoře)

# TESTING zapne Flasku testovací režim - chyby pak nezůstanou schované
# za stránkou "vnitřní chyba serveru", ale probublají do testu.
web.app.config["TESTING"] = True


def cista_databaze():
    """Zahodí obsah dočasné databáze a založí ji znovu prázdnou."""
    if os.path.exists(DOCASNA):
        os.remove(DOCASNA)
    database.init_db()


def zaloz_uzivatele(jmeno="Testovaci", heslo="tajne-heslo"):
    """
    Založí účet, se kterým se dá v testu přihlásit, a vrátí (jméno, heslo).

    První účet v prázdné databázi dostane automaticky všechna práva, takže
    se s ním dostaneme i do Správy.
    """
    database.vytvor_uzivatele(jmeno, heslo)
    return jmeno, heslo


def klient():
    """Prohlížeč naoko - umí GET a POST na stránky aplikace."""
    return web.app.test_client()


def _je_otevrene(spojeni):
    """
    Je tohle spojení pořád otevřené?

    Zavřené spojení zůstane v paměti jako objekt, ale soubor už drží.
    Poznáme ho tak, že na něm SQLite odmítne cokoliv udělat.
    """
    try:
        spojeni.execute("SELECT 1")
        return True
    except sqlite3.ProgrammingError:
        return False


def otevrenych_spojeni():
    """
    Kolik spojení s databází je právě teď OTEVŘENÝCH.

    Používá se na hlídání netěsnosti, kvůli které 4. 9. 2026 spadl server:
    spojení se nezavírala a workerům došly souborové deskriptory.

    Počítají se jen otevřená spojení, ne všechny objekty v paměti - už
    zavřené spojení, na které jen ještě někde vede jméno proměnné, žádný
    soubor nedrží a je nám jedno. gc.collect() je tu proto, aby se počítalo
    až po úklidu, ne před ním.
    """
    gc.collect()
    return sum(1 for o in gc.get_objects()
               if isinstance(o, sqlite3.Connection) and _je_otevrene(o))


def spust(jmenny_prostor, nazev):
    """
    Pustí všechny funkce začínající na `test_` a vypíše, jak dopadly.

    `jmenny_prostor` je globals() volajícího souboru - díky tomu se nemusí
    testy nikam zapisovat do seznamu, stačí je napsat.

    Před KAŽDÝM testem se databáze vyprázdní, aby na sobě testy nezávisely
    a nezáleželo na pořadí.

    Vrací dvojici (kolik testů proběhlo, kolik jich spadlo).
    """
    testy = [(j, f) for j, f in sorted(jmenny_prostor.items())
             if j.startswith("test_") and callable(f)]

    spadlo = 0
    print("== %s ==" % nazev)
    for jmeno, test in testy:
        cista_databaze()
        try:
            test()
            print("   OK     %s" % jmeno)
        except Exception as chyba:
            spadlo += 1
            print("   SPADL  %s -> %s: %s" % (jmeno, type(chyba).__name__, chyba))

    return len(testy), spadlo
