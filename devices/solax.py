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
"""

import socket
import json

# Mapa indexů v poli "Data". Odvozeno z reálných hodnot, ověřeno součtem
# fázových výkonů (index 6+7+8 == index 9). Platí pro třífázový měnič (type 14).
IDX_VYKON_FAZE = (6, 7, 8)     # výkon jednotlivých fází [W]
IDX_VYKON_AC = 9              # celkový střídavý výkon do sítě/domu [W]
IDX_VYKON_MPPT1 = 14          # výkon 1. řetězce panelů [W]
IDX_VYKON_MPPT2 = 15          # výkon 2. řetězce panelů [W]
IDX_FREKVENCE = 16           # frekvence sítě ×100 [Hz]


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

    Vrací slovník:
        {
            "vykon_panelu": 6238,   # co právě teď vyrábějí panely [W]
            "vykon_do_site": 1832,  # co teče do sítě/domu [W]
            "mppt1": 3650,          # výkon 1. řetězce panelů [W]
            "mppt2": 2588,          # výkon 2. řetězce panelů [W]
            "frekvence": 50.04,     # frekvence sítě [Hz]
        }

    (Denní a celkovou výrobu zatím nečteme — jejich index v poli ještě
     musíme ověřit porovnáním s hodnotou v SolaX aplikaci.)
    """
    d = _precti_syrova_data(ip, pwd)
    data = d["Data"]

    mppt1 = data[IDX_VYKON_MPPT1]
    mppt2 = data[IDX_VYKON_MPPT2]

    return {
        "vykon_panelu": mppt1 + mppt2,
        "vykon_do_site": data[IDX_VYKON_AC],
        "mppt1": mppt1,
        "mppt2": mppt2,
        "frekvence": data[IDX_FREKVENCE] / 100,
    }
