/* =========================================================
   KickTipp WM 2026 — rendering + interactions
   ========================================================= */

(function () {
  const matches = window.MATCHES || [];
  const CC = window.COUNTRY_CODES || {};
  const META = window.META || {};

  // ---------- helpers ----------
  const $ = (sel, ctx = document) => ctx.querySelector(sel);
  const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];

  const ev3 = (n) => n.toFixed(3);
  const ev2 = (n) => n.toFixed(2);

  function evClass(ev) {
    if (ev >= 2.0) return "ev-high";
    if (ev >= 1.4) return "ev-mid";
    return "ev-low";
  }
  function evClassBar(ev) {
    if (ev >= 2.0) return "high";
    if (ev >= 1.2) return "mid";
    return "low";
  }

  const WEEKDAYS = {
    "11.06.": "Donnerstag", "12.06.": "Freitag", "13.06.": "Samstag",
    "14.06.": "Sonntag", "15.06.": "Montag", "16.06.": "Dienstag",
    "17.06.": "Mittwoch", "18.06.": "Donnerstag", "19.06.": "Freitag",
    "20.06.": "Samstag", "21.06.": "Sonntag", "22.06.": "Montag",
    "23.06.": "Dienstag", "24.06.": "Mittwoch", "25.06.": "Donnerstag",
    "26.06.": "Freitag", "27.06.": "Samstag", "28.06.": "Sonntag"
  };

  // ---------- error banner ----------
  function renderError() {
    if (!META.error) return;
    const banner = document.createElement("div");
    banner.style.cssText = "background:oklch(0.93 0.05 25);border-left:3px solid oklch(0.58 0.16 25);padding:14px 22px;font-size:13px;font-family:var(--mono);color:var(--ink-2);margin-bottom:24px;max-width:100%;";
    banner.innerHTML = `<strong style="color:var(--red)">API-Fehler:</strong> ${META.error}`;
    // Insert after stats-strip, before the first section
    const anchor = $("#stats-strip");
    if (anchor && anchor.parentNode) {
      anchor.parentNode.insertBefore(banner, anchor.nextSibling);
    } else {
      document.body.prepend(banner);
    }
  }

  // ---------- stats ----------
  function computeStats() {
    const total = matches.length;
    if (!total) {
      ["stat-total","stat-avg-ev","stat-high","stat-close","stat-ger"].forEach(id => {
        const el = $("#" + id); if (el) el.textContent = "0";
      });
      ["all","high","close","ger"].forEach(f => {
        const el = document.querySelector(`[data-filter="${f}"] .count`);
        if (el) el.textContent = "0";
      });
      return;
    }
    const avg = matches.reduce((a, m) => a + m.ev, 0) / total;
    const high = matches.filter((m) => m.ev >= 2.0).length;
    const close = matches.filter((m) => m.isClose).length;
    const ger = matches.filter((m) => m.germany).length;

    const set = (id, val) => { const el = $("#" + id); if (el) el.textContent = val; };
    set("stat-total", total);
    set("stat-avg-ev", avg.toFixed(2));
    set("stat-high", high);
    set("stat-close", close);
    set("stat-ger", ger);

    const setChip = (f, n) => {
      const el = document.querySelector(`[data-filter="${f}"] .count`);
      if (el) el.textContent = n;
    };
    setChip("all", total);
    setChip("high", high);
    setChip("close", close);
    setChip("ger", ger);
  }

  // ---------- summary table ----------
  function renderTable() {
    const tbody = $("#summary-table tbody");
    if (!tbody) return;
    if (!matches.length) {
      tbody.innerHTML = `<tr><td colspan="9" style="text-align:center;padding:32px;color:var(--muted);font-family:var(--mono);font-size:13px;">Keine Spiele verfügbar.</td></tr>`;
      return;
    }
    const rows = matches.map((m) => {
      const closeBadge = m.isClose ? `<span class="close-badge">knapp</span>` : "";
      const gerBadge = m.germany ? `<span class="ger-badge">GER</span>` : "";
      return `
        <tr>
          <td>${m.date}</td>
          <td>${m.kickoff}</td>
          <td class="match-cell"><strong>${m.home}</strong><span class="vs">—</span>${m.away}${gerBadge}</td>
          <td><span class="tip-cell">${m.tip}</span></td>
          <td class="num ev-cell ${evClass(m.ev)}">${ev3(m.ev)}</td>
          <td class="num">${m.q1p}%</td>
          <td class="num">${m.qxp}%</td>
          <td class="num">${m.q2p}%</td>
          <td>${closeBadge}</td>
        </tr>
      `;
    });
    tbody.innerHTML = rows.join("");
  }

  // ---------- histogram ----------
  function renderHistogram() {
    const host = $("#histogram");
    if (!host) return;
    if (!matches.length) { host.innerHTML = ""; return; }

    const bins = 20;
    const min = 0.9, max = 2.3;
    const width = (max - min) / bins;
    const counts = new Array(bins).fill(0);
    matches.forEach((m) => {
      let idx = Math.floor((m.ev - min) / width);
      if (idx < 0) idx = 0;
      if (idx >= bins) idx = bins - 1;
      counts[idx]++;
    });
    const maxCount = Math.max(...counts);
    host.innerHTML = counts.map((c, i) => {
      const evMid = min + i * width + width / 2;
      const heightPct = c === 0 ? 2 : (c / maxCount) * 100;
      const cls = evClassBar(evMid);
      return `<div class="bar ${cls}" style="height:${heightPct}%" data-label="EV ≈ ${evMid.toFixed(2)} · ${c} Spiel${c === 1 ? "" : "e"}"></div>`;
    }).join("");
  }

  // ---------- match card ----------
  function matchCard(m) {
    const homeCode = CC[m.home] || m.home.slice(0, 3).toUpperCase();
    const awayCode = CC[m.away] || m.away.slice(0, 3).toUpperCase();
    const closeBadge = m.isClose ? `<span class="badge close">⚠ Alternative prüfen</span>` : "";
    const gerBadge = m.germany ? `<span class="badge ger">Deutschland</span>` : "";

    const total = m.q1p + m.qxp + m.q2p;
    const seg1 = (m.q1p / total) * 100;
    const segX = (m.qxp / total) * 100;
    const seg2 = (m.q2p / total) * 100;

    const localDisplay = m.local ? `/ ${m.tz_approx ? "~" : ""}${m.local} Ortszeit` : "";

    const alts = (m.alts || []).map((a) =>
      `<span class="alt"><span class="alt-score">${a.tip}</span><span class="alt-ev">${ev3(a.ev)}</span></span>`
    ).join("");

    return `
      <article class="match ${m.germany ? "ger" : ""}" data-ev="${m.ev}" data-home="${m.home.toLowerCase()}" data-away="${m.away.toLowerCase()}" data-close="${m.isClose}" data-ger="${m.germany}" data-high="${m.ev >= 2.0}">
        <div class="match-head">
          <div class="time">
            ${m.kickoff} MESZ <span class="local">${localDisplay}</span>
          </div>
          <div class="right">
            ${gerBadge}
            ${closeBadge}
            ${m.venue ? `<span class="venue">${m.venue}</span>` : ""}
          </div>
        </div>

        <div class="match-bowl">
          <div class="team home">
            <span class="code mono">${homeCode}</span>
            <span class="name">${m.home}</span>
            <span class="role">Heim · ${m.bookies} Buchm.</span>
          </div>

          <div class="tip-block ${evClass(m.ev)}">
            <div class="label">Tipp</div>
            <div class="score">${m.tip}</div>
            <div class="ev">EV <span class="val">${ev3(m.ev)}</span></div>
          </div>

          <div class="team away">
            <span class="code mono">${awayCode}</span>
            <span class="name">${m.away}</span>
            <span class="role">Gast</span>
          </div>
        </div>

        <div class="odds-row">
          <div class="odd"><span class="who">1 · Heim</span><span class="odds">${ev2(m.q1)}</span><span class="pct">${m.q1p}%</span></div>
          <div class="odd"><span class="who">X · Remis</span><span class="odds">${ev2(m.qx)}</span><span class="pct">${m.qxp}%</span></div>
          <div class="odd"><span class="who">2 · Gast</span><span class="odds">${ev2(m.q2)}</span><span class="pct">${m.q2p}%</span></div>
        </div>

        <div class="prob-bar" title="Wahrscheinlichkeitsverteilung 1 / X / 2">
          <div class="seg-1" style="width:${seg1}%"></div>
          <div class="seg-x" style="width:${segX}%"></div>
          <div class="seg-2" style="width:${seg2}%"></div>
        </div>

        ${alts ? `
        <div class="alts">
          <div class="alts-label">Nächstbeste Tipps</div>
          <div class="alts-list">${alts}</div>
        </div>` : ""}
      </article>
    `;
  }

  // ---------- render match list grouped by day ----------
  let activeFilter = "all";
  let activeSort = "date";
  let searchTerm = "";

  function applyFilters(list) {
    let out = [...list];
    if (activeFilter === "high") out = out.filter((m) => m.ev >= 2.0);
    else if (activeFilter === "close") out = out.filter((m) => m.isClose);
    else if (activeFilter === "ger") out = out.filter((m) => m.germany);
    if (searchTerm) {
      const q = searchTerm.toLowerCase();
      out = out.filter((m) => m.home.toLowerCase().includes(q) || m.away.toLowerCase().includes(q));
    }
    if (activeSort === "ev-desc") out.sort((a, b) => b.ev - a.ev);
    else if (activeSort === "ev-asc") out.sort((a, b) => a.ev - b.ev);
    return out;
  }

  function renderMatches() {
    const host = $("#match-list");
    if (!host) return;
    const filtered = applyFilters(matches);

    if (filtered.length === 0) {
      host.innerHTML = `<div style="padding:64px 0;text-align:center;color:var(--muted);font-family:var(--mono);font-size:14px">Keine Spiele entsprechen den Filtern.</div>`;
      return;
    }

    if (activeSort === "date") {
      const groups = {};
      filtered.forEach((m) => { (groups[m.date] = groups[m.date] || []).push(m); });
      const html = Object.keys(groups).map((date) => {
        const list = groups[date];
        return `
          <section class="day-group">
            <div class="day-header">
              <div>
                <div class="weekday">${WEEKDAYS[date] || ""}</div>
              </div>
              <div class="date">${date.replace(/\.(\d{2})\.$/, ". $1").replace(/^(\d{2})\./, "$1.")}</div>
              <div class="count">${list.length} Spiel${list.length === 1 ? "" : "e"}</div>
            </div>
            <div class="match-grid">${list.map(matchCard).join("")}</div>
          </section>
        `;
      }).join("");
      host.innerHTML = html;
    } else {
      host.innerHTML = `
        <section class="day-group">
          <div class="day-header">
            <div><div class="weekday">Sortiert nach Expected Value</div></div>
            <div class="date">EV</div>
            <div class="count">${filtered.length} Spiele</div>
          </div>
          <div class="match-grid">${filtered.map(matchCard).join("")}</div>
        </section>
      `;
    }
  }

  // ---------- filter / sort wiring ----------
  function wireControls() {
    $$(".chip").forEach((chip) => {
      chip.addEventListener("click", () => {
        $$(".chip").forEach((c) => c.classList.remove("active"));
        chip.classList.add("active");
        activeFilter = chip.dataset.filter;
        renderMatches();
      });
    });
    const sortEl = $("#sort");
    if (sortEl) sortEl.addEventListener("change", (e) => {
      activeSort = e.target.value;
      renderMatches();
    });
    let debounce;
    const searchEl = $("#search");
    if (searchEl) searchEl.addEventListener("input", (e) => {
      clearTimeout(debounce);
      debounce = setTimeout(() => {
        searchTerm = e.target.value.trim();
        renderMatches();
      }, 120);
    });

    // Refresh button → real /refresh endpoint
    const refreshBtn = $("#refresh");
    if (refreshBtn) {
      refreshBtn.addEventListener("click", () => {
        if (refreshBtn.classList.contains("spinning")) return;
        refreshBtn.classList.add("spinning");
        setTimeout(() => { window.location.href = "/refresh"; }, 300);
      });
    }
  }

  // ---------- reveal-on-scroll ----------
  function wireReveal() {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
      });
    }, { threshold: 0.08, rootMargin: "0px 0px -40px 0px" });
    $$("[data-reveal]").forEach((el) => io.observe(el));
  }

  // ---------- init ----------
  function init() {
    renderError();
    computeStats();
    renderTable();
    renderHistogram();
    renderMatches();
    wireControls();
    wireReveal();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
