"use client";

import { ChangeEvent, useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import PriceChart from "./PriceChart";
import styles from "./dashboard.module.css";

type Holding = { id: string; symbol: string; company_name: string; quantity?: number; buy_price?: number; exchange: string };
type Position = { holding: Holding; invested_amount: number; current_amount?: number | null; quote?: { price?: number; source?: string; as_of?: string; previous_close?: number; day_change_pct?: number; currency?: string }; error?: string | null };
type PortfolioAnalysis = { positions: Position[]; total_invested: number; total_current: number; price_coverage: number };
type RiskReport = { summary: { portfolio_risk_level: string; diversification_verdict: string; sarvam_insight?: string | null }; executive_report?: { sector_commentary: string; asset_commentary: string; risk_commentary: string; recommendations: string[] }; stock_level_risk_profiles: Array<{ ticker: string; sector: string; overall_risk_rating: string }>; portfolio_diversification_analysis: { sector_allocation: Array<{ sector: string; allocation_pct: number }>; concentration_flags: Array<{ sector: string; allocation_pct: number }>; under_exposed_or_missing_sectors: string[] } };
type Candle = { time: string; open: number; high: number; low: number; close: number; volume: number; sma50?: number | null; sma200?: number | null; bollinger_upper?: number | null; bollinger_lower?: number | null; rsi14?: number | null; macd?: number | null; macd_signal?: number | null; macd_histogram?: number | null };
type IndicatorSummary = { rsi14?: number | null; macd?: number | null; macd_signal?: number | null; macd_histogram?: number | null; sma_crossover?: "bullish" | "bearish" | "neutral" };
type HistoryState = { data?: Candle[]; indicators?: IndicatorSummary; source?: string; error?: string; loading: boolean };
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function deriveIndicators(rows?: Candle[]): IndicatorSummary | undefined {
  if (!rows?.length) return undefined;
  const latest = rows[rows.length - 1];
  const closes = rows.map((row) => row.close);
  const ema = (period: number) => {
    if (closes.length < period) return Array<number | null>(closes.length).fill(null);
    const output: Array<number | null> = Array(closes.length).fill(null);
    let value = closes.slice(0, period).reduce((sum, price) => sum + price, 0) / period;
    output[period - 1] = value;
    const multiplier = 2 / (period + 1);
    for (let index = period; index < closes.length; index += 1) { value = (closes[index] - value) * multiplier + value; output[index] = value; }
    return output;
  };
  const fast = ema(12), slow = ema(26);
  const macd = closes.map((_, index) => fast[index] == null || slow[index] == null ? null : fast[index]! - slow[index]!);
  const signal: Array<number | null> = Array(closes.length).fill(null);
  const firstMacd = macd.findIndex((value) => value != null);
  if (firstMacd >= 0 && macd.length - firstMacd >= 9) {
    let value = macd.slice(firstMacd, firstMacd + 9).map((item) => item ?? 0).reduce((sum, item) => sum + item, 0) / 9;
    signal[firstMacd + 8] = value;
    const multiplier = 2 / 10;
    for (let index = firstMacd + 9; index < macd.length; index += 1) { value = (macd[index]! - value) * multiplier + value; signal[index] = value; }
  }
  const histogram = macd.map((value, index) => value == null || signal[index] == null ? null : value - signal[index]!);
  let gain = 0, loss = 0;
  const rsiValues: Array<number | null> = Array(closes.length).fill(null);
  if (closes.length > 14) {
    for (let index = 1; index <= 14; index += 1) { const delta = closes[index] - closes[index - 1]; gain += Math.max(delta, 0); loss += Math.max(-delta, 0); }
    const rsiValue = () => loss === 0 ? (gain === 0 ? 50 : 100) : 100 - (100 / (1 + gain / loss));
    rsiValues[14] = rsiValue();
    for (let index = 15; index < closes.length; index += 1) { const delta = closes[index] - closes[index - 1]; gain = (gain * 13 + Math.max(delta, 0)) / 14; loss = (loss * 13 + Math.max(-delta, 0)) / 14; rsiValues[index] = rsiValue(); }
  }
  const sma50 = [...rows].reverse().find((row) => row.sma50 != null)?.sma50;
  const sma200 = [...rows].reverse().find((row) => row.sma200 != null)?.sma200;
  return {
    rsi14: latest.rsi14 ?? rsiValues.at(-1),
    macd: latest.macd ?? macd.at(-1),
    macd_signal: latest.macd_signal ?? signal.at(-1),
    macd_histogram: latest.macd_histogram ?? histogram.at(-1),
    sma_crossover: sma50 == null || sma200 == null ? "neutral" : sma50 > sma200 ? "bullish" : sma50 < sma200 ? "bearish" : "neutral",
  };
}

export default function DashboardPage() {
  const { data: session } = useSession();
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [symbol, setSymbol] = useState(""); const [quantity, setQuantity] = useState(""); const [buyPrice, setBuyPrice] = useState(""); const [file, setFile] = useState<File | null>(null);
  const [analysis, setAnalysis] = useState<PortfolioAnalysis | null>(null); const [busy, setBusy] = useState(""); const [message, setMessage] = useState("");
  const [riskReport, setRiskReport] = useState<RiskReport | null>(null);
  const [isAddPanelOpen, setIsAddPanelOpen] = useState(true);
  const [histories, setHistories] = useState<Record<string, HistoryState>>({});
  const [openCharts, setOpenCharts] = useState<Record<string, boolean>>({});
  async function token() { const response = await fetch("/api/auth/token"); return response.ok ? (await response.json()).token : null; }
  async function loadDashboard() {
    const auth = await token();
    if (!auth) return;
    const headers = { Authorization: `Bearer ${auth}` };
    const [holdingsResponse, portfolioResponse] = await Promise.all([
      fetch(`${API_URL}/api/holdings`, { headers }),
      fetch(`${API_URL}/api/analysis/portfolio`, { headers }),
    ]);
    let loadedHoldings: Holding[] = [];
    if (holdingsResponse.ok) {
      loadedHoldings = await holdingsResponse.json();
      setHoldings(loadedHoldings);
      setIsAddPanelOpen(loadedHoldings.length === 0);
    }
    if (portfolioResponse.ok) {
      const result = await portfolioResponse.json();
      setAnalysis(result);
      // Technical indicators power the visible holding cards, not just the
      // expandable chart. Start fetching them immediately and independently
      // from the slower multi-agent Sarvam report.
      void Promise.all(loadedHoldings.map((holding) => loadHistory(holding, auth)));
      const riskResponse = await fetch(`${API_URL}/api/analysis/risk-profile`, { method: "POST", headers: { ...headers, "Content-Type": "application/json" }, body: JSON.stringify({ holdings: loadedHoldings.map((holding, index) => ({ ticker: holding.symbol, quantity: holding.quantity, buy_price: holding.buy_price, current_price: result.positions?.[index]?.quote?.price ?? holding.buy_price })), include_llm_insight: true }) });
      if (riskResponse.ok) setRiskReport(await riskResponse.json()); else if (riskResponse.status === 503) { setRiskReport(null); setMessage("AI analysis is temporarily unavailable. Please retry."); }
      window.sessionStorage.setItem("portfolio-analysis", JSON.stringify(result));
    }
  }
  // Initial portfolio hydration is an intentional external-data sync.
  useEffect(() => {
    loadDashboard();
    const restore = window.sessionStorage.getItem("portfolio-analysis");
    if (restore) {
      try { setAnalysis(JSON.parse(restore)); } catch { window.sessionStorage.removeItem("portfolio-analysis"); }
    }
    const clearAnalysis = () => { setAnalysis(null); setRiskReport(null); window.sessionStorage.removeItem("portfolio-analysis"); };
    window.addEventListener("portfolio-signout", clearAnalysis);
    return () => window.removeEventListener("portfolio-signout", clearAnalysis);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  async function loadHistory(holding: Holding, auth?: string) {
    if (histories[holding.id]?.loading || histories[holding.id]?.data) return;
    setHistories((current) => ({ ...current, [holding.id]: { ...current[holding.id], loading: true } }));
    try {
      const accessToken = auth ?? await token();
      if (!accessToken) throw new Error("Your session has expired. Please sign in again.");
      const response = await fetch(`${API_URL}/api/analysis/history/${encodeURIComponent(holding.symbol)}?exchange=${encodeURIComponent(holding.exchange || "NSE")}`, { headers: { Authorization: `Bearer ${accessToken}` } });
      const result = await response.json();
      const derived = deriveIndicators(result.history);
      const indicators = result.indicators ? { ...derived, ...result.indicators, rsi14: result.indicators.rsi14 ?? derived?.rsi14, macd: result.indicators.macd ?? derived?.macd, macd_signal: result.indicators.macd_signal ?? derived?.macd_signal, macd_histogram: result.indicators.macd_histogram ?? derived?.macd_histogram } : derived;
      setHistories((current) => ({ ...current, [holding.id]: response.ok ? { data: result.history, indicators, source: result.source, loading: false } : { error: result.detail || "Price history is unavailable.", loading: false } }));
    } catch (error) {
      setHistories((current) => ({ ...current, [holding.id]: { error: error instanceof Error ? error.message : "Price history is unavailable.", loading: false } }));
    }
  }
  async function addManual(event: React.FormEvent) {
    event.preventDefault();
    setBusy("adding");
    setMessage("");

    const auth = await token();
    if (!auth) {
      setMessage("Your session has expired. Please sign in again.");
      setBusy("");
      return;
    }

    const response = await fetch(`${API_URL}/api/holdings/manual`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${auth}`,
      },
      body: JSON.stringify({
        symbol,
        quantity: Number(quantity),
        buy_price: Number(buyPrice),
      }),
    });

    if (response.ok) {
      setSymbol("");
      setQuantity("");
      setBuyPrice("");
      setMessage("Holding added. Market prices are updating now.");
      await loadDashboard();
    } else {
      setMessage("Please enter a valid symbol, quantity, and average price.");
    }
    setBusy("");
  }
  async function importFile() { if (!file) return; setBusy("importing"); const auth = await token(); const body = new FormData(); body.append("file", file); const response = await fetch(`${API_URL}/api/holdings/import`, { method: "POST", headers: { Authorization: `Bearer ${auth}` }, body }); const data = await response.json(); setMessage(response.ok ? `${data.count} equity holdings imported.` : data.detail || "Import failed."); if (response.ok) { setFile(null); await loadDashboard(); } setBusy(""); }
  async function analyzePortfolio() { setBusy("analyzing"); setMessage(""); await loadDashboard(); setBusy(""); }
  async function remove(id: string) {
    const auth = await token();
    if (!auth) {
      setMessage("Your session has expired. Please sign in again.");
      return;
    }

    const response = await fetch(`${API_URL}/api/holdings/${id}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${auth}` },
    });

    if (!response.ok) {
      setMessage("Could not remove holding. Please try again.");
      return;
    }

    setHoldings((items) => items.filter((item) => item.id !== id));
    setHistories((current) => { const next = { ...current }; delete next[id]; return next; });
    setOpenCharts((current) => { const next = { ...current }; delete next[id]; return next; });
    setAnalysis(null); setRiskReport(null);
    window.sessionStorage.removeItem("portfolio-analysis");
  }
  async function clearPortfolio() {
    if (!window.confirm("Clear all holdings and saved analysis? This cannot be undone.")) return;
    setBusy("clearing");
    const auth = await token();
    if (!auth) { setMessage("Your session has expired. Please sign in again."); setBusy(""); return; }
    const responses = await Promise.all(holdings.map((holding) => fetch(`${API_URL}/api/holdings/${holding.id}`, { method: "DELETE", headers: { Authorization: `Bearer ${auth}` } })));
    if (responses.every((response) => response.ok)) { setHoldings([]); setHistories({}); setOpenCharts({}); setAnalysis(null); setRiskReport(null); setIsAddPanelOpen(true); window.sessionStorage.removeItem("portfolio-analysis"); setMessage("All holdings cleared."); }
    else setMessage("Some holdings could not be cleared. Please try again.");
    setBusy("");
  }
  const money = (value?: number | null) => value == null ? "—" : `₹${value.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
  const percent = (value?: number | null) => value == null || !Number.isFinite(value) ? "—" : `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
  const returnPercent = (current?: number | null, invested?: number | null) => current == null || !invested ? null : ((current - invested) / invested) * 100;
  const pricedCount = analysis?.price_coverage ?? 0;
  const snapshot = analysis?.positions.find((position) => position.quote?.as_of)?.quote;
  const snapshotLabel = snapshot?.as_of ? new Date(snapshot.as_of).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" }) : null;
  const quoteSources = analysis ? Array.from(new Set(analysis.positions.map((position) => position.quote?.source).filter(Boolean))) : [];
  return <div className={styles.wrapper}>
    <div className={styles.disclaimerBanner}>Insights only · Prices may be delayed · This tool never recommends buying or selling.</div>
    <header className={styles.header}><div><div className={styles.eyebrow}>DALAL.AI INTELLIGENCE</div><h1 className={styles.title}>See your portfolio clearly.</h1><p className={styles.subtitle}>Add every holding, then get one market-price snapshot across your entire portfolio.</p></div></header>
    <section className={`${styles.panel} ${!isAddPanelOpen ? styles.panelCollapsed : ""}`}><div className={styles.sectionIntro}><div><h2 className={styles.panelTitle}>Add holdings</h2>{isAddPanelOpen && <p className={styles.helper}>Use your average buy price and total quantity for each stock.</p>}</div>{holdings.length > 0 && <button type="button" className={styles.panelToggle} aria-expanded={isAddPanelOpen} aria-controls="add-holdings-controls" onClick={() => setIsAddPanelOpen((open) => !open)}>{isAddPanelOpen ? "Hide input" : "Add holdings"}<span aria-hidden="true">{isAddPanelOpen ? "⌃" : "＋"}</span></button>}</div>
      {isAddPanelOpen && <div id="add-holdings-controls">
      <form className={styles.quickAddForm} onSubmit={addManual}><input className={styles.symbolInput} placeholder="Symbol (e.g. INFY)" value={symbol} onChange={(e) => setSymbol(e.target.value)} required /><input className={styles.numberInput} type="number" min="0" step="any" placeholder="Quantity" value={quantity} onChange={(e) => setQuantity(e.target.value)} required /><input className={styles.numberInput} type="number" min="0" step="any" placeholder="Avg price ₹" value={buyPrice} onChange={(e) => setBuyPrice(e.target.value)} required /><button className="btn" disabled={busy === "adding"}>{busy === "adding" ? "Adding…" : "Add holding"}</button></form>
      <div className={styles.importRow}><label className={styles.fileLabel}>Import CSV or XLSX<input type="file" accept=".csv,.xlsx" onChange={(e: ChangeEvent<HTMLInputElement>) => setFile(e.target.files?.[0] || null)} /></label><span className={styles.fileName}>{file?.name}</span><button className="btn btnOutline" onClick={importFile} disabled={!file || busy === "importing"}>{busy === "importing" ? "Importing…" : "Import holdings"}</button></div>
      </div>}{message && <p className={styles.message} role="status">{message}</p>}
    </section>
    {riskReport && <section className={styles.aiPanel}><div className={styles.eyebrow}>AI PORTFOLIO ANALYSIS</div><h2>{riskReport.summary.diversification_verdict}</h2><p className={styles.aiInsight}>{riskReport.summary.sarvam_insight || "Risk analysis is based on your holdings, allocation, and available market data."}</p><div className={styles.aiGrid}><div><small>Overall risk</small><strong>{riskReport.summary.portfolio_risk_level}</strong></div><div><small>Concentration flags</small><strong>{riskReport.portfolio_diversification_analysis.concentration_flags.length || "None"}</strong></div><div><small>Missing / low exposure</small><strong>{riskReport.portfolio_diversification_analysis.under_exposed_or_missing_sectors.length}</strong></div></div>{riskReport.executive_report && <div className={styles.aiNarrative}><h3>Sector outlook</h3><p>{riskReport.executive_report.sector_commentary}</p>{riskReport.executive_report.asset_commentary && <><h3>Asset analysis</h3><p>{riskReport.executive_report.asset_commentary}</p></>}<h3>Risk diagnostics</h3><p>{riskReport.executive_report.risk_commentary}</p><h3>Educational next steps</h3><ul>{riskReport.executive_report.recommendations.map((item) => <li key={item}>{item}</li>)}</ul></div>}<div className={styles.aiColumns}><div><h3>Sector allocation</h3>{riskReport.portfolio_diversification_analysis.sector_allocation.map((item) => <div className={styles.aiRow} key={item.sector}><span>{item.sector}</span><strong>{item.allocation_pct.toFixed(1)}%</strong></div>)}</div><div><h3>Stock risk ratings</h3>{riskReport.stock_level_risk_profiles.map((item) => <div className={styles.aiRow} key={item.ticker}><span>{item.ticker} <small>{item.sector}</small></span><strong>{item.overall_risk_rating}</strong></div>)}</div></div><p className={styles.aiMissing}><b>Under-exposed or missing:</b> {riskReport.portfolio_diversification_analysis.under_exposed_or_missing_sectors.join(", ") || "None identified"}</p></section>}
    <div className={styles.sectionHeading}><div><div className={styles.eyebrow}>YOUR HOLDINGS</div><h2>Portfolio positions <span className={styles.count}>{holdings.length}</span></h2></div><div className={styles.stockActions}><span className={styles.helper}>{session?.user?.email}</span>{holdings.length > 0 && <><button className="btn" onClick={analyzePortfolio} disabled={busy === "analyzing"}>{busy === "analyzing" ? "Refreshing prices…" : "Refresh market prices"}</button><button className="btn btnDanger clearButton" onClick={clearPortfolio} disabled={busy === "clearing"}>{busy === "clearing" ? "Clearing…" : "Clear portfolio"}</button></>}</div></div>
    {holdings.length === 0 ? <div className={styles.empty}>Add a holding manually or import the spreadsheet to begin.</div> : <div className={styles.holdingList}>{analysis && <div className={styles.metrics}><div><small>Total invested</small><strong>{money(analysis.total_invested)}</strong></div><div className={analysis.total_current >= analysis.total_invested ? styles.returnPositive : styles.returnNegative}><small>Current value</small><strong>{money(analysis.total_current)}</strong></div><div className={analysis.total_current >= analysis.total_invested ? styles.returnPositive : styles.returnNegative}><small>Total return</small><strong className={analysis.total_current >= analysis.total_invested ? styles.goodText : styles.badText}>{percent(returnPercent(analysis.total_current, analysis.total_invested))}</strong></div><div><small>Price coverage</small><strong>{pricedCount} of {holdings.length}</strong></div><div><small>Latest snapshot</small><strong className={styles.metricDetail}>{snapshotLabel || "Not available"}</strong><span className={styles.metricCaption}>{quoteSources.join(", ") || "No quote source"}</span></div></div>}{holdings.map((holding) => { const item = analysis?.positions.find((position) => position.holding.id === holding.id); const history = histories[holding.id]; const indicators = history?.indicators; const isChartOpen = openCharts[holding.id] === true; const rsiLabel = indicators?.rsi14 == null ? "Unavailable" : indicators.rsi14 >= 70 ? "Overbought" : indicators.rsi14 <= 30 ? "Oversold" : "Neutral"; const crossoverLabel = indicators?.sma_crossover ? indicators.sma_crossover[0].toUpperCase() + indicators.sma_crossover.slice(1) : "Unavailable"; const change = returnPercent(item?.current_amount, item?.invested_amount); const positive = change != null && change >= 0; const performanceClass = change == null ? styles.valueTile : positive ? styles.profitTile : styles.lossTile; const valueClass = `${styles.valueTile} ${performanceClass}`; const chartId = `price-chart-${holding.id}`; return <article className={styles.stockCard} key={holding.id}><div className={styles.stockTop}><div><span className={styles.stockSymbol}>{holding.symbol}</span><span className={styles.stockName}>{holding.company_name}</span></div><div className={styles.stockCardActions}><button type="button" className={styles.chartCollapseButton} aria-label={isChartOpen ? `Collapse ${holding.symbol} chart` : `Expand ${holding.symbol} chart`} aria-expanded={isChartOpen} aria-controls={chartId} onClick={() => { if (!isChartOpen) void loadHistory(holding); setOpenCharts((current) => ({ ...current, [holding.id]: !isChartOpen })); }}>{isChartOpen ? "^" : "⌄"}</button><button className={styles.removeButton} onClick={() => remove(holding.id)}>Remove</button></div></div><div className={styles.bentoGrid}><div><small>Quantity</small><strong>{holding.quantity ?? "—"}</strong></div><div><small>Average price</small><strong>{money(holding.buy_price)}</strong></div>{item && <><div><small>Market price</small><strong>{money(item.quote?.price)}</strong></div><div><small>Invested</small><strong>{money(item.invested_amount)}</strong></div><div className={valueClass}><small>Current value</small><strong>{money(item.current_amount)}</strong></div><div className={performanceClass}><small>Profit / loss</small><strong>{percent(change)}</strong></div></>}<div className={styles.indicatorTile}><small>RSI (14)</small><strong>{indicators?.rsi14 == null ? "—" : indicators.rsi14.toFixed(1)}</strong><span>{rsiLabel}</span></div><div className={styles.indicatorTile}><small>SMA 50 / 200</small><strong>{crossoverLabel}</strong><span>Long-term trend</span></div><div className={styles.indicatorTile}><small>MACD histogram</small><strong>{indicators?.macd_histogram == null ? "—" : indicators.macd_histogram.toFixed(2)}</strong><span>{indicators?.macd_histogram == null ? "Unavailable" : indicators.macd_histogram >= 0 ? "Positive" : "Negative"}</span></div></div>{isChartOpen && <div id={chartId}>{history?.loading && <div className={styles.chartStatus}>Loading two-year price chart…</div>}{history?.error && <p className={styles.chartError}>{history.error}</p>}{history?.data && <><PriceChart data={history.data} /><p className={styles.chartSource}>2-year daily data · {history.source}</p></>}</div>}{item?.error && <p className={styles.quoteError}>{item.error}</p>}</article>; })}</div>}
  </div>;
}
