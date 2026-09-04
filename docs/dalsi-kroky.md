# Další kroky

Věci, na které jsme narazili a odložili je. **Není to plán** — ten je
v [`plan.md`](plan.md). Tohle je odkladiště, ať nezapadnou.

Co odtud přešlo mezi podmínky otevření veřejnosti, tady zůstává i tak:
plán říká *že* se to musí udělat, tenhle soubor *jak*.

## Výkon a provoz stránek

### Stránka Soláry je velká (284 kB)
**Priorita: střední.** Grafy kreslí ke každému naměřenému bodu neviditelný
kroužek s bublinou, aby šla hodnota přečíst po najetí myší. Při měření po
pěti minutách to je 288 bodů za den, krát čtyři grafy — přes tisíc kroužků
na stránce.

Samo o sobě by to nevadilo, jenže stránka se obnovuje každých 30 sekund.
Kdo ji nechá otevřenou na mobilních datech, protočí za hodinu kolem 34 MB.

Přišlo se na to až ve chvíli, kdy sběrač poprvé naběhal celý den — do té
doby bylo bodů pár desítek a nebylo to poznat.

Co s tím:
- kroužky kreslit jen u části bodů (na dotyk se stejně nedá trefit každý)
- nebo data pro graf prořídit — na 720 bodů šířky je 288 hodnot zbytečně
  jemné rozlišení
- nebo obnovovat řidčeji, případně jen tu část stránky, která se mění

### Přehled se obnovuje celý každých 10 sekund
Je to **položka 2 v [`plan.md`](plan.md)**, ne odložená věc — zapsané tady,
protože je to stejná rodina problému jako Soláry výš. Pro člověka, který má
jen Nákup, se na Přehledu nic živého neděje a překreslovat ho nemá důvod.

## Provoz serveru

### Y520 místo domácího PC jako Tailscale průchod
Teď drží spojku k zařízením hlavní počítač. Y520 by bral míň proudu
a nerestartoval se při práci. Postup je stejný jako u desktopu.

### Druhá adresa `asistent.` (bez překlepu)
Doména běží na `asistant.pepacodes.cz`. Kdyby vadilo, dá se přidat
`A` záznam pro `asistent.` a v Caddy nechat obojí.

## Rozvoj

- portfolio na `pepacodes.cz` — přidá se jako další blok v Caddy
- e-shop — dostane vlastní server
- další zařízení = další tab (viz `VSECHNY_TABY` v `database.py`)
