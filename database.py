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

# Taby, na které se udělují práva.
#
# Přehled tu SCHVÁLNĚ NENÍ: je vždy dostupný každému přihlášenému a jeho
# obsah se poskládá z toho, na co uživatel právo má. Nemá tedy smysl ho
# povolovat - kdo se přihlásí, na Přehled patří.
#
# Přidání dalšího zařízení = přidat sem jeho název. Nic v databázi se měnit
# nemusí (viz komentář u tabulky 'opravneni').
VSECHNY_TABY = ("solary", "nanoleaf", "nakup", "sprava")

# Co dostane nově založený uživatel. Nejopatrnější rozumný start:
# přihlásí se, vidí Přehled a může přidávat na nákupní seznam.
VYCHOZI_PRAVA = ("nakup",)


def _spojeni():
    """
    Otevře spojení s databázovým souborem a vrátí ho.

    Když soubor asistent.db ještě neexistuje, SQLite ho při prvním
    spojení sám vytvoří. Není tedy co "zakládat" ručně.
    """
    spojeni = sqlite3.connect(DB_SOUBOR)

    # SQLite má hlídání vazeb mezi tabulkami ve výchozím stavu VYPNUTÉ
    # (kvůli zpětné kompatibilitě) a zapíná se pro každé spojení zvlášť.
    # Bez tohohle řádku by ON DELETE CASCADE u oprávnění nefungovalo
    # a po smazání uživatele by v databázi zůstala jeho osiřelá práva.
    spojeni.execute("PRAGMA foreign_keys = ON")
    return spojeni


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

        # Oprávnění: kdo smí na který tab.
        #
        # Jeden řádek = jedno udělené právo. Proč zvláštní tabulka místo
        # sloupců "muze_solary", "muze_nakup"? Protože přidání dalšího
        # zařízení pak nevyžaduje ŽÁDNOU změnu struktury - jen se začnou
        # zapisovat řádky s novým názvem tabu.
        #
        # PRIMARY KEY přes obě pole znamená, že stejná dvojice nemůže být
        # dvakrát - o duplicity se postará databáze sama.
        #
        # ON DELETE CASCADE = "když zmizí uživatel, zmiz i jeho práva".
        # Bez toho by v tabulce zůstaly řádky ukazující na neexistující účet.
        db.execute("""
            CREATE TABLE IF NOT EXISTS opravneni (
                uzivatel_id INTEGER NOT NULL,
                tab         TEXT    NOT NULL,
                PRIMARY KEY (uzivatel_id, tab),
                FOREIGN KEY (uzivatel_id) REFERENCES uzivatele(id)
                    ON DELETE CASCADE
            )
        """)

        # MIGRACE existující databáze.
        #
        # Tabulka uživatelů už obsahuje účty založené dřív, než oprávnění
        # vůbec existovala. Kdybychom nic neudělali, neměly by po nasazení
        # práva na nic - včetně Správy - a nikdo by se do aplikace nedostal.
        #
        # Proto: když jsou oprávnění prázdná, ale uživatelé ne, udělíme
        # všem existujícím účtům všechna práva. Je to bezpečné i při
        # opakovaném spuštění, protože podmínka platí jen jednou (pravidlo
        # "aspoň jeden správce" pak zaručí, že tabulka nikdy neklesne na nulu).
        prazdna = db.execute("SELECT COUNT(*) FROM opravneni").fetchone()[0] == 0
        nejaci = db.execute("SELECT COUNT(*) FROM uzivatele").fetchone()[0] > 0
        if prazdna and nejaci:
            for (id_u,) in db.execute("SELECT id FROM uzivatele").fetchall():
                for tab in VSECHNY_TABY:
                    db.execute(
                        "INSERT INTO opravneni (uzivatel_id, tab) VALUES (?, ?)",
                        (id_u, tab),
                    )
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


def vytvor_uzivatele(jmeno, heslo, prava=None):
    """
    Založí nového uživatele. Heslo uloží jako hash, nikdy v původní podobě.

    prava - seznam tabů, které má dostat. Když se nezadá, použijí se
            VYCHOZI_PRAVA (jen nákupní seznam).

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
            # ÚPLNĚ PRVNÍ účet dostane všechna práva, ať se zadá cokoliv.
            #
            # Bez tohohle by na čerstvé databázi (třeba na novém serveru)
            # vznikl první uživatel jen s právem na nákup - a protože by
            # nikdo neměl Správu, nešlo by ji nikomu přidělit. Zamčeno
            # zvenku hned při prvním spuštění.
            prvni = db.execute("SELECT COUNT(*) FROM uzivatele").fetchone()[0] == 0

            kurzor = db.execute(
                "INSERT INTO uzivatele (jmeno, heslo_hash) VALUES (?, ?)",
                (jmeno, hash_hesla),
            )

            if prvni:
                udelit = VSECHNY_TABY
            elif prava is not None:
                udelit = prava
            else:
                udelit = VYCHOZI_PRAVA

            # lastrowid = id právě vloženého řádku. Potřebujeme ho hned,
            # abychom novému účtu rovnou udělili práva.
            for tab in udelit:
                if tab in VSECHNY_TABY:
                    db.execute(
                        "INSERT INTO opravneni (uzivatel_id, tab) VALUES (?, ?)",
                        (kurzor.lastrowid, tab),
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


# ==================== Oprávnění ====================

def prava_uzivatele(id_uzivatele):
    """Vrátí množinu tabů, na které má uživatel právo."""
    with _spojeni() as db:
        radky = db.execute(
            "SELECT tab FROM opravneni WHERE uzivatel_id = ?", (id_uzivatele,)
        ).fetchall()
    # set() místo seznamu: ptáme se hlavně "je tam tenhle tab?",
    # a na to je množina rychlejší i čitelnější (tab in prava).
    return {radek[0] for radek in radky}


def stari_posledniho_mereni():
    """
    Kolik minut uplynulo od posledního uloženého měření.

    Vrací None, když v databázi zatím nic není. Slouží k tomu, aby se
    dalo na první pohled poznat, jestli sběrač běží.

    Počítá to databáze sama funkcí julianday() - vrací počet dní jako
    desetinné číslo, takže rozdíl krát 1440 dá minuty. Je to spolehlivější
    než porovnávat texty s časem v Pythonu.
    """
    with _spojeni() as db:
        radek = db.execute("""
            SELECT (julianday('now', 'localtime') - julianday(MAX(cas))) * 1440
            FROM mereni
        """).fetchone()

    return None if radek is None or radek[0] is None else radek[0]


def uzivatel_a_prava(id_uzivatele):
    """
    Vrátí (jmeno, mnozina_prav) pro daného uživatele, nebo None když už
    neexistuje (třeba když mu správce mezitím účet smazal).

    Čte se při KAŽDÉM požadavku, proto jedním dotazem místo dvou.
    LEFT JOIN vrátí uživatele i tehdy, když nemá žádná práva - pak přijde
    jeden řádek s prázdným tabem, který níž přeskočíme.
    """
    with _spojeni() as db:
        radky = db.execute("""
            SELECT u.jmeno, o.tab
            FROM uzivatele u
            LEFT JOIN opravneni o ON o.uzivatel_id = u.id
            WHERE u.id = ?
        """, (id_uzivatele,)).fetchall()

    if not radky:
        return None

    return radky[0][0], {tab for _, tab in radky if tab}


def pocet_spravcu():
    """Kolik uživatelů má právo na Správu. Používá se v pojistkách."""
    with _spojeni() as db:
        return db.execute(
            "SELECT COUNT(*) FROM opravneni WHERE tab = 'sprava'"
        ).fetchone()[0]


def _je_spravce(db, id_uzivatele):
    """Má daný uživatel právo na Správu? (uvnitř už otevřeného spojení)"""
    return db.execute(
        "SELECT 1 FROM opravneni WHERE uzivatel_id = ? AND tab = 'sprava'",
        (id_uzivatele,),
    ).fetchone() is not None


def nastav_prava(id_uzivatele, taby):
    """
    Nastaví uživateli přesně tahle práva (stará se zahodí).

    Vrací (True, None) při úspěchu, jinak (False, "důvod").

    POJISTKA: odmítne odebrat Správu poslednímu, kdo ji má - jinak by se
    do správy uživatelů už nikdo nedostal a šlo by to spravit jen
    přes příkazovou řádku.
    """
    # Pustíme dál jen názvy, které známe. Kdyby někdo do formuláře
    # podstrčil vlastní hodnotu, tady skončí.
    nove = {tab for tab in taby if tab in VSECHNY_TABY}

    with _spojeni() as db:
        if _je_spravce(db, id_uzivatele) and "sprava" not in nove:
            pocet = db.execute(
                "SELECT COUNT(*) FROM opravneni WHERE tab = 'sprava'"
            ).fetchone()[0]
            if pocet <= 1:
                return False, ("Tohle je poslední účet se Správou. "
                               "Nejdřív ji dej někomu jinému.")

        # Smazat a zapsat znovu je jednodušší a spolehlivější než počítat,
        # co přibylo a co ubylo. Obojí je v jedné transakci ('with'),
        # takže se buď povede všechno, nebo nic.
        db.execute("DELETE FROM opravneni WHERE uzivatel_id = ?", (id_uzivatele,))
        for tab in nove:
            db.execute(
                "INSERT INTO opravneni (uzivatel_id, tab) VALUES (?, ?)",
                (id_uzivatele, tab),
            )
    return True, None


def zmen_heslo(id_uzivatele, nove_heslo):
    """Nastaví uživateli nové heslo. Ukládá se zase jen jako hash."""
    if len(nove_heslo) < 6:
        return False, "Heslo musí mít aspoň 6 znaků."

    with _spojeni() as db:
        db.execute(
            "UPDATE uzivatele SET heslo_hash = ? WHERE id = ?",
            (generate_password_hash(nove_heslo), id_uzivatele),
        )
    return True, None


def smaz_uzivatele(id_uzivatele):
    """
    Smaže uživatele i jeho práva (o práva se postará ON DELETE CASCADE).

    POJISTKA: neumaže posledního správce.
    """
    with _spojeni() as db:
        if _je_spravce(db, id_uzivatele):
            pocet = db.execute(
                "SELECT COUNT(*) FROM opravneni WHERE tab = 'sprava'"
            ).fetchone()[0]
            if pocet <= 1:
                return False, "Tohle je poslední účet se Správou, nelze smazat."

        db.execute("DELETE FROM uzivatele WHERE id = ?", (id_uzivatele,))
    return True, None


def uzivatele_s_pravy():
    """
    Vrátí seznam uživatelů i s jejich právy - pro tab Správa.

    Formát: [{"id": 1, "jmeno": "petr", "vytvoren": "...", "prava": {...}}, ...]

    Používá JEDEN dotaz s LEFT JOIN místo toho, aby se pro každého uživatele
    zvlášť ptal na jeho práva. Se třemi účty je to jedno, ale je to návyk:
    dotaz v cyklu je klasická příčina pomalých aplikací.

    LEFT JOIN = "vezmi všechny uživatele a přilep k nim jejich práva;
    když nějaký žádná nemá, stejně ho vrať" (proto LEFT). Uživatel bez práv
    přijde s prázdnou hodnotou v sloupci tab, kterou níž přeskočíme.
    """
    with _spojeni() as db:
        radky = db.execute("""
            SELECT u.id, u.jmeno, u.vytvoren, o.tab
            FROM uzivatele u
            LEFT JOIN opravneni o ON o.uzivatel_id = u.id
            ORDER BY u.id
        """).fetchall()

    # Dotaz vrací jeden řádek na KAŽDÉ právo, takže se uživatel opakuje.
    # Poskládáme to zpátky do jednoho záznamu na uživatele.
    podle_id = {}
    for id_u, jmeno, vytvoren, tab in radky:
        if id_u not in podle_id:
            podle_id[id_u] = {"id": id_u, "jmeno": jmeno,
                              "vytvoren": vytvoren, "prava": set()}
        if tab:
            podle_id[id_u]["prava"].add(tab)

    return list(podle_id.values())


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
