r"""
Webové rozhraní domácího asistenta (Flask).

Na rozdíl od main.py, který proběhne a skončí, tenhle soubor spustí
SERVER, který běží pořád a čeká, až si prohlížeč řekne o stránku.

Spuštění (cmd):
    .venv\Scripts\python.exe web.py
pak v prohlížeči:  127.0.0.1:5000

Vzhled je oddělený v templates/ - společnou kostru drží zaklad.html,
jednotlivé stránky ji dědí. Tenhle soubor řeší jen LOGIKU:
přečti data a předej je šabloně.
"""

import os
import shutil
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import (Flask, render_template, request, redirect, url_for,
                   session, g, jsonify, abort)
from werkzeug.middleware.proxy_fix import ProxyFix

import config
import database
import diagram
import graf
import pocasi
import qr
import svatky
from devices.nanoleaf import (get_nanoleaf_status, get_nanoleaf_detail,
                             set_nanoleaf_on, set_nanoleaf_brightness,
                             set_nanoleaf_effect, get_nanoleaf_paleta)
from devices.solax import get_solax_status

# Běžíme na serveru, nebo doma při vývoji?
#
# Ten samý kód se chová na dvou místech trochu jinak. Rozhoduje o tom
# proměnná prostředí - nastavení, které kód dostane zvenku od systému,
# místo aby ho měl napsané v sobě. Na serveru ji nastaví systemd,
# doma není nastavená vůbec, takže tam vyjde False.
PRODUKCE = os.environ.get("ASISTENT_PRODUKCE") == "1"

# Připravit databázi (vytvořit chybějící tabulky, doplnit nové sloupce).
# Volá to i sber.py; je to bezpečné volat opakovaně a díky tomu se migrace
# spustí i tehdy, když se restartuje jen web.
database.init_db()

app = Flask(__name__)

# Tajný klíč, kterým Flask PODEPISUJE přihlašovací cookie. Bez něj by
# session vůbec nefungovala. Obsah cookie je čitelný, ale díky podpisu
# ho uživatel nemůže změnit, aniž by to server nepoznal.
app.secret_key = config.SECRET_KEY

# --- Zabezpečení přihlašovací cookie ---
app.config.update(
    # Cookie se nesmí odeslat po nešifrovaném spojení. Bez toho by ji
    # šlo na cizí Wi-Fi odposlechnout a přihlásit se jako někdo jiný.
    # Doma to musí zůstat vypnuté, jinak by se přes http:// nedalo
    # přihlásit vůbec.
    SESSION_COOKIE_SECURE=PRODUKCE,

    # JavaScript na stránce se k cookie nedostane. Kdyby se někdy povedlo
    # propašovat na web cizí skript, přihlášení rodiny mu zůstane skryté.
    SESSION_COOKIE_HTTPONLY=True,

    # Cookie se nepošle, když na náš web někdo odkáže z cizí stránky
    # formulářem. Ochrana proti tomu, aby tě podvržený odkaz odhlásil
    # nebo něco provedl tvým jménem.
    SESSION_COOKIE_SAMESITE="Lax",
)

if PRODUKCE:
    # Na serveru stojí před aplikací Caddy (reverzní proxy). Aplikace by
    # tedy každý požadavek viděla jako "HTTP z adresy 127.0.0.1" - Caddy
    # je totiž její jediný soused.
    #
    # ProxyFix ji naučí číst hlavičky, které Caddy přidává: skutečnou
    # adresu návštěvníka a to, že spojení bylo HTTPS. Bez toho by
    # url_for() skládal odkazy s http:// a cookie s příznakem Secure
    # by se nikdy neodeslala.
    #
    # x_for/x_proto=1 znamená "věř přesně jedné proxy před sebou" -
    # tolik jich tam je. Vyšší číslo by dovolilo hlavičky podvrhnout.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# Do které půlky aplikace tab patří.
#
# Přepínač v navigaci má ukazovat, kde zrovna jsi - a to i tehdy, když
# nekoukáš na úvodní stránku. Kdo je na Solárech, je v Domácnosti; kdo je
# na Nákupu, je u Asistenta. Bez téhle tabulky by přepínač na podstránkách
# nevěděl, co o sobě říct.
#
# Správa je zatím u Asistenta, protože spravuje účty celé aplikace.
# Až se z ní stane správa domácnosti (nápad z 3. 9.), přesune se sem.
PULKA_TABU = {
    "domacnost": "domacnost",
    "solary": "domacnost",
    "nanoleaf": "domacnost",
    "asistent": "asistent",
    "nakup": "asistent",
    "sprava": "asistent",
    "profil": "asistent",
}

# Lidské názvy tabů pro Správu. Klíče musí sedět na database.VSECHNY_TABY.
POPISY_TABU = {
    "solary": "☀️ Soláry",
    "nanoleaf": "💡 Nanoleaf",
    "sprava": "⚙️ Správa",
}


# Jak staré smí být, aby to ještě bylo "v pořádku".
# Sběrač měří po 5 minutách, takže dvě zmeškaná kola ještě nejsou porucha.
# Záloha běží denně, jeden vynechaný běh taky ne.
LIMIT_MERENI_MINUT = 15
LIMIT_ZALOHY_HODIN = 48


def podrobny_stav():
    """
    Podrobnosti o běhu systému pro tab Správa.

    Tohle je to, co jsme na přihlašovací obrazovce ZÁMĚRNĚ nezobrazili -
    tam jsou jen barevné tečky. Tady je to v pořádku: je to po přihlášení
    a jen pro správce.
    """
    def zjisti():
        udaje = {}

        minuty = database.stari_posledniho_mereni()
        udaje["mereni_minut"] = None if minuty is None else round(minuty)

        with database._spojeni() as db:
            udaje["mereni_pocet"] = db.execute(
                "SELECT COUNT(*) FROM mereni").fetchone()[0]
            udaje["mereni_od"] = db.execute(
                "SELECT MIN(cas) FROM mereni").fetchone()[0]

        # Velikost databáze a volné místo na disku
        udaje["db_mb"] = round(os.path.getsize(database.DB_SOUBOR) / 1048576, 1)
        volno = shutil.disk_usage(os.path.dirname(database.DB_SOUBOR) or ".")
        udaje["disk_volno_gb"] = round(volno.free / 1073741824, 1)
        udaje["disk_celkem_gb"] = round(volno.total / 1073741824, 1)

        # Stáří zálohy v hodinách
        slozka = os.path.expanduser(getattr(config, "ZALOHY_SLOZKA", "~/zalohy"))
        zalohy = []
        if os.path.isdir(slozka):
            zalohy = [os.path.join(slozka, f) for f in os.listdir(slozka)
                      if f.endswith(".db.gz")]
        if zalohy:
            nejnovejsi = max(os.path.getmtime(z) for z in zalohy)
            udaje["zaloha_hodin"] = round(
                (datetime.now().timestamp() - nejnovejsi) / 3600, 1)
            udaje["zaloha_pocet"] = len(zalohy)
        else:
            udaje["zaloha_hodin"] = None
            udaje["zaloha_pocet"] = 0

        return udaje

    return _bezpecne(zjisti)[0]


def denni_nalada():
    """
    Podle hodiny vrátí náladu pro pozadí přihlašovací stránky.

    Rozhoduje SERVER, ne JavaScript - pozadí je tak správné hned
    při prvním vykreslení a neprobliká se. Stejný důvod jako u motivu.
    """
    hodina = datetime.now().hour
    if hodina < 6:
        return "noc"
    if hodina < 10:
        return "rano"
    if hodina < 18:
        return "den"
    if hodina < 22:
        return "vecer"
    return "noc"


def pozdrav():
    """
    Pozdrav podle denní doby: "Dobré ráno", "Dobrý den", ...

    Schválně BEZ oslovení jménem. Čeština by chtěla pátý pád ("Petře",
    "Jano") a ten se z uloženého jména odvodit nedá - závisí na rodu,
    který o uživateli nevíme. Je to stejný důvod, proč se u nákupu píše
    "koupil(a)". Jméno má člověk vedle sebe v hlavičce, tak ať radši
    chybí tady, než aby bylo zkomolené.

    Hranice jsou jiné než u denni_nalada(): ta vybírá barvu pozadí, kdežto
    tohle je věta pro člověka. Ve tři ráno je "noc" správné pozadí, ale
    "Dobrou noc" je i správný pozdrav - proto se rozchází jen ráno.
    """
    hodina = datetime.now().hour
    if hodina < 5:
        return "Dobrou noc"
    if hodina < 10:
        return "Dobré ráno"
    if hodina < 18:
        return "Dobrý den"
    if hodina < 22:
        return "Dobrý večer"
    return "Dobrou noc"


def stav_sberu():
    """
    Běží sběr měření? Vrací jen "ok" / "problem" / "nezname".

    Schválně nevrací žádné číslo ani čas: tenhle údaj se ukazuje
    PŘED přihlášením, takže ho vidí kdokoliv na internetu. Barevná
    tečka majiteli stačí, kolemjdoucímu neřekne nic použitelného.
    """
    minuty, chyba = _bezpecne(database.stari_posledniho_mereni)
    if chyba is not None or minuty is None:
        return "nezname"
    return "ok" if minuty <= LIMIT_MERENI_MINUT else "problem"


def stav_zalohy():
    """
    Je záloha databáze čerstvá? Zase jen "ok" / "problem" / "nezname".

    Dívá se na stáří nejnovějšího souboru ve složce záloh. Doma složka
    neexistuje, takže vyjde "nezname" - a to je správně, doma se
    nezálohuje.
    """
    def zjisti():
        slozka = Path(os.path.expanduser(
            getattr(config, "ZALOHY_SLOZKA", "~/zalohy")))
        zalohy = list(slozka.glob("*.db.gz"))
        if not zalohy:
            return None
        nejnovejsi = max(z.stat().st_mtime for z in zalohy)
        return (datetime.now().timestamp() - nejnovejsi) / 3600

    hodiny, chyba = _bezpecne(zjisti)
    if chyba is not None or hodiny is None:
        return "nezname"
    return "ok" if hodiny <= LIMIT_ZALOHY_HODIN else "problem"


def aktualni_prava():
    """
    Práva přihlášeného uživatele, čtená z DATABÁZE - ne ze session.

    Proč z databáze: session vzniká při přihlášení a pak se nemění. Když
    správce někomu přidá právo, ten člověk by o tom nevěděl, dokud by se
    neodhlásil a nepřihlásil - reload stránky nepomůže, protože prohlížeč
    posílá pořád tu samou cookie.

    Je to jeden malý dotaz navíc při každém požadavku. Výsledek si uložíme
    do g, což je úložiště platné po dobu JEDNOHO požadavku - takže i když
    se na práva zeptáme na pěti místech, do databáze se sáhne jednou.

    Když už uživatel neexistuje (správce mu smazal účet), session se
    vyprázdní a pošleme ho na přihlášení.
    """
    if "prava" in g:
        return g.prava

    if "uzivatel_id" not in session:
        g.prava = set()
        return g.prava

    zaznam = database.uzivatel_a_prava(session["uzivatel_id"])
    if zaznam is None:
        session.clear()
        g.prava = set()
    else:
        g.prava = zaznam[1]
    return g.prava


def vyzaduje_prihlaseni(funkce):
    """
    Nálepka pro route, které mají být jen pro přihlášené.

    Použití:
        @app.route("/")
        @vyzaduje_prihlaseni
        def asistent(): ...

    Je to vlastní DEKORÁTOR - stejný princip jako @app.route, jen si ho
    tentokrát píšeme sami. Obalí původní funkci kontrolou: když v session
    není uživatel, místo stránky pošle přesměrování na přihlášení.

    @wraps(funkce) jen zajistí, že si obalená funkce podrží své jméno -
    bez toho by si Flask myslel, že se všechny route jmenují stejně.
    """
    @wraps(funkce)
    def obalena_funkce(*args, **kwargs):
        if "uzivatel" not in session:
            return redirect(url_for("prihlaseni"))
        return funkce(*args, **kwargs)
    return obalena_funkce


def vyzaduje_pravo(tab):
    """
    Nálepka pro route, které smí jen uživatel s právem na daný tab.

        @app.route("/solary")
        @vyzaduje_pravo("solary")
        def solary(): ...

    Oproti vyzaduje_prihlaseni je to o patro výš: dekorátor S PARAMETREM.
    Funguje tak, že vyzaduje_pravo("solary") nejdřív VYROBÍ dekorátor
    (funkci dekorator níž) a teprve ten se přilepí na route. Proto jsou
    tu tři vnořené funkce místo dvou.

    DŮLEŽITÉ: tahle kontrola je ta skutečná ochrana. Skrytí tabu v menu
    je jen pohodlí - kdo zná adresu, může požadavek poslat i tak.
    """
    def dekorator(funkce):
        @wraps(funkce)
        def obalena_funkce(*args, **kwargs):
            if "uzivatel" not in session:
                return redirect(url_for("prihlaseni"))
            if tab not in aktualni_prava():
                # Bez práva pošleme na Asistenta - ten je pro každého.
                return redirect(url_for("asistent"))
            return funkce(*args, **kwargs)
        return obalena_funkce
    return dekorator


@app.context_processor
def spolecna_data():
    """
    Data, která dostane KAŽDÁ šablona automaticky.

    Dřív každá route posílala uzivatel=session.get("uzivatel") zvlášť -
    pětkrát to samé. Context processor to řeší na jednom místě: co vrátí
    tenhle slovník, je vidět ve všech šablonách.

    Práva bereme z aktualni_prava(), tedy z databáze - viz vysvětlení tam.
    """
    return {
        "uzivatel": session.get("uzivatel"),
        "uzivatel_id": session.get("uzivatel_id"),
        "prava": aktualni_prava(),
        "pulka_tabu": PULKA_TABU,
    }


def _cesky_pocet(kolik, jedna, dve_az_ctyri, pet_a_vic):
    """
    Čeština skloňuje podle počtu: 1 minutu, 3 minuty, 5 minut. U jedničky
    se číslo nepíše vůbec - "za minutu" zní líp než "za 1 minutu".
    """
    if kolik == 1:
        return jedna
    if kolik < 5:
        return "%d %s" % (kolik, dve_az_ctyri)
    return "%d %s" % (kolik, pet_a_vic)


def _za_jak_dlouho(sekundy):
    """
    Přeloží počet sekund na text do hlášky: "za sekundu", "za 30 sekund",
    "za minutu", "za 5 minut".

    Zaokrouhluje se NAHORU. Slíbit kratší čekání, než jaké doopravdy platí,
    by znamenalo, že se člověk vrátí a narazí na tutéž hlášku znovu.
    """
    if sekundy < 60:
        return _cesky_pocet(sekundy, "sekundu", "sekundy", "sekund")

    minut = -(-sekundy // 60)  # dělení se zaokrouhlením nahoru
    return _cesky_pocet(minut, "minutu", "minuty", "minut")


# methods=["GET", "POST"] říká, že tahle adresa umí dvě věci:
#   GET  = "ukaž mi formulář"        (když na stránku přijdeš)
#   POST = "tady máš vyplněné údaje" (když odešleš formulář)
# Bez toho seznamu by Flask POST odmítl.
@app.route("/prihlaseni", methods=["GET", "POST"])
def prihlaseni():
    chyba = None

    if request.method == "POST":
        # request.form je slovník s odeslanými poli. Klíče odpovídají
        # atributům name="..." v HTML formuláři.
        jmeno = request.form.get("jmeno", "").strip()
        heslo = request.form.get("heslo", "")

        # Skutečnou adresu návštěvníka sem dosazuje ProxyFix z hlavičky,
        # kterou přidává Caddy. Bez něj by tu byla adresa samotné proxy -
        # pro všechny stejná, takže by strop platil pro celý internet
        # dohromady a první útočník by zamkl všechny ostatní.
        adresa = request.remote_addr or "neznámá"
        zbyva = database.zbyva_blokace(adresa)

        if zbyva:
            # Heslo se tu schválně vůbec neověřuje. Hashování je záměrně
            # pomalé, takže by se opakovanými pokusy dal vytížit procesor
            # serveru i bez sebemenší naděje na uhodnutí hesla.
            chyba = ("Příliš mnoho pokusů o přihlášení. "
                     "Zkus to znovu za %s." % _za_jak_dlouho(zbyva))
        else:
            uzivatel = database.over_uzivatele(jmeno, heslo)

            if uzivatel:
                # Povedlo se - počítadlo chyb té adresy jde pryč, ať se
                # doma nezasekneme kvůli pár překlepům.
                database.zapomen_pokusy(adresa)

                # Do session zapíšeme, kdo je přihlášen. Flask to zabalí
                # do podepsané cookie a prohlížeč ji pošle s každým dalším
                # požadavkem - tím si nás server "pamatuje".
                session["uzivatel"] = uzivatel["jmeno"]
                session["uzivatel_id"] = uzivatel["id"]
                _bezpecne(lambda: database.zaznamenej_prihlaseni(uzivatel["id"]))
                return redirect(url_for("asistent"))

            database.zaznamenej_chybny_pokus(adresa)

            # Schválně neříkáme, jestli je špatně jméno, nebo heslo. Kdybychom
            # rozlišovali, útočník by si mohl ověřit, která jména existují.
            chyba = "Nesprávné jméno nebo heslo."

    return render_template(
        "prihlaseni.html",
        chyba=chyba,
        nalada=denni_nalada(),
        datum_svatek=_bezpecne(svatky.popis_dne)[0],
        pocasi=_bezpecne(lambda: pocasi.predpoved(
            config.POCASI_LAT, config.POCASI_LON))[0],
        misto=getattr(config, "POCASI_MISTO", ""),
        stav_sber=stav_sberu(),
        stav_zaloha=stav_zalohy(),
    )


@app.route("/odhlaseni")
def odhlaseni():
    # Vyprázdní session -> cookie přestane platit -> uživatel je odhlášen.
    session.clear()
    return redirect(url_for("prihlaseni"))


def _bezpecne(nacti):
    """
    Zavolá zadanou funkci a vrátí dvojici (data, chyba).

    Když čtení projde:   vrátí (slovník_dat, None)
    Když spadne:         vrátí (None, "text chyby")

    Díky tomu se o try/except staráme na jednom místě a route dole
    zůstane přehledná. Předání funkce jako parametru (nacti) je
    pythonovský zvyk - funkce se dá poslat dál stejně jako číslo.
    """
    try:
        return nacti(), None
    except Exception as chyba:
        return None, str(chyba)


def _stav_nanoleaf():
    """Přečte Nanoleaf. Vrací (data, chyba) - jedno z toho je vždy None."""
    return _bezpecne(
        lambda: get_nanoleaf_status(config.NANOLEAF_IP, config.NANOLEAF_TOKEN))


def _stav_solax():
    """Přečte soláry. Vrací (data, chyba)."""
    return _bezpecne(
        lambda: get_solax_status(config.SOLAX_DONGLE_IP, config.SOLAX_WIFI_SN))


@app.template_filter("cislo")
def _cislo(hodnota, desetin=1):
    """
    Napíše číslo tak, jak se píše česky: 22 321,4.

    Python sám formátuje anglicky (22,321.4) - čárka po tisících,
    tečka před desetinami. My to potřebujeme obráceně. Nejdřív tedy
    necháme Python udělat anglický tvar a pak oba oddělovače prohodíme;
    pořadí záměn je důležité, jinak by si přepsaly cestu.

    Mezera po tisících je nezlomitelná - jinak by se číslo
    na konci řádku mohlo rozpadnout na dva kusy.

    Filtr se v šabloně používá takhle:  {{ hodnota|cislo }}
                                        {{ hodnota|cislo(2) }}
    """
    return f"{hodnota:,.{desetin}f}".replace(",", "\u00a0").replace(".", ",")


@app.template_filter("cena")
def _cena(hodnota):
    """
    Napíše cenu i s korunami: 35.0 -> '35 Kč', 35.5 -> '35,50 Kč'.

    Celé koruny se píšou bez desetin - "35,00 Kč" u rohlíků vypadá jako
    účetnictví. Halíře se ukážou, jen když nějaké jsou.
    """
    if hodnota is None:
        return ""
    if float(hodnota) == int(hodnota):
        return _cislo(int(hodnota), 0) + " Kč"
    return _cislo(hodnota, 2) + " Kč"


# ---------- Dvě úvodní stránky ----------
#
# Aplikace má dvě půlky a přepíná se mezi nimi domácím tlačítkem
# v navigaci. Nedrží se to v session ani v prohlížeči, ale v ADRESE:
# každá půlka je obyčejný odkaz, takže se dá uložit na plochu telefonu
# a funguje i bez JavaScriptu.
#
#   /            Asistent  - Nákup a osobní hlavička. Má ji každý.
#   /domacnost   Domácnost - zařízení. Jen pro toho, kdo je má.
#
# Kořen aplikace je Asistent schválně: to je půlka, na kterou patří
# každý přihlášený. Domácnost je sekce pro toho, kdo má zařízení.


@app.route("/")
@vyzaduje_prihlaseni
def asistent():
    """Asistent - osobní hlavička a nákupní seznamy. Pro každého stejné."""
    # Datum, svátek a počasí. Dosud to viselo jen na PŘIHLAŠOVACÍ stránce,
    # takže to viděl kolemjdoucí, ale přihlášený člověk ne.
    #
    # Obojí má v pocasi.py mezipaměť (10 a 30 minut), takže se Open-Meteo
    # neptáme při každém načtení stránky.
    venku = _bezpecne(lambda: pocasi.ted(
        config.POCASI_LAT, config.POCASI_LON))[0]
    predpoved = _bezpecne(lambda: pocasi.predpoved(
        config.POCASI_LAT, config.POCASI_LON))[0]
    dnes = predpoved[0] if predpoved else None

    return render_template(
        "asistent.html", aktivni="asistent",
        pozdrav=pozdrav(),
        datum_svatek=_bezpecne(svatky.popis_dne)[0],
        venku=venku, dnes=dnes,
        misto=getattr(config, "POCASI_MISTO", ""),
        seznamy=database.seznamy_uzivatele(session["uzivatel_id"]),
    )


@app.route("/domacnost")
@vyzaduje_prihlaseni
def domacnost():
    """
    Domácnost - od každého zařízení to nejdůležitější.

    Právo tu NENÍ potřeba: stránku otevře každý, ale poskládá se jen
    z toho, na co má právo. Kdo nemá žádné zařízení, uvidí prázdno -
    a to je zatím schválně, viz plán.
    """
    # Čteme jen zařízení, na která má uživatel právo. Nejde jen o úsporu:
    # každé čtení je volání po síti, takže bez téhle podmínky by se čekalo
    # i na data, která se stejně nezobrazí.
    prava = aktualni_prava()

    nanoleaf, nanoleaf_chyba = (
        _stav_nanoleaf() if "nanoleaf" in prava else (None, None))
    solax, solax_chyba = (
        _stav_solax() if "solary" in prava else (None, None))

    return render_template(
        "domacnost.html", aktivni="domacnost",
        nanoleaf=nanoleaf, nanoleaf_chyba=nanoleaf_chyba,
        solax=solax, solax_chyba=solax_chyba,
    )


@app.route("/solary")
@vyzaduje_pravo("solary")
def solary():
    """Detail solární elektrárny: aktuální stav, grafy, historie."""
    solax, solax_chyba = _stav_solax()

    # Historie z databáze pro grafy. Sloupce řádku jsou v pořadí, v jakém
    # je vrací nacti_pro_graf(): 0=cas, 1=vykon_panelu, 2=denni_vyroba,
    # 3=soc, 4=spotreba_domu, 5=tok_site, 6=vykon_baterie.
    #
    # Výkon a baterie mají ÚPLNĚ JINOU stupnici (watty vs. procenta), proto
    # dva samostatné grafy pod sebou, ne jeden se dvěma osami. Graf se dvěma
    # osami y je klasická past: dvě křivky v něm jdou libovolně "posunout"
    # vůči sobě jen změnou měřítka, takže svádí vidět souvislost, která tam není.
    historie = _bezpecne(lambda: database.nacti_pro_graf(hodin=24))[0] or []

    graf_vykon = graf.priprav(
        historie, index_hodnoty=1, klic="vykon", barva="var(--serie-vykon)",
        jednotka="kW", delitel=1000, desetin=1)
    graf_baterie = graf.priprav(
        historie, index_hodnoty=3, klic="baterie", barva="var(--serie-baterie)",
        jednotka="%", desetin=0)
    graf_dum = graf.priprav(
        historie, index_hodnoty=4, klic="dum", barva="var(--tok-dum)",
        jednotka="kW", delitel=1000, desetin=1)

    # Tok sítě jde oběma směry, takže dvě barvy: nad nulou zeleně to,
    # co dodáváme ven, pod nulou fialově to, co si bereme.
    graf_sit = graf.priprav(
        historie, index_hodnoty=5, klic="sit", barva="var(--zelena)",
        barva_zaporna="var(--tok-sit)", jednotka="kW", delitel=1000, desetin=1)

    # Diagram se dá připravit, jen když se solár povedlo přečíst.
    # Bez dat není co kreslit a šablona v tom případě ukáže hlášku.
    diagram_toku = diagram.priprav(solax) if solax else None

    # Kolik slunce zrovna dopadá. Je to z předpovědi počasí, ne z panelů,
    # takže se stránka vykreslí i bez toho - jen se pruh neukáže.
    slunce = _bezpecne(lambda: pocasi.ted(
        config.POCASI_LAT, config.POCASI_LON))[0]

    return render_template(
        "solary.html", aktivni="solary",
        solax=solax, solax_chyba=solax_chyba, diagram_toku=diagram_toku,
        slunce=slunce,
        graf_vykon=graf_vykon, graf_baterie=graf_baterie,
        graf_dum=graf_dum, graf_sit=graf_sit,
        historie=list(reversed(historie))[:20],   # tabulka: nejnovější nahoře
    )


@app.route("/nanoleaf")
@vyzaduje_pravo("nanoleaf")
def nanoleaf():
    """Detail Nanoleaf: stav, rozložení panelů, ovládání."""
    stav, chyba = _bezpecne(lambda: get_nanoleaf_detail(
        config.NANOLEAF_IP, config.NANOLEAF_TOKEN))
    return render_template(
        "nanoleaf.html", aktivni="nanoleaf",
        nanoleaf=stav, nanoleaf_chyba=chyba,
    )


# ---------------------------------------------------------------------------
# Ovládání Nanoleaf.
#
# Zápis do zařízení je POST + redirect, stejně jako u nákupu: GET musí
# zůstat bezpečný. Kdyby zhasnutí světla bylo obyčejný odkaz, stačilo by,
# aby ho prohlížeč načetl na pozadí, a světlo by zhaslo samo od sebe.
# ---------------------------------------------------------------------------

@app.route("/nanoleaf/prepnout", methods=["POST"])
@vyzaduje_pravo("nanoleaf")
def nanoleaf_prepnout():
    """Zapne nebo vypne panely - podle toho, jak svítí teď."""
    stav, chyba = _stav_nanoleaf()
    if stav is not None:
        _bezpecne(lambda: set_nanoleaf_on(
            config.NANOLEAF_IP, config.NANOLEAF_TOKEN, not stav["on"]))
    return redirect(url_for("nanoleaf"))


@app.route("/nanoleaf/jas", methods=["POST"])
@vyzaduje_pravo("nanoleaf")
def nanoleaf_jas():
    """
    Nastaví jas podle posuvníku.

    Umí odpovědět dvěma způsoby:
      - obyčejné odeslání formuláře -> přesměrování zpět na stránku
      - volání z JavaScriptu        -> jen data, stránka se nenačítá znovu

    To druhé je potřeba kvůli náhledu efektu: kdyby se stránka překreslila,
    rozpracovaný náhled by zmizel.
    """
    z_javascriptu = request.headers.get("X-Pozadavek") == "fetch"

    try:
        jas = int(request.form.get("jas", 0))
    except ValueError:
        return (jsonify({"chyba": "neplatná hodnota"}), 400) if z_javascriptu             else redirect(url_for("nanoleaf"))

    nastaveno, chyba = _bezpecne(lambda: set_nanoleaf_brightness(
        config.NANOLEAF_IP, config.NANOLEAF_TOKEN, jas))

    if z_javascriptu:
        if nastaveno is None:
            return jsonify({"chyba": chyba}), 502
        return jsonify({"jas": nastaveno})
    return redirect(url_for("nanoleaf"))


@app.route("/nanoleaf/efekt", methods=["POST"])
@vyzaduje_pravo("nanoleaf")
def nanoleaf_efekt():
    """
    Potvrzení návrhu: přepne efekt a zároveň nastaví jas.

    Obojí naráz proto, že v režimu návrhu se ani jedno do panelů neposílá -
    uživatel si to skládá v prohlížeči a odešle to jedním tlačítkem.

    Pořadí není náhodné: nejdřív efekt, pak jas. Některé efekty si totiž
    jas přenastavují samy, takže kdyby šel jas první, efekt by ho přepsal.
    """
    nazev = request.form.get("efekt", "")
    if nazev:
        _bezpecne(lambda: set_nanoleaf_effect(
            config.NANOLEAF_IP, config.NANOLEAF_TOKEN, nazev))

    if request.form.get("jas"):
        try:
            jas = int(request.form["jas"])
        except ValueError:
            jas = None
        if jas is not None:
            _bezpecne(lambda: set_nanoleaf_brightness(
                config.NANOLEAF_IP, config.NANOLEAF_TOKEN, jas))

    return redirect(url_for("nanoleaf"))


@app.route("/nanoleaf/paleta")
@vyzaduje_pravo("nanoleaf")
def nanoleaf_paleta():
    """
    Vrátí barvy zvoleného efektu jako JSON - pro náhled v prohlížeči.

    Tohle je první adresa, která nevrací STRÁNKU, ale DATA. Používá ji
    JavaScript: uživatel vybere efekt, prohlížeč si sem řekne o barvy
    a nakreslí náhled - a to všechno bez znovunačtení stránky
    a bez jediného příkazu do panelů.

    Je to GET a je to v pořádku: nic se tím nemění, jen se čte.
    """
    nazev = request.args.get("efekt", "")
    if not nazev:
        return jsonify({"chyba": "chybí jméno efektu"}), 400

    paleta, chyba = _bezpecne(lambda: get_nanoleaf_paleta(
        config.NANOLEAF_IP, config.NANOLEAF_TOKEN, nazev))

    if paleta is None:
        return jsonify({"chyba": chyba}), 502
    return jsonify(paleta)


def _seznam_nebo_404(id_seznamu):
    """
    Načte seznam a ověří, že na něj přihlášený uživatel má právo.

    404, ne 403 - stejně jako u položek. Kdo na seznam nemá právo, nemá se
    ani dozvědět, že takové číslo něco znamená.
    """
    seznam = database.seznam_pro_uzivatele(id_seznamu, session["uzivatel_id"])
    if seznam is None:
        abort(404)
    return seznam


def _polozka_nebo_404(id_polozky):
    """
    Najde položku a ověří, že na ni přihlášený uživatel má právo.

    Když nemá, vrací 404 - NE 403. Kdo na cizí seznam nemá právo, nemá se
    ani dozvědět, že taková položka existuje; hláška "sem nesmíš" by sama
    o sobě prozradila, že tam něco je.
    """
    polozka = database.polozka_pro_uzivatele(id_polozky, session["uzivatel_id"])
    if polozka is None:
        abort(404)
    return polozka


def _zpet(id_seznamu, koupeno=False, **hlaska):
    """
    Návrat na seznam, případně s hláškou v adrese.

    koupeno=True nechá rozbalený blok Koupeno. Bez toho by se po každé
    úpravě sbalil a člověk, který vyplňuje ceny, by ho otevíral znovu
    u každé položky. Stav se veze v adrese - <details> si ho sám
    nezapamatuje a JavaScript kvůli tomu psát nebudeme.
    """
    if koupeno:
        hlaska["koupeno"] = 1
    return redirect(url_for("nakup_seznam", id_seznamu=id_seznamu, **hlaska))


@app.route("/nakup")
@vyzaduje_prihlaseni
def nakup():
    """
    Rozcestí: pošle na první seznam, který uživatel má.

    Kdo nemá žádný, uvidí rovnou tady stránku s nabídkou nějaký založit.
    Přesměrovávat ho nemáme kam.
    """
    seznam_id = database.vychozi_seznam(session["uzivatel_id"])
    if seznam_id is None:
        return render_template(
            "nakup.html", aktivni="nakup",
            seznam=None, moje_seznamy=[], chybejici=[], koupene=[],
            k_uklidu=0, caste=[],
            chyba=request.args.get("chyba"), zprava=request.args.get("zprava"),
        )
    return redirect(url_for("nakup_seznam", id_seznamu=seznam_id))


@app.route("/nakup/<int:id_seznamu>")
@vyzaduje_prihlaseni
def nakup_seznam(id_seznamu):
    """Jeden nákupní seznam."""
    seznam = _seznam_nebo_404(id_seznamu)
    polozky = database.seznam_nakupu(id_seznamu, session["uzivatel_id"])

    # Rozdělíme rovnou tady, ať to šablona nemusí filtrovat dvakrát.
    chybejici = [p for p in polozky if not p["koupeno"]]
    koupene = [p for p in polozky if p["koupeno"]]

    return render_template(
        "nakup.html", aktivni="nakup",
        seznam=seznam,
        moje_seznamy=database.seznamy_uzivatele(session["uzivatel_id"]),
        chybejici=chybejici, koupene=koupene,
        # Kolik odškrtnutých položek tenhle člověk doopravdy uklidí -
        # ať tlačítko neslibuje víc, než udělá.
        k_uklidu=sum(1 for p in koupene if p["smi_upravit"]),
        caste=_bezpecne(lambda: database.caste_polozky(id_seznamu))[0] or [],
        clenove=database.clenove(id_seznamu),
        vyuctovani=database.vyuctovani(id_seznamu) if koupene else None,
        otevrit_koupene=request.args.get("koupeno") == "1",
        chyba=request.args.get("chyba"), zprava=request.args.get("zprava"),
    )


# Hláška, když někdo sáhne na cizí položku. Tlačítka se u cizích schovávají,
# takže se sem člověk běžně nedostane - je to pojistka pro případ, že by
# formulář odešel z jiné stránky nebo ze staré, mezitím změněné.
NENI_TVOJE = "Upravovat a mazat můžeš jen položky, které jsi přidal."


# ---------------------------------------------------------------------------
# Akce nad seznamem.
#
# Adresy mají dva tvary a je v tom systém:
#     /nakup/<číslo>/...          <číslo> je SEZNAM
#     /nakup/polozka/<číslo>/...  <číslo> je POLOŽKA
# Bez toho oddělení by /nakup/7/smazat znamenalo jednou seznam a jednou
# položku - a na takové adrese se dřív nebo později někdo splete.
#
# Všechny jsou POST, ne GET - a je to důležité pravidlo, ne formalita:
# GET musí být "bezpečný", tedy nic neměnit. Kdyby odškrtnutí položky bylo
# GET, stačilo by, aby prohlížeč (nebo jeho přednačítání, nebo antivirus)
# ten odkaz otevřel na pozadí, a položka by se odškrtla sama od sebe.
#
# Každá akce končí redirectem zpátky na seznam. Tomu se říká vzorec
# POST -> redirect -> GET a řeší otravný problém: kdyby route po POSTu
# rovnou vykreslila stránku, tak by po stisku F5 prohlížeč nabídl
# "odeslat formulář znovu" a položka by se přidala podruhé.
# ---------------------------------------------------------------------------

@app.route("/nakup/novy", methods=["POST"])
@vyzaduje_prihlaseni
def nakup_novy_seznam():
    """Založí nový seznam. Zakladatel je jeho vlastníkem."""
    ok, vysledek = database.vytvor_seznam(
        request.form.get("nazev", ""), session["uzivatel_id"])
    if not ok:
        return redirect(url_for("nakup", chyba=vysledek))
    return _zpet(vysledek, zprava="Seznam založen.")


@app.route("/nakup/<int:id_seznamu>/prejmenovat", methods=["POST"])
@vyzaduje_prihlaseni
def nakup_prejmenovat(id_seznamu):
    _seznam_nebo_404(id_seznamu)
    ok, hlaska = database.prejmenuj_seznam(
        id_seznamu, session["uzivatel_id"], request.form.get("nazev", ""))
    return _zpet(id_seznamu, **({"zprava": hlaska} if ok else {"chyba": hlaska}))


@app.route("/nakup/<int:id_seznamu>/smazat", methods=["POST"])
@vyzaduje_prihlaseni
def nakup_smazat_seznam(id_seznamu):
    _seznam_nebo_404(id_seznamu)
    ok, hlaska = database.smaz_seznam(id_seznamu, session["uzivatel_id"])
    if ok:
        return redirect(url_for("nakup", zprava=hlaska))
    return _zpet(id_seznamu, chyba=hlaska)


@app.route("/nakup/pripojit", methods=["POST"])
@vyzaduje_prihlaseni
def nakup_pripojit():
    """Připojení k cizímu seznamu podle kódu pozvánky."""
    ok, hlaska, id_seznamu = database.pripoj_kodem(
        request.form.get("kod", ""), session["uzivatel_id"])

    # Když seznam známe, pošleme člověka rovnou na něj - i v případě
    # "už na něm jsi". Nechat ho stát na místě s chybou by bylo zbytečně
    # nevlídné, když je vlastně tam, kam chtěl.
    if id_seznamu is None:
        return redirect(url_for("nakup", chyba=hlaska))
    return _zpet(id_seznamu, **({"zprava": hlaska} if ok else {"chyba": hlaska}))


@app.route("/nakup/<int:id_seznamu>/novy-kod", methods=["POST"])
@vyzaduje_prihlaseni
def nakup_novy_kod(id_seznamu):
    _seznam_nebo_404(id_seznamu)
    ok, hlaska = database.novy_kod_seznamu(id_seznamu, session["uzivatel_id"])
    return _zpet(id_seznamu, **({"zprava": hlaska} if ok else {"chyba": hlaska}))


@app.route("/nakup/<int:id_seznamu>/zvani", methods=["POST"])
@vyzaduje_prihlaseni
def nakup_zvani(id_seznamu):
    """Smí členové zvát další lidi? Rozhoduje vlastník."""
    _seznam_nebo_404(id_seznamu)
    ok, hlaska = database.nastav_zvani(
        id_seznamu, session["uzivatel_id"],
        request.form.get("povolit") == "1")
    return _zpet(id_seznamu, **({"zprava": hlaska} if ok else {"chyba": hlaska}))


@app.route("/nakup/<int:id_seznamu>/odebrat/<int:id_clena>", methods=["POST"])
@vyzaduje_prihlaseni
def nakup_odebrat_clena(id_seznamu, id_clena):
    _seznam_nebo_404(id_seznamu)
    ok, hlaska = database.odeber_clena(
        id_seznamu, session["uzivatel_id"], id_clena)
    return _zpet(id_seznamu, **({"zprava": hlaska} if ok else {"chyba": hlaska}))


@app.route("/nakup/<int:id_seznamu>/odejit", methods=["POST"])
@vyzaduje_prihlaseni
def nakup_odejit(id_seznamu):
    _seznam_nebo_404(id_seznamu)
    ok, hlaska = database.opust_seznam(id_seznamu, session["uzivatel_id"])
    if ok:
        # Na seznam už právo nemá, takže zpátky na něj poslat nejde.
        return redirect(url_for("nakup", zprava=hlaska))
    return _zpet(id_seznamu, chyba=hlaska)


@app.route("/nakup/<int:id_seznamu>/pridat", methods=["POST"])
@vyzaduje_prihlaseni
def nakup_pridat(id_seznamu):
    _seznam_nebo_404(id_seznamu)
    database.pridej_polozku(
        id_seznamu,
        request.form.get("text", ""),
        session.get("uzivatel"),
        session["uzivatel_id"],
        request.form.get("mnozstvi", ""),
    )
    return _zpet(id_seznamu)


@app.route("/nakup/<int:id_seznamu>/uklidit", methods=["POST"])
@vyzaduje_prihlaseni
def nakup_uklidit(id_seznamu):
    """Uklidí odškrtnuté položky - to, co uživatel smí smazat."""
    _seznam_nebo_404(id_seznamu)
    database.smaz_koupene(id_seznamu, session["uzivatel_id"])
    return _zpet(id_seznamu)


# <int:id_polozky> je proměnná část adresy. Flask z /nakup/polozka/7/prepnout
# vytáhne sedmičku a předá ji funkci jako parametr. To "int:" navíc hlídá,
# že to je opravdu číslo - když někdo zkusí .../abc/prepnout, Flask vrátí
# 404 a naše funkce se vůbec nespustí.
@app.route("/nakup/polozka/<int:id_polozky>/prepnout", methods=["POST"])
@vyzaduje_prihlaseni
def nakup_prepnout(id_polozky):
    # Odškrtnout smí každý, kdo položku vidí - stačí tedy branka.
    polozka = _polozka_nebo_404(id_polozky)
    database.prepni_koupeno(id_polozky, session.get("uzivatel"),
                            session["uzivatel_id"])
    # Když se položka vracela zpátky mezi chybějící, člověk stál v bloku
    # Koupeno - ať mu pod rukama nezmizí.
    return _zpet(polozka["seznam_id"], koupeno=polozka["koupeno"])


@app.route("/nakup/polozka/<int:id_polozky>/upravit", methods=["POST"])
@vyzaduje_prihlaseni
def nakup_upravit(id_polozky):
    polozka = _polozka_nebo_404(id_polozky)
    if not polozka["smi_upravit"]:
        return _zpet(polozka["seznam_id"], koupeno=polozka["koupeno"],
                     chyba=NENI_TVOJE)

    database.uprav_polozku(
        id_polozky,
        request.form.get("text", ""),
        request.form.get("mnozstvi", ""),
    )
    return _zpet(polozka["seznam_id"], koupeno=polozka["koupeno"])


@app.route("/nakup/polozka/<int:id_polozky>/cena", methods=["POST"])
@vyzaduje_prihlaseni
def nakup_cena(id_polozky):
    """Kolik položka stála. Vyplňuje ji ten, kdo ji koupil."""
    polozka = _polozka_nebo_404(id_polozky)
    ok, hlaska = database.nastav_cenu(
        id_polozky, session["uzivatel_id"], request.form.get("cena", ""))
    if ok:
        return _zpet(polozka["seznam_id"], koupeno=True)
    return _zpet(polozka["seznam_id"], koupeno=True, chyba=hlaska)


@app.route("/nakup/polozka/<int:id_polozky>/smazat", methods=["POST"])
@vyzaduje_prihlaseni
def nakup_smazat(id_polozky):
    polozka = _polozka_nebo_404(id_polozky)
    if not polozka["smi_upravit"]:
        return _zpet(polozka["seznam_id"], koupeno=polozka["koupeno"],
                     chyba=NENI_TVOJE)

    database.smaz_polozku(id_polozky)
    return _zpet(polozka["seznam_id"], koupeno=polozka["koupeno"])


# ===========================================================================
# Správa uživatelů
#
# Kdo má právo "sprava", spravuje ostatní. Žádné zvláštní role - Správa
# je prostě další tab jako Soláry nebo Nákup.
#
# Hlášky (chyba/zprava) se předávají přes query parametr v adrese. Je to
# nejjednodušší způsob, jak přežít redirect po POSTu; Flask má na tohle
# i hezčí nástroj (flash zprávy), ale ten by sem přinesl nový koncept.
# ===========================================================================

@app.route("/profil", methods=["GET", "POST"])
@vyzaduje_prihlaseni
def profil():
    """
    Můj profil - vlastní údaje a změna hesla.

    Chrání ho JEN přihlášení, ne právo na tab. Kdyby vyžadoval právo,
    běžný uživatel by si heslo zase nezměnil a přesně to tu řešíme.
    """
    chyba = zprava = None

    if request.method == "POST":
        nove = request.form.get("nove", "")

        # Shodu obou nových hesel zkontrolovat DŘÍV, než se cokoliv změní -
        # jinak by se při překlepu heslo stejně přepsalo.
        if nove != request.form.get("nove2", ""):
            chyba = "Nová hesla se neshodují."
        else:
            ok, duvod = database.zmen_heslo_s_overenim(
                session["uzivatel_id"], request.form.get("stare", ""), nove)
            chyba, zprava = (None, "Heslo změněno.") if ok else (duvod, None)

    return render_template(
        "profil.html", aktivni="profil",
        udaje=_bezpecne(lambda: database.udaje_uzivatele(
            session["uzivatel_id"]))[0],
        chyba=chyba, zprava=zprava,
        popisy_tabu=POPISY_TABU,
    )


@app.route("/sprava")
@vyzaduje_pravo("sprava")
def sprava():
    """Seznam účtů, jejich práva a zakládání nových."""
    return render_template(
        "sprava.html", aktivni="sprava",
        ucty=database.uzivatele_s_pravy(),
        vsechny_taby=database.VSECHNY_TABY,
        popisy_tabu=POPISY_TABU,
        muj_id=session.get("uzivatel_id"),
        stav=podrobny_stav(),
        # Adresu bereme z požadavku, ne z configu - Flask ji zná a díky
        # ProxyFixu je i za Caddy správná (https, skutečná doména).
        adresa=request.url_root.rstrip("/"),
        qr_kod=_bezpecne(lambda: qr.qr_pro_svg(request.url_root.rstrip("/")))[0],
        chyba=request.args.get("chyba"),
        zprava=request.args.get("zprava"),
    )


@app.route("/sprava/pridat", methods=["POST"])
@vyzaduje_pravo("sprava")
def sprava_pridat():
    jmeno = request.form.get("jmeno", "").strip()
    heslo = request.form.get("heslo", "")

    if not jmeno:
        return redirect(url_for("sprava", chyba="Jméno nesmí být prázdné."))
    if len(heslo) < 6:
        return redirect(url_for("sprava", chyba="Heslo musí mít aspoň 6 znaků."))

    if database.vytvor_uzivatele(jmeno, heslo):
        return redirect(url_for(
            "sprava", zprava=f"Účet {jmeno} vytvořen (zatím jen Nákup)."))
    return redirect(url_for("sprava", chyba=f"Účet {jmeno} už existuje."))


@app.route("/sprava/<int:id_uzivatele>/prava", methods=["POST"])
@vyzaduje_pravo("sprava")
def sprava_prava(id_uzivatele):
    # getlist, ne get: zaškrtávátek se stejným name je víc a chceme
    # VŠECHNA zaškrtnutá. Nezaškrtnutá se neodešlou vůbec - proto stačí
    # vzít, co přišlo, a zbytek se odebere.
    taby = request.form.getlist("tab")

    ok, chyba = database.nastav_prava(id_uzivatele, taby)
    if not ok:
        return redirect(url_for("sprava", chyba=chyba))
    return redirect(url_for("sprava", zprava="Práva uložena."))


@app.route("/sprava/<int:id_uzivatele>/heslo", methods=["POST"])
@vyzaduje_pravo("sprava")
def sprava_heslo(id_uzivatele):
    ok, chyba = database.zmen_heslo(id_uzivatele, request.form.get("heslo", ""))
    if not ok:
        return redirect(url_for("sprava", chyba=chyba))
    return redirect(url_for("sprava", zprava="Heslo změněno."))


@app.route("/sprava/<int:id_uzivatele>/smazat", methods=["POST"])
@vyzaduje_pravo("sprava")
def sprava_smazat(id_uzivatele):
    # Pojistka proti sebevraždě. Databáze hlídá "poslední správce",
    # tohle navíc brání i tomu, aby ses smazal, když jsou správci dva.
    if id_uzivatele == session.get("uzivatel_id"):
        return redirect(url_for("sprava", chyba="Sám sebe smazat nemůžeš."))

    ok, chyba = database.smaz_uzivatele(id_uzivatele)
    if not ok:
        return redirect(url_for("sprava", chyba=chyba))
    return redirect(url_for("sprava", zprava="Účet smazán."))


if __name__ == "__main__":
    # debug=True = při chybě ukáže podrobnosti a po změně kódu sám restartuje.
    # V ostrém provozu VYPNOUT (přijde na řadu ve fázi hostingu).
    app.run(debug=True)
