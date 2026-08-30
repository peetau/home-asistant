/*
  Přepínač světlého a tmavého motivu.

  Motiv má TŘI stavy, ne dva:
      systém  -> řídí se nastavením počítače/telefonu (výchozí)
      světlý  -> vždy světlý, i když má systém tmavý
      tmavý   -> vždy tmavý, i když má systém světlý

  Proč tři: kdyby byly jen dva, uživatel by se po prvním kliknutí už nikdy
  nemohl vrátit k "řiď se systémem" - a to je pro většinu lidí nejlepší
  volba, protože se web sám přepne večer s celým telefonem.

  Volba se ukládá do localStorage prohlížeče. Na server se neposílá:
  je to věc konkrétního zařízení, ne uživatelského účtu.
*/

(function () {
    "use strict";

    var STAVY = ["system", "light", "dark"];

    var POPIS = {
        system: { ikona: "🌗", text: "Motiv: podle systému" },
        light:  { ikona: "☀️", text: "Motiv: světlý" },
        dark:   { ikona: "🌙", text: "Motiv: tmavý" }
    };

    var tlacitko = document.getElementById("prepinac-motivu");
    if (!tlacitko) {
        return;   // stránka přepínač nemá, není co dělat
    }

    /* Přečte uloženou volbu. Když tam nic (nebo nesmysl) není, je to "system". */
    function nactiVolbu() {
        try {
            var v = localStorage.getItem("motiv");
            return STAVY.indexOf(v) !== -1 ? v : "system";
        } catch (e) {
            return "system";
        }
    }

    /* Uloží volbu a promítne ji do stránky. */
    function pouzij(volba) {
        // data-theme na kořenovém <html> je to, co CSS poslouchá.
        // "system" znamená atribut vůbec nenastavit - pak rozhodne @media.
        if (volba === "system") {
            document.documentElement.removeAttribute("data-theme");
        } else {
            document.documentElement.setAttribute("data-theme", volba);
        }

        try {
            if (volba === "system") {
                localStorage.removeItem("motiv");
            } else {
                localStorage.setItem("motiv", volba);
            }
        } catch (e) {
            // Nejde uložit (anonymní okno) - přepnutí platí aspoň pro tuhle
            // návštěvu. Radši než aby celý přepínač spadl.
        }

        // Popisek tlačítka musí odpovídat stavu - jinak by uživatel nevěděl,
        // co je zrovna nastavené. title se ukáže po najetí myší,
        // aria-label čtou hlasové čtečky.
        tlacitko.textContent = POPIS[volba].ikona;
        tlacitko.title = POPIS[volba].text + " (klikni pro změnu)";
        tlacitko.setAttribute("aria-label", POPIS[volba].text);
    }

    /* Klik posune stav o jeden dál dokola: systém -> světlý -> tmavý -> systém */
    tlacitko.addEventListener("click", function () {
        var dalsi = STAVY[(STAVY.indexOf(nactiVolbu()) + 1) % STAVY.length];
        pouzij(dalsi);
    });

    // Tlačítko je v HTML schované (hidden). Odkryjeme ho až teď, kdy je
    // jisté, že JavaScript běží - bez něj by to bylo mrtvé tlačítko.
    tlacitko.hidden = false;

    // Na začátku srovnáme popisek s tím, co je opravdu nastavené.
    pouzij(nactiVolbu());
})();
