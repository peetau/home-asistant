"""
Práce s databází (SQLite).

SQLite je "databáze v jednom souboru" - žádný samostatný program navíc.
Modul sqlite3 přišel rovnou s Pythonem, nic se neinstaluje.

Ukládáme sem měření ze solární elektrárny, ať máme HISTORII v čase
(z ní pak nakreslíme graf). Zatím jen zápis a čtení, žádný web.
"""

import os
import sqlite3

# Funkce na bezpečnou práci s hesly. Werkzeug přišel automaticky s Flaskem,
# takže se nic neinstaluje. Sami si hashování NIKDY nepíšeme - je to oblast,
# kde se snadno udělá chyba s vážnými následky, a tyhle funkce ji řeší správně.
from werkzeug.security import generate_password_hash, check_password_hash

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

        # Tabulka uživatelů (rodinné účty).
        #
        # POZOR na sloupec heslo_hash: ukládáme HASH, nikdy samotné heslo.
        # Hash je výsledek jednosměrné funkce - z hesla ho spočítáš snadno,
        # ale z hashe heslo zpátky nedostaneš. Kdyby někdo databázi ukradl,
        # hesla rodiny nezíská.
        #
        # UNIQUE u jména znamená, že databáze sama odmítne druhého uživatele
        # se stejným jménem - nemusíme to hlídat v Pythonu.
        db.execute("""
            CREATE TABLE IF NOT EXISTS uzivatele (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                jmeno       TEXT    NOT NULL UNIQUE,
                heslo_hash  TEXT    NOT NULL,
                vytvoren    TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
        """)
        # Nákupní seznam - společný pro celou rodinu.
        #
        # Ukládáme i to, KDO položku přidal a kdo ji odškrtl. Není to jen
        # zajímavost: v obchodě se hodí vědět, kdo co chtěl, kdyby bylo
        # potřeba se doptat ("jaké mléko jsi myslel?").
        #
        # koupeno je 0/1 - SQLite nemá zvláštní typ pro ano/ne, používá
        # se celé číslo. Python si to přeloží na False/True sám.
        db.execute("""
            CREATE TABLE IF NOT EXISTS nakup (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                text         TEXT    NOT NULL,
                koupeno      INTEGER NOT NULL DEFAULT 0,
                pridal       TEXT    NOT NULL,
                pridano      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
                koupil       TEXT,
                koupeno_kdy  TEXT
            )
        """)
    # 'with' se postará o uzavření spojení a uložení (commit) změn.


# ==================== Nákupní seznam ====================

def pridej_polozku(text, kdo):
    """Přidá položku na nákupní seznam. Vrací False u prázdného textu."""
    text = text.strip()
    if not text:
        return False

    # Rozumný strop na délku. Bez něj by šlo do databáze poslat megabajty
    # textu - ne kvůli zlému úmyslu, stačí omylem vložený text ze schránky.
    text = text[:200]

    with _spojeni() as db:
        db.execute(
            "INSERT INTO nakup (text, pridal) VALUES (?, ?)",
            (text, kdo),
        )
    return True


def seznam_nakupu():
    """
    Vrátí položky seznamu: nekoupené první, uvnitř skupin nejnovější nahoře.

    ORDER BY koupeno ASC, id DESC znamená "nejdřív seřaď podle koupeno
    (0 před 1), a při shodě podle id sestupně". Tak zůstane to, co ještě
    chybí, nahoře - a to je v obchodě jediné, co člověk potřebuje vidět.
    """
    with _spojeni() as db:
        kurzor = db.execute(
            "SELECT id, text, koupeno, pridal, koupil "
            "FROM nakup ORDER BY koupeno ASC, id DESC"
        )
        return kurzor.fetchall()


def prepni_koupeno(id_polozky, kdo):
    """Odškrtne položku, nebo odškrtnutí zruší (přepne stav)."""
    with _spojeni() as db:
        radek = db.execute(
            "SELECT koupeno FROM nakup WHERE id = ?", (id_polozky,)
        ).fetchone()
        if radek is None:
            return False

        if radek[0]:
            # Bylo koupeno -> vracíme zpět mezi chybějící, stopu mažeme.
            db.execute(
                "UPDATE nakup SET koupeno = 0, koupil = NULL, koupeno_kdy = NULL "
                "WHERE id = ?",
                (id_polozky,),
            )
        else:
            db.execute(
                "UPDATE nakup SET koupeno = 1, koupil = ?, "
                "koupeno_kdy = datetime('now', 'localtime') WHERE id = ?",
                (kdo, id_polozky),
            )
    return True


def smaz_polozku(id_polozky):
    """Smaže jednu položku ze seznamu."""
    with _spojeni() as db:
        db.execute("DELETE FROM nakup WHERE id = ?", (id_polozky,))


def smaz_koupene():
    """Uklidí všechny odškrtnuté položky. Vrací, kolik jich zmizelo."""
    with _spojeni() as db:
        kurzor = db.execute("DELETE FROM nakup WHERE koupeno = 1")
        return kurzor.rowcount


def vytvor_uzivatele(jmeno, heslo):
    """
    Založí nového uživatele. Heslo uloží jako hash, nikdy v původní podobě.

    Vrací True když se povedlo, False když jméno už existuje.
    """
    # generate_password_hash dělá tři důležité věci naráz:
    #  1) zahashuje heslo jednosměrnou funkcí
    #  2) přidá "sůl" - náhodnou přísadu, takže dva lidé se stejným heslem
    #     mají různý hash (jinak by šlo poznat, kdo má stejné heslo)
    #  3) je schválně POMALÁ, aby útočník nemohl zkoušet miliony hesel za sekundu
    hash_hesla = generate_password_hash(heslo)

    try:
        with _spojeni() as db:
            db.execute(
                "INSERT INTO uzivatele (jmeno, heslo_hash) VALUES (?, ?)",
                (jmeno, hash_hesla),
            )
        return True
    except sqlite3.IntegrityError:
        # Sem se dostaneme, když jméno porušilo pravidlo UNIQUE.
        return False


def over_uzivatele(jmeno, heslo):
    """
    Ověří přihlašovací údaje.

    Vrací slovník {"id": ..., "jmeno": ...} když sedí, jinak None.

    Všimni si, že heslo NEHLEDÁME v databázi. Vytáhneme uloženy hash
    a necháme check_password_hash spočítat, jestli k němu zadané heslo
    pasuje. Databáze původní heslo nezná a znát nemá.
    """
    with _spojeni() as db:
        radek = db.execute(
            "SELECT id, jmeno, heslo_hash FROM uzivatele WHERE jmeno = ?",
            (jmeno,),
        ).fetchone()

    if radek is None:
        return None

    id_uzivatele, jmeno_z_db, hash_z_db = radek
    if check_password_hash(hash_z_db, heslo):
        return {"id": id_uzivatele, "jmeno": jmeno_z_db}
    return None


def seznam_uzivatelu():
    """Vrátí jména všech založených uživatelů (bez hesel, ta nikam nepatří)."""
    with _spojeni() as db:
        kurzor = db.execute("SELECT id, jmeno, vytvoren FROM uzivatele ORDER BY id")
        return kurzor.fetchall()


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
