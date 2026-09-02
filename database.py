"""
Práce s databází (SQLite).

SQLite je "databáze v jednom souboru" - žádný samostatný program navíc.
Modul sqlite3 přišel rovnou s Pythonem, nic se neinstaluje.

Ukládáme sem měření ze solární elektrárny, ať máme HISTORII v čase
(z ní pak nakreslíme graf). Zatím jen zápis a čtení, žádný web.
"""

import os
import secrets
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


# Z čeho se skládá kód pozvánky. Chybí O/0 a I/1 schválně - kód se bude
# přepisovat z telefonu na telefon rukou a tyhle znaky se pletou.
ABECEDA_KODU = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _uprav_kod(kod):
    """
    Srovná ručně opsaný kód do tvaru, ve kterém je uložený: 'K7M-4QP'.

    Lidi ho budou přepisovat z telefonu na telefon, takže může přijít malými
    písmeny, bez pomlčky nebo s mezerami. Zahodíme všechno, co do abecedy
    kódů nepatří, a pomlčku doplníme sami.

    Vrací None, když po očištění nezbylo přesně šest znaků.
    """
    znaky = "".join(z for z in (kod or "").upper() if z in ABECEDA_KODU)
    if len(znaky) != 6:
        return None
    return znaky[:3] + "-" + znaky[3:]


def _migrace_zabrana(db, nazev):
    """
    Zabere jednorázovou migraci pro sebe. True = má ji provést tenhle proces.

    PROČ TO NESTAČÍ OHLÍDAT DOTAZEM "už je to hotové?": gunicorn spouští na
    serveru dva workery naráz a oba se zeptají dřív, než kterýkoliv z nich
    stihne cokoliv zapsat. Oba dostanou "ještě ne" a oba migraci provedou.
    Přesně tak po prvním nasazení vznikly DVA seznamy "Domácnost".

    Zápis do tabulky je proti tomu odolný: název je primární klíč, takže
    druhý proces na něm neuspěje, ať se ptá kdykoliv. Nerozhoduje o tom
    načasování, ale databáze.

    Používá se jen u migrací, které NĚCO ZAKLÁDAJÍ. Přidání sloupce se
    hlídat nemusí - to se buď povede, nebo skončí chybou "sloupec už je",
    a obojí je v pořádku.
    """
    try:
        db.execute("INSERT INTO migrace (nazev) VALUES (?)", (nazev,))
        return True
    except sqlite3.IntegrityError:
        return False


def _novy_kod():
    """
    Vyrobí kód pozvánky do seznamu, například 'K7M-4QP'.

    Používáme modul secrets, NE random. random je určený na simulace a jeho
    čísla se dají při znalosti několika předchozích dopočítat - u pozvánky
    by to znamenalo, že si někdo odvodí kódy cizích seznamů. secrets je
    přesně pro případy, kdy na uhodnutelnosti záleží.

    Pomlčka uprostřed je jen kvůli čitelnosti, do porovnávání nezasahuje.
    """
    znaky = "".join(secrets.choice(ABECEDA_KODU) for _ in range(6))
    return znaky[:3] + "-" + znaky[3:]


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
                baterie_soc   INTEGER,
                spotreba_domu INTEGER,
                tok_site      INTEGER,
                vykon_baterie INTEGER
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
                seznam_id    INTEGER REFERENCES seznamy(id) ON DELETE CASCADE,
                text         TEXT    NOT NULL,
                koupeno      INTEGER NOT NULL DEFAULT 0,
                pridal       TEXT    NOT NULL,
                pridal_id    INTEGER REFERENCES uzivatele(id) ON DELETE SET NULL,
                pridano      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
                koupil       TEXT,
                koupil_id    INTEGER REFERENCES uzivatele(id) ON DELETE SET NULL,
                koupeno_kdy  TEXT,
                cena         REAL
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

        # Historie nákupů - z čeho se nabízí rychlé přidání.
        #
        # PROČ ZVLÁŠTNÍ TABULKA: "Smazat odškrtnuté" řádky z tabulky nakup
        # zahodí a s nimi i informaci, co se kupuje často. Tahle tabulka
        # se nikdy nemaže, takže historie úklid přežije.
        #
        # klic je název malými písmeny - díky němu se "Mléko" a "mléko"
        # počítají jako jedna položka.
        # Které jednorázové migrace už proběhly.
        #
        # Slouží jako zámek, ne jako záznam pro lidi - viz _migrace_zabrana().
        db.execute("""
            CREATE TABLE IF NOT EXISTS migrace (
                nazev     TEXT PRIMARY KEY,
                provedena TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
        """)

        # Nákupní seznamy.
        #
        # Jeden seznam = jedna parta lidí, co spolu nakupuje. Vlastník je
        # SLOUPEC, ne řádek v tabulce členů s nějakou rolí. Díky tomu hlídá
        # databáze sama, že seznam má právě jednoho vlastníka (NOT NULL
        # a cizí klíč) - s rolí by to byla jen dohoda v kódu a rozpadlo by
        # se to tiše.
        #
        # 'kod' je pozvánka. Vlastník ji pošle komu chce, ten si ji zadá
        # a stane se členem. Nikdo přitom nemusí vidět seznam uživatelů.
        db.execute("""
            CREATE TABLE IF NOT EXISTS seznamy (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                nazev       TEXT    NOT NULL,
                vlastnik_id INTEGER NOT NULL REFERENCES uzivatele(id),
                kod         TEXT    UNIQUE,
                clenove_zvou INTEGER NOT NULL DEFAULT 0,
                vytvoren    TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
        """)

        # Kdo je do seznamu přizvaný. VLASTNÍK TU NENÍ - ten je sloupcem
        # v tabulce výš. Kdyby byl v obou, mohly by si obě místa začít
        # protiřečit a nebylo by jasné, které platí.
        db.execute("""
            CREATE TABLE IF NOT EXISTS clenove_seznamu (
                seznam_id   INTEGER NOT NULL
                            REFERENCES seznamy(id) ON DELETE CASCADE,
                uzivatel_id INTEGER NOT NULL
                            REFERENCES uzivatele(id) ON DELETE CASCADE,
                pridan      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
                PRIMARY KEY (seznam_id, uzivatel_id)
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS historie_nakupu (
                seznam_id INTEGER NOT NULL
                          REFERENCES seznamy(id) ON DELETE CASCADE,
                klic      TEXT    NOT NULL,
                text      TEXT    NOT NULL,
                pocet     INTEGER NOT NULL DEFAULT 1,
                naposledy TEXT    NOT NULL,
                PRIMARY KEY (seznam_id, klic)
            )
        """)

        # MIGRACE: sloupec s množstvím.
        #
        # Tabulka nakup uz obsahuje data, takze ji nestaci vytvorit jinak -
        # CREATE TABLE IF NOT EXISTS by u existujici tabulky neudelal nic.
        # Musime ji zmenit prikazem ALTER TABLE.
        #
        # Sloupec pridavame jen kdyz chybi. PRAGMA table_info vrati popis
        # sloupcu tabulky - podivame se, jestli mezi nimi mnozstvi uz je.
        sloupce = [r[1] for r in db.execute("PRAGMA table_info(nakup)")]
        if "mnozstvi" not in sloupce:
            try:
                db.execute("ALTER TABLE nakup ADD COLUMN mnozstvi TEXT")
            except sqlite3.OperationalError:
                # Gunicorn ma dva workery a mohly by se o migraci pokusit
                # oba naraz. Ten druhy dostane chybu "sloupec uz existuje"
                # a to je v poradku - prace je hotova.
                pass

        # MIGRACE: kdy se uživatel naposledy přihlásil.
        # Stejný postup jako u sloupce mnozstvi - přidat jen když chybí.
        # U účtu, který se nikdy nepřihlásil, zůstane prázdné, a to je
        # právě ta užitečná informace.
        sloupce_u = [r[1] for r in db.execute("PRAGMA table_info(uzivatele)")]
        if "posledni_prihlaseni" not in sloupce_u:
            try:
                db.execute(
                    "ALTER TABLE uzivatele ADD COLUMN posledni_prihlaseni TEXT")
            except sqlite3.OperationalError:
                pass

        # MIGRACE: tři nové veličiny ze soláru.
        #
        # Dřív jsme z dongle uměli přečíst jen výkon panelů a baterii.
        # Teď z něj dostaneme i spotřebu domu, tok sítě a výkon baterie -
        # a bez historie by se z nich nedaly nakreslit grafy.
        #
        # Tok sítě i výkon baterie můžou být ZÁPORNÉ; právě znaménko určuje
        # SMĚR: záporná síť = odebíráme, záporná baterie = vybíjí se.
        #
        # U řádků naměřených dřív zůstane prázdno (NULL), a to je správně:
        # tehdy jsme ta data neměli a dopisovat si je zpětně nebudeme.
        # Grafy s tím počítají a prázdné řádky přeskočí.
        #
        # Stačí zjistit, jestli chybí první z nich - přidávají se všechny tři
        # naráz, takže buď jsou v tabulce všechny, nebo žádná.
        sloupce_m = [r[1] for r in db.execute("PRAGMA table_info(mereni)")]
        if "spotreba_domu" not in sloupce_m:
            try:
                db.execute("ALTER TABLE mereni ADD COLUMN spotreba_domu INTEGER")
                db.execute("ALTER TABLE mereni ADD COLUMN tok_site INTEGER")
                db.execute("ALTER TABLE mereni ADD COLUMN vykon_baterie INTEGER")
            except sqlite3.OperationalError:
                pass

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
        if prazdna and nejaci and _migrace_zabrana(db, "prvni_opravneni"):
            for (id_u,) in db.execute("SELECT id FROM uzivatele").fetchall():
                for tab in VSECHNY_TABY:
                    db.execute(
                        "INSERT INTO opravneni (uzivatel_id, tab) VALUES (?, ?)",
                        (id_u, tab),
                    )

        # MIGRACE: položky patří do seznamu a vědí, kdo je přidal.
        #
        # Sloupce se jménem (pridal, koupil) ZŮSTÁVAJÍ vedle nových s ID.
        # Není to nedopatření: ID slouží k rozhodování, kdo smí položku
        # upravit, kdežto jméno je záznam do historie. Když se účet smaže,
        # ID se vynuluje (ON DELETE SET NULL), ale u položky pořád zůstane
        # napsané, kdo ji tenkrát přidal.
        sloupce_n = [r[1] for r in db.execute("PRAGMA table_info(nakup)")]
        if "seznam_id" not in sloupce_n:
            try:
                db.execute("ALTER TABLE nakup ADD COLUMN seznam_id INTEGER "
                           "REFERENCES seznamy(id) ON DELETE CASCADE")
                db.execute("ALTER TABLE nakup ADD COLUMN pridal_id INTEGER "
                           "REFERENCES uzivatele(id) ON DELETE SET NULL")
                db.execute("ALTER TABLE nakup ADD COLUMN koupil_id INTEGER "
                           "REFERENCES uzivatele(id) ON DELETE SET NULL")
            except sqlite3.OperationalError:
                pass

        # MIGRACE: smí členové zvát další lidi?
        #
        # Výchozí je NE, a to i u seznamů, které už existují. Zvát dál je
        # rozšíření důvěry - to má vlastník zapnout vědomě, ne ho k tomu
        # přivést aktualizace.
        sloupce_s = [r[1] for r in db.execute("PRAGMA table_info(seznamy)")]
        if "clenove_zvou" not in sloupce_s:
            try:
                db.execute("ALTER TABLE seznamy ADD COLUMN clenove_zvou "
                           "INTEGER NOT NULL DEFAULT 0")
            except sqlite3.OperationalError:
                pass

        # MIGRACE: kolik položka stála.
        #
        # Vyplňuje ji ten, kdo nákup zaplatil, a je nepovinná - kdo si
        # účtenku hlídat nechce, prostě nic nezadá.
        if "cena" not in sloupce_n:
            try:
                db.execute("ALTER TABLE nakup ADD COLUMN cena REAL")
            except sqlite3.OperationalError:
                pass

        # MIGRACE: první seznam pro to, co v aplikaci už je.
        #
        # Nákupní seznam dosud patřil "všem, kdo mají právo na Nákup".
        # Teď musí patřit konkrétnímu seznamu, jinak by po nasazení nebylo
        # jasné, čí ty položky vlastně jsou. Založíme "Domácnost",
        # vlastníkem uděláme prvního správce a členy všechny ostatní,
        # kdo dnes na Nákup právo mají.
        #
        # Běží to jen jednou - podmínkou je, že tabulka seznamů je prázdná.
        # Musí to být až tady, za migrací oprávnění výš: bez ní by na
        # čerstvě povýšené databázi ještě žádná práva neexistovala a seznam
        # by zůstal bez členů.
        zadny_seznam = db.execute("SELECT COUNT(*) FROM seznamy").fetchone()[0] == 0
        if zadny_seznam:
            # Vlastníkem první správce, a když žádný není, první účet vůbec.
            # Řazení: nejdřív ti s právem na Správu (o.tab není prázdné),
            # uvnitř skupiny podle pořadí založení.
            vlastnik = db.execute("""
                SELECT u.id FROM uzivatele u
                LEFT JOIN opravneni o ON o.uzivatel_id = u.id AND o.tab = 'sprava'
                ORDER BY (o.tab IS NULL), u.id
                LIMIT 1
            """).fetchone()

            # Zámek až tady: na prázdné databázi bez účtů není co zakládat
            # a nemá smysl si migraci zabírat - udělá se, až účet vznikne.
            if vlastnik and _migrace_zabrana(db, "prvni_seznam"):
                id_vlastnika = vlastnik[0]
                db.execute(
                    "INSERT INTO seznamy (nazev, vlastnik_id, kod) VALUES (?, ?, ?)",
                    ("Domácnost", id_vlastnika, _novy_kod()),
                )
                id_seznamu = db.execute("SELECT last_insert_rowid()").fetchone()[0]

                db.execute("""
                    INSERT OR IGNORE INTO clenove_seznamu (seznam_id, uzivatel_id)
                    SELECT ?, uzivatel_id FROM opravneni
                    WHERE tab = 'nakup' AND uzivatel_id <> ?
                """, (id_seznamu, id_vlastnika))

                db.execute("UPDATE nakup SET seznam_id = ? WHERE seznam_id IS NULL",
                           (id_seznamu,))

                # Jména u položek přeložíme na účty. Jméno, které už žádnému
                # účtu neodpovídá (smazaný účet), zůstane bez ID - a to je
                # v pořádku, text jména u položky pořád zůstává.
                db.execute("""
                    UPDATE nakup SET pridal_id =
                        (SELECT id FROM uzivatele WHERE jmeno = nakup.pridal)
                    WHERE pridal_id IS NULL
                """)
                db.execute("""
                    UPDATE nakup SET koupil_id =
                        (SELECT id FROM uzivatele WHERE jmeno = nakup.koupil)
                    WHERE koupil_id IS NULL AND koupil IS NOT NULL
                """)

        # ÚKLID po chybě: první nasazení založilo "Domácnost" dvakrát.
        #
        # Oba workery migraci provedly současně (proto teď existuje
        # _migrace_zabrana). Položky i historie skončily jen v jednom z nich,
        # druhý zůstal prázdný. Necháme ten s obsahem a prázdné duplikáty
        # smažeme.
        #
        # Maže se JEN seznam, ve kterém není vůbec nic. Kdyby se obsah nějak
        # rozdělil do obou, radši zůstanou oba a člověk si to srovná ručně -
        # tichá ztráta cizích položek je horší než dva seznamy v proužku.
        if _migrace_zabrana(db, "uklid_dvojiteho_seznamu"):
            skupiny = db.execute("""
                SELECT s.nazev, s.vlastnik_id, COUNT(*)
                FROM seznamy s GROUP BY s.nazev, s.vlastnik_id
                HAVING COUNT(*) > 1
            """).fetchall()

            for nazev, vlastnik_id, _ in skupiny:
                stejne = db.execute("""
                    SELECT s.id,
                           (SELECT COUNT(*) FROM nakup n WHERE n.seznam_id = s.id)
                         + (SELECT COUNT(*) FROM historie_nakupu h
                            WHERE h.seznam_id = s.id) AS obsah
                    FROM seznamy s
                    WHERE s.nazev = ? AND s.vlastnik_id = ?
                    ORDER BY s.id
                """, (nazev, vlastnik_id)).fetchall()

                # Necháme ten s nejvíc obsahem; při shodě ten starší.
                nechat = max(stejne, key=lambda r: (r[1], -r[0]))[0]
                for id_seznamu, obsah in stejne:
                    if id_seznamu != nechat and obsah == 0:
                        db.execute("DELETE FROM clenove_seznamu WHERE seznam_id = ?",
                                   (id_seznamu,))
                        db.execute("DELETE FROM seznamy WHERE id = ?", (id_seznamu,))

        # MIGRACE: historie se vede zvlášť pro každý seznam.
        #
        # Tady nestačí přidat sloupec. Klíčem tabulky byl NÁZEV POLOŽKY
        # samotný, takže by dva seznamy nemohly mít v historii stejnou věc -
        # jakmile by si jeden zapsal mléko, druhý už ho zapsat nemohl.
        # Klíčem musí být dvojice (seznam, název), a klíč se v SQLite
        # dodatečně změnit nedá. Tabulka se proto postaví znovu a data se
        # přelijí do ní.
        sloupce_h = [r[1] for r in db.execute("PRAGMA table_info(historie_nakupu)")]
        if "seznam_id" not in sloupce_h:
            cil = db.execute("SELECT id FROM seznamy ORDER BY id LIMIT 1").fetchone()
            kolik = db.execute("SELECT COUNT(*) FROM historie_nakupu").fetchone()[0]

            # Když ještě žádný seznam není, ale historie už něco obsahuje,
            # radši nesaháme na nic - jinak bychom neměli kam ta data přelít.
            if cil or kolik == 0:
                try:
                    db.execute("""
                        CREATE TABLE historie_nova (
                            seznam_id INTEGER NOT NULL
                                      REFERENCES seznamy(id) ON DELETE CASCADE,
                            klic      TEXT    NOT NULL,
                            text      TEXT    NOT NULL,
                            pocet     INTEGER NOT NULL DEFAULT 1,
                            naposledy TEXT    NOT NULL,
                            PRIMARY KEY (seznam_id, klic)
                        )
                    """)
                    if cil:
                        db.execute("""
                            INSERT INTO historie_nova
                                   (seznam_id, klic, text, pocet, naposledy)
                            SELECT ?, klic, text, pocet, naposledy
                            FROM historie_nakupu
                        """, (cil[0],))
                    db.execute("DROP TABLE historie_nakupu")
                    db.execute("ALTER TABLE historie_nova RENAME TO historie_nakupu")
                except sqlite3.OperationalError:
                    pass
    # 'with' se postará o uzavření spojení a uložení (commit) změn.


# ==================== Nákupní seznam ====================

def _prevod_ceny(text):
    """
    Převede zapsanou cenu na číslo. Vrací (povedlo_se, číslo_nebo_None).

    Prázdný vstup znamená "cenu smazat", proto (True, None) - není to chyba.
    Čárku měníme na tečku, protože česky se píše 35,50, kdežto Python umí
    přečíst jen 35.50. Mezery (i ta nezlomitelná z "1 250") jdou pryč.
    """
    text = (text or "").strip().replace("\u00a0", "").replace(" ", "")
    text = text.replace("Kč", "").replace("kc", "").replace(",", ".")
    if not text:
        return True, None
    try:
        cena = float(text)
    except ValueError:
        return False, None
    if cena < 0 or cena > 1000000:
        return False, None
    return True, round(cena, 2)


def nastav_cenu(id_polozky, id_uzivatele, cena_text):
    """
    Uloží cenu u koupené položky. Smí to JEN ten, kdo ji koupil.

    Nikdo jiný cenu nezná - proto tu nestačí ani vlastník seznamu. Kdyby ji
    vyplňoval někdo od oka, bylo by číslo horší než žádné.
    """
    ok, cena = _prevod_ceny(cena_text)
    if not ok:
        return False, "Ceně nerozumím. Zkus třeba 35 nebo 35,50."

    with _spojeni() as db:
        kurzor = db.execute(
            "UPDATE nakup SET cena = ? WHERE id = ? AND koupil_id = ?",
            (cena, id_polozky, id_uzivatele),
        )
    if kurzor.rowcount == 0:
        return False, "Cenu vyplňuje ten, kdo položku koupil."
    return True, None


def seznamy_uzivatele(id_uzivatele):
    """
    Vrátí seznamy, na které uživatel má právo - vlastní i ty, kam ho přizvali.

    Vrací řádky (id, nazev, je_vlastnik, chybi), vlastní první. Tohle je
    JEDINÉ místo, kde je napsané, co znamená "můj seznam" - všechno ostatní
    se na něj odkazuje, aby to pravidlo nebylo rozeseté po aplikaci a nedalo
    se někde omylem obejít.

    'chybi' je počet neodškrtnutých položek. Počítá ho poddotaz rovnou
    v databázi; načítat kvůli číslu celý seznam by bylo zbytečné.
    """
    with _spojeni() as db:
        radky = db.execute("""
            SELECT s.id, s.nazev, s.vlastnik_id = ? AS je_vlastnik,
                   (SELECT COUNT(*) FROM nakup n
                    WHERE n.seznam_id = s.id AND n.koupeno = 0) AS chybi
            FROM seznamy s
            WHERE s.vlastnik_id = ?
               OR s.id IN (SELECT seznam_id FROM clenove_seznamu
                           WHERE uzivatel_id = ?)
            ORDER BY je_vlastnik DESC, s.nazev
        """, (id_uzivatele, id_uzivatele, id_uzivatele)).fetchall()

    # Slovníky, ne n-tice: v šabloně se pak píše s.nazev místo s[1].
    return [{"id": r[0], "nazev": r[1], "je_vlastnik": bool(r[2]), "chybi": r[3]}
            for r in radky]


def vychozi_seznam(id_uzivatele):
    """
    Který seznam ukázat, když si uživatel žádný nevybral.

    Vrací None, když uživatel nemá ani jeden - to zatím nastat nemůže,
    ale až přibude zakládání seznamů, bude to úplně běžný stav.
    """
    seznamy = seznamy_uzivatele(id_uzivatele)
    return seznamy[0]["id"] if seznamy else None


def vytvor_seznam(nazev, vlastnik_id):
    """
    Založí nový seznam. Vrací (True, id) nebo (False, "co je špatně").

    Kód pozvánky se losuje, a protože musí být jedinečný, může (byť
    nepravděpodobně) padnout na už existující. Proto těch pár pokusů -
    databáze na tom neuspěje a my to zkusíme znovu s jiným.
    """
    nazev = nazev.strip()[:60]
    if not nazev:
        return False, "Seznam musí mít název."

    with _spojeni() as db:
        for _ in range(5):
            try:
                db.execute(
                    "INSERT INTO seznamy (nazev, vlastnik_id, kod) VALUES (?, ?, ?)",
                    (nazev, vlastnik_id, _novy_kod()),
                )
                return True, db.execute("SELECT last_insert_rowid()").fetchone()[0]
            except sqlite3.IntegrityError:
                continue
    return False, "Nepodařilo se vyrobit kód pozvánky, zkus to znovu."


def prejmenuj_seznam(id_seznamu, id_uzivatele, nazev):
    """
    Přejmenuje seznam. Smí to jen vlastník.

    Podmínka na vlastníka je součástí UPDATE, ne kontrola před ním. Když
    nesedí, dotaz prostě nezmění ani řádek - a nemůže se stát, že by se
    mezi kontrolou a zápisem něco změnilo.
    """
    nazev = nazev.strip()[:60]
    if not nazev:
        return False, "Seznam musí mít název."

    with _spojeni() as db:
        kurzor = db.execute(
            "UPDATE seznamy SET nazev = ? WHERE id = ? AND vlastnik_id = ?",
            (nazev, id_seznamu, id_uzivatele),
        )
    if kurzor.rowcount == 0:
        return False, "Přejmenovat seznam může jen jeho vlastník."
    return True, "Seznam přejmenován."


def smaz_seznam(id_seznamu, id_uzivatele):
    """
    Smaže seznam - ale jen vlastníkův a jen úplně prázdný.

    Proč tak přísně: se seznamem by zmizely i položky a historie, a to
    i lidem, kteří na něm jsou. Na to je smazání moc tiché. Takhle se dá
    uklidit překlep v názvu, ale ne omylem vymazat cizí nákup.

    Až budou seznamy chodit z ruky do ruky přes pozvánky, bude to chtít
    pořádné řešení - nabídnout předání vlastníkovi nebo aspoň vypsat,
    o co všechno kdo přijde.
    """
    with _spojeni() as db:
        seznam = db.execute(
            "SELECT vlastnik_id FROM seznamy WHERE id = ?", (id_seznamu,)
        ).fetchone()
        if seznam is None:
            return False, "Takový seznam neexistuje."
        if seznam[0] != id_uzivatele:
            return False, "Smazat seznam může jen jeho vlastník."

        polozek = db.execute(
            "SELECT COUNT(*) FROM nakup WHERE seznam_id = ?", (id_seznamu,)
        ).fetchone()[0]
        clenu = db.execute(
            "SELECT COUNT(*) FROM clenove_seznamu WHERE seznam_id = ?", (id_seznamu,)
        ).fetchone()[0]

        if polozek or clenu:
            duvod = []
            if polozek:
                duvod.append("%d položek" % polozek if polozek > 4
                             else "%d položky" % polozek if polozek > 1
                             else "jednu položku")
            if clenu:
                duvod.append("%d dalších lidí" % clenu if clenu > 4
                             else "%d další lidi" % clenu if clenu > 1
                             else "ještě jednoho člověka")
            return False, ("Smazat jde jen úplně prázdný seznam a tenhle "
                           "obsahuje " + " a ".join(duvod) + ".")

        db.execute("DELETE FROM historie_nakupu WHERE seznam_id = ?", (id_seznamu,))
        db.execute("DELETE FROM seznamy WHERE id = ?", (id_seznamu,))
    return True, "Seznam smazán."


def seznam_pro_uzivatele(id_seznamu, id_uzivatele):
    """
    Vrátí (id, nazev, je_vlastnik), jen když na seznam uživatel právo má.
    Jinak None.

    Podmínka je schválně v SQL dotazu, ne v Pythonu za ním. Kdyby se řádek
    načetl a teprve pak posuzoval, dřív nebo později by někde vzniklo místo,
    kde se na to posouzení zapomene - a data už by přitom byla venku.
    """
    with _spojeni() as db:
        radek = db.execute("""
            SELECT s.id, s.nazev, s.vlastnik_id = ? AS je_vlastnik, s.kod,
                   s.clenove_zvou
            FROM seznamy s
            WHERE s.id = ?
              AND (s.vlastnik_id = ?
                   OR s.id IN (SELECT seznam_id FROM clenove_seznamu
                               WHERE uzivatel_id = ?))
        """, (id_uzivatele, id_seznamu, id_uzivatele, id_uzivatele)).fetchone()

    if radek is None:
        return None

    je_vlastnik = bool(radek[2])
    clenove_zvou = bool(radek[4])

    # Kód dostane jen ten, kdo ho vidět smí - vlastník vždycky, člen jen
    # když to vlastník povolil. Nevracíme ho a šablona pak nemá co
    # prozradit: kdyby se na podmínku zapomnělo, není tam co ukázat.
    vidi_kod = je_vlastnik or clenove_zvou

    return {"id": radek[0], "nazev": radek[1], "je_vlastnik": je_vlastnik,
            "kod": radek[3] if vidi_kod else None,
            "clenove_zvou": clenove_zvou}


def polozka_pro_uzivatele(id_polozky, id_uzivatele):
    """
    Vrátí položku, JEN když je na seznamu, na který uživatel má právo.
    Jinak None.

    Tohle je jediná branka k položkám - každá akce nad položkou musí projít
    tudy. Vrací slovník:

        {"id": 7, "seznam_id": 1, "smi_upravit": True}

    'smi_upravit' říká, jestli ji smí přepsat nebo smazat. Pravidlo zní
    "vlastník seznamu cokoliv, člen jen to, co sám přidal" a je spočítané
    rovnou v dotazu - aby si ho nemohla žádná route domýšlet po svém.

    Odškrtávat smí každý, kdo položku vidí. V obchodě je u regálu ten, kdo
    tam zrovna je, a nemá cenu ho nutit řešit, kdo to psal na seznam.
    """
    with _spojeni() as db:
        radek = db.execute("""
            SELECT n.id, n.seznam_id, n.koupeno,
                   (s.vlastnik_id = ? OR n.pridal_id = ?) AS smi_upravit
            FROM nakup n
            JOIN seznamy s ON s.id = n.seznam_id
            WHERE n.id = ?
              AND (s.vlastnik_id = ?
                   OR s.id IN (SELECT seznam_id FROM clenove_seznamu
                               WHERE uzivatel_id = ?))
        """, (id_uzivatele, id_uzivatele, id_polozky,
              id_uzivatele, id_uzivatele)).fetchone()

    if radek is None:
        return None
    return {"id": radek[0], "seznam_id": radek[1], "koupeno": bool(radek[2]),
            "smi_upravit": bool(radek[3])}


def pripoj_kodem(kod, id_uzivatele):
    """
    Připojí uživatele k seznamu podle kódu pozvánky.

    Vrací (povedlo_se, hláška, id_seznamu). id_seznamu se vrací i při
    neúspěchu z důvodu "už na něm jsi" - je kam poslat, a je to vstřícnější
    než hlásit chybu a nechat člověka stát na místě.

    Hláška u neznámého kódu záměrně neříká, jestli takový seznam neexistuje,
    nebo jestli na něj jen nemáš právo. Není z čeho vyčíst, které kódy
    platí.
    """
    upraveny = _uprav_kod(kod)
    if upraveny is None:
        return False, "Kód má šest znaků, například K7M-4QP.", None

    with _spojeni() as db:
        seznam = db.execute(
            "SELECT id, nazev, vlastnik_id FROM seznamy WHERE kod = ?",
            (upraveny,)).fetchone()
        if seznam is None:
            return False, "Takový kód nikam nevede.", None

        id_seznamu, nazev, vlastnik_id = seznam
        if vlastnik_id == id_uzivatele:
            return False, "Tenhle seznam je tvůj vlastní.", id_seznamu

        try:
            db.execute(
                "INSERT INTO clenove_seznamu (seznam_id, uzivatel_id) VALUES (?, ?)",
                (id_seznamu, id_uzivatele))
        except sqlite3.IntegrityError:
            # Dvojice (seznam, uživatel) je primární klíč, takže druhé
            # připojení databáze sama odmítne.
            return False, "Na seznamu %s už jsi." % nazev, id_seznamu

    return True, "Připojeno k seznamu %s." % nazev, id_seznamu


def clenove(id_seznamu):
    """
    Kdo je na seznamu. Vlastník první, pak přizvaní podle abecedy.

    Vlastník není v tabulce členů (je sloupcem v tabulce seznamů), takže se
    obě skupiny musí spojit - od toho je UNION ALL.
    """
    with _spojeni() as db:
        radky = db.execute("""
            SELECT u.id, u.jmeno, 1 AS je_vlastnik
            FROM seznamy s JOIN uzivatele u ON u.id = s.vlastnik_id
            WHERE s.id = ?
            UNION ALL
            SELECT u.id, u.jmeno, 0
            FROM clenove_seznamu c JOIN uzivatele u ON u.id = c.uzivatel_id
            WHERE c.seznam_id = ?
            ORDER BY je_vlastnik DESC, jmeno
        """, (id_seznamu, id_seznamu)).fetchall()

    return [{"id": r[0], "jmeno": r[1], "je_vlastnik": bool(r[2])} for r in radky]


def novy_kod_seznamu(id_seznamu, id_vlastnika):
    """
    Vygeneruje nový kód pozvánky. Starý tím přestane platit.

    Hodí se, když se kód dostal někam, kam neměl - na nikoho, kdo už je
    členem, to nemá vliv.
    """
    with _spojeni() as db:
        for _ in range(5):
            try:
                kurzor = db.execute(
                    "UPDATE seznamy SET kod = ? WHERE id = ? AND vlastnik_id = ?",
                    (_novy_kod(), id_seznamu, id_vlastnika))
                if kurzor.rowcount == 0:
                    return False, "Změnit kód může jen vlastník seznamu."
                return True, "Nový kód vygenerován, starý už neplatí."
            except sqlite3.IntegrityError:
                continue
    return False, "Nepodařilo se vyrobit nový kód, zkus to znovu."


def nastav_zvani(id_seznamu, id_vlastnika, povolit):
    """
    Určí, jestli smí členové zvát další lidi. Rozhoduje jen vlastník.

    Zvát dál v našem případě znamená VIDĚT KÓD - kdo ho má, může ho poslat
    komukoliv. Přepínač tedy nedělá nic jiného, než že členům kód ukáže
    nebo skryje.

    Přegenerovat kód smí pořád jen vlastník: tím by se ostatním zneplatnily
    pozvánky, které už rozeslali.
    """
    with _spojeni() as db:
        kurzor = db.execute(
            "UPDATE seznamy SET clenove_zvou = ? WHERE id = ? AND vlastnik_id = ?",
            (1 if povolit else 0, id_seznamu, id_vlastnika),
        )
    if kurzor.rowcount == 0:
        return False, "Tohle nastavuje jen vlastník seznamu."
    if povolit:
        return True, "Členové teď můžou zvát další lidi."
    return True, "Zvaní dalších lidí je zase jen na tobě."


def odeber_clena(id_seznamu, id_vlastnika, id_clena):
    """
    Odebere člena ze seznamu. Smí to jen vlastník.

    Položky, které člen přidal, na seznamu ZŮSTÁVAJÍ - patří seznamu, ne
    jemu. Přestane je jen vidět.
    """
    with _spojeni() as db:
        kurzor = db.execute("""
            DELETE FROM clenove_seznamu
            WHERE seznam_id = ? AND uzivatel_id = ?
              AND EXISTS (SELECT 1 FROM seznamy
                          WHERE id = ? AND vlastnik_id = ?)
        """, (id_seznamu, id_clena, id_seznamu, id_vlastnika))

    if kurzor.rowcount == 0:
        return False, "Odebrat člena může jen vlastník seznamu."
    return True, "Člen odebrán."


def opust_seznam(id_seznamu, id_uzivatele):
    """
    Odchod ze seznamu, na který mě někdo přizval.

    Vlastník odejít nemůže - seznam by zůstal bez vlastníka. Ten ho musí
    buď smazat, nebo (až to půjde) předat.
    """
    with _spojeni() as db:
        kurzor = db.execute(
            "DELETE FROM clenove_seznamu WHERE seznam_id = ? AND uzivatel_id = ?",
            (id_seznamu, id_uzivatele))

    if kurzor.rowcount == 0:
        return False, "Ze svého vlastního seznamu odejít nejde."
    return True, "Seznam jsi opustil."


def pridej_polozku(seznam_id, text, kdo, kdo_id, mnozstvi=None):
    """
    Přidá položku na nákupní seznam a započítá ji do historie.

    mnozstvi je volný text ("2 l", "3x", "půl kila") a je nepovinné -
    potraviny se nedají nacpat do jednoho formátu.

    Ukládá se jméno i ID uživatele. Jméno je záznam do historie (zůstane
    čitelné, i když účet jednou zmizí), ID slouží k rozhodování, kdo smí
    položku později upravit nebo smazat.
    """
    if seznam_id is None:
        return False

    text = text.strip()
    if not text:
        return False

    # Rozumný strop na délku. Bez něj by šlo do databáze poslat megabajty
    # textu - ne kvůli zlému úmyslu, stačí omylem vložený text ze schránky.
    text = text[:200]
    mnozstvi = (mnozstvi or "").strip()[:40] or None

    with _spojeni() as db:
        db.execute(
            "INSERT INTO nakup (seznam_id, text, mnozstvi, pridal, pridal_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (seznam_id, text, mnozstvi, kdo, kdo_id),
        )

        # Zápis do historie. ON CONFLICT znamená "když už takový klíč
        # existuje, místo vložení udělej tohle" - tady zvýšíme počítadlo
        # a zapamatujeme si poslední zápis názvu.
        #
        # Klíč je dvojice (seznam, název), ne jen název: každá parta má
        # svoji historii a nemá vidět do cizí.
        db.execute("""
            INSERT INTO historie_nakupu (seznam_id, klic, text, pocet, naposledy)
            VALUES (?, ?, ?, 1, datetime('now', 'localtime'))
            ON CONFLICT(seznam_id, klic) DO UPDATE SET
                pocet = pocet + 1,
                text = excluded.text,
                naposledy = excluded.naposledy
        """, (seznam_id, text.lower(), text))
    return True


def uprav_polozku(id_polozky, text, mnozstvi=None):
    """Změní název a množství existující položky."""
    text = text.strip()[:200]
    if not text:
        return False

    with _spojeni() as db:
        db.execute(
            "UPDATE nakup SET text = ?, mnozstvi = ? WHERE id = ?",
            (text, (mnozstvi or "").strip()[:40] or None, id_polozky),
        )
    return True


def caste_polozky(seznam_id, limit=8):
    """
    Nejčastěji kupované položky pro rychlé přidání.

    Vynechává to, co už na seznamu je - nemá smysl nabízet položku,
    která tam visí. Řeší to poddotaz v NOT IN.

    Všechno je omezené na JEDEN seznam, historie i to porovnání. Bez toho
    by tlačítka ukazovala, co nakupují cizí lidé, a položka na cizím
    seznamu by ti tu tvoji z nabídky vyškrtla.
    """
    if seznam_id is None:
        return []

    with _spojeni() as db:
        radky = db.execute("""
            SELECT text FROM historie_nakupu
            WHERE seznam_id = ?
              AND klic NOT IN (SELECT LOWER(text) FROM nakup
                               WHERE seznam_id = ?)
            ORDER BY pocet DESC, naposledy DESC
            LIMIT ?
        """, (seznam_id, seznam_id, limit)).fetchall()
    return [r[0] for r in radky]


def seznam_nakupu(seznam_id, id_uzivatele):
    """
    Vrátí položky jednoho seznamu: nekoupené první, nejnovější nahoře.

    ORDER BY koupeno ASC, id DESC znamená "nejdřív seřaď podle koupeno
    (0 před 1), a při shodě podle id sestupně". Tak zůstane to, co ještě
    chybí, nahoře - a to je v obchodě jediné, co člověk potřebuje vidět.

    'smi_upravit' říká, jestli smí tenhle člověk položku přepsat nebo
    smazat. Šablona podle něj u cizích schová tužku a křížek: nabízet
    tlačítko, které skončí hláškou "tohle nesmíš", je horší než ho
    neukázat vůbec.

    Vrací slovníky, ne n-tice - položka jich nese devět a číst v šabloně
    p[7] by byla hádanka.
    """
    if seznam_id is None:
        return []

    with _spojeni() as db:
        radky = db.execute("""
            SELECT n.id, n.text, n.koupeno, n.mnozstvi,
                   n.pridal, n.pridal_id, n.koupil, n.koupil_id, n.cena,
                   (s.vlastnik_id = ? OR n.pridal_id = ?) AS smi_upravit
            FROM nakup n
            JOIN seznamy s ON s.id = n.seznam_id
            WHERE n.seznam_id = ?
            ORDER BY n.koupeno ASC, n.id DESC
        """, (id_uzivatele, id_uzivatele, seznam_id)).fetchall()

    return [{"id": r[0], "text": r[1], "koupeno": bool(r[2]), "mnozstvi": r[3],
             "pridal": r[4], "pridal_id": r[5],
             "koupil": r[6], "koupil_id": r[7], "cena": r[8],
             "smi_upravit": bool(r[9])} for r in radky]


def prepni_koupeno(id_polozky, kdo, kdo_id):
    """Odškrtne položku, nebo odškrtnutí zruší (přepne stav)."""
    with _spojeni() as db:
        radek = db.execute(
            "SELECT koupeno FROM nakup WHERE id = ?", (id_polozky,)
        ).fetchone()
        if radek is None:
            return False

        if radek[0]:
            # Bylo koupeno -> vracíme zpět mezi chybějící, stopu mažeme.
            # Cena zmizí s odškrtnutím: patřila k tomu nákupu, a ten
            # se právě vzal zpátky.
            db.execute(
                "UPDATE nakup SET koupeno = 0, koupil = NULL, koupil_id = NULL, "
                "koupeno_kdy = NULL, cena = NULL WHERE id = ?",
                (id_polozky,),
            )
        else:
            db.execute(
                "UPDATE nakup SET koupeno = 1, koupil = ?, koupil_id = ?, "
                "koupeno_kdy = datetime('now', 'localtime') WHERE id = ?",
                (kdo, kdo_id, id_polozky),
            )
    return True


def smaz_polozku(id_polozky):
    """Smaže jednu položku ze seznamu."""
    with _spojeni() as db:
        db.execute("DELETE FROM nakup WHERE id = ?", (id_polozky,))


def vyuctovani(seznam_id):
    """
    Spočítá, kdo za odškrtnuté položky zaplatil a kdo komu dluží.

    Vrací:
        {"celkem": 224.5,
         "zaplatili": [{"jmeno": "Petrjr", "castka": 224.5}],
         "dluhy": [{"dluznik": "Petr", "verite": "Petrjr", "castka": 71.0}],
         "bez_ceny": 1}

    KDO KOMU DLUŽÍ vychází z toho, co u položky stojí: kdo ji koupil a komu.
    Když si ji koupil sám sobě, nikdo nikomu nic nedluží.

    Vzájemné dluhy se ODEČÍTAJÍ. Když Petr dluží Janě stovku a Jana Petrovi
    třicet, výsledek je "Petr dluží Janě sedmdesát" - vracet si dvě částky
    tam a zpátky nemá smysl.

    Počítá se podle JMEN, ne podle ID: jméno je u položky vždycky, i když
    účet mezitím zmizel, a v aplikaci je jedinečné.
    """
    with _spojeni() as db:
        radky = db.execute("""
            SELECT cena, koupil, pridal FROM nakup
            WHERE seznam_id = ? AND koupeno = 1
        """, (seznam_id,)).fetchall()

    celkem = 0.0
    bez_ceny = 0
    zaplatil = {}
    dluh = {}

    for cena, koupil, pridal in radky:
        if cena is None:
            bez_ceny += 1
            continue
        celkem += cena
        zaplatil[koupil] = zaplatil.get(koupil, 0.0) + cena
        if koupil != pridal:
            dluh[(pridal, koupil)] = dluh.get((pridal, koupil), 0.0) + cena

    # Odečtení vzájemných dluhů. Dvojici procházíme jen jednou - proto ta
    # podmínka na pořadí jmen, jinak bychom si odečet udělali dvakrát
    # a vyrušil by se.
    vysledek = {}
    for (dluznik, verite), castka in dluh.items():
        if (verite, dluznik) in dluh and (verite, dluznik) < (dluznik, verite):
            continue
        protismer = dluh.get((verite, dluznik), 0.0)
        rozdil = round(castka - protismer, 2)
        if rozdil > 0:
            vysledek[(dluznik, verite)] = rozdil
        elif rozdil < 0:
            vysledek[(verite, dluznik)] = -rozdil

    return {
        "celkem": round(celkem, 2),
        "zaplatili": sorted(
            ({"jmeno": j, "castka": round(c, 2)} for j, c in zaplatil.items()),
            key=lambda z: -z["castka"]),
        "dluhy": sorted(
            ({"dluznik": d, "verite": v, "castka": c}
             for (d, v), c in vysledek.items()),
            key=lambda z: -z["castka"]),
        "bez_ceny": bez_ceny,
    }


def smaz_koupene(seznam_id, id_uzivatele):
    """
    Uklidí odškrtnuté položky jednoho seznamu. Vrací, kolik jich zmizelo.

    Smaže přesně to, co ten člověk smět má - vlastníkovi seznamu všechno
    odškrtnuté, členovi jen jeho vlastní. Vyplývá to ze stejného pravidla
    jako u jednotlivé položky, takže tu není žádná výjimka navíc.

    Dřív tahle funkce mazala odškrtnuté položky v CELÉ tabulce. Dokud byl
    seznam jeden, nevadilo to; s druhým by jedno klepnutí smazalo cizím
    lidem jejich nákup.
    """
    if seznam_id is None:
        return 0

    with _spojeni() as db:
        kurzor = db.execute("""
            DELETE FROM nakup
            WHERE seznam_id = ? AND koupeno = 1
              AND (pridal_id = ?
                   OR EXISTS (SELECT 1 FROM seznamy
                              WHERE id = ? AND vlastnik_id = ?))
        """, (seznam_id, id_uzivatele, seznam_id, id_uzivatele))
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


def zaznamenej_prihlaseni(id_uzivatele):
    """Uloží čas posledního přihlášení."""
    with _spojeni() as db:
        db.execute(
            "UPDATE uzivatele SET posledni_prihlaseni = "
            "datetime('now', 'localtime') WHERE id = ?",
            (id_uzivatele,),
        )


def zmen_heslo_s_overenim(id_uzivatele, stare, nove):
    """
    Změna vlastního hesla - vyžaduje to staré.

    Vrací (True, None) nebo (False, "důvod").

    PROČ STARÉ HESLO: kdyby stačilo zadat jen nové, komukoliv by k převzetí
    účtu stačil odemčený mobil na stole. Správcova zmen_heslo() staré heslo
    nechce a to je v pořádku - to je nouzová cesta pro zapomenutá hesla.
    """
    if len(nove) < 6:
        return False, "Nové heslo musí mít aspoň 6 znaků."

    with _spojeni() as db:
        radek = db.execute(
            "SELECT heslo_hash FROM uzivatele WHERE id = ?", (id_uzivatele,)
        ).fetchone()

    if radek is None:
        return False, "Účet neexistuje."
    if not check_password_hash(radek[0], stare):
        return False, "Staré heslo nesouhlasí."

    with _spojeni() as db:
        db.execute(
            "UPDATE uzivatele SET heslo_hash = ? WHERE id = ?",
            (generate_password_hash(nove), id_uzivatele),
        )
    return True, None


def udaje_uzivatele(id_uzivatele):
    """Jméno a datum založení účtu - pro stránku profilu."""
    with _spojeni() as db:
        radek = db.execute(
            "SELECT jmeno, vytvoren, posledni_prihlaseni "
            "FROM uzivatele WHERE id = ?", (id_uzivatele,)
        ).fetchone()
    if radek is None:
        return None
    return {"jmeno": radek[0], "vytvoren": radek[1], "posledni": radek[2]}


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


def _pocet_seznamu(kolik):
    """Napíše počet seznamů česky: 'jeden seznam', '3 seznamy', '7 seznamů'."""
    if kolik == 1:
        return "jeden nákupní seznam"
    if kolik < 5:
        return "%d nákupní seznamy" % kolik
    return "%d nákupních seznamů" % kolik


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

        # POJISTKA: účet, který vlastní nějaký nákupní seznam, smazat nejde.
        #
        # Seznam by zůstal bez vlastníka a lidem, kteří na něm jsou, by
        # zmizely položky. Radši to odmítneme a řekneme proč, než abychom
        # potichu smazali cizí data.
        vlastni = db.execute(
            "SELECT COUNT(*) FROM seznamy WHERE vlastnik_id = ?", (id_uzivatele,)
        ).fetchone()[0]
        if vlastni:
            return False, ("Tenhle účet vlastní %s. Nejdřív ho smaž nebo "
                           "předej někomu jinému." % _pocet_seznamu(vlastni))

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
            SELECT u.id, u.jmeno, u.vytvoren, o.tab, u.posledni_prihlaseni
            FROM uzivatele u
            LEFT JOIN opravneni o ON o.uzivatel_id = u.id
            ORDER BY u.id
        """).fetchall()

    # Dotaz vrací jeden řádek na KAŽDÉ právo, takže se uživatel opakuje.
    # Poskládáme to zpátky do jednoho záznamu na uživatele.
    podle_id = {}
    for id_u, jmeno, vytvoren, tab, posledni in radky:
        if id_u not in podle_id:
            podle_id[id_u] = {"id": id_u, "jmeno": jmeno,
                              "vytvoren": vytvoren, "posledni": posledni,
                              "prava": set()}
        if tab:
            podle_id[id_u]["prava"].add(tab)

    return list(podle_id.values())


def uloz_mereni(cas, vykon_panelu, denni_vyroba, baterie_soc,
                spotreba_domu, tok_site, vykon_baterie):
    """
    Přidá do tabulky 'mereni' jeden nový řádek (jedno měření).

    tok_site a vykon_baterie chodí SE ZNAMÉNKEM - záporná síť znamená,
    že ze sítě bereme, záporná baterie že se vybíjí. Ukládáme je tak,
    jak přijdou; převádět je na "kladné číslo plus směr" by znamenalo
    dva sloupce místo jednoho a nic bychom tím nezískali.
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
            "INSERT INTO mereni "
            "(cas, vykon_panelu, denni_vyroba, baterie_soc, "
            " spotreba_domu, tok_site, vykon_baterie) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (cas, vykon_panelu, denni_vyroba, baterie_soc,
             spotreba_domu, tok_site, vykon_baterie),
        )


def nacti_pro_graf(hodin=24):
    """
    Vrátí měření za posledních 'hodin' hodin, seřazená od nejstaršího.

    Pro graf potřebujeme opačné pořadí než pro výpis: čas musí růst
    zleva doprava, takže ORDER BY id ASC (vzestupně).

    Sloupce v řádku jsou v pořadí:
        0 cas, 1 vykon_panelu, 2 denni_vyroba, 3 baterie_soc,
        4 spotreba_domu, 5 tok_site, 6 vykon_baterie
    U měření z doby před rozšířením sběru jsou poslední tři prázdné (None).

    Filtrování času necháváme na databázi (WHERE) - je to její práce
    a je v tom rychlejší, než kdybychom načetli všechno a třídili v Pythonu.
    """
    with _spojeni() as db:
        # datetime('now', 'localtime', '-24 hours') je funkce SQLite:
        # spočítá časovou hranici přímo v databázi.
        kurzor = db.execute(
            "SELECT cas, vykon_panelu, denni_vyroba, baterie_soc, "
            "       spotreba_domu, tok_site, vykon_baterie "
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
            "SELECT id, cas, vykon_panelu, denni_vyroba, baterie_soc, "
            "       spotreba_domu, tok_site, vykon_baterie "
            "FROM mereni ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return kurzor.fetchall()  # fetchall = "dej mi všechny nalezené řádky"
