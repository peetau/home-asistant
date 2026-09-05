# -*- coding: utf-8 -*-
"""
Nákupní seznamy: předání vlastnictví.

Účet, který vlastní neprázdný seznam, se nedal zrušit vůbec — smazat jde
jen prázdný. Předání je ta chybějící cesta ven.
"""

from spolecne import database, klient, spust

HESLO = "tajne-heslo"


def email_pro(jmeno):
    return "%s@test.cz" % jmeno.lower()


def zaloz_ucet(jmeno):
    database.vytvor_uzivatele(jmeno, email_pro(jmeno), HESLO)
    with database._spojeni() as db:
        return db.execute("SELECT id FROM uzivatele WHERE email = ?",
                          (email_pro(jmeno),)).fetchone()[0]


def prihlaseny(jmeno):
    prohlizec = klient()
    prohlizec.post("/prihlaseni",
                   data={"email": email_pro(jmeno), "heslo": HESLO})
    return prohlizec


def pridej_clena(id_seznamu, id_uzivatele):
    with database._spojeni() as db:
        db.execute("INSERT INTO clenove_seznamu (seznam_id, uzivatel_id) "
                   "VALUES (?, ?)", (id_seznamu, id_uzivatele))


def role(id_seznamu, id_uzivatele):
    """Vrátí 'vlastnik', 'clen', nebo None."""
    with database._spojeni() as db:
        if db.execute("SELECT 1 FROM seznamy WHERE id = ? AND vlastnik_id = ?",
                      (id_seznamu, id_uzivatele)).fetchone():
            return "vlastnik"
        if db.execute("SELECT 1 FROM clenove_seznamu "
                      "WHERE seznam_id = ? AND uzivatel_id = ?",
                      (id_seznamu, id_uzivatele)).fetchone():
            return "clen"
    return None


# --- předání vlastnictví ----------------------------------------------

def test_vlastnik_preda_clenovi_a_role_se_prohodi():
    id_petr = zaloz_ucet("Petr")
    id_hana = zaloz_ucet("Hana")
    ok, id_seznamu = database.vytvor_seznam("Doma", id_petr)
    pridej_clena(id_seznamu, id_hana)

    povedlo, hlaska = database.predej_seznam(id_seznamu, id_petr, id_hana)

    assert povedlo, hlaska
    assert role(id_seznamu, id_hana) == "vlastnik"
    assert role(id_seznamu, id_petr) == "clen", \
        "starý vlastník má zůstat členem, ne přijít o seznam"


def test_clen_predat_nemuze():
    id_petr = zaloz_ucet("Petr")
    id_hana = zaloz_ucet("Hana")
    id_alex = zaloz_ucet("Alex")
    ok, id_seznamu = database.vytvor_seznam("Doma", id_petr)
    pridej_clena(id_seznamu, id_hana)
    pridej_clena(id_seznamu, id_alex)

    povedlo, hlaska = database.predej_seznam(id_seznamu, id_hana, id_alex)

    assert not povedlo, "člen předal cizí seznam"
    assert role(id_seznamu, id_petr) == "vlastnik"


def test_predat_neclenovi_nejde():
    id_petr = zaloz_ucet("Petr")
    id_cizi = zaloz_ucet("Cizi")
    ok, id_seznamu = database.vytvor_seznam("Doma", id_petr)

    povedlo, hlaska = database.predej_seznam(id_seznamu, id_petr, id_cizi)

    assert not povedlo, "seznam se předal někomu, kdo na něm není"


def test_predat_sam_sobe_nejde():
    id_petr = zaloz_ucet("Petr")
    ok, id_seznamu = database.vytvor_seznam("Doma", id_petr)

    povedlo, hlaska = database.predej_seznam(id_seznamu, id_petr, id_petr)

    assert not povedlo


def test_po_predani_jde_puvodni_ucet_zrusit():
    """Kvůli tomuhle předání vzniklo: účet s neprázdným seznamem se nedal
    zrušit, protože smazat jde jen prázdný."""
    zaloz_ucet("Petr")
    id_tester = zaloz_ucet("Tester")
    id_hana = zaloz_ucet("Hana")
    ok, id_seznamu = database.vytvor_seznam("Doma", id_tester)
    pridej_clena(id_seznamu, id_hana)
    database.pridej_polozku(id_seznamu, "Mleko", "Tester", id_tester)

    neslo, duvod = database.smaz_uzivatele(id_tester)
    assert not neslo, "účet vlastnící seznam šel smazat rovnou"

    database.predej_seznam(id_seznamu, id_tester, id_hana)
    ok, hlaska = database.smaz_uzivatele(id_tester)

    assert ok, hlaska


def test_polozky_predanim_nezmizi():
    id_petr = zaloz_ucet("Petr")
    id_hana = zaloz_ucet("Hana")
    ok, id_seznamu = database.vytvor_seznam("Doma", id_petr)
    pridej_clena(id_seznamu, id_hana)
    database.pridej_polozku(id_seznamu, "Mleko", "Petr", id_petr)

    database.predej_seznam(id_seznamu, id_petr, id_hana)

    polozky = database.seznam_nakupu(id_seznamu, id_hana)
    assert len(polozky) == 1, "položky se předáním ztratily"


def test_vlastnik_vidi_tlacitko_predat():
    id_petr = zaloz_ucet("Petr")
    id_hana = zaloz_ucet("Hana")
    ok, id_seznamu = database.vytvor_seznam("Doma", id_petr)
    pridej_clena(id_seznamu, id_hana)

    html = prihlaseny("Petr").get(
        "/nakup/%d" % id_seznamu).get_data(as_text=True)
    assert "/nakup/%d/predat/%d" % (id_seznamu, id_hana) in html, \
        "vlastník nemá čím seznam předat"


def test_clen_tlacitko_predat_nevidi():
    id_petr = zaloz_ucet("Petr")
    id_hana = zaloz_ucet("Hana")
    ok, id_seznamu = database.vytvor_seznam("Doma", id_petr)
    pridej_clena(id_seznamu, id_hana)

    html = prihlaseny("Hana").get(
        "/nakup/%d" % id_seznamu).get_data(as_text=True)
    assert "/predat/" not in html, "člen může předávat cizí seznam"


if __name__ == "__main__":
    import sys
    kolik, spadlo = spust(globals(), "Nákup")
    sys.exit(1 if spadlo else 0)
