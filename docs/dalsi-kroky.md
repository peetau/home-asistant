# Další kroky

Seznam věcí, na které jsme narazili a odložili je. Není to plán, jen ať
nezapadnou.

## Bezpečnost

### Limit pokusů o přihlášení
**Priorita: vysoká.** Přihlašovací formulář je veřejně na internetu
a nemá žádný strop na počet pokusů — kdokoliv může zkoušet hesla
donekonečna. Hashování hesel je schválně pomalé, takže útok není snadný,
ale bránit se tomu nijak nebráníme.

Co s tím:
- počítat neúspěšné pokusy podle jména i podle IP adresy
- po několika pokusech krátká prodleva, po dalších delší
- pozor, ať se tím nedá vyřadit z provozu poctivý uživatel (útočník by
  mohl schválně zkoušet cizí jméno, aby ho zablokoval)
- za Caddy je skutečná IP v hlavičce, kterou už čte ProxyFix

## Provoz

### Y520 místo domácího PC jako Tailscale průchod
Teď drží spojku k zařízením hlavní počítač. Y520 by bral míň proudu
a nerestartoval se při práci. Postup je stejný jako u desktopu.

### Druhá adresa `asistent.` (bez překlepu)
Doména běží na `asistant.pepacodes.cz`. Kdyby vadilo, dá se přidat
`A` záznam pro `asistent.` a v Caddy nechat obojí.

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

## Rozvoj

- portfolio na `pepacodes.cz` — přidá se jako další blok v Caddy
- e-shop — dostane vlastní server
- další zařízení = další tab (viz `VSECHNY_TABY` v `database.py`)
