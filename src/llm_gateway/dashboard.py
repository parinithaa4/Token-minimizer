"""The admin dashboard — a single self-contained HTML page.

Served by the gateway at ``GET /dashboard``. It is deliberately framework-free
(vanilla JS, no build step) and fully inline so there are no static-asset routes
to wire up. The page polls ``GET /admin/usage`` and renders a totals header plus
per-key cards in the owner's "Electric Cyan" terminal aesthetic.

Design system (must match the owner's token-diet / site exactly):
  bg #0A0B0C · bg-2 #0F1113 · surface #14171A · ink #F4F6F7 · muted #8A9196
  line rgba(244,246,247,.10) · cyan #34E7FF · cyan-glow rgba(52,231,255,.45)
  fonts: Syne (display 700/800) + JetBrains Mono (mono) via Google Fonts.
No emoji — clean inline SVG icons only. Honors prefers-reduced-motion.
"""

from __future__ import annotations

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>llm-gateway · dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet" />
<style>
  :root {
    --bg: #0A0B0C;
    --bg-2: #0F1113;
    --surface: #14171A;
    --ink: #F4F6F7;
    --muted: #8A9196;
    --line: rgba(244,246,247,.10);
    --cyan: #34E7FF;
    --cyan-glow: rgba(52,231,255,.45);
    --amber: #FFC24B;
    --red: #FF5C66;
    --radius: 14px;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; }
  body {
    background:
      radial-gradient(900px 480px at 78% -8%, rgba(52,231,255,.07), transparent 60%),
      radial-gradient(700px 420px at 8% 108%, rgba(52,231,255,.045), transparent 60%),
      var(--bg);
    color: var(--ink);
    font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 14px;
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
    min-height: 100vh;
  }
  .wrap { max-width: 1160px; margin: 0 auto; padding: 40px 24px 72px; }

  header.top { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; margin-bottom: 30px; }
  .brand { display: flex; align-items: center; gap: 14px; min-width: 0; }
  .brand .mark {
    width: 40px; height: 40px; flex: 0 0 40px; border-radius: 11px;
    display: grid; place-items: center;
    border: 1px solid var(--line);
    background: linear-gradient(180deg, rgba(52,231,255,.10), rgba(52,231,255,0));
    box-shadow: 0 0 0 1px rgba(52,231,255,.06) inset, 0 0 22px -8px var(--cyan-glow);
  }
  .brand .mark svg { color: var(--cyan); filter: drop-shadow(0 0 6px var(--cyan-glow)); }
  .brand h1 {
    font-family: 'Syne', sans-serif; font-weight: 800;
    font-size: 22px; letter-spacing: -.01em; margin: 0; line-height: 1.05;
  }
  .brand .sub { color: var(--muted); font-size: 11.5px; letter-spacing: .04em; text-transform: uppercase; }

  .live {
    display: inline-flex; align-items: center; gap: 9px;
    border: 1px solid var(--line); border-radius: 999px;
    padding: 7px 13px; font-size: 11.5px; letter-spacing: .06em;
    text-transform: uppercase; color: var(--muted); background: var(--bg-2);
    white-space: nowrap;
  }
  .live .dot {
    width: 8px; height: 8px; border-radius: 50%; background: var(--cyan);
    box-shadow: 0 0 0 0 var(--cyan-glow); animation: pulse 1.8s ease-out infinite;
  }
  .live.stale .dot { background: var(--red); animation: none; box-shadow: none; }
  .live .label { color: var(--ink); }
  @keyframes pulse {
    0%   { box-shadow: 0 0 0 0 var(--cyan-glow); }
    70%  { box-shadow: 0 0 0 7px rgba(52,231,255,0); }
    100% { box-shadow: 0 0 0 0 rgba(52,231,255,0); }
  }

  .totals { display: grid; grid-template-columns: repeat(5, 1fr); gap: 14px; margin-bottom: 34px; }
  .stat {
    background: linear-gradient(180deg, var(--surface), var(--bg-2));
    border: 1px solid var(--line); border-radius: var(--radius);
    padding: 17px 18px 16px; position: relative; overflow: hidden;
  }
  .stat::after {
    content: ""; position: absolute; left: 0; top: 0; height: 2px; width: 38px;
    background: var(--cyan); box-shadow: 0 0 12px var(--cyan-glow); border-radius: 2px;
  }
  .stat .k { display: flex; align-items: center; gap: 7px; color: var(--muted); font-size: 11px; letter-spacing: .07em; text-transform: uppercase; }
  .stat .k svg { width: 13px; height: 13px; color: var(--muted); }
  .stat .v {
    font-family: 'Syne', sans-serif; font-weight: 800; letter-spacing: -.02em;
    font-size: 27px; margin-top: 9px; line-height: 1;
  }
  .stat .v.glow { color: var(--cyan); text-shadow: 0 0 18px var(--cyan-glow); }
  .stat .u { color: var(--muted); font-size: 11px; margin-top: 6px; }

  .section-h { display: flex; align-items: baseline; gap: 12px; margin: 6px 2px 16px; }
  .section-h h2 { font-family: 'Syne', sans-serif; font-weight: 700; font-size: 14.5px; letter-spacing: .02em; margin: 0; }
  .section-h .count { color: var(--muted); font-size: 12px; }
  .section-h .rule { flex: 1; height: 1px; background: var(--line); }

  .cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(330px, 1fr)); gap: 16px; }
  .card {
    background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius);
    padding: 18px 18px 17px; transition: border-color .18s ease, transform .18s ease;
  }
  .card:hover { border-color: rgba(52,231,255,.28); transform: translateY(-1px); }
  .card .hd { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 15px; }
  .card .name { font-family: 'Syne', sans-serif; font-weight: 700; font-size: 16px; letter-spacing: -.01em; }
  .card .keyid {
    color: var(--muted); font-size: 11px; background: var(--bg-2);
    border: 1px solid var(--line); border-radius: 7px; padding: 3px 8px; white-space: nowrap;
  }

  .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px 16px; margin-bottom: 16px; }
  .metric .ml { color: var(--muted); font-size: 11px; letter-spacing: .05em; text-transform: uppercase; }
  .metric .mv { font-size: 17px; font-weight: 500; margin-top: 3px; }
  .metric .mv.accent { color: var(--cyan); }

  .budget { margin-top: 4px; }
  .budget .brow { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 7px; }
  .budget .blabel { color: var(--muted); font-size: 11px; letter-spacing: .05em; text-transform: uppercase; }
  .budget .bval { font-size: 12.5px; }
  .budget .bval b { font-weight: 700; }
  .bar { height: 9px; border-radius: 999px; background: rgba(244,246,247,.07); border: 1px solid var(--line); overflow: hidden; }
  .bar > span {
    display: block; height: 100%; width: 0%; border-radius: 999px;
    background: var(--cyan); box-shadow: 0 0 12px var(--cyan-glow);
    transition: width .5s cubic-bezier(.22,.61,.36,1), background-color .3s ease;
  }
  .bar > span.warn { background: var(--amber); box-shadow: 0 0 12px rgba(255,194,75,.4); }
  .bar > span.crit { background: var(--red); box-shadow: 0 0 12px rgba(255,92,102,.4); }
  .budget .pct { font-size: 11px; color: var(--muted); margin-top: 6px; }
  .budget.none .bar { opacity: .35; }

  .empty {
    border: 1px dashed var(--line); border-radius: var(--radius);
    padding: 40px 22px; text-align: center; color: var(--muted); background: var(--bg-2);
  }
  .empty .big { font-family: 'Syne', sans-serif; font-weight: 700; color: var(--ink); font-size: 16px; margin-bottom: 6px; }
  code.kbd { color: var(--cyan); background: rgba(52,231,255,.08); border: 1px solid var(--line); border-radius: 6px; padding: 1px 7px; }

  footer { margin-top: 40px; color: var(--muted); font-size: 11.5px; display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  footer .sep { opacity: .4; }

  @media (max-width: 880px) { .totals { grid-template-columns: repeat(2, 1fr); } }
  @media (max-width: 560px) {
    .wrap { padding: 26px 16px 56px; }
    .totals { grid-template-columns: 1fr; }
    .cards { grid-template-columns: 1fr; }
    .grid2 { grid-template-columns: 1fr 1fr; }
  }
  @media (prefers-reduced-motion: reduce) {
    .live .dot { animation: none; }
    .bar > span { transition: none; }
    .card { transition: none; }
  }
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <div class="brand">
      <div class="mark" aria-hidden="true">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 17l6-6-6-6"/><path d="M12 19h8"/></svg>
      </div>
      <div>
        <h1>llm&#8209;gateway</h1>
        <div class="sub">usage &middot; budgets &middot; jtf savings</div>
      </div>
    </div>
    <div class="live" id="live" role="status" aria-live="polite">
      <span class="dot" aria-hidden="true"></span>
      <span class="label" id="liveLabel">live</span>
    </div>
  </header>

  <section class="totals" id="totals" aria-label="portfolio totals"></section>

  <div class="section-h">
    <h2>Virtual keys</h2>
    <span class="count" id="keyCount"></span>
    <span class="rule" aria-hidden="true"></span>
  </div>
  <section class="cards" id="cards" aria-label="per-key usage"></section>

  <footer>
    <span>llm-gateway dashboard</span>
    <span class="sep">&middot;</span>
    <span id="lastUpdate">connecting&hellip;</span>
    <span class="sep">&middot;</span>
    <span>auto&#8209;refresh 4s</span>
  </footer>
</div>

<script>
(function () {
  "use strict";

  // Forward an admin_token from the page URL to the API fetch, if present.
  var pageParams = new URLSearchParams(window.location.search);
  var adminToken = pageParams.get("admin_token");
  var USAGE_URL = "/admin/usage" + (adminToken ? "?admin_token=" + encodeURIComponent(adminToken) : "");
  var REFRESH_MS = 4000;

  var ICON = {
    req: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12h4l3 8 4-16 3 8h4"/></svg>',
    tok: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 9h10M7 13h6"/></svg>',
    usd: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v20"/><path d="M17 6.5C17 4.6 14.8 4 12 4S7 4.9 7 7s2.2 2.6 5 3 5 1 5 3-2.2 3-5 3-5-.7-5-2.5"/></svg>',
    cache: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/></svg>',
    jtf: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2L4 14h7l-1 8 9-12h-7z"/></svg>'
  };

  function fmtInt(n) { return (n || 0).toLocaleString("en-US"); }
  function fmtUsd(n) {
    n = n || 0;
    if (n !== 0 && n < 0.01) return "$" + n.toFixed(6);
    return "$" + n.toFixed(n < 100 ? 4 : 2);
  }
  function fmtPct(r) { return Math.round((r || 0) * 100) + "%"; }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function stat(icon, label, value, unit, glow) {
    return '<div class="stat">' +
      '<div class="k">' + icon + '<span>' + esc(label) + '</span></div>' +
      '<div class="v' + (glow ? ' glow' : '') + '">' + esc(value) + '</div>' +
      (unit ? '<div class="u">' + esc(unit) + '</div>' : '') +
      '</div>';
  }

  function renderTotals(t) {
    t = t || {};
    document.getElementById("totals").innerHTML =
      stat(ICON.req, "Requests", fmtInt(t.requests), "across all keys") +
      stat(ICON.tok, "Tokens", fmtInt(t.total_tokens), "prompt + completion") +
      stat(ICON.usd, "Spent", fmtUsd(t.cost_usd), "billed total", true) +
      stat(ICON.cache, "Cache hit-rate", fmtPct(t.cache_hit_rate), fmtInt(t.cache_hits) + " hits") +
      stat(ICON.jtf, "JTF saved", fmtInt(t.jtf_potential_tokens_saved), "potential tokens", true);
  }

  function budgetBlock(key) {
    var hasUsd = key.budget_usd != null && key.budget_usd > 0;
    if (!hasUsd) {
      return '<div class="budget none">' +
        '<div class="brow"><span class="blabel">Budget</span>' +
        '<span class="bval">' + fmtUsd(key.cost_usd) + ' <span style="color:var(--muted)">spent &middot; no cap</span></span></div>' +
        '<div class="bar"><span style="width:0%"></span></div>' +
        '<div class="pct">unlimited</div></div>';
    }
    var ratio = key.budget_used_ratio != null ? key.budget_used_ratio : (key.cost_usd / key.budget_usd);
    ratio = Math.max(0, Math.min(1, ratio));
    var cls = ratio >= 0.9 ? "crit" : (ratio >= 0.7 ? "warn" : "");
    var pct = Math.round(ratio * 100);
    return '<div class="budget">' +
      '<div class="brow"><span class="blabel">Budget</span>' +
      '<span class="bval"><b>' + fmtUsd(key.cost_usd) + '</b> / ' + fmtUsd(key.budget_usd) + '</span></div>' +
      '<div class="bar"><span class="' + cls + '" style="width:' + pct + '%"></span></div>' +
      '<div class="pct">' + pct + '% used &middot; ' + fmtUsd(key.budget_remaining_usd) + ' remaining</div>' +
      '</div>';
  }

  function card(key) {
    return '<article class="card">' +
      '<div class="hd"><span class="name">' + esc(key.key_name || "key") + '</span>' +
      '<span class="keyid">' + esc(key.key || "") + '</span></div>' +
      '<div class="grid2">' +
        metric("Requests", fmtInt(key.requests)) +
        metric("Tokens", fmtInt(key.total_tokens)) +
        metric("Cache hit-rate", fmtPct(key.cache_hit_rate), true) +
        metric("JTF saved", fmtInt(key.jtf_potential_tokens_saved), true) +
      '</div>' +
      budgetBlock(key) +
      '</article>';
  }

  function metric(label, value, accent) {
    return '<div class="metric"><div class="ml">' + esc(label) + '</div>' +
      '<div class="mv' + (accent ? ' accent' : '') + '">' + esc(value) + '</div></div>';
  }

  function renderCards(keys) {
    var el = document.getElementById("cards");
    document.getElementById("keyCount").textContent = keys.length + (keys.length === 1 ? " key" : " keys");
    if (!keys.length) {
      el.innerHTML = '<div class="empty"><div class="big">No keys yet</div>' +
        'Seed a key and send a request, e.g. ' +
        '<code class="kbd">llm-gateway create-key --name demo</code>, then make a chat completion.</div>';
      return;
    }
    el.innerHTML = keys.map(card).join("");
  }

  function setLive(ok) {
    var live = document.getElementById("live");
    var label = document.getElementById("liveLabel");
    if (ok) { live.classList.remove("stale"); label.textContent = "live"; }
    else { live.classList.add("stale"); label.textContent = "offline"; }
  }

  function pad(n) { return n < 10 ? "0" + n : "" + n; }
  function stamp() {
    var d = new Date();
    return pad(d.getHours()) + ":" + pad(d.getMinutes()) + ":" + pad(d.getSeconds());
  }

  function load() {
    fetch(USAGE_URL, { headers: { "Accept": "application/json" } })
      .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
      .then(function (data) {
        renderTotals(data.totals);
        renderCards(data.keys || []);
        setLive(true);
        document.getElementById("lastUpdate").textContent = "updated " + stamp();
      })
      .catch(function () {
        setLive(false);
        document.getElementById("lastUpdate").textContent = "fetch failed — retrying";
      });
  }

  load();
  setInterval(load, REFRESH_MS);
})();
</script>
</body>
</html>
"""
