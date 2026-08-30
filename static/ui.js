/*
  Drobnosti kolem ovládání, které se hodí na všech stránkách:

    1) notifikace, která po pár vteřinách sama zmizí
    2) potvrzovací okno u akcí, které nechceš udělat omylem

  Obojí je "navíc": bez JavaScriptu zůstane notifikace viset (dá se
  zavřít křížkem) a odkazy fungují rovnou. Nic se tím nerozbije.
*/

(function () {
    "use strict";

    // ---------- 1) Notifikace ----------

    var notifikace = document.getElementById("notifikace");
    if (notifikace) {
        var zavri = function () {
            notifikace.classList.add("odchazi");
            // Počkat, až doběhne animace, teprve pak prvek schovat
            setTimeout(function () { notifikace.hidden = true; }, 300);
        };

        var tlacitkoZavrit = notifikace.querySelector(".notifikace-zavrit");
        if (tlacitkoZavrit) tlacitkoZavrit.addEventListener("click", zavri);

        // Chybu necháme na obrazovce déle - je potřeba si ji přečíst.
        var jeChyba = notifikace.classList.contains("notifikace-chyba");
        setTimeout(zavri, jeChyba ? 6000 : 3500);
    }

    // ---------- 2) Potvrzovací okno ----------

    var dialog = document.getElementById("potvrzeni");

    // Když prohlížeč <dialog> neumí, necháme odkazy fungovat rovnou.
    if (!dialog || typeof dialog.showModal !== "function") return;

    var text = dialog.querySelector(".potvrzeni-text");
    var ano = dialog.querySelector(".potvrzeni-ano");
    var ne = dialog.querySelector(".potvrzeni-ne");
    var cekaNaPotvrzeni = null;

    ne.addEventListener("click", function () {
        cekaNaPotvrzeni = null;
        dialog.close();
    });

    ano.addEventListener("click", function () {
        var akce = cekaNaPotvrzeni;
        cekaNaPotvrzeni = null;
        dialog.close();
        if (!akce) return;

        if (akce.tagName === "FORM") {
            akce.submit();
        } else {
            window.location.href = akce.href;
        }
    });

    // Odkazy i formuláře označené data-potvrdit="Otázka?" se nejdřív zeptají.
    // Stačí ten atribut přidat kamkoliv, nic dalšího se nastavovat nemusí.
    document.querySelectorAll("[data-potvrdit]").forEach(function (prvek) {
        var udalost = prvek.tagName === "FORM" ? "submit" : "click";
        prvek.addEventListener(udalost, function (e) {
            e.preventDefault();
            text.textContent = prvek.getAttribute("data-potvrdit");
            cekaNaPotvrzeni = prvek;
            dialog.showModal();
        });
    });
})();
