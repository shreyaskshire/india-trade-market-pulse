const DATA_URL = "./data/dashboard.json";
const ONE_HOUR = 60 * 60 * 1000;

const state = {
  data: null,
  searchTerm: "",
};

const summaryGrid = document.querySelector("#summary-grid");
const tradeSignals = document.querySelector("#trade-signals");
const tradeHeadlines = document.querySelector("#trade-headlines");
const indiaBusiness = document.querySelector("#india-business");
const globalBusiness = document.querySelector("#global-business");
const topGainers = document.querySelector("#top-gainers");
const topLosers = document.querySelector("#top-losers");
const mostActive = document.querySelector("#most-active");
const watchlistTable = document.querySelector("#watchlist-table");
const refreshStatus = document.querySelector("#refresh-status");
const stocksNote = document.querySelector("#stocks-note");
const searchInput = document.querySelector("#ticker-search");
const refreshButton = document.querySelector("#manual-refresh");

const headlineTemplate = document.querySelector("#headline-template");
const tickerTemplate = document.querySelector("#ticker-template");

async function loadDashboard() {
  refreshStatus.textContent = "Refreshing snapshot...";

  try {
    const response = await fetch(`${DATA_URL}?t=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Request failed with ${response.status}`);
    }

    state.data = await response.json();
    render();
    refreshStatus.textContent = `Last updated ${formatDateTime(state.data.generated_at)}`;
  } catch (error) {
    refreshStatus.textContent = "Could not load the latest snapshot. Showing cached page if available.";
    console.error(error);
  }
}

function render() {
  if (!state.data) {
    return;
  }

  renderSummary();
  renderSignals();
  renderHeadlines(tradeHeadlines, state.data.sections.trade_news.items);
  renderHeadlines(indiaBusiness, state.data.sections.india_business.items);
  renderHeadlines(globalBusiness, state.data.sections.global_business.items);
  renderTickers(topGainers, state.data.sections.stocks.top_gainers);
  renderTickers(topLosers, state.data.sections.stocks.top_losers);
  renderTickers(mostActive, state.data.sections.stocks.most_active);
  renderWatchlist();

  const stockMeta = state.data.sections.stocks.meta;
  stocksNote.textContent = `${stockMeta.coverage_label}. ${stockMeta.note}`;
}

function renderSummary() {
  const summary = [
    {
      label: "Tracked headlines",
      value: state.data.metrics.total_headlines,
      caption: "Across trade, business, finance, and market feeds",
    },
    {
      label: "India stock symbols",
      value: state.data.metrics.stock_symbols_covered,
      caption: "Hourly quote scan using the watchlist pipeline",
    },
    {
      label: "Trade signals",
      value: state.data.sections.trade_signals.length,
      caption: "Auto-derived themes from the latest India-focused trade coverage",
    },
    {
      label: "Auto refresh",
      value: "1 hour",
      caption: "Browser polling plus scheduled snapshot generation",
    },
  ];

  summaryGrid.innerHTML = "";
  summary.forEach((item) => {
    const card = document.createElement("article");
    card.className = "summary-card";
    card.innerHTML = `
      <span>${item.label}</span>
      <strong>${item.value}</strong>
      <p>${item.caption}</p>
    `;
    summaryGrid.appendChild(card);
  });
}

function renderSignals() {
  tradeSignals.innerHTML = "";
  state.data.sections.trade_signals.forEach((signal) => {
    const pill = document.createElement("div");
    pill.className = "signal-pill";
    pill.textContent = signal;
    tradeSignals.appendChild(pill);
  });
}

function renderHeadlines(container, items) {
  container.innerHTML = "";

  if (!items.length) {
    container.appendChild(createEmptyState("No fresh items were available in the latest snapshot."));
    return;
  }

  items.forEach((item) => {
    const node = headlineTemplate.content.firstElementChild.cloneNode(true);
    node.querySelector(".headline-source").textContent = item.source;
    node.querySelector(".headline-link").href = item.link;
    node.querySelector(".headline-title").textContent = item.title;
    node.querySelector(".headline-time").textContent = formatDateTime(item.published);
    node.querySelector(".headline-summary").textContent = item.summary || "Summary unavailable in this snapshot.";
    node.querySelector(".headline-detail-text").textContent = item.detailed_summary || item.summary || "Detailed summary unavailable in this snapshot.";
    node.querySelector(".headline-source-link").href = item.link;
    container.appendChild(node);
  });
}

function renderTickers(container, items) {
  container.innerHTML = "";

  if (!items.length) {
    container.appendChild(createEmptyState("No market movers available in this snapshot."));
    return;
  }

  items.forEach((item) => {
    const node = tickerTemplate.content.firstElementChild.cloneNode(true);
    node.querySelector(".ticker-name").textContent = item.name;
    node.querySelector(".ticker-symbol").textContent = item.symbol;
    node.querySelector(".ticker-price").textContent = formatNumber(item.price, {
      style: "currency",
      currency: item.currency || "INR",
      maximumFractionDigits: 2,
    });

    const changeNode = node.querySelector(".ticker-change");
    changeNode.textContent = `${item.change_percent >= 0 ? "+" : ""}${item.change_percent.toFixed(2)}%`;
    changeNode.className = `ticker-change ${changeClass(item.change_percent)}`;
    container.appendChild(node);
  });
}

function renderWatchlist() {
  const rows = state.data.sections.stocks.watchlist.filter((item) => {
    const term = state.searchTerm.trim().toLowerCase();
    if (!term) {
      return true;
    }

    return `${item.name} ${item.symbol} ${item.sector}`.toLowerCase().includes(term);
  });

  watchlistTable.innerHTML = "";

  if (!rows.length) {
    const row = document.createElement("tr");
    row.innerHTML = `<td colspan="6"><div class="empty-state">No matching companies found.</div></td>`;
    watchlistTable.appendChild(row);
    return;
  }

  rows.forEach((item) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${item.name}</td>
      <td>${item.symbol}</td>
      <td>${formatNumber(item.price, { style: "currency", currency: item.currency || "INR", maximumFractionDigits: 2 })}</td>
      <td class="${changeClass(item.change_percent)}">${item.change_percent >= 0 ? "+" : ""}${item.change_percent.toFixed(2)}%</td>
      <td>${formatCompact(item.market_cap)}</td>
      <td>${item.sector || "Unspecified"}</td>
    `;
    watchlistTable.appendChild(row);
  });
}

function createEmptyState(message) {
  const node = document.createElement("div");
  node.className = "empty-state";
  node.textContent = message;
  return node;
}

function formatDateTime(value) {
  if (!value) {
    return "Unknown time";
  }

  const date = new Date(value);
  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function formatNumber(value, options = {}) {
  const number = Number(value ?? 0);
  return new Intl.NumberFormat("en-IN", options).format(number);
}

function formatCompact(value) {
  const number = Number(value ?? 0);
  if (!number) {
    return "-";
  }

  return new Intl.NumberFormat("en-IN", {
    notation: "compact",
    maximumFractionDigits: 2,
  }).format(number);
}

function changeClass(value) {
  if (value > 0) {
    return "change-positive";
  }
  if (value < 0) {
    return "change-negative";
  }
  return "change-flat";
}

searchInput.addEventListener("input", (event) => {
  state.searchTerm = event.target.value;
  renderWatchlist();
});

refreshButton.addEventListener("click", () => {
  loadDashboard();
});

loadDashboard();
setInterval(loadDashboard, ONE_HOUR);
