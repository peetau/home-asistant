# -*- coding: utf-8 -*-
"""
Domácnost jako věc v databázi.

Zařízení (Soláry, Nanoleaf) přestávají být právem a stávají se členstvím
v domácnosti. Zařízení samotná zůstávají v `config.py`, takže musí být
jasně řečeno, KTERÉ domácnosti patří - jinak by k nim přišel každý, kdo si
nějakou domácnost založí. Říká to sloupec `ma_zarizeni` a hlídá ho
částečný unikátní index.
"""

import sqlite3

from spolecne import database, klient, spust, web

HESLO = "tajne-heslo"


def zaloz_ucet(jmeno):
    """Založí účet a vrátí jeho id."""
    database.vytvor_uzivatele(jmeno, HESLO)
    with database._spojeni() as db:
        return db.execute(
            "SELECT id FROM uzivatele WHERE jmeno = ?", (jmeno,)
        ).fetchone()[0]


def pridej_clena(id_domacnosti, id_uzivatele):
    with database._spojeni() as db:
        db.execute(
            "INSERT INTO clenove_domacnosti (domacnost_id, uzivatel_id) "
            "VALUES (?, ?)",
            (id_domacnosti, id_uzivatele),
        )


def zestarni_migraci():
    """
    Udělá z databáze takovou, jaká byla před migrací.

    cista_databaze() volá init_db(), takže migrace už proběhla (naprázdno,
    nebyli tam uživatelé). Aby šlo otestovat, co udělá se skutečnými daty,
    musí se jí uvolnit název, který si zabrala.
    """
    with database._spojeni() as db:
        db.execute("DELETE FROM migrace WHERE nazev = 'zalozeni_domacnosti'")


def dej_stare_pravo(id_uzivatele, tab):
    """Zapíše právo přímo, protože VSECHNY_TABY už 'solary' nezná."""
    with database._spojeni() as db:
        db.execute(
            "INSERT OR IGNORE INTO opravneni (uzivatel_id, tab) VALUES (?, ?)",
            (id_uzivatele, tab),
        )


# --- zakládání a sloupec ma_zarizeni ----------------------------------

def test_prvni_domacnost_zdedi_zarizeni_z_configu():
    """Na čerstvé databázi žádná domácnost není. Ta první dostane zařízení,
    jinak by je neuviděl ani majitel serveru."""
    id_petr = zaloz_ucet("Petr")
    ok, id_domacnosti = database.zaloz_domacnost("Doma", id_petr)
    assert ok, id_domacnosti

    with database._spojeni() as db:
        ma = db.execute(
            "SELECT ma_zarizeni FROM domacnosti WHERE id = ?", (id_domacnosti,)
        ).fetchone()[0]
    assert ma == 1, "první domácnost měla zdědit zařízení"


def test_druha_domacnost_zarizeni_nedostane():
    id_petr = zaloz_ucet("Petr")
    id_cizi = zaloz_ucet("Cizi")
    database.zaloz_domacnost("Doma", id_petr)
    ok, id_druhe = database.zaloz_domacnost("U cizich", id_cizi)
    assert ok, id_druhe

    with database._spojeni() as db:
        ma = db.execute(
            "SELECT ma_zarizeni FROM domacnosti WHERE id = ?", (id_druhe,)
        ).fetchone()[0]
    assert ma == 0, "zařízení z configu smí mít jen jedna domácnost"


def test_databaze_nedovoli_dve_domacnosti_se_zarizenimi():
    """Pojistka nesmí být jen v Pythonu - dva workery by ji obešly."""
    id_petr = zaloz_ucet("Petr")
    database.zaloz_domacnost("Doma", id_petr)

    try:
        with database._spojeni() as db:
            db.execute(
                "INSERT INTO domacnosti (nazev, vlastnik_id, kod, ma_zarizeni) "
                "VALUES ('Podvod', ?, 'AAA-BBB', 1)",
                (id_petr,),
            )
    except sqlite3.IntegrityError:
        return
    raise AssertionError("databáze pustila druhou domácnost se zařízeními")


# --- kdo se k zařízením dostane ---------------------------------------

def test_vlastnik_svou_domacnost_dostane():
    id_petr = zaloz_ucet("Petr")
    database.zaloz_domacnost("Doma", id_petr)

    radek = database.domacnost_uzivatele(id_petr)
    assert radek is not None, "vlastník se ke své domácnosti nedostal"
    assert radek[2] is True, "vlastník má být poznaný jako vlastník"


def test_clen_domacnost_dostane():
    id_petr = zaloz_ucet("Petr")
    id_hana = zaloz_ucet("Hana")
    ok, id_domacnosti = database.zaloz_domacnost("Doma", id_petr)
    pridej_clena(id_domacnosti, id_hana)

    radek = database.domacnost_uzivatele(id_hana)
    assert radek is not None, "člen se k domácnosti nedostal"
    assert radek[2] is False, "člen není vlastník"


def test_neclen_nedostane_nic():
    id_petr = zaloz_ucet("Petr")
    id_cizi = zaloz_ucet("Cizi")
    database.zaloz_domacnost("Doma", id_petr)

    assert database.domacnost_uzivatele(id_cizi) is None


def test_clen_domacnosti_bez_zarizeni_nedostane_nic():
    """Tohle je ta past, kvůli které sloupec ma_zarizeni vznikl: kdyby se
    ptalo jen 'jsi člen nějaké domácnosti', pustilo by to cizího člověka
    k Petrovu SolaXu."""
    id_petr = zaloz_ucet("Petr")
    id_cizi = zaloz_ucet("Cizi")
    database.zaloz_domacnost("Doma", id_petr)
    ok, id_druhe = database.zaloz_domacnost("U cizich", id_cizi)
    assert ok, id_druhe

    assert database.domacnost_uzivatele(id_cizi) is None, \
        "člen domácnosti bez zařízení se dostal k cizím zařízením"


# --- migrace ze starých práv ------------------------------------------

def priprav_starou_databazi():
    """Účty s právy na zařízení, tak jak vypadala databáze před migrací."""
    id_petr = zaloz_ucet("Petrjr")     # první účet dostane 'sprava'
    id_hana = zaloz_ucet("Hana")
    id_kamarad = zaloz_ucet("Kamarad")  # jen Nákup, žádné zařízení

    zestarni_migraci()
    dej_stare_pravo(id_petr, "solary")
    dej_stare_pravo(id_petr, "nanoleaf")
    dej_stare_pravo(id_hana, "solary")

    database.init_db()
    return id_petr, id_hana, id_kamarad


def test_migrace_udela_z_prav_clenstvi():
    id_petr, id_hana, id_kamarad = priprav_starou_databazi()

    assert database.domacnost_uzivatele(id_petr) is not None, \
        "vlastník po migraci na svá zařízení nedosáhne"
    assert database.domacnost_uzivatele(id_hana) is not None, \
        "kdo měl právo na Soláry, měl se stát členem"
    assert database.domacnost_uzivatele(id_kamarad) is None, \
        "kdo zařízení nikdy neměl, členem být nemá"


def test_migrace_smaze_prava_na_zarizeni():
    priprav_starou_databazi()

    with database._spojeni() as db:
        zbylo = db.execute(
            "SELECT COUNT(*) FROM opravneni WHERE tab IN ('solary','nanoleaf')"
        ).fetchone()[0]
    assert zbylo == 0, "stará práva na zařízení měla zmizet"


def test_migrace_nikoho_neudela_spravcem():
    """Mazání řádků z opravneni kdysi hrozilo spuštěním záchranné migrace,
    která rozdala všem všechna práva. Tenhle test to hlídá."""
    id_petr, id_hana, id_kamarad = priprav_starou_databazi()

    with database._spojeni() as db:
        spravci = [r[0] for r in db.execute(
            "SELECT uzivatel_id FROM opravneni WHERE tab = 'sprava'")]

    assert id_hana not in spravci, "Hana se omylem stala správcem"
    assert id_kamarad not in spravci, "kamarád se omylem stal správcem"


def test_migrace_probehne_jen_jednou():
    """init_db() se volá při každém startu, takže musí být bezpečné ho
    pouštět opakovaně."""
    priprav_starou_databazi()
    database.init_db()
    database.init_db()

    with database._spojeni() as db:
        kolik = db.execute("SELECT COUNT(*) FROM domacnosti").fetchone()[0]
    assert kolik == 1, "domácností vzniklo %d místo jedné" % kolik


# --- přístup k zařízením přes web -------------------------------------

def bez_skutecnych_zarizeni():
    """
    Nahradí čtení ze SolaXu, ať testy nezávisí na tom, jestli je doma
    zapnutý počítač s Tailscale. Vrací funkci, která to vrátí zpátky.

    Je to jediné místo, kde si testy něco podstrkují - a je to tu proto,
    že za tou funkcí je krabička na drátě, ne kód. Kontrolu přístupu, tedy
    to, co se doopravdy testuje, se to nedotýká: dekorátor rozhodne dřív,
    než se k tomuhle vůbec dojde.
    """
    puvodni_solax = web._stav_solax
    puvodni_nanoleaf = web._stav_nanoleaf
    web._stav_solax = lambda: (None, "zařízení není v testu dostupné")
    web._stav_nanoleaf = lambda: (None, "zařízení není v testu dostupné")

    def vrat_zpatky():
        web._stav_solax = puvodni_solax
        web._stav_nanoleaf = puvodni_nanoleaf

    return vrat_zpatky


def prihlaseny(jmeno):
    prohlizec = klient()
    prohlizec.post("/prihlaseni", data={"jmeno": jmeno, "heslo": HESLO})
    return prohlizec


def test_vlastnik_projde_na_solary():
    id_petr = zaloz_ucet("Petr")
    database.zaloz_domacnost("Doma", id_petr)

    vrat_zpatky = bez_skutecnych_zarizeni()
    try:
        odpoved = prihlaseny("Petr").get("/solary")
    finally:
        vrat_zpatky()

    assert odpoved.status_code == 200, \
        "vlastníka to na jeho vlastní Soláry nepustilo (%d)" % odpoved.status_code


def test_clen_projde_na_solary():
    id_petr = zaloz_ucet("Petr")
    id_hana = zaloz_ucet("Hana")
    ok, id_domacnosti = database.zaloz_domacnost("Doma", id_petr)
    pridej_clena(id_domacnosti, id_hana)

    vrat_zpatky = bez_skutecnych_zarizeni()
    try:
        odpoved = prihlaseny("Hana").get("/solary")
    finally:
        vrat_zpatky()

    assert odpoved.status_code == 200, \
        "člena to na Soláry nepustilo (%d)" % odpoved.status_code


def test_neclen_je_poslan_na_asistenta():
    """302, ne 404. Pravidlo '404 místo 403' platí u Nákupu, kde by se dalo
    poznat, že cizí seznam existuje. U tabu není co prozradit."""
    id_petr = zaloz_ucet("Petr")
    zaloz_ucet("Cizi")
    database.zaloz_domacnost("Doma", id_petr)

    odpoved = prihlaseny("Cizi").get("/solary")
    assert odpoved.status_code == 302, \
        "nečlen se dostal na Soláry (%d)" % odpoved.status_code
    assert odpoved.headers["Location"].endswith("/"), \
        "měl jít na Asistenta, šel na %s" % odpoved.headers["Location"]


def test_clen_domacnosti_bez_zarizeni_se_na_solary_nedostane():
    """Tatáž past jako u domacnost_uzivatele(), ale ověřená přes web -
    tedy tak, jak by se k tomu dostal skutečný člověk."""
    id_petr = zaloz_ucet("Petr")
    id_cizi = zaloz_ucet("Cizi")
    database.zaloz_domacnost("Doma", id_petr)
    database.zaloz_domacnost("U cizich", id_cizi)

    odpoved = prihlaseny("Cizi").get("/solary")
    assert odpoved.status_code == 302, \
        "člen cizí domácnosti se dostal k Petrovu SolaXu (%d)" % odpoved.status_code


def test_neprihlaseny_jde_na_prihlaseni_ne_na_asistenta():
    id_petr = zaloz_ucet("Petr")
    database.zaloz_domacnost("Doma", id_petr)

    odpoved = klient().get("/solary")
    assert odpoved.status_code == 302
    assert "/prihlaseni" in odpoved.headers["Location"], \
        "nepřihlášený měl jít na přihlášení, šel na %s" % odpoved.headers["Location"]


def test_nanoleaf_je_chraneny_stejne():
    """Zařízení jsou dvě a obě musí být za stejnou brankou."""
    id_petr = zaloz_ucet("Petr")
    zaloz_ucet("Cizi")
    database.zaloz_domacnost("Doma", id_petr)

    odpoved = prihlaseny("Cizi").get("/nanoleaf")
    assert odpoved.status_code == 302, \
        "nečlen se dostal na Nanoleaf (%d)" % odpoved.status_code


def test_sablony_dostanou_domacnost():
    """spolecna_data() posílá do šablon proměnnou 'domacnost' - podle ní se
    filtruje pruh tabů."""
    id_petr = zaloz_ucet("Petr")
    database.zaloz_domacnost("Doma", id_petr)

    with web.app.test_request_context("/"):
        from flask import session as flask_session
        flask_session["uzivatel"] = "Petr"
        flask_session["uzivatel_id"] = id_petr
        data = web.spolecna_data()

    assert data["domacnost"] is not None, "šablony se o domácnosti nedozvědí"


# --- pozvánka kódem ---------------------------------------------------

def kod_domacnosti(id_domacnosti):
    with database._spojeni() as db:
        return db.execute(
            "SELECT kod FROM domacnosti WHERE id = ?", (id_domacnosti,)
        ).fetchone()[0]


def test_pripojeni_kodem_udela_clena():
    id_petr = zaloz_ucet("Petr")
    id_hana = zaloz_ucet("Hana")
    ok, id_domacnosti = database.zaloz_domacnost("Doma", id_petr)

    povedlo, hlaska = database.pripoj_domacnost_kodem(
        kod_domacnosti(id_domacnosti), id_hana)

    assert povedlo, hlaska
    assert database.domacnost_uzivatele(id_hana) is not None, \
        "po připojení kódem se Hana členkou nestala"


def test_neznamy_kod_nikam_nevede():
    id_petr = zaloz_ucet("Petr")
    id_hana = zaloz_ucet("Hana")
    database.zaloz_domacnost("Doma", id_petr)

    povedlo, hlaska = database.pripoj_domacnost_kodem("AAA-BBB", id_hana)

    assert not povedlo
    assert database.domacnost_uzivatele(id_hana) is None, \
        "neplatný kód někoho pustil dovnitř"


def test_kdo_uz_je_clenem_dostane_vlidnou_hlasku():
    id_petr = zaloz_ucet("Petr")
    id_hana = zaloz_ucet("Hana")
    ok, id_domacnosti = database.zaloz_domacnost("Doma", id_petr)
    kod = kod_domacnosti(id_domacnosti)

    database.pripoj_domacnost_kodem(kod, id_hana)
    povedlo, hlaska = database.pripoj_domacnost_kodem(kod, id_hana)

    assert not povedlo
    assert database.domacnost_uzivatele(id_hana) is not None, \
        "druhé připojení Hanu z domácnosti vyhodilo"


def test_vlastnik_se_ke_sve_domacnosti_nepripoji():
    id_petr = zaloz_ucet("Petr")
    ok, id_domacnosti = database.zaloz_domacnost("Doma", id_petr)

    povedlo, hlaska = database.pripoj_domacnost_kodem(
        kod_domacnosti(id_domacnosti), id_petr)

    assert not povedlo
    assert database.domacnost_uzivatele(id_petr) is not None, \
        "vlastník o svou domácnost přišel"


# --- co je na stránkách vidět ------------------------------------------

def stranka(prohlizec, cesta):
    """Vrátí HTML stránky, se zařízeními umlčenými."""
    vrat_zpatky = bez_skutecnych_zarizeni()
    try:
        return prohlizec.get(cesta).get_data(as_text=True)
    finally:
        vrat_zpatky()


def test_neclen_vidi_pozvankovou_kartu():
    id_petr = zaloz_ucet("Petr")
    zaloz_ucet("Cizi")
    database.zaloz_domacnost("Doma", id_petr)

    html = stranka(prihlaseny("Cizi"), "/domacnost")
    assert "/domacnost/pripojit" in html, \
        "nečlen nemá kudy zadat kód pozvánky"


def test_clen_vidi_karty_zarizeni():
    id_petr = zaloz_ucet("Petr")
    database.zaloz_domacnost("Doma", id_petr)

    html = stranka(prihlaseny("Petr"), "/domacnost")
    assert "Solární elektrárna" in html, "členovi se nevykreslily karty zařízení"
    assert "/domacnost/pripojit" not in html, \
        "členovi se pořád nabízí připojení kódem"


def test_v_asistentovi_nejsou_taby_zarizeni():
    """Pruh tabů se filtruje podle půlky. Petr na zařízení právo má,
    a přesto je v Asistentovi nemá vidět."""
    id_petr = zaloz_ucet("Petr")
    database.zaloz_domacnost("Doma", id_petr)

    html = stranka(prihlaseny("Petr"), "/nakup")
    assert "/solary" not in html, "tab Soláry svítí i v Asistentovi"
    assert "/nanoleaf" not in html, "tab Nanoleaf svítí i v Asistentovi"


def test_v_domacnosti_taby_zarizeni_jsou():
    id_petr = zaloz_ucet("Petr")
    database.zaloz_domacnost("Doma", id_petr)

    html = stranka(prihlaseny("Petr"), "/domacnost")
    assert "/solary" in html, "tab Soláry chybí i členovi v Domácnosti"


def test_nakup_v_domacnosti_neni():
    id_petr = zaloz_ucet("Petr")
    database.zaloz_domacnost("Doma", id_petr)

    html = stranka(prihlaseny("Petr"), "/domacnost")
    assert "/nakup" not in html, "tab Nákup svítí i v Domácnosti"


def test_vlastnik_vidi_kod_pozvanky():
    id_petr = zaloz_ucet("Petr")
    ok, id_domacnosti = database.zaloz_domacnost("Doma", id_petr)

    html = stranka(prihlaseny("Petr"), "/domacnost")
    assert kod_domacnosti(id_domacnosti) in html, \
        "vlastník nemá kde vzít kód, který má rozeslat"


def test_clen_kod_pozvanky_nevidi():
    """Zvát smí zatím jen vlastník - stejně jako u nákupního seznamu, kde
    se kód do šablony nedostane tomu, kdo ho vidět nemá."""
    id_petr = zaloz_ucet("Petr")
    id_hana = zaloz_ucet("Hana")
    ok, id_domacnosti = database.zaloz_domacnost("Doma", id_petr)
    pridej_clena(id_domacnosti, id_hana)

    html = stranka(prihlaseny("Hana"), "/domacnost")
    assert kod_domacnosti(id_domacnosti) not in html, \
        "člen vidí kód pozvánky, i když zvát nesmí"


# --- správa členů -----------------------------------------------------

def jmena(seznam):
    return [c["jmeno"] for c in seznam]


def test_vypis_clenu_ma_vlastnika_prvniho():
    id_petr = zaloz_ucet("Petr")
    id_hana = zaloz_ucet("Hana")
    id_alex = zaloz_ucet("Alex")
    ok, id_dom = database.zaloz_domacnost("Doma", id_petr)
    pridej_clena(id_dom, id_hana)
    pridej_clena(id_dom, id_alex)

    seznam = database.clenove_domacnosti(id_dom)
    assert jmena(seznam) == ["Petr", "Alex", "Hana"], \
        "vlastník má být první, pak abeceda: %s" % jmena(seznam)
    assert seznam[0]["je_vlastnik"] is True
    assert seznam[1]["je_vlastnik"] is False


def test_vlastnik_odebere_clena():
    id_petr = zaloz_ucet("Petr")
    id_hana = zaloz_ucet("Hana")
    ok, id_dom = database.zaloz_domacnost("Doma", id_petr)
    pridej_clena(id_dom, id_hana)

    povedlo, hlaska = database.odeber_clena_domacnosti(id_dom, id_petr, id_hana)

    assert povedlo, hlaska
    assert database.domacnost_uzivatele(id_hana) is None, \
        "odebraná Hana pořád vidí zařízení"


def test_clen_nemuze_odebrat_jineho_clena():
    id_petr = zaloz_ucet("Petr")
    id_hana = zaloz_ucet("Hana")
    id_alex = zaloz_ucet("Alex")
    ok, id_dom = database.zaloz_domacnost("Doma", id_petr)
    pridej_clena(id_dom, id_hana)
    pridej_clena(id_dom, id_alex)

    povedlo, hlaska = database.odeber_clena_domacnosti(id_dom, id_hana, id_alex)

    assert not povedlo
    assert database.domacnost_uzivatele(id_alex) is not None, \
        "člen dokázal odebrat jiného člena"


def test_vlastnika_odebrat_nejde():
    id_petr = zaloz_ucet("Petr")
    ok, id_dom = database.zaloz_domacnost("Doma", id_petr)

    povedlo, hlaska = database.odeber_clena_domacnosti(id_dom, id_petr, id_petr)

    assert not povedlo, "vlastník odebral sám sebe a domácnost osiřela"
    assert database.domacnost_uzivatele(id_petr) is not None


def test_novy_kod_zneplatni_stary_ale_clenstvi_nechá():
    id_petr = zaloz_ucet("Petr")
    id_hana = zaloz_ucet("Hana")
    ok, id_dom = database.zaloz_domacnost("Doma", id_petr)
    pridej_clena(id_dom, id_hana)
    stary = kod_domacnosti(id_dom)

    povedlo, hlaska = database.novy_kod_domacnosti(id_dom, id_petr)

    assert povedlo, hlaska
    assert kod_domacnosti(id_dom) != stary, "kód se nezměnil"
    assert database.domacnost_uzivatele(id_hana) is not None, \
        "nový kód vyhodil stávajícího člena"

    id_cizi = zaloz_ucet("Cizi")
    slo, _ = database.pripoj_domacnost_kodem(stary, id_cizi)
    assert not slo, "starý kód pořád funguje"


def test_clen_nemuze_vygenerovat_novy_kod():
    id_petr = zaloz_ucet("Petr")
    id_hana = zaloz_ucet("Hana")
    ok, id_dom = database.zaloz_domacnost("Doma", id_petr)
    pridej_clena(id_dom, id_hana)
    stary = kod_domacnosti(id_dom)

    povedlo, hlaska = database.novy_kod_domacnosti(id_dom, id_hana)

    assert not povedlo
    assert kod_domacnosti(id_dom) == stary, "člen přegeneroval cizí kód"


def test_clen_muze_odejit():
    id_petr = zaloz_ucet("Petr")
    id_hana = zaloz_ucet("Hana")
    ok, id_dom = database.zaloz_domacnost("Doma", id_petr)
    pridej_clena(id_dom, id_hana)

    povedlo, hlaska = database.opust_domacnost(id_dom, id_hana)

    assert povedlo, hlaska
    assert database.domacnost_uzivatele(id_hana) is None


def test_vlastnik_odejit_nemuze():
    """Domácnost musí někomu patřit - vlastnik_id je NOT NULL. Odchod
    vlastníka by udělal sirotka, takže se musí odmítnout hláškou, ne mlčky."""
    id_petr = zaloz_ucet("Petr")
    ok, id_dom = database.zaloz_domacnost("Doma", id_petr)

    povedlo, hlaska = database.opust_domacnost(id_dom, id_petr)

    assert not povedlo
    assert database.domacnost_uzivatele(id_petr) is not None


# --- správa členů na stránce ------------------------------------------

def test_vlastnik_vidi_u_clena_odebrat():
    id_petr = zaloz_ucet("Petr")
    id_hana = zaloz_ucet("Hana")
    ok, id_dom = database.zaloz_domacnost("Doma", id_petr)
    pridej_clena(id_dom, id_hana)

    html = stranka(prihlaseny("Petr"), "/domacnost")
    assert "Hana" in html, "vlastník nevidí výpis členů"
    assert "/domacnost/odebrat/%d" % id_hana in html, \
        "vlastník nemá čím člena odebrat"


def test_clen_vidi_vypis_ale_neodebira():
    id_petr = zaloz_ucet("Petr")
    id_hana = zaloz_ucet("Hana")
    ok, id_dom = database.zaloz_domacnost("Doma", id_petr)
    pridej_clena(id_dom, id_hana)

    html = stranka(prihlaseny("Hana"), "/domacnost")
    assert "Petr" in html, "člen nevidí, kdo do domácnosti patří"
    assert "/domacnost/odebrat/" not in html, "člen má tlačítko Odebrat"
    assert "/domacnost/novy-kod" not in html, "člen může přegenerovat kód"
    assert "/domacnost/odejit" in html, "člen nemá jak odejít"


def test_vlastnik_nema_tlacitko_odejit():
    id_petr = zaloz_ucet("Petr")
    database.zaloz_domacnost("Doma", id_petr)

    html = stranka(prihlaseny("Petr"), "/domacnost")
    assert "/domacnost/odejit" not in html, \
        "vlastník má nabídnuté odejít, čímž by domácnost osiřela"


def test_odebrany_clen_prijde_o_zarizeni_hned():
    """Práva se čtou z databáze při každém požadavku, ne ze session - takže
    odebranému zmizí Soláry na další kliknutí, ne až po odhlášení."""
    id_petr = zaloz_ucet("Petr")
    id_hana = zaloz_ucet("Hana")
    ok, id_dom = database.zaloz_domacnost("Doma", id_petr)
    pridej_clena(id_dom, id_hana)

    hana = prihlaseny("Hana")
    prihlaseny("Petr").post("/domacnost/odebrat/%d" % id_hana)

    assert hana.get("/solary").status_code == 302, \
        "odebraná Hana se pořád dostane na Soláry"


def test_domacnost_ukazuje_stari_mereni():
    """Když karta Solárů hlásí chybu, tohle je odpověď na otázku, jestli
    sběrač ještě měří."""
    id_petr = zaloz_ucet("Petr")
    database.zaloz_domacnost("Doma", id_petr)
    with database._spojeni() as db:
        db.execute("INSERT INTO mereni (cas) VALUES (datetime('now','localtime'))")

    html = stranka(prihlaseny("Petr"), "/domacnost")
    assert "Poslední měření" in html, "na Domácnosti chybí stáří měření"


if __name__ == "__main__":
    import sys
    kolik, spadlo = spust(globals(), __doc__.strip().splitlines()[0])
    sys.exit(1 if spadlo else 0)
