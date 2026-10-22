const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
let trendChart, histChart, currentQuery = null;

async function api(path, opts = {}) {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!r.ok) {
    let detail = r.statusText;
    try { detail = (await r.json()).detail || detail; } catch {}
    throw new Error(detail);
  }
  return r.status === 204 ? null : r.json();
}

function flash(text, err = false) {
  const m = $("msg");
  m.textContent = text; m.className = "msg" + (err ? " err" : ""); m.hidden = false;
  setTimeout(() => (m.hidden = true), 6000);
}

const fmt = (v, cur = "") => (v == null ? "-" : `${Number(v).toFixed(2)} ${cur}`.trim());
const fmtDate = (d) => new Date(d).toLocaleString();

async function loadOverview() {
  const o = await api("/analytics/overview");
  $("cards").innerHTML = [
    ["Tracked searches", o.tracked_queries], ["Listings tracked", o.products],
    ["Price captures", o.price_snapshots], ["Last capture", o.latest_capture ? fmtDate(o.latest_capture) : "-"],
  ].map(([l, v]) => `<div class="card"><span>${l}</span><b>${esc(v)}</b></div>`).join("");
}

async function loadQueries() {
  const qs = await api("/queries");
  $("queries").innerHTML = qs.length ? qs.map((q) => `
    <li><span><b>${esc(q.query)}</b> <span class="hint">${esc(q.marketplace)}</span></span>
      <span class="actions">
        <button class="ghost" data-open="${q.id}" data-name="${esc(q.query)}">View</button>
        <button class="ghost" data-ingest="${q.id}">Capture now</button>
        <button class="danger" data-del="${q.id}">Delete</button>
      </span></li>`).join("") : '<li class="hint">No searches yet - add one above.</li>';
}

async function openQuery(id, name) {
  currentQuery = id;
  $("trendPanel").hidden = false; $("productsPanel").hidden = false;
  $("trendTitle").textContent = `Market price trend: ${name}`;
  const trend = await api(`/queries/${id}/trend`);
  const labels = trend.map((t) => fmtDate(t.captured_at));
  const ds = (label, key, color) => ({ label, data: trend.map((t) => t[key]), borderColor: color, tension: .25 });
  trendChart?.destroy();
  trendChart = new Chart($("trendChart"), {
    type: "line",
    data: { labels, datasets: [ds("Min", "min_price", "#4ade80"), ds("Median", "median_price", "#38bdf8"), ds("Max", "max_price", "#f87171")] },
    options: { plugins: { legend: { labels: { color: "#e2e8f0" } } }, scales: { x: { ticks: { color: "#94a3b8" } }, y: { ticks: { color: "#94a3b8" } } } },
  });
  loadProducts();
}

async function loadProducts() {
  if (!currentQuery) return;
  const s = encodeURIComponent($("search").value);
  const ps = await api(`/products?query_id=${currentQuery}&limit=50&search=${s}`);
  $("products").innerHTML = ps.map((p) => `
    <tr><td>${p.image_url ? `<img src="${esc(p.image_url)}" alt="">` : ""}</td>
      <td>${esc(p.title)}</td><td>${esc(p.condition || "-")}</td>
      <td>${fmt(p.latest_price, p.currency)}</td><td>${p.snapshot_count}</td>
      <td><button class="ghost" data-details="${p.id}">Details</button></td></tr>`).join("");
}

async function showDetails(id) {
  const [p, st, hist] = await Promise.all([api(`/products/${id}`), api(`/products/${id}/statistics`), api(`/products/${id}/history`)]);
  $("mTitle").textContent = p.title;
  $("mLink").href = p.item_url || "#";
  const cls = st.absolute_change > 0 ? "up" : st.absolute_change < 0 ? "down" : "";
  $("mStats").innerHTML = [
    ["Current", fmt(st.current_price, st.currency)], ["Lowest", fmt(st.lowest_price)], ["Highest", fmt(st.highest_price)],
    ["Average", fmt(st.average_price)], ["Change", `<span class="${cls}">${st.percentage_change}%</span>`], ["Captures", st.snapshot_count],
  ].map(([l, v]) => `<div>${l}<b>${v}</b></div>`).join("");
  histChart?.destroy();
  histChart = new Chart($("histChart"), {
    type: "line",
    data: { labels: hist.map((h) => fmtDate(h.captured_at)), datasets: [{ label: "Price", data: hist.map((h) => h.price), borderColor: "#38bdf8", tension: .25 }] },
    options: { plugins: { legend: { labels: { color: "#e2e8f0" } } }, scales: { x: { ticks: { color: "#94a3b8" } }, y: { ticks: { color: "#94a3b8" } } } },
  });
  $("modal").hidden = false;
}

async function refreshAll() {
  await Promise.all([loadOverview(), loadQueries()]);
  if (currentQuery) { const q = document.querySelector(`[data-open="${currentQuery}"]`); if (q) openQuery(currentQuery, q.dataset.name); }
}

async function guarded(btn, fn) {
  btn.disabled = true;
  try { await fn(); } catch (e) { flash(e.message, true); } finally { btn.disabled = false; }
}

$("addForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  await guarded(e.submitter, async () => {
    await api("/queries", { method: "POST", body: JSON.stringify({ query: $("qInput").value }) });
    $("qInput").value = ""; await refreshAll();
  });
});
$("runAll").onclick = (e) => guarded(e.target, async () => {
  const r = await api("/ingest", { method: "POST" });
  flash(`Ingestion done: ${r.reduce((a, x) => a + x.listings, 0)} listings captured`); await refreshAll();
});
$("queries").addEventListener("click", (e) => {
  const b = e.target.closest("button"); if (!b) return;
  if (b.dataset.open) openQuery(b.dataset.open, b.dataset.name);
  if (b.dataset.ingest) guarded(b, async () => { const r = await api(`/queries/${b.dataset.ingest}/ingest`, { method: "POST" }); flash(`${r.listings} listings captured`); await refreshAll(); });
  if (b.dataset.del && confirm("Delete this search and all its history?")) guarded(b, async () => {
    await api(`/queries/${b.dataset.del}`, { method: "DELETE" });
    if (currentQuery == b.dataset.del) { currentQuery = null; $("trendPanel").hidden = $("productsPanel").hidden = true; }
    await refreshAll();
  });
});
$("products").addEventListener("click", (e) => { const b = e.target.closest("[data-details]"); if (b) showDetails(b.dataset.details); });
$("search").addEventListener("input", loadProducts);
$("closeModal").onclick = () => ($("modal").hidden = true);
$("modal").addEventListener("click", (e) => { if (e.target.id === "modal") $("modal").hidden = true; });

refreshAll().catch((e) => flash(e.message, true));
