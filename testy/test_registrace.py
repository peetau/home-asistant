# -*- coding: utf-8 -*-
"""
Registrace a přihlašování e-mailem (kus B).

Nasazuje se ve dvou krocích, protože přepnout přihlašování na e-mail dřív,
než účty adresu mají, by zamklo ven úplně všechny včetně správce. Tenhle
soubor roste s nimi; zatím pokrývá krok první, tedy pole na e-mail.
"""

from spolecne import database, klient, spust

HESLO = "tajne-heslo"


def email_pro(jmeno):
    """Předvídatelná adresa, ať se testy nemusí starat o její tvar."""
    return "%s@test.cz" % jmeno.lower()


def zaloz_ucet(jmeno):
    """Založí účet a vrátí jeho id. První účet dostane právo na Správu."""
    database.vytvor_uzivatele(jmeno, email_pro(jmeno), HESLO)
    with database._spojeni() as db:
        return db.execute(
            "SELECT id FROM uzivatele WHERE email = ?", (email_pro(jmeno),)
        ).fetchone()[0]


def email_uctu(id_uzivatele):
    with database._spojeni() as db:
        return db.execute(
            "SELECT email FROM uzivatele WHERE id = ?", (id_uzivatele,)
        ).fetchone()[0]


def prihlaseny(jmeno):
    prohlizec = klient()
    prohlizec.post("/prihlaseni",
                   data={"email": email_pro(jmeno), "heslo": HESLO})
    return prohlizec


# --- ukládání adresy ---------------------------------------------------

def test_email_se_ulozi():
    id_petr = zaloz_ucet("Petr")

    ok, hlaska = database.nastav_email(id_petr, "petr@example.cz")

    assert ok, hlaska
    assert email_uctu(id_petr) == "petr@example.cz"


def test_email_se_normalizuje():
    """Přihlašovat se bude podle e-mailu, takže se musí ukládat v jedné
    podobě - jinak by se ten samý člověk podruhé nepřihlásil kvůli velkému
    písmenu nebo mezeře, kterou mu přidal telefon."""
    id_petr = zaloz_ucet("Petr")

    database.nastav_email(id_petr, "  Petr@Example.CZ  ")

    assert email_uctu(id_petr) == "petr@example.cz"


def test_dva_ucty_nemuzou_mit_stejny_email():
    id_petr = zaloz_ucet("Petr")
    id_hana = zaloz_ucet("Hana")
    database.nastav_email(id_petr, "spolecny@example.cz")

    ok, hlaska = database.nastav_email(id_hana, "spolecny@example.cz")

    assert not ok, "dva účty dostaly stejný e-mail"
    assert email_uctu(id_hana) == email_pro("Hana"), "adresa se neměla změnit"
    assert email_uctu(id_petr) == "spolecny@example.cz", \
        "neúspěšný zápis sebral adresu tomu, kdo ji měl"


def test_stejny_email_jinou_velikosti_pismen_taky_neprojde():
    """Normalizace není kosmetika: bez ní by dvě různá psaní téhle adresy
    prošla jako dvě různé a přihlášení by pak nevědělo, koho pustit."""
    id_petr = zaloz_ucet("Petr")
    id_hana = zaloz_ucet("Hana")
    database.nastav_email(id_petr, "petr@example.cz")

    ok, hlaska = database.nastav_email(id_hana, "PETR@EXAMPLE.CZ")

    assert not ok, "stejná adresa jinou velikostí písmen prošla podruhé"


def test_email_bez_zavinace_neprojde():
    id_petr = zaloz_ucet("Petr")

    ok, hlaska = database.nastav_email(id_petr, "tohle neni adresa")

    assert not ok
    assert email_uctu(id_petr) == email_pro("Petr"), "adresa se neměla změnit"


def test_prazdny_email_neprojde():
    id_petr = zaloz_ucet("Petr")

    ok, hlaska = database.nastav_email(id_petr, "   ")

    assert not ok
    assert email_uctu(id_petr) == email_pro("Petr"), "adresa se neměla změnit"


def test_prepsat_svuj_email_jde():
    """Překlep se opravuje přepsáním, ne mazáním."""
    id_petr = zaloz_ucet("Petr")
    database.nastav_email(id_petr, "peter@example.cz")

    ok, hlaska = database.nastav_email(id_petr, "petr@example.cz")

    assert ok, hlaska
    assert email_uctu(id_petr) == "petr@example.cz"


# --- Správa ------------------------------------------------------------

def test_sprava_ukaze_email_uctu():
    """Petrovi adresu neměníme - přihlašuje se podle ní a odhlásil by se."""
    zaloz_ucet("Petr")
    zaloz_ucet("Hana")

    html = prihlaseny("Petr").get("/sprava").get_data(as_text=True)
    assert email_pro("Hana") in html, "Správa neukazuje e-mail účtu"


def test_spravce_ulozi_email_formularem():
    id_petr = zaloz_ucet("Petr")
    id_hana = zaloz_ucet("Hana")

    prihlaseny("Petr").post("/sprava/%d/email" % id_hana,
                            data={"email": "hana@example.cz"})

    assert email_uctu(id_hana) == "hana@example.cz"


def test_kdo_neni_spravce_email_nemeni():
    """Druhý založený účet nedostane žádná práva, takže do Správy nesmí."""
    zaloz_ucet("Petr")
    id_hana = zaloz_ucet("Hana")

    odpoved = prihlaseny("Hana").post("/sprava/%d/email" % id_hana,
                                      data={"email": "hana@example.cz"})

    assert odpoved.status_code == 302, "nesprávce se dostal do Správy"
    assert email_uctu(id_hana) == email_pro("Hana"), "adresa se neměla změnit"


# --- přihlašování e-mailem --------------------------------------------

def test_prihlaseni_emailem_projde():
    zaloz_ucet("Petr")

    odpoved = klient().post("/prihlaseni",
                            data={"email": "petr@test.cz", "heslo": HESLO})

    assert odpoved.status_code == 302, "správný e-mail a heslo nepustily dál"


def test_prihlaseni_nezalezi_na_velikosti_pismen():
    """Telefon rád velké první písmeno. E-mail se ukládá i hledá malými,
    takže se tím člověk nesmí zamknout ven."""
    zaloz_ucet("Petr")

    odpoved = klient().post("/prihlaseni",
                            data={"email": "  Petr@Test.CZ ", "heslo": HESLO})

    assert odpoved.status_code == 302, "e-mail jinou velikostí písmen neprošel"


def test_prihlaseni_jmenem_uz_neprojde():
    zaloz_ucet("Petr")

    odpoved = klient().post("/prihlaseni",
                            data={"email": "Petr", "heslo": HESLO})

    assert odpoved.status_code == 200, "jméno pořád funguje jako přihlašovací údaj"


# --- registrace --------------------------------------------------------

def registruj(prohlizec, jmeno, email, heslo, kod):
    return prohlizec.post("/registrace", data={
        "jmeno": jmeno, "email": email, "heslo": heslo, "kod": kod})


def test_registrace_se_spravnym_kodem_zalozi_ucet_a_prihlasi():
    zaloz_ucet("Petr")
    kod = database.registracni_kod()

    odpoved = registruj(klient(), "Nova", "nova@test.cz", "dost-dlouhe", kod)

    assert odpoved.status_code == 302, "registrace nepustila dál"
    with database._spojeni() as db:
        assert db.execute("SELECT COUNT(*) FROM uzivatele WHERE email = ?",
                          ("nova@test.cz",)).fetchone()[0] == 1


def test_registrace_se_spatnym_kodem_neprojde():
    zaloz_ucet("Petr")

    registruj(klient(), "Cizi", "cizi@test.cz", "dost-dlouhe", "XXX-XXX")

    with database._spojeni() as db:
        assert db.execute("SELECT COUNT(*) FROM uzivatele WHERE email = ?",
                          ("cizi@test.cz",)).fetchone()[0] == 0, \
            "špatný kód pustil dovnitř"


def test_registrace_obsazeny_email_neprojde():
    zaloz_ucet("Petr")
    kod = database.registracni_kod()

    registruj(klient(), "Jiny Petr", "petr@test.cz", "dost-dlouhe", kod)

    with database._spojeni() as db:
        assert db.execute("SELECT COUNT(*) FROM uzivatele WHERE email = ?",
                          ("petr@test.cz",)).fetchone()[0] == 1, \
            "e-mail se použil podruhé"


def test_registrace_kratke_heslo_neprojde():
    """Minimum šesti znaků platilo jen při změně hesla, při zakládání ne."""
    zaloz_ucet("Petr")
    kod = database.registracni_kod()

    registruj(klient(), "Nova", "nova@test.cz", "abc", kod)

    with database._spojeni() as db:
        assert db.execute("SELECT COUNT(*) FROM uzivatele WHERE email = ?",
                          ("nova@test.cz",)).fetchone()[0] == 0
def test_strop_plati_i_na_registraci():
    """Formulář musí u obsazené adresy říct, že je obsazená - jinak člověk
    neví, proč to neprošlo. Tím se ale dá zkoušením adres zjišťovat, kdo
    u nás účet má, takže platí stejný strop jako na přihlášení."""
    zaloz_ucet("Petr")
    prohlizec = klient()

    for _ in range(6):
        prohlizec.post("/registrace",
                       data={"jmeno": "X", "email": "x@test.cz",
                             "heslo": "dost-dlouhe", "kod": "XXX-XXX"},
                       environ_base={"REMOTE_ADDR": "203.0.113.9"})

    odpoved = prohlizec.post(
        "/registrace",
        data={"jmeno": "Nova", "email": "nova@test.cz",
              "heslo": "dost-dlouhe", "kod": database.registracni_kod()},
        environ_base={"REMOTE_ADDR": "203.0.113.9"})

    assert "mnoho pokus" in odpoved.get_data(as_text=True), \
        "registrace nemá strop, dá se přes ni zkoušet adresy donekonečna"


def test_spravce_zmeni_registracni_kod():
    zaloz_ucet("Petr")
    stary = database.registracni_kod()

    prihlaseny("Petr").post("/sprava/novy-registracni-kod")

    assert database.registracni_kod() != stary, "kód se nezměnil"


def test_sprava_ukaze_registracni_kod():
    zaloz_ucet("Petr")

    html = prihlaseny("Petr").get("/sprava").get_data(as_text=True)
    assert database.registracni_kod() in html, "Správa neukazuje registrační kód"


# --- jméno přestalo být jedinečné --------------------------------------

def test_dva_ucty_mohou_mit_stejne_jmeno():
    database.vytvor_uzivatele("Petr", "petr1@test.cz", HESLO)

    ok = database.vytvor_uzivatele("Petr", "petr2@test.cz", HESLO)

    assert ok, "druhý Petr se nezaložil"
    with database._spojeni() as db:
        assert db.execute("SELECT COUNT(*) FROM uzivatele WHERE jmeno = ?",
                          ("Petr",)).fetchone()[0] == 2


def test_vyuctovani_neslije_dva_stejnojmenne():
    """Vyúčtování se dosud počítalo podle JMEN, protože byla jedinečná.
    Od chvíle, kdy jedinečná nejsou, by se dva různí Petrové slili do
    jednoho a dluhy by seděly někomu jinému."""
    id_a = zaloz_ucet("Petr")
    database.vytvor_uzivatele("Petr", "petr2@test.cz", HESLO)
    with database._spojeni() as db:
        id_b = db.execute("SELECT id FROM uzivatele WHERE email = ?",
                          ("petr2@test.cz",)).fetchone()[0]

    ok, id_seznamu = database.vytvor_seznam("Doma", id_a)
    with database._spojeni() as db:
        db.execute("INSERT INTO clenove_seznamu (seznam_id, uzivatel_id) "
                   "VALUES (?, ?)", (id_seznamu, id_b))

    database.pridej_polozku(id_seznamu, "Mleko", "Petr", id_a)
    with database._spojeni() as db:
        id_polozky = db.execute("SELECT id FROM nakup").fetchone()[0]
    database.prepni_koupeno(id_polozky, "Petr", id_b)
    database.nastav_cenu(id_polozky, id_b, "50")

    v = database.vyuctovani(id_seznamu)

    # Podle JMÉN se ti dva rozlišit nedají - oba se jmenují Petr, a to je
    # cena za to, že jména už jedinečná nejsou. Pozná se to jinak: když se
    # počítalo podle jmen, koupil == pridal a žádný dluh nevznikl vůbec.
    assert v["dluhy"], "dva různí Petrové se slili a dluh zmizel"
    assert v["dluhy"][0]["castka"] == 50.0, "dluh nesedí: %r" % v["dluhy"]


if __name__ == "__main__":
    import sys
    kolik, spadlo = spust(globals(), "Registrace")
    sys.exit(1 if spadlo else 0)
