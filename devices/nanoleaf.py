"""
Čtení stavu Nanoleaf panelů.

Nanoleaf má REST API přímo v zařízení — mluvíme s ním po domácí síti,
žádný cloud, žádný internet. Adresa vypadá takto:

    http://<IP-panelu>:16021/api/v1/<token>/

ÚKOL A (přijde na řadu jako další krok — píšeme společně):
    get_nanoleaf_status(ip, token) -> dict se stavem
    (zapnuto/vypnuto, jas, aktuální efekt)
"""

# TODO: import requests a implementace get_nanoleaf_status()
