# -*- coding: utf-8 -*-
"""
Spojení s databází se musí zavírat.

Proč to hlídáme: 4. 9. 2026 kvůli tomu spadl server. `with sqlite3.connect(...)`
transakci potvrdí, ale soubor nechá otevřený. Za patnáct hodin provozu tak
každý gunicorn worker nasbíral přes tisíc otevřených kopií `asistent.db`,
narazil na systémový strop 1024 a aplikace přestala umět databázi otevřít.
"""

import sqlite3

from spolecne import database, spust, otevrenych_spojeni


def test_spojeni_se_po_bloku_with_zavre():
    with database._spojeni() as db:
        db.execute("SELECT 1").fetchone()

    # Na zavřeném spojení SQLite odmítne pracovat - a přesně to chceme.
    try:
        db.execute("SELECT 1")
    except sqlite3.ProgrammingError:
        return
    raise AssertionError("spojení zůstalo otevřené, deskriptory se hromadí")


def test_sto_dotazu_nenecha_viset_ani_jedno_spojeni():
    pred = otevrenych_spojeni()

    for _ in range(100):
        with database._spojeni() as db:
            db.execute("SELECT COUNT(*) FROM uzivatele").fetchone()

    po = otevrenych_spojeni()
    assert po <= pred, "po 100 dotazech visí %d spojení navíc" % (po - pred)


def test_chyba_uvnitr_bloku_spojeni_taky_zavre():
    """Zavření patří do `finally`, ne za poslední řádek - jinak by výjimka
    uvnitř bloku nechala soubor otevřený."""
    try:
        with database._spojeni() as db:
            db.execute("SELECT * FROM tabulka_ktera_neexistuje")
    except sqlite3.OperationalError:
        pass

    try:
        db.execute("SELECT 1")
    except sqlite3.ProgrammingError:
        return
    raise AssertionError("po chybě uvnitř bloku zůstalo spojení otevřené")


if __name__ == "__main__":
    import sys
    kolik, spadlo = spust(globals(), __doc__.strip().splitlines()[0])
    sys.exit(1 if spadlo else 0)
