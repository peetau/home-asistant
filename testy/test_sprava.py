# -*- coding: utf-8 -*-
"""
Správa po zavedení registrace: správcovství jako sloupec a zrušení účtu.

Z práv zbylo jediné, `sprava`, takže celá tabulka `opravneni` i konstanty
kolem ní existovaly kvůli jedné nule nebo jedničce. Nahradil je sloupec
`uzivatele.spravce`. K tomu přibylo zrušení vlastního účtu v Profilu —
kdo si účet založil sám, má ho umět i zrušit.
"""

import sqlite3

from spolecne import database, klient, spust

HESLO = "tajne-heslo"


def email_pro(jmeno):
    return "%s@test.cz" % jmeno.lower()


def zaloz_ucet(jmeno):
    """Založí účet a vrátí jeho id. První účet je automaticky správce."""
    database.vytvor_uzivatele(jmeno, email_pro(jmeno), HESLO)
    with database._spojeni() as db:
        return db.execute("SELECT id FROM uzivatele WHERE email = ?",
                          (email_pro(jmeno),)).fetchone()[0]


def prihlaseny(jmeno):
    prohlizec = klient()
    prohlizec.post("/prihlaseni",
                   data={"email": email_pro(jmeno), "heslo": HESLO})
    return prohlizec


def je_spravce(id_uzivatele):
    with database._spojeni() as db:
        return bool(db.execute("SELECT spravce FROM uzivatele WHERE id = ?",
                               (id_uzivatele,)).fetchone()[0])


def ucet_existuje(id_uzivatele):
    with database._spojeni() as db:
        return db.execute("SELECT COUNT(*) FROM uzivatele WHERE id = ?",
                          (id_uzivatele,)).fetchone()[0] == 1


# --- správcovství ------------------------------------------------------

def test_prvni_ucet_je_spravce():
    """Jinak by se do Správy nedostal nikdo a nešlo by ji nikomu přidělit."""
    assert je_spravce(zaloz_ucet("Petr"))


def test_dalsi_ucty_spravci_nejsou():
    zaloz_ucet("Petr")
    assert not je_spravce(zaloz_ucet("Hana"))


def test_spravce_povysi_jineho():
    zaloz_ucet("Petr")
    id_hana = zaloz_ucet("Hana")

    prihlaseny("Petr").post("/sprava/%d/spravce" % id_hana,
                            data={"spravce": "1"})

    assert je_spravce(id_hana)


def test_kdo_neni_spravce_do_spravy_neprojde():
    zaloz_ucet("Petr")
    id_hana = zaloz_ucet("Hana")

    odpoved = prihlaseny("Hana").post("/sprava/%d/spravce" % id_hana,
                                      data={"spravce": "1"})

    assert odpoved.status_code == 302, "nesprávce se dostal do Správy"
    assert not je_spravce(id_hana), "nesprávce si udělil správcovství"


def test_posledni_spravce_o_spravcovstvi_neprijde():
    """Kdyby přišel, do Správy by se už nedostal nikdo a nešlo by to vrátit."""
    id_petr = zaloz_ucet("Petr")

    ok, hlaska = database.nastav_spravce(id_petr, False)

    assert not ok, "poslední správce přišel o správcovství"
    assert je_spravce(id_petr)


def test_spravcovstvi_jde_odebrat_kdyz_jsou_dva():
    id_petr = zaloz_ucet("Petr")
    id_hana = zaloz_ucet("Hana")
    database.nastav_spravce(id_hana, True)

    ok, hlaska = database.nastav_spravce(id_petr, False)

    assert ok, hlaska
    assert not je_spravce(id_petr)


# --- migrace ze staré tabulky opravneni --------------------------------

def priprav_starou_databazi():
    """
    Postaví stav, jaký byl před 5. 9. 2026: správcovství v tabulce
    `opravneni`, sloupec `spravce` ještě nic neříká.
    """
    id_petr = zaloz_ucet("Petr")
    id_hana = zaloz_ucet("Hana")

    with database._spojeni() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS opravneni (
                uzivatel_id INTEGER NOT NULL,
                tab         TEXT    NOT NULL,
                PRIMARY KEY (uzivatel_id, tab),
                FOREIGN KEY (uzivatel_id) REFERENCES uzivatele(id)
                    ON DELETE CASCADE
            )
        """)
        db.execute("INSERT INTO opravneni (uzivatel_id, tab) VALUES (?, 'sprava')",
                   (id_hana,))
        db.execute("UPDATE uzivatele SET spravce = 0")

    return id_petr, id_hana


def test_migrace_prenese_spravcovstvi():
    id_petr, id_hana = priprav_starou_databazi()

    database.init_db()

    assert je_spravce(id_hana), "kdo měl právo sprava, měl se stát správcem"
    assert not je_spravce(id_petr), "správcovství dostal i ten, kdo ho neměl"


def test_migrace_zahodi_tabulku_opravneni():
    priprav_starou_databazi()

    database.init_db()

    with database._spojeni() as db:
        tabulky = [r[0] for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")]
    assert "opravneni" not in tabulky, "tabulka práv zůstala"


def test_migrace_se_smi_pustit_opakovane():
    priprav_starou_databazi()

    database.init_db()
    database.init_db()

    with database._spojeni() as db:
        assert db.execute("SELECT COUNT(*) FROM uzivatele").fetchone()[0] == 2


# --- zrušení vlastního účtu -------------------------------------------

def test_vlastni_ucet_jde_zrusit_se_spravnym_heslem():
    zaloz_ucet("Petr")
    id_hana = zaloz_ucet("Hana")

    prihlaseny("Hana").post("/profil/zrusit", data={"heslo": HESLO})

    assert not ucet_existuje(id_hana), "účet se nezrušil"


def test_se_spatnym_heslem_ucet_zustane():
    """Účet mizí nenávratně, takže odemčený mobil na stole stačit nesmí."""
    zaloz_ucet("Petr")
    id_hana = zaloz_ucet("Hana")

    prihlaseny("Hana").post("/profil/zrusit", data={"heslo": "spatne"})

    assert ucet_existuje(id_hana), "účet zmizel i se špatným heslem"


def test_posledni_spravce_se_sam_nezrusi():
    id_petr = zaloz_ucet("Petr")

    prihlaseny("Petr").post("/profil/zrusit", data={"heslo": HESLO})

    assert ucet_existuje(id_petr), "poslední správce se zrušil"


def test_kdo_vlastni_seznam_se_nezrusi():
    zaloz_ucet("Petr")
    id_hana = zaloz_ucet("Hana")
    database.vytvor_seznam("Doma", id_hana)

    prihlaseny("Hana").post("/profil/zrusit", data={"heslo": HESLO})

    assert ucet_existuje(id_hana), "zrušil se účet, který vlastní seznam"


def test_po_zruseni_se_uz_neprihlasi():
    zaloz_ucet("Petr")
    zaloz_ucet("Hana")
    prihlaseny("Hana").post("/profil/zrusit", data={"heslo": HESLO})

    odpoved = klient().post("/prihlaseni",
                            data={"email": email_pro("Hana"), "heslo": HESLO})

    assert odpoved.status_code == 200, "zrušený účet se pořád přihlásí"


def test_polozky_po_zrusenem_uctu_zustanou():
    """Jméno u položky je text, takže vyúčtování dál sedí. Zmizí jen odkaz."""
    id_petr = zaloz_ucet("Petr")
    id_hana = zaloz_ucet("Hana")
    ok, id_seznamu = database.vytvor_seznam("Doma", id_petr)
    with database._spojeni() as db:
        db.execute("INSERT INTO clenove_seznamu (seznam_id, uzivatel_id) "
                   "VALUES (?, ?)", (id_seznamu, id_hana))

    database.pridej_polozku(id_seznamu, "Mleko", "Petr", id_petr)
    with database._spojeni() as db:
        id_polozky = db.execute("SELECT id FROM nakup").fetchone()[0]
    database.prepni_koupeno(id_polozky, "Hana", id_hana)
    database.nastav_cenu(id_polozky, id_hana, "42")

    prihlaseny("Hana").post("/profil/zrusit", data={"heslo": HESLO})

    v = database.vyuctovani(id_seznamu)
    assert v["celkem"] == 42.0, "částka po zrušeném účtu zmizela"
    assert v["zaplatili"][0]["jmeno"] == "Hana", "u položky zmizelo jméno"


# --- co je na Správě vidět ---------------------------------------------

def test_sprava_uz_nenabizi_novy_ucet():
    zaloz_ucet("Petr")

    html = prihlaseny("Petr").get("/sprava").get_data(as_text=True)
    assert "/sprava/pridat" not in html, "Správa pořád zakládá účty ručně"


def test_sprava_ma_pozvanku_s_kodem():
    zaloz_ucet("Petr")

    html = prihlaseny("Petr").get("/sprava").get_data(as_text=True)
    assert database.registracni_kod() in html, "chybí registrační kód"
    assert "Pozvat" in html, "chybí karta Pozvat člověka"


def test_profil_rekne_ze_spravce_muze_prepsat_heslo():
    """Rozhodnutí z 5. 9.: správce zůstává pečovatel, ale nemá to být
    schované."""
    zaloz_ucet("Petr")
    zaloz_ucet("Hana")

    html = prihlaseny("Hana").get("/profil").get_data(as_text=True)
    assert "/profil/zrusit" in html, "v Profilu chybí zrušení účtu"


if __name__ == "__main__":
    import sys
    kolik, spadlo = spust(globals(), "Správa")
    sys.exit(1 if spadlo else 0)
