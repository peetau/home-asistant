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
SOLAX_WIFI_SN = "sem-patri-SN"    # sériové číslo Wi-Fi modulu měniče
