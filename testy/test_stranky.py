# -*- coding: utf-8 -*-
"""
Stránky odpovídají a nenechávají za sebou viset spojení s databází.

Je to hrubé síto, ne kontrola vzhledu: projde hlavní stránky jako přihlášený
uživatel a hlídá dvě věci - že nespadnou a že po stovce požadavků nezůstane
otevřené ani jedno spojení navíc.
"""

from spolecne import klient, spust, zaloz_uzivatele, otevrenych_spojeni

# Stránky zařízení (Soláry, Nanoleaf) tu schválně nejsou: sahají po síti na
# solární strídač a na panely, takže by test záležel na tom, jestli je zrovna
# zapnutý domácí počítač s Tailscale.
STRANKY = ["/", "/domacnost", "/nakup", "/profil", "/sprava"]


def prihlaseny_prohlizec():
    jmeno, heslo = zaloz_uzivatele()
    prohlizec = klient()
    prohlizec.post("/prihlaseni", data={"jmeno": jmeno, "heslo": heslo})
    return prohlizec


def test_prihlasovaci_stranka_jde_otevrit_i_bez_prihlaseni():
    odpoved = klient().get("/prihlaseni")
    assert odpoved.status_code == 200


def test_neprihlaseny_je_poslan_na_prihlaseni():
    odpoved = klient().get("/domacnost")
    assert odpoved.status_code == 302, "nepřihlášený se dostal na stránku"
    assert "/prihlaseni" in odpoved.headers["Location"]


def test_hlavni_stranky_prihlasenemu_odpovidaji():
    prohlizec = prihlaseny_prohlizec()
    for cesta in STRANKY:
        stav = prohlizec.get(cesta).status_code
        assert stav < 400, "%s vrátilo %d" % (cesta, stav)


def test_sto_pozadavku_nenecha_viset_spojeni():
    prohlizec = prihlaseny_prohlizec()
    pred = otevrenych_spojeni()

    for _ in range(20):
        for cesta in STRANKY:
            prohlizec.get(cesta)

    po = otevrenych_spojeni()
    assert po <= pred, "po 100 požadavcích visí %d spojení navíc" % (po - pred)


if __name__ == "__main__":
    import sys
    kolik, spadlo = spust(globals(), __doc__.strip().splitlines()[0])
    sys.exit(1 if spadlo else 0)
