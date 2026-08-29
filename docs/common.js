// Shared utilities for the macro dashboard UI.

const PRI = { must: "必須", next: "次に見る", advanced: "上級" };

const fmt = (v, d = 2) => (v === null || v === undefined || Number.isNaN(v)) ? "—" : Number(v).toFixed(d);

const signed = (v) => {
  if (v === null || v === undefined || Number.isNaN(v)) return { t: "—", c: "" };
  const n = Number(v);
  const t = (n > 0 ? "+" : "") + n.toFixed(2);
  const c = n > 0 ? "up" : n < 0 ? "down" : "";
  return { t, c };
};

function vixClass(last) {
  if (last == null) return "";
  if (last < 20) return "";
  if (last < 30) return "warn";
  return "down";
}

function lastClass(item) {
  const th = item.thresholds || {};
  if (th.vix) return vixClass(item.last);
  if (th.invert_red && item.last != null && item.last < 0) return "down";
  if (th.wider_is_red && item.chg_1d_pct != null && item.chg_1d_pct > 0) return "down";
  return "";
}

function strokeColor(item) {
  const v = item.chg_1d_pct;
  if (v == null) return "#7aa2d4";
  if (v > 0) return "#3dcc8a";
  if (v < 0) return "#ef6b6b";
  return "#7aa2d4";
}

function drawLine(canvas, item, pad) {
  const hist = item.history || {};
  const t = hist.t || [];
  const v = hist.v || [];
  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth || canvas.width;
  const h = canvas.clientHeight || canvas.height;
  canvas.width = Math.max(1, Math.floor(w * dpr));
  canvas.height = Math.max(1, Math.floor(h * dpr));
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);
  if (v.length < 2) {
    ctx.fillStyle = "#8b95a8";
    ctx.font = "12px sans-serif";
    ctx.fillText("データなし", 8, h / 2);
    return;
  }
  const lo = Math.min(...v);
  const hi = Math.max(...v);
  const span = hi - lo || 1;
  const p = pad || { l: 4, r: 4, t: 6, b: 6 };
  const x = (i) => p.l + i * (w - p.l - p.r) / (v.length - 1);
  const y = (val) => p.t + (1 - (val - lo) / span) * (h - p.t - p.b);
  const color = strokeColor(item);
  ctx.beginPath();
  ctx.moveTo(x(0), y(v[0]));
  for (let i = 1; i < v.length; i++) ctx.lineTo(x(i), y(v[i]));
  const lastY = y(v[v.length - 1]);
  ctx.lineTo(x(v.length - 1), h - p.b);
  ctx.lineTo(x(0), h - p.b);
  ctx.closePath();
  ctx.fillStyle = color + "22";
  ctx.fill();
  ctx.beginPath();
  ctx.moveTo(x(0), y(v[0]));
  for (let i = 1; i < v.length; i++) ctx.lineTo(x(i), y(v[i]));
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5;
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(x(v.length - 1), lastY, 2.4, 0, Math.PI * 2);
  ctx.fillStyle = color;
  ctx.fill();
  canvas._chart = { t, v, x, y, w, h };
}

function bindHover(canvas, item) {
  const tip = document.getElementById("tip");
  if (!tip) return;
  canvas.addEventListener("mousemove", (ev) => {
    const c = canvas._chart;
    if (!c || !c.v.length) return;
    const rect = canvas.getBoundingClientRect();
    const px = ev.clientX - rect.left;
    let best = 0, bestD = 1e9;
    for (let i = 0; i < c.v.length; i++) {
      const d = Math.abs(c.x(i) - px);
      if (d < bestD) { bestD = d; best = i; }
    }
    tip.style.display = "block";
    tip.style.left = (ev.clientX + 12) + "px";
    tip.style.top = (ev.clientY + 12) + "px";
    tip.textContent = `${item.name}  ${c.t[best]}  ${fmt(c.v[best])}`;
  });
  canvas.addEventListener("mouseleave", () => { tip.style.display = "none"; });
}

function bindClick(canvas, item) {
  canvas.addEventListener("click", () => {
    location.href = `detail.html?id=${encodeURIComponent(item.id)}`;
  });
}
