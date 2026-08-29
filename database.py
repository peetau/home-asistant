"""
Práce s databází (SQLite).

SQLite je "databáze v jednom souboru" - žádný samostatný program navíc.
Modul sqlite3 přišel rovnou s Pythonem, nic se neinstaluje.

Ukládáme sem měření ze solární elektrárny, ať máme HISTORII v čase
(z ní pak nakreslíme graf). Zatím jen zápis a čtení, žádný web.
"""

import os
import sqlite3

# Cesta k souboru databáze. Skládáme ji z místa, kde leží tenhle .py soubor,
# aby databáze vždy vznikla ve složce projektu - ať skript spustíš odkudkoliv.
DB_SOUBOR = os.path.join(os.path.dirname(__file__), "asistent.db")


def _spojeni():
    """
    Otevře spojení s databázovým souborem a vrátí ho.

    Když soubor asistent.db ještě neexistuje, SQLite ho při prvním
    spojení sám vytvoří. Není tedy co "zakládat" ručně.
    """
    return sqlite3.connect(DB_SOUBOR)


def init_db():
    """
    Připraví strukturu databáze: vytvoří tabulku 'mereni', pokud chybí.

    Tohle je bezpečné volat kolikrát chceš - "IF NOT EXISTS" znamená
    "vytvoř jen když ještě není". Při druhém spuštění tedy neudělá nic.
    """
    with _spojeni() as db:
        # SQL příkaz CREATE TABLE popisuje SLOUPCE a jejich typ:
        #   INTEGER = celé číslo, REAL = desetinné, TEXT = text
        # id ... PRIMARY KEY AUTOINCREMENT = automatické pořadové číslo řádku;
        #   nemusíme ho vyplňovat, databáze ho přidělí sama (1, 2, 3, ...).
        db.execute("""
            CREATE TABLE IF NOT EXISTS mereni (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                cas           TEXT    NOT NULL,
                vykon_panelu  INTEGER,
                denni_vyroba  REAL,
                baterie_soc   INTEGER
            )
        """)
    # 'with' se postará o uzavření spojení a uložení (commit) změn.


def uloz_mereni(cas, vykon_panelu, denni_vyroba, baterie_soc):
    """
    Přidá do tabulky 'mereni' jeden nový řádek (jedno měření).
    """
    with _spojeni() as db:
        # POZOR na ty otazníky. NIKDY nelepíme hodnoty přímo do SQL textu
        # (např. f-stringem). Místo hodnot dáme ? a skutečná data předáme
        # zvlášť jako druhý argument. Databáze si je bezpečně doplní sama.
        #
        # Proč: kdyby se do hodnoty dostalo něco záludného (však uvidíš
        # u přihlašování, kde data píše uživatel), lepení do textu by šlo
        # zneužít. Otazníky tomu zabrání. Zvykni si na ně od začátku.
        db.execute(
            "INSERT INTO mereni (cas, vykon_panelu, denni_vyroba, baterie_soc) "
            "VALUES (?, ?, ?, ?)",
            (cas, vykon_panelu, denni_vyroba, baterie_soc),
        )


def nacti_pro_graf(hodin=24):
    """
    Vrátí měření za posledních 'hodin' hodin, seřazená od nejstaršího.

    Pro graf potřebujeme opačné pořadí než pro výpis: čas musí růst
    zleva doprava, takže ORDER BY id ASC (vzestupně).

    Filtrování času necháváme na databázi (WHERE) - je to její práce
    a je v tom rychlejší, než kdybychom načetli všechno a třídili v Pythonu.
    """
    with _spojeni() as db:
        # datetime('now', 'localtime', '-24 hours') je funkce SQLite:
        # spočítá časovou hranici přímo v databázi.
        kurzor = db.execute(
            "SELECT cas, vykon_panelu, denni_vyroba, baterie_soc "
            "FROM mereni "
            "WHERE cas >= datetime('now', 'localtime', ?) "
            "ORDER BY id ASC",
            (f"-{int(hodin)} hours",),
        )
        return kurzor.fetchall()


def nacti_mereni(limit=10):
    """
    Vrátí posledních 'limit' měření, nejnovější první.

    Vrací seznam řádků; každý řádek je n-tice hodnot v pořadí sloupců.
    """
    with _spojeni() as db:
        # SELECT = "vyber". * znamená všechny sloupce.
        # ORDER BY id DESC = seřaď podle id sestupně (nejnovější nahoře).
        # LIMIT ? = vrať jen tolik řádků.
        kurzor = db.execute(
            "SELECT id, cas, vykon_panelu, denni_vyroba, baterie_soc "
            "FROM mereni ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return kurzor.fetchall()  # fetchall = "dej mi všechny nalezené řádky"
