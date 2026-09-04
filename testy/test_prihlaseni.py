# -*- coding: utf-8 -*-
"""
Strop na počet přihlašovacích pokusů.

Formulář je veřejně na internetu, takže bez stropu by do něj šlo zkoušet
hesla donekonečna. Počítají se chybné pokusy z jedné IP adresy: po pěti
minuta čekání, po deseti pět minut, po patnácti čtvrt hodiny.

Počítá se ADRESA, ne jméno - jinak by stačilo zkoušet cizí jméno a majitele
účtu tím vyřadit z provozu.
"""

from spolecne import database, klient, spust, zaloz_uzivatele

IP = "203.0.113.9"        # adresa vyhrazená pro příklady, nikomu nepatří
JINA_IP = "198.51.100.7"


def chybne_pokusy(kolik, ip=IP):
    for _ in range(kolik):
        database.zaznamenej_chybny_pokus(ip)


def posun_blokaci_do_minulosti(ip=IP):
    """Tváří se, že blokace už vypršela - abychom v testu nemuseli čekat."""
    with database._spojeni() as db:
        db.execute(
            "UPDATE pokusy_prihlaseni SET blokovano_do = "
            "datetime('now', 'localtime', '-1 minute') WHERE ip = ?",
            (ip,),
        )


# --- samotné počítadlo -------------------------------------------------

def test_neznama_adresa_neni_blokovana():
    assert database.zbyva_blokace(IP) == 0


def test_ctyri_chyby_jeste_pousti():
    chybne_pokusy(4)
    assert database.zbyva_blokace(IP) == 0


def test_pata_chyba_zablokuje_na_minutu():
    chybne_pokusy(5)
    zbyva = database.zbyva_blokace(IP)
    assert 50 <= zbyva <= 60, "čeká se ~60 s, vráceno %s" % zbyva


def test_deset_chyb_zablokuje_na_pet_minut():
    chybne_pokusy(10)
    zbyva = database.zbyva_blokace(IP)
    assert 290 <= zbyva <= 300, "čeká se ~300 s, vráceno %s" % zbyva


def test_patnact_chyb_zablokuje_na_ctvrt_hodiny():
    chybne_pokusy(15)
    zbyva = database.zbyva_blokace(IP)
    assert 890 <= zbyva <= 900, "čeká se ~900 s, vráceno %s" % zbyva


def test_blokace_plati_jen_pro_svou_adresu():
    chybne_pokusy(5)
    assert database.zbyva_blokace(JINA_IP) == 0


def test_po_vyprseni_se_zase_pousti():
    chybne_pokusy(5)
    posun_blokaci_do_minulosti()
    assert database.zbyva_blokace(IP) == 0


def test_zapomen_pokusy_pocitadlo_vynuluje():
    chybne_pokusy(5)
    database.zapomen_pokusy(IP)
    assert database.zbyva_blokace(IP) == 0


# --- chování formuláře -------------------------------------------------

def test_formular_odmitne_i_spravne_heslo_behem_blokace():
    """To hlavní: když je adresa zablokovaná, nepomůže ani správné heslo."""
    jmeno, heslo = zaloz_uzivatele()
    prohlizec = klient()

    for _ in range(5):
        prohlizec.post("/prihlaseni", data={"jmeno": jmeno, "heslo": "spatne"},
                       environ_base={"REMOTE_ADDR": IP})

    odpoved = prohlizec.post("/prihlaseni", data={"jmeno": jmeno, "heslo": heslo},
                             environ_base={"REMOTE_ADDR": IP})

    # 302 by znamenalo přesměrování na přihlášenou stránku, tedy průchod.
    assert odpoved.status_code == 200, "přihlásil se, i když byl zablokovaný"
    assert "mnoho pokus" in odpoved.get_data(as_text=True), \
        "chybí hláška o příliš mnoha pokusech"


def test_uspesne_prihlaseni_smaze_pocitadlo():
    """Rodina má doma jednu společnou adresu, takže pár překlepů před
    úspěšným přihlášením nesmí nikoho zablokovat."""
    jmeno, heslo = zaloz_uzivatele()
    prohlizec = klient()

    for _ in range(4):
        prohlizec.post("/prihlaseni", data={"jmeno": jmeno, "heslo": "spatne"},
                       environ_base={"REMOTE_ADDR": IP})

    prohlizec.post("/prihlaseni", data={"jmeno": jmeno, "heslo": heslo},
                   environ_base={"REMOTE_ADDR": IP})

    assert database.zbyva_blokace(IP) == 0
    with database._spojeni() as db:
        zbylo = db.execute(
            "SELECT COUNT(*) FROM pokusy_prihlaseni WHERE ip = ?", (IP,)
        ).fetchone()[0]
    assert zbylo == 0, "po přihlášení měl řádek zmizet"


def test_spravne_heslo_bez_blokace_projde():
    """Pojistka, ať se strop nezvrhne v to, že nepustí dovnitř nikoho."""
    jmeno, heslo = zaloz_uzivatele()
    odpoved = klient().post("/prihlaseni", data={"jmeno": jmeno, "heslo": heslo},
                            environ_base={"REMOTE_ADDR": IP})
    assert odpoved.status_code == 302, "správné heslo mělo pustit dál"


if __name__ == "__main__":
    import sys
    kolik, spadlo = spust(globals(), __doc__.strip().splitlines()[0])
    sys.exit(1 if spadlo else 0)
