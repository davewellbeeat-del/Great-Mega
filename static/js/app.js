// GREAT MEGA front end
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function esc(text) {
  const d = document.createElement("div");
  d.textContent = String(text ?? "");
  return d.innerHTML.replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

let toastTimer;
function toast(message, isError = false) {
  const el = $("#toast");
  el.textContent = message;
  el.className = "toast show" + (isError ? " error" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (el.className = "toast"), 3200);
}

function fmtUptime(sec) {
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
  return h ? `${h}h ${m}m` : m ? `${m}m ${s}s` : `${s}s`;
}

function money(n, currency) {
  if (n === null || n === undefined || Number.isNaN(Number(n))) return "\u2014";
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency: currency || "USD" }).format(n);
  } catch (e) {
    return Number(n).toFixed(2) + (currency ? " " + currency : "");
  }
}
function signedMoney(n, currency) {
  if (n === null || n === undefined || Number.isNaN(Number(n))) return "\u2014";
  return (n > 0 ? "+" : n < 0 ? "-" : "") + money(Math.abs(n), currency);
}
const price = (v, digits) => (digits === null || digits === undefined ? String(v) : Number(v).toFixed(digits));
const tone = (n) => (n > 0 ? "profit-up" : n < 0 ? "profit-down" : "");

async function api(path, method = "GET", body) {
  const res = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json", "X-Requested-With": "GreatMega" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (res.status === 401) {                 // login expired or password changed
    location.href = "/login";
    throw new Error("Please log in.");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}

// ---------------------------------------------------------------- pages
const PAGES = {
  dashboard: "Dashboard", bots: "Bot Control", accounts: "My Accounts",
  analytics: "Analytics", history: "Trade History", settings: "Settings", support: "Support",
};

function showPage() {
  const hash = (location.hash || "#dashboard").slice(1);
  const page = PAGES[hash] ? hash : "dashboard";
  $$(".page").forEach((p) => p.classList.toggle("active", p.id === "page-" + page));
  $$("#nav .nav-link").forEach((a) => a.classList.toggle("active", a.dataset.page === page));
  $("#topTitle").textContent = PAGES[page];
  window.scrollTo(0, 0);
  if (page === "history") loadHistory();
}
const currentPage = () => (location.hash || "#dashboard").slice(1);
window.addEventListener("hashchange", showPage);

// ---------------------------------------------------------------- rendering
let state = { bots: [], activity: [], instruments: [], limits: { min_lot: 0.01, max_lot: 10 } };

function botCard(b) {
  const lock = b.running ? "disabled" : "";
  return `
    <div class="bot-card" data-id="${esc(b.id)}">
      <h3>${esc(b.name)}</h3>
      <p class="bot-description">${esc(b.description || "No description provided.")}</p>
      <span class="bot-status ${b.running ? "on" : "off"}">${b.running ? "&#9679; ACTIVE" : "&#9679; INACTIVE"}</span>

      <div class="bot-info"><span>Magic Number</span><strong>${esc(b.magic)}</strong></div>
      <div class="bot-info"><span>Instrument</span><strong>${esc(b.instrument)}</strong></div>
      <div class="bot-info">
        <span>Lot size</span>
        <span class="lot-edit">
          <input class="lot-input" type="number" step="0.01" min="${state.limits.min_lot}" max="${state.limits.max_lot}"
                 value="${b.lot_size.toFixed(2)}" ${lock} aria-label="Lot size for ${esc(b.name)}">
          <button class="btn btn-secondary btn-sm" data-action="lot" ${lock}>Save</button>
        </span>
      </div>

      <div class="bot-actions">
        <button class="btn ${b.running ? "btn-warning" : "btn-primary"}" data-action="toggle">${b.running ? "Stop" : "Activate"}</button>
        <button class="btn btn-secondary" data-action="edit" ${lock} title="${b.running ? "Stop the bot to edit it" : ""}">Edit</button>
        <button class="btn btn-danger" data-action="delete" ${lock} title="${b.running ? "Stop the bot to delete it" : ""}">Delete</button>
      </div>
      ${b.running ? `<div class="bot-uptime">Active for ${fmtUptime(b.uptime_seconds)}</div>` : ""}
    </div>`;
}

function isTypingLot() {
  const a = document.activeElement;
  return !!(a && a.classList && a.classList.contains("lot-input"));
}

function render() {
  renderMt5();
  const { bots, activity, limits } = state;
  const running = bots.filter((b) => b.running).length;

  $("#statActive").textContent = `${running} / ${bots.length}`;

  $("#botSummary").innerHTML = bots.length
    ? bots.map((b) => `
        <div class="sum-row">
          <span>${esc(b.name)}</span>
          <span class="pill ${b.running ? "on" : "off"}">&#9679; ${b.running ? "Active" : "Inactive"}</span>
        </div>`).join("")
    : '<p class="muted">No bots yet.</p>';

  if (!isTypingLot()) {            // don't redraw while someone is typing a lot size
    $("#botGrid").innerHTML = bots.length
      ? bots.map(botCard).join("")
      : '<div class="empty-note">No bots yet. Click "Register New Bot" to add one.</div>';
  }

  $("#activity").innerHTML = activity.length
    ? activity.map((a) => `<div class="act-row"><time>${esc(a.time)}</time>${esc(a.message)}</div>`).join("")
    : '<p class="muted">No activity yet.</p>';

  $("#maxLotInfo").textContent = Number(limits.max_lot).toFixed(2);

  const protectedSite = !!(state.auth && state.auth.enabled);
  $("#logoutBtn").hidden = !protectedSite;
  $("#pwRemove").hidden = !protectedSite;
  $("#currentPwRow").hidden = !protectedSite;
  $("#pwSubmit").textContent = protectedSite ? "Change password" : "Set password";
  $("#authInfo").textContent = protectedSite
    ? "Password protection is ON. Anyone opening this site must log in."
    : "No password is set, so the site only answers this computer. Set one to use it from your phone.";
}

// ---------------------------------------------------------------- MetaTrader 5 (read-only)
const MODE_LABEL = { demo: "DEMO", real: "REAL", contest: "CONTEST", unknown: "?" };
let lastWatchKey = "";

function setHtmlIfChanged(el, html) {
  if (el.dataset.html !== html) { el.innerHTML = html; el.dataset.html = html; }
}

function renderMt5() {
  const m = state.mt5 || { status: "starting", message: "", account: null, positions: [], market: [], watchlist: [] };
  const a = m.account;
  const connected = m.status === "connected" && !!a;
  const ccy = a ? a.currency : "";

  // status chip in the top bar
  const chip = $("#mt5Chip");
  let chipState = "wait", full = "Connecting to MT5\u2026", short = "MT5";
  if (connected) {
    chipState = a.is_real ? "real" : "ok";
    full = `MT5 connected \u00b7 ${MODE_LABEL[a.mode] || "?"}`;
    short = MODE_LABEL[a.mode] || "MT5";
  } else if (m.status === "not_installed") { chipState = "bad"; full = "MT5 not set up"; short = "Setup"; }
  else if (m.status === "disconnected") { chipState = "bad"; full = "MT5 not connected"; short = "Offline"; }
  chip.dataset.state = chipState;
  $("#mt5ChipFull").textContent = full;
  $("#mt5ChipShort").textContent = short;

  // banners
  $("#realBanner").hidden = !(connected && a.is_real);
  const notice = $("#mt5Notice");
  notice.hidden = connected || !m.message;
  notice.textContent = m.message || "";

  // account selector (one account: whichever MT5 is logged in to)
  const select = $("#accountSelect");
  const label = connected ? `${MODE_LABEL[a.mode]} \u00b7 ${a.login} \u00b7 ${a.server}` : "Not connected";
  if (select.dataset.label !== label) { select.innerHTML = `<option>${esc(label)}</option>`; select.dataset.label = label; }

  // stat cards
  $("#statBalance").textContent = connected ? money(a.balance, ccy) : "\u2014";
  $("#statBalanceSub").textContent = connected ? `Live \u00b7 ${a.currency}` : "MT5 not connected";
  $("#statEquity").textContent = connected ? money(a.equity, ccy) : "\u2014";
  $("#statEquitySub").textContent = connected ? `Free margin ${money(a.free_margin, ccy)}` : "MT5 not connected";
  const profit = $("#statProfit");
  profit.textContent = connected ? signedMoney(a.profit, ccy) : "\u2014";
  profit.className = "stat-value " + (connected ? tone(a.profit) : "");
  $("#statProfitSub").textContent = connected
    ? (m.today_profit === null ? "Open positions" : `Closed today: ${signedMoney(m.today_profit, ccy)}`)
    : "MT5 not connected";

  // market watch
  $("#marketTag").textContent = connected ? "Live" : "Not connected";
  setHtmlIfChanged($("#marketRows"), connected
    ? (m.market.length ? m.market.map((r) => {
        if (r.error) {
          return `<div class="mkt-row"><div><strong>${esc(r.requested)}</strong><small>${esc(r.error)}</small></div><div class="r"><small class="down">&mdash;</small></div></div>`;
        }
        const ch = r.change_pct;
        const chText = ch === null || ch === undefined ? "" : `${ch > 0 ? "+" : ""}${ch.toFixed(2)}%`;
        const sub = r.symbol !== r.requested ? esc(r.symbol) : "";
        return `<div class="mkt-row"><div><strong>${esc(r.requested)}</strong><small>${sub}</small></div>
                <div class="r"><strong>${r.price.toFixed(r.digits)}</strong><small class="${ch > 0 ? "up" : ch < 0 ? "down" : ""}">${chText}</small></div></div>`;
      }).join("") : '<p class="muted">Add symbols in Settings.</p>')
    : '<p class="muted">Connect MetaTrader 5 to see live prices.</p>');

  // open positions
  $("#posCount").textContent = connected ? String(m.positions.length) : "0";
  setHtmlIfChanged($("#positionsBody"), connected && m.positions.length
    ? m.positions.map((p) => {
        const bot = state.bots.find((b) => b.magic === p.magic);
        return `<tr><td>${esc(p.symbol)}</td><td>${esc(p.type.toUpperCase())}</td>
                <td class="num">${p.volume.toFixed(2)}</td><td class="num">${price(p.price_open, p.digits)}</td><td class="num">${price(p.price_current, p.digits)}</td>
                <td class="num ${tone(p.profit)}">${signedMoney(p.profit, ccy)}</td><td>${bot ? esc(bot.name) : (p.magic ? "Magic " + esc(p.magic) : "Manual")}</td></tr>`;
      }).join("")
    : `<tr><td colspan="7" class="empty-cell">${connected ? "No open positions." : "Connect MetaTrader 5 to see positions."}</td></tr>`);

  // My Accounts page
  setHtmlIfChanged($("#accountCard"), connected ? `
    <dl class="kv">
      <dt>Mode</dt><dd><span class="badge-mode ${esc(a.mode)}">${esc(MODE_LABEL[a.mode] || "?")}</span></dd>
      <dt>Name</dt><dd>${esc(a.name)}</dd>
      <dt>Login</dt><dd>${esc(a.login)}</dd>
      <dt>Broker</dt><dd>${esc(a.company)}</dd>
      <dt>Server</dt><dd>${esc(a.server)}</dd>
      <dt>Currency / leverage</dt><dd>${esc(a.currency)} \u00b7 1:${esc(a.leverage)}</dd>
      <dt>Balance</dt><dd>${money(a.balance, ccy)}</dd>
      <dt>Equity</dt><dd>${money(a.equity, ccy)}</dd>
      <dt>Margin used / free</dt><dd>${money(a.margin, ccy)} / ${money(a.free_margin, ccy)}</dd>
    </dl>`
    : `<h3>No MT5 account connected</h3><p class="muted">${esc(m.message || "Open MetaTrader 5 and log in to your account.")}</p>`);

  // Settings > MetaTrader 5
  $("#mt5Message").textContent = connected
    ? `Connected (read-only) to ${a.company} \u00b7 ${MODE_LABEL[a.mode]} account ${a.login}.`
    : (m.message || "Not connected.");
  setHtmlIfChanged($("#mt5Info"), connected
    ? `<dt>Server</dt><dd>${esc(a.server)}</dd><dt>Mode</dt><dd>${esc(MODE_LABEL[a.mode])}</dd>
       <dt>Last update</dt><dd>${new Date(m.updated_at * 1000).toLocaleTimeString()}</dd>`
    : "");
  const key = (m.watchlist || []).join(",");
  if (key !== lastWatchKey && document.activeElement !== $("#watchlistInput")) {
    $("#watchlistInput").value = (m.watchlist || []).join(", ");
    lastWatchKey = key;
  }
}

async function loadHistory() {
  try {
    const h = await api("/api/mt5/history?days=30");
    const ccy = state.mt5 && state.mt5.account ? state.mt5.account.currency : "";
    $("#historySummary").textContent = h.status === "connected" ? `${h.deals.length} trades \u00b7 net ${signedMoney(h.total, ccy)}` : "\u2014";
    const note = $("#historyNote");
    note.hidden = !h.message;
    note.textContent = h.message || "";
    setHtmlIfChanged($("#historyBody"), h.deals.length
      ? h.deals.map((d) => `<tr><td>${esc(d.time)}</td><td>${esc(d.symbol)}</td><td>${esc(d.type.toUpperCase())}</td>
          <td class="num">${d.volume.toFixed(2)}</td><td class="num">${price(d.price, d.digits)}</td>
          <td class="num ${tone(d.profit)}">${signedMoney(d.profit, ccy)}</td>
          <td class="num ${tone(d.net)}">${signedMoney(d.net, ccy)}</td><td>${d.magic || "Manual"}</td></tr>`).join("")
      : `<tr><td colspan="8" class="empty-cell">${h.status === "connected" ? "No closed trades in the last 30 days." : "Connect MetaTrader 5 to see your history."}</td></tr>`);
  } catch (err) {
    if (err.message !== "Please log in.") toast(err.message, true);
  }
}

let offline = false;
async function refresh() {
  try {
    state = await api("/api/state");
    offline = false;
    render();
  } catch (err) {
    if (err.message === "Please log in.") return;      // redirecting to the login page
    if (!offline) toast("Can't reach the server. Is it still running on your computer?", true);
    offline = true;
  }
}

async function act(fn, okMessage) {
  try {
    await fn();
    if (okMessage) toast(okMessage);
    await refresh();
  } catch (err) {
    toast(err.message, true);
  }
}

// ---------------------------------------------------------------- bot cards
$("#botGrid").addEventListener("click", (event) => {
  const btn = event.target.closest("button[data-action]");
  if (!btn || btn.disabled) return;
  const card = btn.closest(".bot-card");
  const bot = state.bots.find((b) => b.id === card.dataset.id);
  if (!bot) return;

  switch (btn.dataset.action) {
    case "toggle":
      act(() => api(`/api/bots/${bot.id}/${bot.running ? "stop" : "start"}`, "POST"),
          bot.running ? `${bot.name} deactivated` : `${bot.name} activated`);
      break;
    case "lot": {
      const lot = $(".lot-input", card).value;
      document.activeElement.blur();
      act(() => api(`/api/bots/${bot.id}/lot`, "POST", { lot }), "Lot size saved");
      break;
    }
    case "edit":
      openModal(bot);
      break;
    case "delete":
      if (confirm(`Delete ${bot.name}? This can't be undone.`)) {
        act(() => api(`/api/bots/${bot.id}`, "DELETE"), `${bot.name} deleted`);
      }
      break;
  }
});

// ---------------------------------------------------------------- quick actions
$("#startAll").addEventListener("click", () => {
  const idle = state.bots.filter((b) => !b.running).length;
  if (!idle) return toast("All bots are already active");
  if (confirm(`Activate ${idle} bot${idle > 1 ? "s" : ""}?`)) {
    act(() => api("/api/bots/start-all", "POST"), "Bots activated");
  }
});

$("#stopAll").addEventListener("click", () => {
  if (!state.bots.some((b) => b.running)) return toast("No bots are running");
  act(() => api("/api/bots/stop-all", "POST"), "All bots deactivated");
});

$("#addAccountBtn").addEventListener("click", () =>
  toast("GREAT MEGA follows the account MetaTrader 5 is logged in to. Switch accounts inside MT5."));

// ---------------------------------------------------------------- MT5 settings
$("#watchlistSave").addEventListener("click", async () => {
  $("#watchError").textContent = "";
  const symbols = $("#watchlistInput").value.split(/[,\s]+/).filter(Boolean);
  try {
    await api("/api/mt5/watchlist", "POST", { symbols });
    lastWatchKey = "";
    toast("Symbols saved");
    await refresh();
  } catch (err) {
    $("#watchError").textContent = err.message;
  }
});

$("#mt5Reconnect").addEventListener("click", async () => {
  const btn = $("#mt5Reconnect");
  btn.disabled = true;
  btn.textContent = "Connecting\u2026";
  try {
    await api("/api/mt5/reconnect", "POST");
    await refresh();
    toast(state.mt5 && state.mt5.status === "connected" ? "Connected to MetaTrader 5" : "Still not connected. See the message above.", !(state.mt5 && state.mt5.status === "connected"));
  } catch (err) {
    toast(err.message, true);
  } finally {
    btn.disabled = false;
    btn.textContent = "Reconnect to MT5";
  }
});

// ---------------------------------------------------------------- register / edit modal
function openModal(bot) {
  $("#botForm").reset();
  $("#formError").textContent = "";
  $("#botId").value = bot ? bot.id : "";
  $("#modalTitle").textContent = bot ? "Edit Bot" : "Register New Bot";
  if (bot) {
    $("#botName").value = bot.name;
    $("#botDescription").value = bot.description;
    $("#botMagic").value = bot.magic;
    $("#botLot").value = bot.lot_size.toFixed(2);
    $("#botInstrument").value = bot.instrument;
    $("#botFile").value = bot.file || "";
  }
  const modal = $("#botModal");
  modal.classList.add("show");
  modal.setAttribute("aria-hidden", "false");
  $("#botName").focus();
}

function closeModal() {
  const modal = $("#botModal");
  modal.classList.remove("show");
  modal.setAttribute("aria-hidden", "true");
}

$("#addBotBtn").addEventListener("click", () => openModal(null));
$("#cancelModal").addEventListener("click", closeModal);
$("#botModal").addEventListener("click", (e) => { if (e.target === e.currentTarget) closeModal(); });

$("#botForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const id = $("#botId").value;
  const body = {
    name: $("#botName").value,
    description: $("#botDescription").value,
    magic: $("#botMagic").value,
    instrument: $("#botInstrument").value,
    file: $("#botFile").value,
    lot_size: $("#botLot").value,
  };
  try {
    await api(id ? `/api/bots/${id}` : "/api/bots", id ? "PUT" : "POST", body);
    closeModal();
    toast(id ? "Bot updated" : "Bot registered");
    await refresh();
  } catch (err) {
    $("#formError").textContent = err.message;      // show the problem inside the form
  }
});

// ---------------------------------------------------------------- theme popover
function initTheme() {
  const btn = $("#themeBtn"), pop = $("#themePop");
  const swatches = $("#swatches"), bgOpts = $("#bgOpts"), custom = $("#customColor");

  swatches.innerHTML = Theme.ACCENTS.map(([name, hex]) =>
    `<button type="button" class="swatch" data-hex="${hex}" title="${name}" aria-label="${name}" style="background:${hex}"></button>`
  ).join("");

  bgOpts.innerHTML = Theme.BACKGROUNDS.map(([key, label, color]) =>
    `<button type="button" class="bg-opt" data-bg="${key}"><i style="background:${color}"></i>${label}</button>`
  ).join("");

  function sync() {
    const t = Theme.get();
    $$(".swatch", swatches).forEach((s) => s.classList.toggle("selected", s.dataset.hex === t.accent));
    $$(".bg-opt", bgOpts).forEach((b) => b.classList.toggle("selected", b.dataset.bg === t.bg));
    custom.value = t.accent;
  }

  swatches.addEventListener("click", (e) => {
    const s = e.target.closest(".swatch");
    if (s) { Theme.set({ accent: s.dataset.hex }); sync(); }
  });
  bgOpts.addEventListener("click", (e) => {
    const b = e.target.closest(".bg-opt");
    if (b) { Theme.set({ bg: b.dataset.bg }); sync(); }
  });
  custom.addEventListener("input", () => { Theme.set({ accent: custom.value.toLowerCase() }); sync(); });
  $("#themeReset").addEventListener("click", () => { Theme.reset(); sync(); });

  const setOpen = (open) => {
    pop.classList.toggle("show", open);
    btn.setAttribute("aria-expanded", String(open));
  };
  btn.addEventListener("click", (e) => { e.stopPropagation(); setOpen(!pop.classList.contains("show")); });
  document.addEventListener("click", (e) => { if (!pop.contains(e.target)) setOpen(false); });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { setOpen(false); closeModal(); }
  });
  sync();
}

// ---------------------------------------------------------------- password
$("#passwordForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("#pwError").textContent = "";
  try {
    await api("/api/auth/password", "POST", {
      current_password: $("#pwCurrent").value,
      new_password: $("#pwNew").value,
      repeat_password: $("#pwRepeat").value,
    });
    $("#passwordForm").reset();
    toast("Password saved");
    await refresh();
  } catch (err) {
    $("#pwError").textContent = err.message;
  }
});

$("#pwRemove").addEventListener("click", async () => {
  const current = $("#pwCurrent").value;
  if (!current) {
    $("#pwError").textContent = "Enter your current password to remove it.";
    return;
  }
  if (!confirm("Remove the password? Phones will no longer be able to connect.")) return;
  try {
    await api("/api/auth/remove", "POST", { current_password: current });
    $("#passwordForm").reset();
    toast("Password removed");
    await refresh();
  } catch (err) {
    $("#pwError").textContent = err.message;
  }
});

// ---------------------------------------------------------------- log out
$("#logoutBtn").addEventListener("click", async () => {
  try {
    await api("/logout", "POST");
  } catch (err) { /* already logged out */ }
  location.href = "/login";
});

// ---------------------------------------------------------------- installable app
let installPrompt = null;
const installBtn = $("#installBtn");
const isInstalled = window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();                    // keep the browser's own banner away; use our button
  installPrompt = event;
  if (!isInstalled) installBtn.hidden = false;
});

installBtn.addEventListener("click", async () => {
  if (!installPrompt) return;
  installPrompt.prompt();
  await installPrompt.userChoice;
  installPrompt = null;
  installBtn.hidden = true;
});

window.addEventListener("appinstalled", () => { installBtn.hidden = true; toast("GREAT MEGA installed"); });

// the service worker only works on https or localhost; elsewhere the site still works normally
if ("serviceWorker" in navigator && window.isSecureContext) {
  navigator.serviceWorker.register("/sw.js").catch(() => { /* not fatal */ });
}

// ---------------------------------------------------------------- start
showPage();
initTheme();
refresh();
setInterval(refresh, 3000);
setInterval(() => { if (currentPage() === "history") loadHistory(); }, 15000);
