"""
Vstupní bod projektu — tenhle soubor se spouští:

    python main.py

Zatím jen ověřuje, že kostra projektu funguje a že je vyplněný config.
Postupně sem budeme přidávat volání jednotlivých zařízení.
"""

import config


def main():
    print("=== Domácí asistent ===")
    print()

    # Zatím jen kontrola, jestli už jsou vyplněné reálné údaje v config.py.
    # Až budou, přidáme sem skutečné čtení ze zařízení.
    if "sem-patri" in config.NANOLEAF_TOKEN:
        print("Nanoleaf: token zatím není vyplněný v config.py")
    else:
        print(f"Nanoleaf: config připraven (IP {config.NANOLEAF_IP})")

    if "sem-patri" in config.SOLAX_TOKEN:
        print("SolaX:    token zatím není vyplněný v config.py")
    else:
        print("SolaX:    config připraven")

    print()
    print("Další krok: Úkol A — čtení stavu Nanoleaf.")


# Tahle podmínka znamená: "spusť main() jen když se soubor spouští přímo,
# ne když ho někdo jen importuje." Je to běžná pythonovská konvence.
if __name__ == "__main__":
    main()
