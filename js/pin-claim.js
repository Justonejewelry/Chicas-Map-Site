(function () {
  var BAR_ID = "chica-pin-claim";
  var CLAIM = "/claim/";
  var PAY =
    (window.CHICA_CONFIG && window.CHICA_CONFIG.PIN_CLAIM_PAYMENT_URL) ||
    "https://square.link/u/qjunxHoo";
  var last = "";
  var queued = 0;

  function skipPath(p) {
    if (!p) p = "/";
    if (p.indexOf("/map") !== -1 || p.indexOf("/claim") !== -1) return true;
    var bare = p.replace(/\/+$/, "") || "/";
    return bare === "/" || bare === "" || p.indexOf("index.html") !== -1;
  }

  function kill() {
    var el = document.getElementById(BAR_ID);
    if (el) el.remove();
    last = "skip";
  }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text) n.textContent = text;
    return n;
  }

  // Pages without fs-map.css (/submit/, 404) still need the bar's look, or it renders as bare text at the top.
  function ensureCss() {
    if (document.getElementById(BAR_ID + "-css")) return;
    var st = document.createElement("style");
    st.id = BAR_ID + "-css";
    st.textContent =
      "#chica-pin-claim{position:fixed;z-index:2147483645;display:flex;gap:8px;align-items:center;justify-content:space-between;flex-wrap:wrap;padding:11px 14px;border-radius:14px;background:#1a1714;color:#f3eee4;box-shadow:0 10px 28px rgba(0,0,0,.4);font:600 14px/1.3 Inter,system-ui,sans-serif;border:1px solid #3a342e;opacity:0;transform:translateY(10px);transition:opacity .32s ease,transform .32s cubic-bezier(.22,1,.36,1);max-width:560px;margin:0 auto}" +
      "#chica-pin-claim.is-in{opacity:1;transform:none}" +
      "#chica-pin-claim .chica-claim-pay,#chica-pin-claim .chica-claim-more{display:inline-flex;align-items:center;min-height:40px;padding:8px 14px;border-radius:10px;text-decoration:none;white-space:nowrap}" +
      "#chica-pin-claim .chica-claim-pay{background:#c513af;color:#fff;font-weight:800}" +
      "#chica-pin-claim .chica-claim-more{padding:8px 12px;background:transparent;color:#f3eee4;border:1px solid #5a534c}" +
      "#chica-pin-claim .chica-claim-x{background:none!important;border:0!important;box-shadow:none!important;color:#c8c0b6;font:700 18px/1 Inter,sans-serif;min-width:40px;min-height:40px;cursor:pointer}" +
      "@media (prefers-reduced-motion:reduce){#chica-pin-claim{transition:none;opacity:1;transform:none}}";
    (document.head || document.documentElement).appendChild(st);
  }

  function paint() {
    var p = location.pathname || "/";
    if (skipPath(p)) {
      if (last !== "skip") kill();
      return;
    }
    var es = (document.documentElement.lang || "").toLowerCase().indexOf("es") === 0;
    var key = es ? "es" : "en";
    if (last === key && document.getElementById(BAR_ID)) return;

    var line = es
      ? "Impulsa mi venta. El pin de oro, este fin."
      : "Boost My Sale. Gold pin this weekend.";
    var payLabel = es ? "Impulsa mi venta · $5" : "Boost My Sale · $5";
    var moreLabel = es ? "Cómo funciona" : "How it works";

    try { if (sessionStorage.getItem(BAR_ID + "-x")) return; } catch (e) {}
    ensureCss();
    var bar = document.getElementById(BAR_ID);
    var fresh = !bar;
    if (!bar) {
      bar = el("div", "");
      bar.id = BAR_ID;
      bar.setAttribute("role", "region");
      document.body.appendChild(bar);
    } else {
      while (bar.firstChild) bar.removeChild(bar.firstChild);
    }
    bar.setAttribute("aria-label", line);
    bar.style.cssText =
      "left:12px;right:12px;bottom:max(76px,calc(env(safe-area-inset-bottom) + 64px));top:auto";

    var copy = el("span", "chica-claim-line", line);
    copy.style.cssText = "flex:1;min-width:140px";
    var actions = el("span", "chica-claim-actions");
    actions.style.cssText = "display:flex;gap:8px;flex-wrap:wrap";
    var pay = el("a", "chica-claim-pay", payLabel);
    pay.href = PAY;
    pay.target = "_blank";
    pay.rel = "noreferrer";
    var more = el("a", "chica-claim-more", moreLabel);
    more.href = CLAIM;
    actions.appendChild(pay);
    actions.appendChild(more);
    var x = el("button", "chica-claim-x", "×");
    x.type = "button";
    x.setAttribute("aria-label", es ? "Cerrar" : "Close");
    x.addEventListener("click", function () { try { sessionStorage.setItem(BAR_ID + "-x", "1"); } catch (e) {} kill(); });
    actions.appendChild(x);
    bar.appendChild(copy);
    bar.appendChild(actions);
    if (fresh) requestAnimationFrame(function () { bar.classList.add("is-in"); });
    last = key;
  }

  // Wait for TanStack/React hydration ($_TSR is deleted when the shell is hydrated)
  // before injecting the claim bar, or React throws hydration error #418.
  function afterHydrate(fn) {
    if (window.$_TSR) {
      var started = Date.now();
      var id = setInterval(function () {
        if (!window.$_TSR || Date.now() - started > 4000) {
          clearInterval(id);
          fn();
        }
      }, 50);
      return;
    }
    fn();
  }

  function schedule() {
    if (queued) return;
    queued = 1;
    var run = function () {
      queued = 0;
      paint();
    };
    afterHydrate(function () {
      if (skipPath(location.pathname || "/")) {
        run();
        return;
      }
      if (typeof requestIdleCallback === "function") {
        requestIdleCallback(run, { timeout: 700 });
      } else {
        setTimeout(run, 0);
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", schedule, { once: true });
  } else {
    schedule();
  }
  window.addEventListener("popstate", schedule, { passive: true });
})();
