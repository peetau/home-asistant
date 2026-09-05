# -*- coding: utf-8 -*-
"""
Registrace a přihlašování e-mailem (kus B).

Nasazuje se ve dvou krocích, protože přepnout přihlašování na e-mail dřív,
než účty adresu mají, by zamklo ven úplně všechny včetně správce. Tenhle
soubor roste s nimi; zatím pokrývá krok první, tedy pole na e-mail.
"""

from spolecne import database, klient, spust

HESLO = "tajne-heslo"


def zaloz_ucet(jmeno):
    """Založí účet a vrátí jeho id. První účet dostane právo na Správu."""
    database.vytvor_uzivatele(jmeno, HESLO)
    with database._spojeni() as db:
        return db.execute(
            "SELECT id FROM uzivatele WHERE jmeno = ?", (jmeno,)
        ).fetchone()[0]


def email_uctu(id_uzivatele):
    with database._spojeni() as db:
        return db.execute(
            "SELECT email FROM uzivatele WHERE id = ?", (id_uzivatele,)
        ).fetchone()[0]


def prihlaseny(jmeno):
    prohlizec = klient()
    prohlizec.post("/prihlaseni", data={"jmeno": jmeno, "heslo": HESLO})
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
    assert email_uctu(id_hana) is None
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
    assert email_uctu(id_petr) is None


def test_prazdny_email_neprojde():
    id_petr = zaloz_ucet("Petr")

    ok, hlaska = database.nastav_email(id_petr, "   ")

    assert not ok
    assert email_uctu(id_petr) is None


def test_prepsat_svuj_email_jde():
    """Překlep se opravuje přepsáním, ne mazáním."""
    id_petr = zaloz_ucet("Petr")
    database.nastav_email(id_petr, "peter@example.cz")

    ok, hlaska = database.nastav_email(id_petr, "petr@example.cz")

    assert ok, hlaska
    assert email_uctu(id_petr) == "petr@example.cz"


# --- Správa ------------------------------------------------------------

def test_sprava_ukaze_email_uctu():
    id_petr = zaloz_ucet("Petr")
    database.nastav_email(id_petr, "petr@example.cz")

    html = prihlaseny("Petr").get("/sprava").get_data(as_text=True)
    assert "petr@example.cz" in html, "Správa neukazuje e-mail účtu"


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
    assert email_uctu(id_hana) is None, "nesprávce si nastavil e-mail"


if __name__ == "__main__":
    import sys
    kolik, spadlo = spust(globals(), "Registrace")
    sys.exit(1 if spadlo else 0)
