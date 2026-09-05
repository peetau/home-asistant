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

# Vyrábí z obyčejné funkce správce kontextu - tedy něco, co se dá použít
# v bloku "with". Co je před yield, se stane při vstupu do bloku,
# co za ním, při odchodu z něj (a to i když blok skončí chybou).
from contextlib import contextmanager

# Funkce na bezpečnou práci s hesly. Werkzeug přišel automaticky s Flaskem,
# takže se nic neinstaluje. Sami si hashování NIKDY nepíšeme - je to oblast,
# kde se snadno udělá chyba s vážnými následky, a tyhle funkce ji řeší správně.
from werkzeug.security import generate_password_hash, check_password_hash

# Cesta k souboru databáze. Skládáme ji z místa, kde leží tenhle .py soubor,
# aby databáze vždy vznikla ve složce projektu - ať skript spustíš odkudkoliv.
DB_SOUBOR = os.path.join(os.path.dirname(__file__), "asistent.db")

# Taby, na které se udělují práva.
#
# Přehled ani Nákup tu SCHVÁLNĚ NEJSOU. Přehled je vždy dostupný každému
# přihlášenému a jeho obsah se poskládá z toho, na co uživatel právo má.
# Správcovství je od 5. 9. 2026 sloupec `uzivatele.spravce`, ne řádek
# v tabulce práv. Z práv zbylo po zrušení 'nakup', 'solary' a 'nanoleaf'
# jediné, takže celá tabulka i tři konstanty kolem ní existovaly kvůli
# jedné nule nebo jedničce. K zařízením se chodí přes členství
# v domácnosti, viz domacnost_uzivatele().


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


@contextmanager
def _spojeni():
    """
    Otevře spojení s databázovým souborem, půjčí ho bloku "with"
    a na konci ho zase zavře.

    Když soubor asistent.db ještě neexistuje, SQLite ho při prvním
    spojení sám vytvoří. Není tedy co "zakládat" ručně.

    ⚠️ Zavírání tu musí být napsané ručně. Samotné "with spojeni:" totiž
    spojení NEZAVÍRÁ - jenom potvrdí (nebo při chybě vrátí zpět) transakci
    a soubor nechá dál otevřený. Na serveru se takhle 4. 9. 2026 za patnáct
    hodin provozu nasbíralo přes tisíc otevřených kopií asistent.db, došly
    systémové deskriptory (strop je 1024) a aplikace přestala umět databázi
    otevřít vůbec. Vnitřní "with spojeni:" se o transakci stará jako dřív,
    "finally" navíc soubor zavře - a to i když v bloku vznikne chyba.
    """
    spojeni = sqlite3.connect(DB_SOUBOR)

    # SQLite má hlídání vazeb mezi tabulkami ve výchozím stavu VYPNUTÉ
    # (kvůli zpětné kompatibilitě) a zapíná se pro každé spojení zvlášť.
    # Bez tohohle řádku by ON DELETE CASCADE u oprávnění nefungovalo
    # a po smazání uživatele by v databázi zůstala jeho osiřelá práva.
    spojeni.execute("PRAGMA foreign_keys = ON")

    try:
        with spojeni:
            yield spojeni
    finally:
        spojeni.close()


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
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                jmeno               TEXT    NOT NULL,
                email               TEXT,
                heslo_hash          TEXT    NOT NULL,
                spravce             INTEGER NOT NULL DEFAULT 0,
                vytvoren            TEXT    NOT NULL
                                    DEFAULT (datetime('now', 'localtime')),
                posledni_prihlaseni TEXT
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

        # Nastavení aplikace: klíč a hodnota.
        #
        # Zatím tu bydlí jediná věc, registrační kód. Tabulka je i tak na
        # místě: alternativou by byl další sloupec někde, kam nepatří, nebo
        # hodnota v souboru, kterou by nešlo změnit z aplikace.
        db.execute("""
            CREATE TABLE IF NOT EXISTS nastaveni (
                klic    TEXT PRIMARY KEY,
                hodnota TEXT NOT NULL
            )
        """)

        # Registrační kód musí existovat od první chvíle, jinak by se nikdo
        # nezaregistroval a nebylo by kde ho vzít. INSERT OR IGNORE proto,
        # že při druhém startu už tam je - a přepsat ho by znamenalo
        # zneplatnit kód, který mezitím někdo rozeslal.
        db.execute("INSERT OR IGNORE INTO nastaveni (klic, hodnota) "
                   "VALUES ('registracni_kod', ?)", (_novy_kod(),))

        # Neúspěšné pokusy o přihlášení, jeden řádek na IP adresu.
        #
        # Počítá se ADRESA, ne jméno. Kdyby se počítalo jméno, stačilo by
        # útočníkovi zkoušet cizí jméno a majitel účtu by se sám nedostal
        # dovnitř - vyřadit člověka z provozu by bylo snazší než se k němu
        # vloupat.
        #
        # Tabulka se schválně nedrží v paměti procesu: gunicorn má dva
        # workery, každý by měl vlastní počítadlo (tedy dvojnásobek pokusů)
        # a restart by je vynuloval.
        db.execute("""
            CREATE TABLE IF NOT EXISTS pokusy_prihlaseni (
                ip           TEXT PRIMARY KEY,
                chyb         INTEGER NOT NULL DEFAULT 0,
                blokovano_do TEXT,
                posledni     TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
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

        # Domácnost: parta lidí, které patří zařízení.
        #
        # Vlastník je SLOUPEC, ne řádek v tabulce členů s nějakou rolí -
        # stejně jako u nákupního seznamu. Díky tomu hlídá databáze sama,
        # že vlastníka má domácnost právě jednoho.
        #
        # ma_zarizeni říká, KTERÉ domácnosti patří zařízení z config.py.
        # Bez toho sloupce by se podmínka nedala napsat bezpečně: zařízení
        # jsou v configu, tedy společná pro celý server, takže "jsi člen
        # nějaké domácnosti" by pustilo k cizímu SolaXu každého, kdo si
        # založí vlastní. Až se zařízení přestěhují do databáze, sloupec
        # zmizí a nahradí ho vazba zařízení -> domácnost.
        db.execute("""
            CREATE TABLE IF NOT EXISTS domacnosti (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                nazev       TEXT    NOT NULL,
                vlastnik_id INTEGER NOT NULL REFERENCES uzivatele(id),
                kod         TEXT    UNIQUE,
                ma_zarizeni INTEGER NOT NULL DEFAULT 0,
                vytvorena   TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
        """)

        # Zařízení smí mít nejvýš JEDNA domácnost - a hlídá to databáze,
        # ne Python. Částečný index (WHERE ma_zarizeni = 1) hlídá jedničky
        # a nuly nechává být, takže domácností bez zařízení může být kolik
        # chce. Dva workery zakládající naráz si tím nemůžou udělat dvě
        # hlavní domácnosti - druhý dostane IntegrityError, úplně stejně
        # jako u _migrace_zabrana(). Rozhoduje databáze, ne načasování.
        db.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS jedna_domacnost_se_zarizenimi
                ON domacnosti (ma_zarizeni) WHERE ma_zarizeni = 1
        """)

        # Kdo do domácnosti patří. Vlastník tu NENÍ - je sloupcem výš.
        db.execute("""
            CREATE TABLE IF NOT EXISTS clenove_domacnosti (
                domacnost_id INTEGER NOT NULL
                             REFERENCES domacnosti(id) ON DELETE CASCADE,
                uzivatel_id  INTEGER NOT NULL
                             REFERENCES uzivatele(id) ON DELETE CASCADE,
                pridan       TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
                PRIMARY KEY (domacnost_id, uzivatel_id)
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

        # MIGRACE: správcovství se stěhuje z tabulky do sloupce.
        #
        # Z práv zbylo po zrušení 'solary' a 'nanoleaf' jediné, 'sprava',
        # takže celá tabulka opravneni i konstanty kolem ní existovaly kvůli
        # jedné nule nebo jedničce.
        #
        # ⚠️ NA POŘADÍ ZÁLEŽÍ: nejdřív se z opravneni PŘEČTE, kdo je správce,
        # pak se to zapíše do sloupce, a teprve potom se tabulka zahodí.
        # Obráceně by se správcovství ztratilo a do Správy by se nedostal
        # nikdo.
        if "spravce" not in sloupce_u:
            try:
                db.execute("ALTER TABLE uzivatele ADD COLUMN "
                           "spravce INTEGER NOT NULL DEFAULT 0")
            except sqlite3.OperationalError:
                pass

        stare_tabulky = [r[0] for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")]
        if "opravneni" in stare_tabulky:
            for (id_u,) in db.execute(
                    "SELECT DISTINCT uzivatel_id FROM opravneni "
                    "WHERE tab = 'sprava'").fetchall():
                db.execute("UPDATE uzivatele SET spravce = 1 WHERE id = ?",
                           (id_u,))
            db.execute("DROP TABLE opravneni")

        # MIGRACE: e-mail, kterým se bude přihlašovat.
        #
        # Zatím SMÍ být prázdný - dnešní účty žádný nemají a doplní se
        # ručně ve Správě. Teprve až je budou mít všechny, přepne se
        # přihlašování ze jména na e-mail. Kdyby se to přehodilo dřív,
        # nepřihlásil by se nikdo včetně správce, a protože Správa je za
        # přihlášením, nešlo by to spravit odjinud než zápisem do databáze.
        if "email" not in sloupce_u:
            try:
                db.execute("ALTER TABLE uzivatele ADD COLUMN email TEXT")
            except sqlite3.OperationalError:
                pass

        # Jedinečnost e-mailu hlídá index, ne sloupec: ALTER TABLE v SQLite
        # neumí přidat sloupec s UNIQUE. Vyjde to nastejno a navíc to
        # dovoluje víc prázdných hodnot - NULL se v unikátním indexu
        # opakovat smí, a to je přesně to, co teď potřebujeme.
        db.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS jeden_email_na_ucet
                ON uzivatele (email)
        """)

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

    # 'with' se postará o uzavření spojení a uložení (commit) změn.

    # Až nakonec, mimo blok výš: přestavba potřebuje vlastní spojení
    # a hlavně už hotový sloupec email, který přidává migrace uvnitř.
    _zrus_jedinecnost_jmena()


def _zrus_jedinecnost_jmena():
    """
    Zruší jedinečnost jména přestavbou tabulky `uzivatele`.

    SQLite neumí UNIQUE odebrat příkazem ALTER - implicitní index, který
    z něj vznikl, nejde zahodit. Tabulka se proto musí postavit znovu
    a data přelít. Jméno už není přihlašovací údaj (od 5. 9. 2026 je jím
    e-mail), takže není důvod někomu brát jméno jen proto, že ho má i někdo
    jiný.

    ⚠️ Běží na VLASTNÍM spojení s VYPNUTÝMI cizími klíči, a schválně mimo
    hlavní blok init_db(). Se zapnutými klíči by `DROP TABLE uzivatele`
    spustil ON DELETE CASCADE u oprávnění a členství a smazal by je - a u
    seznamů a domácností by naopak selhal, protože jejich vlastník je
    NOT NULL. Vypnout klíče uprostřed transakce nejde, PRAGMA se tam tiše
    ignoruje; proto samostatné spojení.

    Na konci se pouští `PRAGMA foreign_key_check`. Přestavba se dělá jednou
    za život aplikace a s vypnutými klíči - kdyby se něco pokazilo, je lepší
    spadnout hned při startu než tihočinit s rozbitou databazí.
    """
    spojeni = sqlite3.connect(DB_SOUBOR)
    try:
        tabulky = [r[0] for r in spojeni.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")]
        if "uzivatele" not in tabulky:
            return

        # Zbyl ještě UNIQUE po jménu? Index z UNIQUE má v index_list původ 'u'.
        potreba = False
        for radek in spojeni.execute("PRAGMA index_list(uzivatele)").fetchall():
            nazev, je_unikatni, puvod = radek[1], radek[2], radek[3]
            if je_unikatni and puvod == "u":
                sloupce = [s[2] for s in
                           spojeni.execute("PRAGMA index_info(%s)" % nazev)]
                if sloupce == ["jmeno"]:
                    potreba = True

        if not potreba:
            return

        spojeni.execute("PRAGMA foreign_keys = OFF")
        with spojeni:
            spojeni.execute("""
                CREATE TABLE uzivatele_nova (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    jmeno               TEXT    NOT NULL,
                    email               TEXT,
                    heslo_hash          TEXT    NOT NULL,
                    spravce             INTEGER NOT NULL DEFAULT 0,
                    vytvoren            TEXT    NOT NULL
                                        DEFAULT (datetime('now', 'localtime')),
                    posledni_prihlaseni TEXT
                )
            """)
            spojeni.execute("""
                INSERT INTO uzivatele_nova
                       (id, jmeno, email, heslo_hash, spravce, vytvoren,
                        posledni_prihlaseni)
                SELECT  id, jmeno, email, heslo_hash, spravce, vytvoren,
                        posledni_prihlaseni
                FROM uzivatele
            """)
            spojeni.execute("DROP TABLE uzivatele")
            spojeni.execute("ALTER TABLE uzivatele_nova RENAME TO uzivatele")
            spojeni.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS jeden_email_na_ucet
                    ON uzivatele (email)
            """)

        potize = spojeni.execute("PRAGMA foreign_key_check").fetchall()
        if potize:
            raise RuntimeError(
                "po přestavbě tabulky uzivatele nesedí cizí klíče: %r"
                % (potize[:3],))
    finally:
        spojeni.close()


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


def predej_seznam(id_seznamu, id_vlastnika, id_noveho):
    """
    Předá nákupní seznam jinému členovi. Vrací (povedlo_se, hláška).

    Stejné pravidlo jako u domácnosti: role se prohodí, předat jde jen
    členovi a obě podmínky jsou v UPDATE, ne před ním. Položky ani historie
    se nedotýkají - patří seznamu, ne vlastníkovi.
    """
    if id_noveho == id_vlastnika:
        return False, "Předat sám sobě nejde."

    with _spojeni() as db:
        radek = db.execute("SELECT nazev FROM seznamy WHERE id = ?",
                           (id_seznamu,)).fetchone()

        kurzor = db.execute("""
            UPDATE seznamy SET vlastnik_id = ?
            WHERE id = ?
              AND vlastnik_id = ?
              AND EXISTS (SELECT 1 FROM clenove_seznamu
                          WHERE seznam_id = ? AND uzivatel_id = ?)
        """, (id_noveho, id_seznamu, id_vlastnika, id_seznamu, id_noveho))

        if kurzor.rowcount == 0:
            return False, ("Předat seznam může jen jeho vlastník, "
                           "a jen někomu, kdo na něm je.")

        db.execute("DELETE FROM clenove_seznamu "
                   "WHERE seznam_id = ? AND uzivatel_id = ?",
                   (id_seznamu, id_noveho))
        db.execute("INSERT OR IGNORE INTO clenove_seznamu "
                   "(seznam_id, uzivatel_id) VALUES (?, ?)",
                   (id_seznamu, id_vlastnika))

    return True, "Seznam %s je předaný, tobě zůstalo členství." % radek[0]


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

    ⚠️ Počítá se podle LIDÍ, ne podle jmen. Dřív stačila jména, protože
    byla jedinečná; od 5. 9. 2026 jedinečná nejsou a dva různí Petrové by
    se slili do jednoho - dluh by pak seděl někomu jinému. Klíčem je proto
    id, a jméno zbývá jen tam, kde id chybí: u účtu, který mezitím zmizel.
    Jméno si položka pamatuje jako text, takže se částka neztratí.
    """
    with _spojeni() as db:
        radky = db.execute("""
            SELECT cena, koupil, koupil_id, pridal, pridal_id FROM nakup
            WHERE seznam_id = ? AND koupeno = 1
        """, (seznam_id,)).fetchall()

    celkem = 0.0
    bez_ceny = 0
    zaplatil = {}
    dluh = {}
    jmena = {}          # klíč člověka -> jméno, které se má vypsat

    def klic(id_cloveka, jmeno):
        """Rozliší LIDI, ne jména. U smazaného účtu id chybí, zbývá jméno."""
        return ("id", id_cloveka) if id_cloveka is not None else ("jmeno", jmeno)

    for cena, koupil, koupil_id, pridal, pridal_id in radky:
        if cena is None:
            bez_ceny += 1
            continue

        k_koupil = klic(koupil_id, koupil)
        k_pridal = klic(pridal_id, pridal)
        jmena[k_koupil] = koupil
        jmena[k_pridal] = pridal

        celkem += cena
        zaplatil[k_koupil] = zaplatil.get(k_koupil, 0.0) + cena
        if k_koupil != k_pridal:
            dluh[(k_pridal, k_koupil)] = dluh.get((k_pridal, k_koupil), 0.0) + cena

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
            ({"jmeno": jmena[k], "castka": round(c, 2)}
             for k, c in zaplatil.items()),
            key=lambda z: -z["castka"]),
        "dluhy": sorted(
            ({"dluznik": jmena[d], "verite": jmena[v], "castka": c}
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


def zaloz_domacnost(nazev, vlastnik_id):
    """
    Založí domácnost. Vrací (True, id) nebo (False, "co je špatně").

    Když ještě žádná domácnost nemá zařízení z config.py, zdědí je tahle.
    Config popisuje zařízení TÉHLE instalace, takže patří té první
    domácnosti, co vznikne - na produkci té z migrace, na čerstvé databázi
    té, kterou si člověk založí sám. Bez toho pravidla by na nové instalaci
    neviděl Soláry ani majitel serveru.

    Kód pozvánky se losuje a musí být jedinečný, takže těch pár pokusů -
    stejně jako u vytvor_seznam(). Ve stejné smyčce se řeší i druhý důvod,
    proč může zápis neuspět: jiný proces si mezitím vzal zařízení. Právě
    proto se ma_zarizeni počítá ZNOVU při každém pokusu, ne jednou předem.
    """
    nazev = nazev.strip()[:60]
    if not nazev:
        return False, "Domácnost musí mít název."

    with _spojeni() as db:
        for _ in range(5):
            zarizeni_volna = db.execute(
                "SELECT COUNT(*) FROM domacnosti WHERE ma_zarizeni = 1"
            ).fetchone()[0] == 0
            try:
                db.execute(
                    "INSERT INTO domacnosti "
                    "(nazev, vlastnik_id, kod, ma_zarizeni) VALUES (?, ?, ?, ?)",
                    (nazev, vlastnik_id, _novy_kod(), 1 if zarizeni_volna else 0),
                )
                return True, db.execute(
                    "SELECT last_insert_rowid()").fetchone()[0]
            except sqlite3.IntegrityError:
                continue

    return False, "Nepodařilo se domácnost založit, zkus to znovu."


def domacnost_uzivatele(id_uzivatele):
    """
    Vrátí (id, nazev, je_vlastnik) domácnosti se zařízeními - ale jen když
    do ní uživatel patří. Jinak None.

    Sama se neptá - bere výsledek z uzivatel_a_prava(). Ta podmínka je
    bezpečnostní a psát ji na dvou místech by znamenalo, že se jednou opraví
    jen jedno z nich. Tady je proto jen jméno pro tu samou věc.
    """
    zaznam = uzivatel_a_prava(id_uzivatele)
    return None if zaznam is None else zaznam[2]


def domacnosti_uzivatele(id_uzivatele):
    """
    Domácnosti, do kterých uživatel patří. Vlastní první, pak podle názvu.

    Vrací seznam slovníků s klíči id, nazev, je_vlastnik, ma_zarizeni
    a clenu (počet lidí včetně vlastníka).

    Vlastník není v tabulce členů, takže se počet skládá z jedničky za něj
    a počtu přizvaných - a proto je v podmínce i "nebo jsi vlastník".
    """
    with _spojeni() as db:
        radky = db.execute("""
            SELECT d.id, d.nazev, d.vlastnik_id = ? AS je_vlastnik,
                   d.ma_zarizeni,
                   1 + (SELECT COUNT(*) FROM clenove_domacnosti c
                        WHERE c.domacnost_id = d.id) AS clenu
            FROM domacnosti d
            WHERE d.vlastnik_id = ?
               OR d.id IN (SELECT domacnost_id FROM clenove_domacnosti
                           WHERE uzivatel_id = ?)
            ORDER BY je_vlastnik DESC, d.nazev
        """, (id_uzivatele, id_uzivatele, id_uzivatele)).fetchall()

    return [{"id": r[0], "nazev": r[1], "je_vlastnik": bool(r[2]),
             "ma_zarizeni": bool(r[3]), "clenu": r[4]} for r in radky]


def domacnost_pro_uzivatele(id_domacnosti, id_uzivatele):
    """
    Vrátí domácnost, ale jen když do ní uživatel patří. Jinak None.

    Branka na KONKRÉTNÍ domácnost - obdoba seznam_pro_uzivatele() u Nákupu.
    Podmínka je v SQL dotazu, ne v Pythonu za ním: kdyby se řádek načetl
    a teprve pak posuzoval, dřív nebo později vznikne místo, kde se na to
    posouzení zapomene.

    Pozor, tohle je něco jiného než domacnost_uzivatele(): ta odpovídá na
    "kam patří zařízení z config.py a smíš k nim", tahle na "smíš vidět
    tuhle konkrétní domácnost".
    """
    with _spojeni() as db:
        radek = db.execute("""
            SELECT d.id, d.nazev, d.vlastnik_id = ? AS je_vlastnik,
                   d.ma_zarizeni
            FROM domacnosti d
            WHERE d.id = ?
              AND (d.vlastnik_id = ?
                   OR d.id IN (SELECT domacnost_id FROM clenove_domacnosti
                               WHERE uzivatel_id = ?))
        """, (id_uzivatele, id_domacnosti, id_uzivatele, id_uzivatele)).fetchone()

    if radek is None:
        return None
    return {"id": radek[0], "nazev": radek[1],
            "je_vlastnik": bool(radek[2]), "ma_zarizeni": bool(radek[3])}


def registracni_kod():
    """Kód, bez kterého se nikdo nezaregistruje."""
    with _spojeni() as db:
        radek = db.execute(
            "SELECT hodnota FROM nastaveni WHERE klic = 'registracni_kod'"
        ).fetchone()

    return None if radek is None else radek[0]


def novy_registracni_kod():
    """
    Vyrobí nový registrační kód. Starý tím přestane platit.

    Na účty, které už vznikly, to nemá vliv - zneplatní se jen pozvánky,
    které ještě nikdo nepoužil.
    """
    with _spojeni() as db:
        kod = _novy_kod()
        db.execute("UPDATE nastaveni SET hodnota = ? "
                   "WHERE klic = 'registracni_kod'", (kod,))

    return kod


def _pocet_domacnosti(kolik):
    """Napíše počet domácností česky: 'domácnost', '3 domácnosti'."""
    if kolik == 1:
        return "domácnost"
    if kolik < 5:
        return "%d domácnosti" % kolik
    return "%d domácností" % kolik


def predej_domacnost(id_domacnosti, id_vlastnika, id_noveho):
    """
    Předá domácnost jinému členovi. Vrací (povedlo_se, hláška).

    Role se PROHODÍ: nový vlastník přestane být členem, starý se jím stane.
    Nepřijde tím o přístup, jen o právo rozhodovat.

    Předat jde jen ČLENOVI - nikoho jiného vlastník stejně nevidí. Obě
    podmínky (ptá se vlastník, nový je člen) jsou součástí UPDATE, ne
    kontrola před ním: kdyby se ptalo dopředu, mezi ověřením a zápisem by
    vzniklo okno, ve kterém se stav změní.

    Zařízení zůstávají domácnosti, ne člověku - `ma_zarizeni` se nedotýkáme.
    Že tím nový vlastník získá přístup k Solárům, říká potvrzení v šabloně.
    """
    if id_noveho == id_vlastnika:
        return False, "Předat sám sobě nejde."

    with _spojeni() as db:
        radek = db.execute("SELECT nazev FROM domacnosti WHERE id = ?",
                           (id_domacnosti,)).fetchone()

        kurzor = db.execute("""
            UPDATE domacnosti SET vlastnik_id = ?
            WHERE id = ?
              AND vlastnik_id = ?
              AND EXISTS (SELECT 1 FROM clenove_domacnosti
                          WHERE domacnost_id = ? AND uzivatel_id = ?)
        """, (id_noveho, id_domacnosti, id_vlastnika,
              id_domacnosti, id_noveho))

        if kurzor.rowcount == 0:
            return False, ("Předat domácnost může jen její vlastník, "
                           "a jen někomu, kdo do ní patří.")

        db.execute("DELETE FROM clenove_domacnosti "
                   "WHERE domacnost_id = ? AND uzivatel_id = ?",
                   (id_domacnosti, id_noveho))
        db.execute("INSERT OR IGNORE INTO clenove_domacnosti "
                   "(domacnost_id, uzivatel_id) VALUES (?, ?)",
                   (id_domacnosti, id_vlastnika))

    return True, "Domácnost %s je předaná, tobě zůstalo členství." % radek[0]


def smaz_domacnost(id_domacnosti, id_vlastnika):
    """
    Smaže domácnost. Smí to jen vlastník a jen když je prázdná. Vrací
    (povedlo_se, hláška).

    Dvě podmínky, obě z dobrého důvodu:

    ⚠️ **Domácnost se zařízeními smazat nejde.** Zařízení jsou v config.py
    a patří té jedné domácnosti, která je zdědila; kdyby zmizela, nikdo by
    se k Solárům nedostal a musela by se dědit znovu.

    ⚠️ **Domácnost s dalšími členy smazat nejde.** Lidem, kteří na ni jsou,
    by beze slova zmizel přístup k zařízením. Radši to odmítneme a řekneme
    proč - stejné pravidlo jako u nákupního seznamu, který smazat jde taky
    jen prázdný.
    """
    with _spojeni() as db:
        radek = db.execute(
            "SELECT nazev, ma_zarizeni FROM domacnosti "
            "WHERE id = ? AND vlastnik_id = ?",
            (id_domacnosti, id_vlastnika),
        ).fetchone()
        if radek is None:
            return False, "Smazat domácnost může jen její vlastník."

        nazev, ma_zarizeni = radek
        if ma_zarizeni:
            return False, ("Domácnost %s má připojená zařízení, takže smazat "
                           "nejde." % nazev)

        clenu = db.execute(
            "SELECT COUNT(*) FROM clenove_domacnosti WHERE domacnost_id = ?",
            (id_domacnosti,),
        ).fetchone()[0]
        if clenu:
            return False, ("V domácnosti %s je ještě někdo další. Smazat jde "
                           "jen prázdná." % nazev)

        db.execute("DELETE FROM domacnosti WHERE id = ? AND vlastnik_id = ?",
                   (id_domacnosti, id_vlastnika))

    return True, "Domácnost %s je smazaná." % nazev


def clenove_domacnosti(id_domacnosti):
    """
    Kdo do domácnosti patří. Vlastník první, pak přizvaní podle abecedy.

    Vlastník není v tabulce členů (je sloupcem v tabulce domácností), takže
    se obě skupiny musí spojit - od toho je UNION ALL. Stejně jako
    u nákupního seznamu.
    """
    with _spojeni() as db:
        radky = db.execute("""
            SELECT u.id, u.jmeno, 1 AS je_vlastnik
            FROM domacnosti d JOIN uzivatele u ON u.id = d.vlastnik_id
            WHERE d.id = ?
            UNION ALL
            SELECT u.id, u.jmeno, 0
            FROM clenove_domacnosti c JOIN uzivatele u ON u.id = c.uzivatel_id
            WHERE c.domacnost_id = ?
            ORDER BY je_vlastnik DESC, jmeno
        """, (id_domacnosti, id_domacnosti)).fetchall()

    return [{"id": r[0], "jmeno": r[1], "je_vlastnik": bool(r[2])} for r in radky]


def odeber_clena_domacnosti(id_domacnosti, id_vlastnika, id_clena):
    """
    Vyhodí člena z domácnosti. Smí to jen vlastník. Vrací (ok, hláška).

    Podmínka na vlastníka je součástí DELETE, ne kontrola před ním. Když
    nesedí, dotaz nesmaže ani řádek a rowcount == 0 je odpověď.
    """
    # Tahle jediná podmínka je v Pythonu, a je tu kvůli HLÁŠCE, ne kvůli
    # ochraně: vlastník v tabulce členů není, takže by ho DELETE netrefil
    # tak jako tak - jenže by to vypadalo jako "tohle smí jen vlastník",
    # což by u vlastníka byla lež.
    if id_clena == id_vlastnika:
        return False, "Vlastníka odebrat nejde, domácnost musí někomu patřit."

    with _spojeni() as db:
        kurzor = db.execute("""
            DELETE FROM clenove_domacnosti
            WHERE domacnost_id = ?
              AND uzivatel_id = ?
              AND EXISTS (SELECT 1 FROM domacnosti
                          WHERE id = ? AND vlastnik_id = ?)
        """, (id_domacnosti, id_clena, id_domacnosti, id_vlastnika))

        if kurzor.rowcount == 0:
            return False, "Odebrat člena může jen vlastník domácnosti."

    return True, "Člen odebrán."


def novy_kod_domacnosti(id_domacnosti, id_vlastnika):
    """
    Vygeneruje nový kód pozvánky. Starý tím přestane platit.

    Na nikoho, kdo už členem je, to nemá vliv - zneplatní se jen pozvánky,
    které ještě nikdo nepoužil.
    """
    with _spojeni() as db:
        for _ in range(5):
            try:
                kurzor = db.execute(
                    "UPDATE domacnosti SET kod = ? WHERE id = ? AND vlastnik_id = ?",
                    (_novy_kod(), id_domacnosti, id_vlastnika),
                )
                if kurzor.rowcount == 0:
                    return False, "Změnit kód může jen vlastník domácnosti."
                return True, "Nový kód je hotový, starý už neplatí."
            except sqlite3.IntegrityError:
                continue

    return False, "Nepodařilo se vyrobit nový kód, zkus to znovu."


def opust_domacnost(id_domacnosti, id_uzivatele):
    """
    Člen odejde z domácnosti sám. Vrací (ok, hláška).

    Vlastník odejít nemůže: vlastnik_id je NOT NULL, takže by jeho odchodem
    vznikla domácnost bez majitele. Odmítne se to hláškou, ne mlčky - DELETE
    by ho stejně netrefil (v tabulce členů není) a "povedlo se" by byla lež.
    """
    with _spojeni() as db:
        je_vlastnik = db.execute(
            "SELECT 1 FROM domacnosti WHERE id = ? AND vlastnik_id = ?",
            (id_domacnosti, id_uzivatele),
        ).fetchone() is not None
        if je_vlastnik:
            return False, "Vlastník z domácnosti odejít nemůže."

        kurzor = db.execute(
            "DELETE FROM clenove_domacnosti "
            "WHERE domacnost_id = ? AND uzivatel_id = ?",
            (id_domacnosti, id_uzivatele),
        )
        if kurzor.rowcount == 0:
            return False, "V téhle domácnosti nejsi."

    return True, "Do domácnosti už nepatříš."


def kod_domacnosti(id_domacnosti, id_vlastnika):
    """
    Kód pozvánky - ale jen vlastníkovi. Jinak None.

    Podmínka na vlastníka je součástí dotazu, ne kontrola před ním. Kód se
    tak k tomu, kdo ho vidět nemá, vůbec nedostane do šablony - úplně
    stejně jako u nákupního seznamu.
    """
    with _spojeni() as db:
        radek = db.execute(
            "SELECT kod FROM domacnosti WHERE id = ? AND vlastnik_id = ?",
            (id_domacnosti, id_vlastnika),
        ).fetchone()

    return None if radek is None else radek[0]


def pripoj_domacnost_kodem(kod, id_uzivatele):
    """
    Připojí uživatele k domácnosti podle kódu pozvánky.

    Vrací (povedlo_se, hláška).

    Hláška u neznámého kódu záměrně neříká, jestli taková domácnost
    neexistuje, nebo jestli se k ní jen nesmí. Není z čeho vyčíst, které
    kódy platí.
    """
    upraveny = _uprav_kod(kod)
    if upraveny is None:
        return False, "Kód má šest znaků, například K7M-4QP."

    with _spojeni() as db:
        radek = db.execute(
            "SELECT id, nazev, vlastnik_id FROM domacnosti WHERE kod = ?",
            (upraveny,),
        ).fetchone()
        if radek is None:
            return False, "Takový kód nikam nevede."

        id_domacnosti, nazev, vlastnik_id = radek
        if vlastnik_id == id_uzivatele:
            return False, "Tahle domácnost je tvoje vlastní."

        try:
            db.execute(
                "INSERT INTO clenove_domacnosti (domacnost_id, uzivatel_id) "
                "VALUES (?, ?)",
                (id_domacnosti, id_uzivatele),
            )
        except sqlite3.IntegrityError:
            # Dvojice (domácnost, uživatel) je primární klíč, takže druhé
            # připojení databáze sama odmítne.
            return False, "V domácnosti %s už jsi." % nazev

    return True, "Připojeno k domácnosti %s." % nazev


def _uprav_email(email):
    """
    Srovná e-mail do jedné podoby a vrátí ho, nebo None když to e-mail není.

    Malá písmena a bez mezer po krajích: přihlašovat se bude podle něj,
    takže "Petr@Example.CZ" a "petr@example.cz" musí být tentýž člověk.
    Telefon navíc rád přidá mezeru a velké první písmeno.

    Kontrola je schválně hrubá - jen zavináč, něco před ním a něco za ním
    a žádné mezery uvnitř. Skutečně ověřit e-mailovou adresu jde jediným
    způsobem: poslat na ni zprávu. To zatím neděláme, takže se aspoň
    nebudeme tvářit, že to umíme.
    """
    email = (email or "").strip().lower()
    if email.count("@") != 1:
        return None

    pred, za = email.split("@")
    if not pred or not za or any(z.isspace() for z in email):
        return None

    return email


def nastav_email(id_uzivatele, email):
    """
    Nastaví uživateli e-mail. Vrací (povedlo_se, hláška).

    Adresu smí mít každý účet jen jednu a žádní dva účty stejnou - hlídá
    to unikátní index, ne kontrola před zápisem. Kdyby se to ptalo dopředu,
    dva souběžné zápisy by mohly projít oba.
    """
    upraveny = _uprav_email(email)
    if upraveny is None:
        return False, "Tohle nevypadá jako e-mailová adresa."

    with _spojeni() as db:
        try:
            db.execute("UPDATE uzivatele SET email = ? WHERE id = ?",
                       (upraveny, id_uzivatele))
        except sqlite3.IntegrityError:
            return False, "Tenhle e-mail už u nás někdo používá."

    return True, "E-mail uložen."


def vytvor_uzivatele(jmeno, email, heslo):
    """
    Založí nového uživatele. Heslo uloží jako hash, nikdy v původní podobě.

    Vrací True když se povedlo, False když e-mail už někdo používá nebo
    to e-mail vůbec není.

    E-mail je od 5. 9. 2026 POVINNÝ: přihlašuje se podle něj, takže účet
    bez něj by se neměl jak dostat dovnitř. Jméno naopak jedinečné být
    nemusí - je to jen to, co o člověku vidí ostatní.
    """
    email = _uprav_email(email)
    if email is None:
        return False

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
            # ÚPLNĚ PRVNÍ účet dostane správcovství, ať se zadá cokoliv.
            # Bez toho by na čerstvé databázi nikdo neměl Správu a nešlo by
            # ji nikomu přidělit - zamčeno zvenku hned při prvním spuštění.
            prvni = db.execute("SELECT COUNT(*) FROM uzivatele").fetchone()[0] == 0

            kurzor = db.execute(
                "INSERT INTO uzivatele (jmeno, email, heslo_hash, spravce) "
                "VALUES (?, ?, ?, ?)",
                (jmeno, email, hash_hesla, 1 if prvni else 0),
            )

        return True
    except sqlite3.IntegrityError:
        # Sem se dostaneme, když e-mail už někdo používá. Jméno se od
        # 5. 9. 2026 nehlídá - přihlašovacím údajem je e-mail, takže není
        # důvod někomu brát jméno jen proto, že ho má i někdo jiný.
        return False


# Strop na přihlašovací pokusy: (kolik chyb, kolik sekund se pak čeká).
# Řadí se od nejpřísnějšího, hledá se první práh, na který se dosáhne.
STROPY_PRIHLASENI = ((15, 900), (10, 300), (5, 60))


def zbyva_blokace(ip):
    """
    Kolik sekund musí adresa ještě počkat, než smí zkusit heslo znovu.
    Vrací 0, když čekat nemusí.
    """
    with _spojeni() as db:
        radek = db.execute("""
            SELECT CAST(strftime('%s', blokovano_do)
                      - strftime('%s', datetime('now', 'localtime')) AS INTEGER)
            FROM pokusy_prihlaseni
            WHERE ip = ? AND blokovano_do IS NOT NULL
        """, (ip,)).fetchone()

    if radek is None or radek[0] is None or radek[0] <= 0:
        return 0
    return radek[0]


def zaznamenej_chybny_pokus(ip):
    """
    Připočte adrese jeden neúspěšný pokus a podle počtu jí nastaví čekání.

    Blokace se přepisuje při KAŽDÉM dalším chybném pokusu nad prahem, ne
    jen přesně na pěti a deseti - jinak by byly pokusy šest až devět zdarma.
    """
    with _spojeni() as db:
        # Úklid, ať tabulka neroste donekonečna. Den je dost: nejdelší
        # čekání je čtvrt hodiny, o starší adresy se nezajímáme.
        db.execute(
            "DELETE FROM pokusy_prihlaseni "
            "WHERE posledni < datetime('now', 'localtime', '-1 day')"
        )

        # ON CONFLICT = "když už řádek s tímhle klíčem je, uprav ho".
        # Jedním příkazem tak zvládneme založení i přičtení.
        db.execute("""
            INSERT INTO pokusy_prihlaseni (ip, chyb, posledni)
            VALUES (?, 1, datetime('now', 'localtime'))
            ON CONFLICT(ip) DO UPDATE SET
                chyb     = chyb + 1,
                posledni = datetime('now', 'localtime')
        """, (ip,))

        chyb = db.execute(
            "SELECT chyb FROM pokusy_prihlaseni WHERE ip = ?", (ip,)
        ).fetchone()[0]

        for prah, sekundy in STROPY_PRIHLASENI:
            if chyb >= prah:
                db.execute(
                    "UPDATE pokusy_prihlaseni SET blokovano_do = "
                    "datetime('now', 'localtime', ?) WHERE ip = ?",
                    ("+%d seconds" % sekundy, ip),
                )
                break


def zapomen_pokusy(ip):
    """
    Zapomene neúspěšné pokusy adresy. Volá se po úspěšném přihlášení.

    Díky tomu se doma nezaseknete: rodina má jednu veřejnou adresu, takže
    když někdo párkrát překlepne heslo a pak se přihlásí, počítadlo je pryč.
    """
    with _spojeni() as db:
        db.execute("DELETE FROM pokusy_prihlaseni WHERE ip = ?", (ip,))


def over_uzivatele(email, heslo):
    """
    Ověří přihlašovací údaje.

    Vrací slovník {"id": ..., "jmeno": ...} když sedí, jinak None.

    Všimni si, že heslo NEHLEDÁME v databázi. Vytáhneme uloženy hash
    a necháme check_password_hash spočítat, jestli k němu zadané heslo
    pasuje. Databáze původní heslo nezná a znát nemá.

    Hledá se podle E-MAILU, ne podle jména - od 5. 9. 2026. Adresa se
    přitom srovnává stejnou funkcí, jakou se ukládala, takže na velikosti
    písmen ani mezerách od telefonu nezáleží.
    """
    email = _uprav_email(email)
    if email is None:
        return None

    with _spojeni() as db:
        radek = db.execute(
            "SELECT id, jmeno, heslo_hash FROM uzivatele WHERE email = ?",
            (email,),
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

    Čte se při KAŽDÉM požadavku, proto jedním dotazem místo tří.
    LEFT JOIN vrátí uživatele i tehdy, když nemá žádná práva ani domácnost -
    pak přijde jeden řádek s prázdnými sloupci, který níž přeskočíme.

    Třetí vrácená věc je domácnost se zařízeními, ale jen když do ní
    uživatel patří: (id, nazev, je_vlastnik), jinak None. Podmínka je
    schválně tady v SQL, ne v Pythonu za dotazem - je to JEDINÉ místo,
    kde je napsaná, takže se nedá zapomenout na druhém.

    ⚠️ Vlastník NENÍ v tabulce clenove_domacnosti, je sloupcem. Podmínka
    proto musí pokrýt obojí, jinak by se vlastník ke svým vlastním
    zařízením nedostal.

    ⚠️ ma_zarizeni = 1 není ozdoba. Bez něj by stačilo založit si libovolnou
    domácnost a člověk by se dostal k cizím zařízením - ta jsou v config.py,
    tedy společná pro celý server.

    Řádky se JOINem násobí počtem domácností, ale ta je nejvýš jedna
    (hlídá to částečný index), takže jedničkou.
    """
    with _spojeni() as db:
        radky = db.execute("""
            SELECT u.jmeno, u.spravce, d.id, d.nazev, d.vlastnik_id = u.id
            FROM uzivatele u
            LEFT JOIN domacnosti d
                   ON d.ma_zarizeni = 1
                  AND (d.vlastnik_id = u.id
                       OR d.id IN (SELECT domacnost_id FROM clenove_domacnosti
                                   WHERE uzivatel_id = u.id))
            WHERE u.id = ?
        """, (id_uzivatele,)).fetchall()

    if not radky:
        return None

    prvni = radky[0]
    domacnost = None if prvni[2] is None else (prvni[2], prvni[3], bool(prvni[4]))

    return prvni[0], bool(prvni[1]), domacnost


def _pocet_seznamu(kolik):
    """Napíše počet seznamů česky: 'jeden seznam', '3 seznamy', '7 seznamů'."""
    if kolik == 1:
        return "jeden nákupní seznam"
    if kolik < 5:
        return "%d nákupní seznamy" % kolik
    return "%d nákupních seznamů" % kolik


def _je_spravce(db, id_uzivatele):
    """Je to správce? (uvnitř už otevřeného spojení)"""
    radek = db.execute("SELECT spravce FROM uzivatele WHERE id = ?",
                       (id_uzivatele,)).fetchone()
    return radek is not None and bool(radek[0])


def nastav_spravce(id_uzivatele, je_spravce):
    """
    Zapne nebo vypne správcovství. Vrací (povedlo_se, hláška).

    ⚠️ POJISTKA: poslednímu správci se vzít nedá. Kdyby se dalo, do Správy
    by se už nedostal nikdo a nešlo by to vrátit odjinud než zápisem do
    databáze.
    """
    with _spojeni() as db:
        if not je_spravce and _je_spravce(db, id_uzivatele):
            pocet = db.execute(
                "SELECT COUNT(*) FROM uzivatele WHERE spravce = 1"
            ).fetchone()[0]
            if pocet <= 1:
                return False, "Tohle je poslední správce, o Správu přijít nesmí."

        kurzor = db.execute("UPDATE uzivatele SET spravce = ? WHERE id = ?",
                            (1 if je_spravce else 0, id_uzivatele))
        if kurzor.rowcount == 0:
            return False, "Účet neexistuje."

    return True, "Správcovství je nastavené."


def smaz_vlastni_ucet(id_uzivatele, heslo):
    """
    Zrušení vlastního účtu. Vyžaduje heslo. Vrací (povedlo_se, hláška).

    Heslo se chce ze stejného důvodu jako u změny hesla: účet mizí
    nenávratně, takže odemčený mobil na stole stačit nesmí.

    Pojistky (poslední správce, vlastník seznamu nebo domácnosti) dělá
    smaz_uzivatele() - proto se volá ona a ne holý DELETE. Pojistka
    "sám sebe smazat nemůžeš" ze Správy tu naopak neplatí: tady je to
    celý smysl.
    """
    with _spojeni() as db:
        radek = db.execute("SELECT heslo_hash FROM uzivatele WHERE id = ?",
                           (id_uzivatele,)).fetchone()

    if radek is None:
        return False, "Účet neexistuje."
    if not check_password_hash(radek[0], heslo):
        return False, "Heslo nesouhlasí."

    return smaz_uzivatele(id_uzivatele)


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
                "SELECT COUNT(*) FROM uzivatele WHERE spravce = 1"
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

        # POJISTKA: účet, který vlastní domácnost, smazat nejde.
        #
        # Stejný důvod jako u seznamů výš - jenže tahle pojistka tu 5. 9.
        # 2026 chyběla a mazání účtu kvůli tomu spadlo na produkci: DELETE
        # narazil na cizí klíč domacnosti.vlastnik_id, který nemá ON DELETE,
        # a route vrátila chybu serveru místo vysvětlení. Schéma domácností
        # je opsané ze seznamů, ale tahle pojistka se s ním neopsala.
        vlastni_dom = db.execute(
            "SELECT COUNT(*) FROM domacnosti WHERE vlastnik_id = ?",
            (id_uzivatele,),
        ).fetchone()[0]
        if vlastni_dom:
            return False, ("Tenhle účet vlastní %s. Nejdřív ji smaž nebo "
                           "předej někomu jinému." % _pocet_domacnosti(vlastni_dom))

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
            SELECT u.id, u.jmeno, u.vytvoren, u.spravce,
                   u.posledni_prihlaseni, u.email
            FROM uzivatele u
            ORDER BY u.id
        """).fetchall()

    # Dotaz vrací jeden řádek na KAŽDÉ právo, takže se uživatel opakuje.
    # Poskládáme to zpátky do jednoho záznamu na uživatele.
    podle_id = {}
    for id_u, jmeno, vytvoren, spravce, posledni, email in radky:
        podle_id[id_u] = {"id": id_u, "jmeno": jmeno, "vytvoren": vytvoren,
                          "posledni": posledni, "email": email,
                          "spravce": bool(spravce)}

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
