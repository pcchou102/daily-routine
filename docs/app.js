"use strict";

const PALETTE = [
  "#4e9bff", "#2ecc71", "#e74c3c", "#f1c40f", "#9b59b6",
  "#1abc9c", "#e67e22", "#ff6b9d", "#7f8c8d", "#46c2cb",
];

let DATA = null;          // { fund, series:[{date, summary, holdings:[...]}] }
let chart = null;
const selected = new Set();

function fmtInt(n) {
  return (n == null) ? "-" : Math.round(n).toLocaleString("en-US");
}
function fmtLots(shares) {
  // 股數 → 張（1 張 = 1000 股）
  return (shares == null) ? "-" : Math.round(shares / 1000).toLocaleString("en-US");
}
function fmtRate(r) {
  return (typeof r === "number") ? r.toFixed(2) + "%" : "-";
}

async function load() {
  const res = await fetch("history.json", { cache: "no-store" });
  if (!res.ok) throw new Error("history.json 載入失敗：" + res.status);
  DATA = await res.json();
  DATA.series.sort((a, b) => a.date.localeCompare(b.date));

  const dates = DATA.series.map((s) => s.date);
  document.getElementById("subtitle").textContent =
    `資料區間 ${dates[0] ?? "—"} ~ ${dates[dates.length - 1] ?? "—"}（共 ${dates.length} 個交易日）`;

  buildPicker();
  renderTable();
  // 預設顯示最新權重前 5 大
  topN(5);
}

// 收集所有出現過的股票（以最新權重排序），建立可點選 chips
function allStocks() {
  const map = new Map(); // code -> {code,name,latestRate}
  for (const s of DATA.series) {
    for (const h of s.holdings) {
      map.set(h.code, { code: h.code, name: h.name, latestRate: h.nav_rate ?? 0 });
    }
  }
  return [...map.values()].sort((a, b) => b.latestRate - a.latestRate);
}

function buildPicker() {
  const picker = document.getElementById("picker");
  picker.innerHTML = "";
  for (const st of allStocks()) {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.dataset.code = st.code;
    chip.textContent = `${st.code} ${st.name}`;
    chip.onclick = () => {
      if (selected.has(st.code)) selected.delete(st.code);
      else selected.add(st.code);
      syncChips();
      renderChart();
    };
    picker.appendChild(chip);
  }
}

function syncChips() {
  document.querySelectorAll(".chip").forEach((c) => {
    c.classList.toggle("active", selected.has(c.dataset.code));
  });
}

function rangeDates() {
  const n = parseInt(document.getElementById("range").value, 10);
  const all = DATA.series.map((s) => s.date);
  if (!n || all.length <= n) return all;
  return all.slice(all.length - n);
}

function renderChart() {
  const dates = rangeDates();
  const dateSet = new Set(dates);
  const codes = [...selected];

  const datasets = codes.map((code, i) => {
    const color = PALETTE[i % PALETTE.length];
    const data = DATA.series
      .filter((s) => dateSet.has(s.date))
      .map((s) => {
        const h = s.holdings.find((x) => x.code === code);
        return { x: s.date, y: h ? h.nav_rate : null };
      });
    const name = (allStocks().find((x) => x.code === code) || {}).name || "";
    return {
      label: `${code} ${name}`,
      data, borderColor: color, backgroundColor: color,
      tension: 0.2, spanGaps: true, pointRadius: dates.length > 60 ? 0 : 3,
    };
  });

  const cfg = {
    type: "line",
    data: { labels: dates, datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { labels: { color: "#e7e9ee" } },
        tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${fmtRate(c.parsed.y)}` } },
      },
      scales: {
        x: { ticks: { color: "#9aa0ad", maxRotation: 0, autoSkip: true }, grid: { color: "#2a2f3a" } },
        y: { ticks: { color: "#9aa0ad", callback: (v) => v + "%" }, grid: { color: "#2a2f3a" }, title: { display: true, text: "占淨值比", color: "#9aa0ad" } },
      },
    },
  };

  if (chart) { chart.data = cfg.data; chart.options = cfg.options; chart.update(); }
  else chart = new Chart(document.getElementById("chart"), cfg);
}

function topN(n) {
  selected.clear();
  allStocks().slice(0, n).forEach((s) => selected.add(s.code));
  syncChips();
  renderChart();
}

function renderTable() {
  const series = DATA.series;
  if (!series.length) return;
  const latest = series[series.length - 1];
  const prev = series.length > 1 ? series[series.length - 2] : null;
  document.getElementById("latestDate").textContent = `（${latest.date}）`;

  const prevRank = new Map();
  if (prev) {
    [...prev.holdings]
      .sort((a, b) => (b.nav_rate ?? 0) - (a.nav_rate ?? 0))
      .forEach((h, i) => prevRank.set(h.code, i + 1));
  }
  const prevRate = new Map((prev ? prev.holdings : []).map((h) => [h.code, h.nav_rate]));
  const prevShare = new Map((prev ? prev.holdings : []).map((h) => [h.code, h.share]));

  const rows = [...latest.holdings].sort((a, b) => (b.nav_rate ?? 0) - (a.nav_rate ?? 0));
  const tbody = document.querySelector("#holdingsTable tbody");
  tbody.innerHTML = "";

  rows.forEach((h, idx) => {
    const rank = idx + 1;
    const dRate = prevRate.has(h.code) ? (h.nav_rate - prevRate.get(h.code)) : null;
    const pr = prevRank.get(h.code);
    const dRank = pr ? (pr - rank) : null; // 正=排名上升

    // 當日操作判定：新進場或股數增加=買(紅)、股數減少=賣(綠)、股數不變=不上色
    let op = "flat";
    if (!prevShare.has(h.code)) {
      op = "buy";
    } else {
      const dShare = (h.share ?? 0) - (prevShare.get(h.code) ?? 0);
      if (dShare > 0) op = "buy";
      else if (dShare < 0) op = "sell";
    }

    const rateCell = (dRate == null)
      ? `<span class="${op}">新增</span>`
      : (Math.abs(dRate) < 0.005 ? `<span class="flat">—</span>`
         : `<span class="${op}">${dRate > 0 ? "▲" : "▼"} ${Math.abs(dRate).toFixed(2)}%</span>`);

    const rankCell = (dRank == null)
      ? `<span class="${op}">NEW</span>`
      : (dRank === 0 ? `<span class="flat">—</span>`
         : `<span class="${op}">${dRank > 0 ? "▲" : "▼"} ${Math.abs(dRank)}</span>`);

    const tr = document.createElement("tr");
    tr.innerHTML =
      `<td>${rank}</td><td>${h.name}</td><td>${h.code}</td>` +
      `<td>${fmtRate(h.nav_rate)}</td><td>${rateCell}</td><td>${rankCell}</td><td>${fmtLots(h.share)}</td>`;
    tbody.appendChild(tr);
  });
}

document.getElementById("range").onchange = renderChart;
document.getElementById("top5").onclick = () => topN(5);
document.getElementById("clear").onclick = () => { selected.clear(); syncChips(); renderChart(); };

load().catch((e) => {
  document.getElementById("subtitle").textContent = "載入失敗：" + e.message;
});
