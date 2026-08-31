"""
Čtení stavu solární elektrárny SolaX — LOKÁLNĚ z Wi-Fi dongle.

Původní plán počítal s cloudem, ale ukázalo se, že dongle má vlastní
API přímo na domácí síti (adresa 10.0.0.33). To je pro nás lepší:
žádná závislost na cloudu SolaXu, data jdou přímo ze zařízení.

Jak se s ním mluví:
    POST http://<IP>/
    tělo: optType=ReadRealTimeData&pwd=<registrační číslo dongle>

Dongle odpoví JSONem, kde je pole "Data" o 300 číslech. Co které číslo
znamená, není nikde oficiálně popsané — museli jsme to odvodit (třífázová
napětí ~230 V, frekvence ~50 Hz, součet výkonů fází). Proto níže ta tabulka
indexů: je to naše mapa, ne oficiální dokumentace.

DŮLEŽITÉ: dongle je levné embedded zařízení a v HTTP hlavičce lže o délce
odpovědi (Content-Length neodpovídá skutečnosti). Knihovna requests je na to
přísná a spojení by shodila. Proto tu čteme přes holý socket a bereme vše,
co přijde, dokud spojení samo neskončí.

ZÁPORNÁ ČÍSLA: dongle posílá 16bitová celá čísla bez znaménka, ale některé
hodnoty (tok sítě, výkon baterie) můžou být záporné. Zapisují se "odspodu":
-1 se pošle jako 65535, -90 jako 65446. Bez převodu bys u baterie neviděl
rozdíl mezi nabíjením a vybíjením — viz funkce _se_znamenkem() níže.
"""

import socket
import json

# ---------------------------------------------------------------------------
# Mapa indexů v poli "Data"
# ---------------------------------------------------------------------------
# Odvozeno z reálných hodnot, ověřeno třemi nezávislými způsoby:
#  - fyzikou (fázová napětí ~230 V, frekvence 50 Hz, součet fází 6+7+8 == index 9)
#  - porovnáním se snímkem obrazovky ze SolaX aplikace
#  - dopočtem: platí "střídač − síť = dům" a přírůstky denních počitadel sedí
#    na to, kolik energie za tu dobu skutečně proteklo
# Platí pro třífázový měnič (type 14).
#
# POZOR na časový posun: SolaX aplikace čte z cloudu, kam dongle nahrává
# jen jednou za ~5 minut. Při porovnávání "naživo" tedy aplikace ukazuje
# stav o několik minut starší — čísla nesmí sedět na jednotku, ale musí
# odpovídat tomu, co bylo před chvílí.

# --- Okamžité hodnoty [W] ---
IDX_VYKON_FAZE = (6, 7, 8)     # výkon jednotlivých fází
IDX_VYKON_AC = 9               # celkový výkon, který střídač dodává
IDX_VYKON_MPPT1 = 14           # výkon 1. řetězce panelů
IDX_VYKON_MPPT2 = 15           # výkon 2. řetězce panelů
IDX_FREKVENCE = 16             # frekvence sítě ×100 [Hz]
IDX_TOK_SITE = 34              # tok sítě, 32bit (druhá polovina je v 35)
IDX_VYKON_BATERIE = 41         # výkon baterie
IDX_SPOTREBA_DOMU = 47         # kolik právě spotřebovává dům

# --- Stav baterie ---
IDX_BATERIE_SOC = 103          # nabití [%]
IDX_BATERIE_ZBYVA = 106        # zbývající energie ×10 [kWh]

# --- Denní počitadla (o půlnoci se vynulují) ---
IDX_DENNI_STRIDAC = 70         # co za dnešek vydal střídač ×10 [kWh]
IDX_DENNI_VYBITO = 78          # vybito z baterie ×10 [kWh]
IDX_DENNI_NABITO = 79          # nabito do baterie ×10 [kWh]
IDX_DENNI_VYROBA = 82          # výroba panelů ×10 [kWh]
IDX_DENNI_DODAVKA = 90         # dodáno do sítě ×100 [kWh]
IDX_DENNI_ODBER = 92           # odebráno ze sítě ×100 [kWh]

# --- Celoživotní ---
IDX_CELKOVA_VYROBA = 68        # výroba od začátku, 32bit, ×10 [kWh]

# ZNAMÉNKA u toku sítě a výkonu baterie (odvozeno z reálných stavů):
#   síť     kladné = dodáváme přetoky do sítě,  záporné = bereme ze sítě
#   baterie kladné = nabíjí se,                 záporné = vybíjí se
# Přesně tohle určuje, kterým směrem se v diagramu toku nakreslí šipka.

# DENNÍ SPOTŘEBU DOMU dongle neposílá — v poli prostě není. SolaX aplikace
# si ji taky jen dopočítává a my to děláme stejně (viz get_solax_status):
#     spotřeba = odběr ze sítě + výstup střídače − dodávka do sítě
# Ověřeno proti aplikaci: 13,03 + 4,20 − 0,04 = 17,19 kWh. Sedí.


def _se_znamenkem(hodnota):
    """
    Přeloží 16bitové číslo z dongle na kladné nebo záporné.

    Dongle nemá pro mínus zvláštní zápis — celý rozsah 0..65535 se dělí
    napůl. Co je nad 32767, je ve skutečnosti záporné a od hodnoty se
    odečte 65536:  65535 -> -1,  63405 -> -2131.

    (Odborně se tomu říká dvojkový doplněk. Používá to skoro každé
     zařízení, které posílá čísla po drátě.)
    """
    return hodnota - 65536 if hodnota > 32767 else hodnota


def _se_znamenkem32(data, index):
    """
    Poskládá 32bitové číslo ze dvou sousedních položek pole.

    Na zadaném indexu je spodní polovina čísla, hned za ní horní. Horní
    se vynásobí 65536 a přičte — a pak platí totéž pravidlo o záporných
    číslech, jen s větší hranicí. Odběr 5342 W tak přijde jako dvojice
    60194 a 65535.
    """
    cislo = data[index] + data[index + 1] * 65536
    return cislo - 2**32 if cislo >= 2**31 else cislo


def _precti_syrova_data(ip, pwd):
    """
    Pošle dotaz na dongle a vrátí rozparsovaný JSON (dict).

    Čte přes holý socket, protože dongle má rozbitou Content-Length hlavičku
    (viz vysvětlení v úvodu souboru). requests.post() by tu spadl.
    """
    telo = f"optType=ReadRealTimeData&pwd={pwd}"
    dotaz = (
        f"POST / HTTP/1.1\r\n"
        f"Host: {ip}\r\n"
        f"Content-Type: application/x-www-form-urlencoded\r\n"
        f"Content-Length: {len(telo)}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
        f"{telo}"
    )

    spojeni = socket.socket()
    spojeni.settimeout(8)
    spojeni.connect((ip, 80))
    spojeni.sendall(dotaz.encode())

    # Bereme všechno až do konce spojení, nespoléháme na Content-Length.
    odpoved = b""
    try:
        while True:
            kus = spojeni.recv(4096)
            if not kus:
                break
            odpoved += kus
    except socket.timeout:
        pass
    finally:
        spojeni.close()

    # Odpověď je "hlavičky\r\n\r\ntělo". Nás zajímá jen tělo za prázdným řádkem.
    telo_odpovedi = odpoved.decode("utf-8", errors="replace").split("\r\n\r\n", 1)[1]
    return json.loads(telo_odpovedi)


def get_solax_status(ip, pwd):
    """
    Zjistí aktuální stav solární elektrárny.

    Vrací slovník ve třech skupinách:

    OKAMŽITÉ [W] — co se děje právě teď, z tohohle se kreslí diagram toku:
        vykon_panelu    3650   kolik vyrábějí panely (vždy 0 nebo víc)
        vykon_stridace  1832   kolik vydává střídač
        spotreba_domu   1210   kolik spotřebovává dům
        tok_site       -5342   ZÁPORNÉ = bereme ze sítě, kladné = dodáváme
        vykon_baterie  -2131   ZÁPORNÉ = vybíjí se, kladné = nabíjí se
        mppt1 / mppt2          výkon jednotlivých řetězců panelů
        frekvence       50.04  frekvence sítě [Hz]

    BATERIE:
        baterie_soc     69     nabití [%]
        baterie_zbyva   7.9    zbývající energie [kWh]

    DNEŠEK [kWh] — počitadla, o půlnoci se vynulují:
        denni_vyroba    28.6   vyrobily panely
        denni_spotreba  17.19  spotřeboval dům (dopočítané, viz výše)
        denni_odber     13.03  odebráno ze sítě
        denni_dodavka    0.04  dodáno do sítě
        denni_nabito     0.0   nabito do baterie
        denni_vybito     3.3   vybito z baterie
        denni_stridac    4.2   vydal střídač
        celkova_vyroba  22321  vyrobily panely od začátku

    Rychlá kontrola, jestli čísla dávají smysl (platí do pár desítek wattů,
    což jsou ztráty a zaokrouhlení):
        vykon_stridace - tok_site == spotreba_domu
    """
    d = _precti_syrova_data(ip, pwd)
    data = d["Data"]

    mppt1 = data[IDX_VYKON_MPPT1]
    mppt2 = data[IDX_VYKON_MPPT2]

    # Dělíme deseti (resp. stem), protože SolaX ukládá kWh jako celé číslo
    # ×10 nebo ×100: 286 znamená 28,6 kWh, 1303 znamená 13,03 kWh. Proč tak?
    # Celé číslo se po drátě přenese bez chyb, desetinné by se muselo
    # zaokrouhlovat. SOC je rovnou v procentech.
    denni_odber = data[IDX_DENNI_ODBER] / 100
    denni_dodavka = data[IDX_DENNI_DODAVKA] / 100
    denni_stridac = data[IDX_DENNI_STRIDAC] / 10

    return {
        # okamžité
        "vykon_panelu": mppt1 + mppt2,
        "vykon_stridace": _se_znamenkem(data[IDX_VYKON_AC]),
        "spotreba_domu": _se_znamenkem(data[IDX_SPOTREBA_DOMU]),
        "tok_site": _se_znamenkem32(data, IDX_TOK_SITE),
        "vykon_baterie": _se_znamenkem(data[IDX_VYKON_BATERIE]),
        "mppt1": mppt1,
        "mppt2": mppt2,
        "frekvence": data[IDX_FREKVENCE] / 100,
        # baterie
        "baterie_soc": data[IDX_BATERIE_SOC],
        "baterie_zbyva": data[IDX_BATERIE_ZBYVA] / 10,
        # dnešek
        "denni_vyroba": data[IDX_DENNI_VYROBA] / 10,
        "denni_spotreba": round(denni_odber + denni_stridac - denni_dodavka, 2),
        "denni_odber": denni_odber,
        "denni_dodavka": denni_dodavka,
        "denni_nabito": data[IDX_DENNI_NABITO] / 10,
        "denni_vybito": data[IDX_DENNI_VYBITO] / 10,
        "denni_stridac": denni_stridac,
        "celkova_vyroba": _se_znamenkem32(data, IDX_CELKOVA_VYROBA) / 10,
    }
