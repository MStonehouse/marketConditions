let payload = null,
  range = "1M";
const $ = (s) => document.querySelector(s);
function scoreColor(v) {
  if (v >= 65) return "var(--green)";
  if (v < 35) return "var(--red)";
  return "var(--neutral)";
}
function sentimentClass(v) {
  if (v >= 81) return "Extreme Greed";
  if (v >= 66) return "Greed";
  if (v >= 56) return "Optimistic";
  if (v >= 45) return "Neutral";
  if (v >= 35) return "Cautious";
  if (v >= 20) return "Fear";
  return "Extreme Fear";
}
function drawComponents(target, items) {
  $(target).innerHTML = items
    .map(
      (c) =>
        `<div class="component"><div><div class="componentName">${c.name}</div><div class="componentDetail">${c.detail} · ${c.weight}%</div></div><div class="componentScore" style="color:${scoreColor(c.score)}">${Math.round(c.score)}</div><div class="componentArrow">${c.direction}</div></div>`,
    )
    .join("");
}
function normalize(vals) {
  const f = vals.filter(Number.isFinite);
  if (!f.length) return vals.map(() => null);
  const lo = Math.min(...f),
    hi = Math.max(...f);
  return vals.map((v) =>
    Number.isFinite(v)
      ? hi === lo
        ? 50
        : 10 + (80 * (v - lo)) / (hi - lo)
      : null,
  );
}
function subset(h, r) {
  const end = new Date(h[h.length - 1].date + "T00:00:00"),
    days = r === "1M" ? 31 : r === "1Y" ? 366 : r === "5Y" ? 1827 : 3653,
    start = new Date(end - days * 86400000);
  return h.filter((d) => new Date(d.date + "T00:00:00") >= start);
}
function drawChart() {
  const c = $("#mainChart"),
    rect = c.getBoundingClientRect(),
    dpr = devicePixelRatio || 1;
  c.width = Math.floor(rect.width * dpr);
  c.height = Math.floor(rect.height * dpr);
  const x = c.getContext("2d");
  x.scale(dpr, dpr);
  const W = rect.width,
    H = rect.height,
    L = 42,
    R = 20,
    T = 18,
    B = 32,
    d = subset(payload.history, range),
    sp = normalize(d.map((v) => v.sp500));
  if (!d.length) return;
  const xx = (i) => L + (W - L - R) * (i / Math.max(1, d.length - 1)),
    yy = (v) => T + (H - T - B) * (1 - v / 100);
  x.clearRect(0, 0, W, H);
  x.font = "11px system-ui";
  x.fillStyle = "#7f8a96";
  x.textAlign = "right";
  [20, 40, 60, 80].forEach((v) => {
    x.strokeStyle = "#27303a";
    x.beginPath();
    x.moveTo(L, yy(v));
    x.lineTo(W - R, yy(v));
    x.stroke();
    x.fillText(v, L - 7, yy(v) + 4);
  });
  function line(key, color, vals, step) {
    x.strokeStyle = color;
    x.lineWidth = 2;
    x.beginPath();
    let started = false,
      py = null;
    d.forEach((o, i) => {
      const v = vals ? vals[i] : o[key];
      if (!Number.isFinite(v)) return;
      const X = xx(i),
        Y = yy(v);
      if (!started) {
        x.moveTo(X, Y);
        started = true;
      } else if (step) {
        x.lineTo(X, py);
        x.lineTo(X, Y);
      } else x.lineTo(X, Y);
      py = Y;
    });
    x.stroke();
  }
  line("economic", "#e8eef4", null, true);
  line("sentiment", "#9fb7d4");
  line(null, "#b8c58c", sp);
  const labels = range === "1M" ? 4 : 6;
  x.fillStyle = "#7f8a96";
  x.textAlign = "center";
  for (let j = 0; j < labels; j++) {
    const i = Math.round(((d.length - 1) * j) / (labels - 1)),
      dt = new Date(d[i].date + "T00:00:00"),
      txt =
        range === "1M"
          ? dt.toLocaleDateString(undefined, { month: "short", day: "numeric" })
          : dt.getFullYear();
    x.fillText(txt, xx(i), H - 8);
  }
}
function render() {
  const e = payload.current.economic,
    s = payload.current.sentiment,
    p = payload.current.sp500;
  $("#updated").textContent = `Updated ${payload.generated_at}`;
  $("#economicScore").textContent = Math.round(e.score);
  $("#economicScore").style.color = scoreColor(e.score);
  $("#economicDir").textContent = e.direction;
  $("#economicClass").textContent = e.classification;
  $("#economicChange").textContent =
    `3-month change: ${e.change_3m >= 0 ? "+" : ""}${e.change_3m.toFixed(1)} points`;
  $("#sentimentScore").textContent = Math.round(s.score);
  $("#sentimentScore").style.color = scoreColor(s.score);
  $("#sentimentDir").textContent = s.direction;
  $("#sentimentClass").textContent = sentimentClass(s.score);
  $("#sentimentChange").textContent =
    `1-month change: ${s.change_1m >= 0 ? "+" : ""}${s.change_1m.toFixed(1)} points`;
  $("#spxValue").textContent = p.value ? Number(p.value).toLocaleString() : "—";
  $("#spxMove").textContent =
    p.change_1m == null
      ? "Display only"
      : `1M ${p.change_1m >= 0 ? "+" : ""}${p.change_1m.toFixed(2)}%`;
  drawComponents("#economicComponents", e.components);
  drawComponents("#sentimentComponents", s.components);
  drawChart();
}
document.querySelectorAll(".rangeButtons button").forEach(
  (b) =>
    (b.onclick = () => {
      range = b.dataset.range;
      document
        .querySelectorAll(".rangeButtons button")
        .forEach((q) => q.classList.toggle("active", q === b));
      drawChart();
    }),
);
addEventListener("resize", () => payload && drawChart());
fetch("data/dashboard.json", { cache: "no-store" })
  .then((r) => r.json())
  .then((j) => {
    payload = j;
    render();
  })
  .catch((e) =>
    document.body.insertAdjacentHTML(
      "afterbegin",
      `<div class="error">${e.message}</div>`,
    ),
  );
