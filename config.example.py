"""
ŠABLONA konfigurace — tenhle soubor JE v Gitu, ale neobsahuje žádné reálné údaje.

Jak se používá:
  1) Zkopíruj tenhle soubor a pojmenuj kopii `config.py`
  2) V `config.py` vyplň skutečné hodnoty
  3) `config.py` je v .gitignore, takže se nikdy nedostane na GitHub

Proč to takhle? Aby kdokoliv (i ty za půl roku na jiném počítači) viděl,
JAKÉ údaje projekt potřebuje, aniž by se ty údaje samotné povalovaly na internetu.
"""

# --- Nanoleaf (lokální zařízení v domácí síti) ---
NANOLEAF_IP = "192.168.0.0"      # IP adresa panelu v tvé domácí síti
NANOLEAF_TOKEN = "sem-patri-token"  # token vygenerovaný podržením tlačítka napájení

# --- SolaX (cloudové API měniče) ---
SOLAX_TOKEN = "sem-patri-token"   # token ze SolaX Cloud
SOLAX_DONGLE_IP = "192.168.0.0"   # IP Wi-Fi dongle v domácí síti (u SolaXu se čte lokálně, ne z cloudu)
SOLAX_WIFI_SN = "sem-patri-SN"    # sériové číslo Wi-Fi modulu měniče

# --- Podpisovy klic pro prihlasovaci cookie (Flask session) ---
# Vygeneruj si vlastni nahodny:
#     python -c "import secrets; print(secrets.token_hex(32))"
#
# POZOR: kazde nasazeni ma SVUJ vlastni klic. Vyvojovy klic se na server
# NEKOPIRUJE - kdyby jeden z pocitacu nekdo ziskal, mohl by si podvrhnout
# prihlaseni i na tom druhem. Na serveru si vygeneruj novy.
SECRET_KEY = "sem-patri-nahodny-retezec"

# --- Slozka se zalohami databaze (jen na serveru) ---
# Podle stari nejnovejsiho souboru se na prihlasovaci strance ukazuje,
# jestli zalohovani bezi. Doma tahle slozka neexistuje a nic se nedeje -
# indikator pak jen ukaze "neznamo".
ZALOHY_SLOZKA = "~/zalohy"
