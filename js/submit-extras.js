/* /submit/: optional photo link field + city permit question + friendlier "what happens next" note.
   Delivery is handled by form-intake.js (FormSubmit -> owner inbox). */
(function () {
  function isEs() { if ((document.documentElement.lang || "").slice(0, 2) === "es") return true; try { return localStorage.getItem("chicas-map-locale") === "es"; } catch (e) { return false; } }
  if (!/\/submit\/?$|submit\.html$/.test(location.pathname || "")) return;

  var PERMIT_APPLY = "https://aca-prod.accela.com/COSA/cap/CapApplyDisclaimer.aspx?Module=Building&agencyCode=COSA&HideHeader=true&CAPType=Building/Permits/Garage%20Sale/Application";
  var PERMIT_INFO = "https://www.sa.gov/Directory/Departments/DSD/CES/Permits-Licenses/Garage-Sales";

  function addPhoto(form) {
    if (form.querySelector('[name="photo_url"]')) return;
    var email = form.querySelector('[name="email"]');
    var anchor = email ? (email.closest("label") || email.parentNode) : null;
    var wrap = document.createElement("label");
    wrap.className = "block";
    wrap.style.cssText = "display:block;margin-top:16px";
    wrap.innerHTML =
      '<span style="display:block;font-weight:600;margin-bottom:6px">' + (isEs() ? "Enlace de foto (opcional)" : "Photo link (optional)") + '</span>' +
      '<input name="photo_url" type="url" inputmode="url" placeholder="' + (isEs() ? "Pega un enlace de Facebook, Marketplace, Google Photos o Imgur" : "Paste a Facebook, Marketplace, Google Photos or Imgur link") + '" ' +
      'style="width:100%;min-height:44px;padding:10px 12px;border:1px solid rgba(0,0,0,.2);border-radius:10px;font:inherit;background:#fff">' +
      '<span style="display:block;font-size:13px;opacity:.75;margin-top:4px">' + (isEs() ? "¿Tienes foto de tus cositas? Pega un enlace público y Chica la agrega a tu pin." : "Got a photo of your goodies? Drop a public link and Chica will add it to your pin.") + '</span>';
    if (anchor && anchor.parentNode) anchor.parentNode.insertBefore(wrap, anchor.nextSibling);
    else form.appendChild(wrap);
  }

  function addPermitQuestion(form) {
    if (form.querySelector('[name="permit_status"]')) return;
    var wrap = document.createElement("div");
    wrap.className = "block";
    wrap.style.cssText = "display:block;margin-top:16px";
    var label = isEs()
      ? "¿Ya obtuviste el permiso requerido de la ciudad?"
      : "Have you obtained your required city permit?";
    var yes = isEs() ? "Sí" : "Yes";
    var no = isEs() ? "No, todavía no" : "No, not yet";
    wrap.innerHTML =
      '<span style="display:block;font-weight:600;margin-bottom:8px">' + label + '</span>' +
      '<label style="display:flex;align-items:center;gap:8px;margin-bottom:6px;font-weight:500">' +
        '<input type="radio" name="permit_status" value="yes"> ' + yes +
      '</label>' +
      '<label style="display:flex;align-items:center;gap:8px;font-weight:500">' +
        '<input type="radio" name="permit_status" value="no"> ' + no +
      '</label>' +
      '<div id="chica-permit-help" style="display:none;margin-top:12px;padding:12px 14px;border-radius:12px;background:#fff3fb;color:#4a0b41">' +
        '<p style="margin:0 0 8px;font-weight:600">' + (isEs() ? "Se requiere permiso para ventas de más de 5 artículos." : "A permit is required for sales of more than 5 items.") + '</p>' +
        '<p style="margin:0 0 10px;font-size:14px">' + (isEs() ? "La tarifa es $20. Puedes solicitarlo en línea en unos minutos." : "Fee is $20. You can apply online in a few minutes.") + '</p>' +
        '<a href="' + PERMIT_APPLY + '" target="_blank" rel="noreferrer" style="display:inline-flex;align-items:center;height:40px;padding:0 16px;border-radius:999px;background:#c513af;color:#fff;font-weight:600;text-decoration:none">' +
          (isEs() ? "Obtener permiso" : "Get your permit") +
        '</a>' +
        '<p style="margin:10px 0 0;font-size:12px;opacity:.8">' +
          (isEs()
            ? "Vender 5 artículos o menos no requiere permiso. Horario 9 a.m.–6 p.m., máximo dos días consecutivos, una venta por trimestre."
            : "Selling 5 items or fewer does not require a permit. Hours are 9 a.m.–6 p.m., max two consecutive days, one sale per quarter.") +
        '</p>' +
        '<p style="margin:6px 0 0;font-size:12px"><a href="' + PERMIT_INFO + '" target="_blank" rel="noreferrer" style="color:#c513af">' +
          (isEs() ? "Más información oficial" : "Official rules") +
        '</a></p>' +
      '</div>';
    form.appendChild(wrap);

    var radios = wrap.querySelectorAll('input[name="permit_status"]');
    var help = wrap.querySelector("#chica-permit-help");
    function toggle() {
      var checked = wrap.querySelector('input[name="permit_status"]:checked');
      if (help) help.style.display = (checked && checked.value === "no") ? "block" : "none";
    }
    radios.forEach(function (r) { r.addEventListener("change", toggle); });
  }

  function addNext(root) {
    if (document.getElementById("chica-next-steps")) return;
    var p = document.createElement("p");
    p.id = "chica-next-steps";
    p.style.cssText = "margin-top:12px;padding:12px 14px;border-radius:12px;background:#fff3fb;color:#4a0b41;font-weight:500";
    p.textContent = isEs() ? "Lo que sigue: Chica revisa cada venta, casi siempre en un día. Cuando se aprueba, tu pin sale en chicasmap.com/map y en la lista del fin. ¡Comparte el mapa con tus vecinos para que lleguen! 🐾" : "What happens next: Chica sniffs out every sale, usually within a day. Once it's approved, your pin shows up on chicasmap.com/map and in the weekend list. Share the map with your neighbors so they come by! 🐾";
    root.appendChild(p);
  }
  // Head for /submit/ and /es/submit/. The TanStack shell ships the home page's description and
  // hreflang pair and no canonical; patch them after hydration (editing the static head trips React #418).
  // The URL that was requested, not the one after the locale script trimmed /es/ off the address bar
  // (and not the stored language, which is sticky across pages).
  var navUrl = "";
  try { navUrl = (performance.getEntriesByType("navigation")[0] || {}).name || ""; } catch (e) {}
  var esPage = /^\/(Chicas-Map\/)?es\//.test(navUrl ? new URL(navUrl).pathname : (location.pathname || ""));
  function fixHead() {
    var O = "https://www.chicasmap.com";
    var url = O + (esPage ? "/es/submit/" : "/submit/");
    var d = document, h = d.head;
    if (!h) return;
    // Title and lang follow the language the form is shown in; canonical follows the URL.
    var ui = isEs();
    d.documentElement.lang = ui ? "es" : "en";
    d.title = ui ? "Publica tu venta de garaje gratis en San Antonio · Chicas Map" : "List Your Garage Sale Free in San Antonio · Chicas Map";
    var desc = h.querySelector('meta[name="description"]');
    if (!desc) { desc = d.createElement("meta"); desc.name = "description"; h.appendChild(desc); }
    desc.content = ui
      ? "Publica gratis tu venta de garaje, patio o bienes en San Antonio. Chica la revisa y la pone en el mapa en un día."
      : "Add your San Antonio garage, yard or estate sale to Chicas Map for free. Chica reviews it and pins it on the live map, usually within a day.";
    var c = h.querySelector('link[rel="canonical"]');
    if (!c) { c = d.createElement("link"); c.rel = "canonical"; h.appendChild(c); }
    c.href = url;
    var pairs = { en: O + "/submit/", es: O + "/es/submit/", "x-default": O + "/submit/" };
    Object.keys(pairs).forEach(function (k) {
      var l = h.querySelector('link[rel="alternate"][hreflang="' + k + '"]');
      if (!l) { l = d.createElement("link"); l.rel = "alternate"; l.hreflang = k; h.appendChild(l); }
      l.href = pairs[k];
    });
  }
  (function waitHydrated(n) {
    if (window.$_TSR && n < 80) return setTimeout(function () { waitHydrated(n + 1); }, 50);
    fixHead();
    setTimeout(fixHead, 1500);
  })(0);
  var tries = 0;
  var id = setInterval(function () {
    tries += 1;
    var form = document.querySelector("main form");
    if (form) {
      addPhoto(form);
      addPermitQuestion(form);
    }
    var main = document.querySelector("main");
    if (main && !form && /got it|lo tengo|recib/i.test(main.textContent || "")) addNext(main.querySelector("section,div") || main);
    if (tries > 600) clearInterval(id);
  }, 500);
})();
