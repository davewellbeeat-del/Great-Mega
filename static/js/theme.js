// Loaded in <head> so the saved theme is applied before the page paints (no flash).
(function () {
  const KEY = "greatMegaTheme2";

  // [name, hex]
  const ACCENTS = [
    ["Blue", "#1a7bff"], ["Yellow", "#f7c331"], ["Green", "#17c47a"], ["Orange", "#ff8a3d"],
    ["Red", "#ff4d5e"], ["Pink", "#ff5fb0"], ["Purple", "#a46bff"], ["Indigo", "#6a76ff"],
    ["Cyan", "#25c7f0"], ["Teal", "#14b8a6"], ["Lime", "#9be234"], ["Silver", "#c9d4e6"],
  ];

  // [key, label, preview colour]
  const BACKGROUNDS = [
    ["navy", "Navy", "#0a2142"], ["black", "Black", "#0a0a0a"], ["charcoal", "Charcoal", "#1b1e25"],
    ["forest", "Forest", "#0a2018"], ["plum", "Plum", "#1d0c33"], ["light", "Light", "#e4ecf7"],
  ];

  const DEFAULTS = { accent: "#1a7bff", bg: "navy" };

  function load() {
    try {
      const t = JSON.parse(localStorage.getItem(KEY));
      if (t && /^#[0-9a-f]{6}$/i.test(t.accent) && BACKGROUNDS.some((b) => b[0] === t.bg)) {
        return { accent: t.accent.toLowerCase(), bg: t.bg };
      }
    } catch (e) { /* no saved theme, or storage blocked */ }
    return { ...DEFAULTS };
  }

  function save(t) {
    try { localStorage.setItem(KEY, JSON.stringify(t)); } catch (e) { /* ignore */ }
  }

  // WCAG relative luminance, used to pick readable text (dark or white) on the accent colour
  function luminance(hex) {
    const n = parseInt(hex.slice(1), 16);
    const ch = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => {
      v /= 255;
      return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2];
  }

  // White text unless it would be hard to read on that colour (contrast below 3:1), then dark text.
  function inkFor(hex) {
    const contrastWhite = 1.05 / (luminance(hex) + 0.05);
    return contrastWhite >= 3 ? "#ffffff" : "#0b1220";
  }

  let theme = load();

  // colour of the phone status bar / app title bar for each background
  const BAR = { navy: "#061326", black: "#000000", charcoal: "#14161b", forest: "#05110c", plum: "#10061c", light: "#f1f5fb" };

  function apply() {
    const root = document.documentElement;
    root.setAttribute("data-bg", theme.bg);
    root.style.setProperty("--accent", theme.accent);
    root.style.setProperty("--accent-ink", inkFor(theme.accent));
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", BAR[theme.bg] || BAR.navy);
  }
  apply();
  // <meta> may not exist yet when this runs in <head>; set it again once the page has loaded
  document.addEventListener("DOMContentLoaded", apply);

  window.Theme = {
    ACCENTS, BACKGROUNDS, DEFAULTS, inkFor,
    get: () => ({ ...theme }),
    set(patch) { theme = { ...theme, ...patch }; apply(); save(theme); },
    reset() { theme = { ...DEFAULTS }; apply(); save(theme); },
  };
})();
