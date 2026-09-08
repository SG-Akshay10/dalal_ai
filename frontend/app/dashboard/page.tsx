"use client";

import { ChangeEvent, useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import styles from "./dashboard.module.css";

type Holding = { id: string; symbol: string; company_name: string; quantity?: number; buy_price?: number; exchange: string };
type Position = { holding: Holding; invested_amount: number; current_amount?: number | null; quote?: { price?: number; source?: string; as_of?: string; previous_close?: number; day_change_pct?: number; currency?: string }; error?: string | null };
type PortfolioAnalysis = { positions: Position[]; total_invested: number; total_current: number; price_coverage: number };
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function DashboardPage() {
  const { data: session } = useSession();
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [symbol, setSymbol] = useState(""); const [quantity, setQuantity] = useState(""); const [buyPrice, setBuyPrice] = useState(""); const [file, setFile] = useState<File | null>(null);
  const [analysis, setAnalysis] = useState<PortfolioAnalysis | null>(null); const [busy, setBusy] = useState(""); const [message, setMessage] = useState("");
  const [isAddPanelOpen, setIsAddPanelOpen] = useState(true);
  async function token() { const response = await fetch("/api/auth/token"); return response.ok ? (await response.json()).token : null; }
  async function load() { const auth = await token(); if (!auth) return; const response = await fetch(`${API_URL}/api/holdings`, { headers: { Authorization: `Bearer ${auth}` } }); if (response.ok) { const items = await response.json(); setHoldings(items); setIsAddPanelOpen(items.length === 0); } }
  // Initial portfolio hydration is an intentional external-data sync.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
    const restore = window.sessionStorage.getItem("portfolio-analysis");
    if (restore) {
      try { setAnalysis(JSON.parse(restore)); } catch { window.sessionStorage.removeItem("portfolio-analysis"); }
    }
    const clearAnalysis = () => { setAnalysis(null); window.sessionStorage.removeItem("portfolio-analysis"); };
    window.addEventListener("portfolio-signout", clearAnalysis);
    return () => window.removeEventListener("portfolio-signout", clearAnalysis);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
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
      setMessage("Holding added. Analyze the portfolio when you’re ready.");
      await load();
    } else {
      setMessage("Please enter a valid symbol, quantity, and average price.");
    }
    setBusy("");
  }
  async function importFile() { if (!file) return; setBusy("importing"); const auth = await token(); const body = new FormData(); body.append("file", file); const response = await fetch(`${API_URL}/api/holdings/import`, { method: "POST", headers: { Authorization: `Bearer ${auth}` }, body }); const data = await response.json(); setMessage(response.ok ? `${data.count} equity holdings imported.` : data.detail || "Import failed."); if (response.ok) { setFile(null); await load(); } setBusy(""); }
  async function analyzePortfolio() { setBusy("analyzing"); setMessage(""); const auth = await token(); const response = await fetch(`${API_URL}/api/analysis/portfolio`, { headers: { Authorization: `Bearer ${auth}` } }); if (response.ok) { const result = await response.json(); setAnalysis(result); window.sessionStorage.setItem("portfolio-analysis", JSON.stringify(result)); } else setMessage("Portfolio analysis could not be completed. Please try again."); setBusy(""); }
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
    setAnalysis(null);
    window.sessionStorage.removeItem("portfolio-analysis");
  }
  async function clearPortfolio() {
    if (!window.confirm("Clear all holdings and saved analysis? This cannot be undone.")) return;
    setBusy("clearing");
    const auth = await token();
    if (!auth) { setMessage("Your session has expired. Please sign in again."); setBusy(""); return; }
    const responses = await Promise.all(holdings.map((holding) => fetch(`${API_URL}/api/holdings/${holding.id}`, { method: "DELETE", headers: { Authorization: `Bearer ${auth}` } })));
    if (responses.every((response) => response.ok)) { setHoldings([]); setAnalysis(null); setIsAddPanelOpen(true); window.sessionStorage.removeItem("portfolio-analysis"); setMessage("All holdings cleared."); }
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
    <div className={styles.sectionHeading}><div><div className={styles.eyebrow}>YOUR HOLDINGS</div><h2>Portfolio positions <span className={styles.count}>{holdings.length}</span></h2></div><div className={styles.stockActions}><span className={styles.helper}>{session?.user?.email}</span>{holdings.length > 0 && <><button className="btn" onClick={analyzePortfolio} disabled={busy === "analyzing"}>{busy === "analyzing" ? "Analyzing portfolio…" : analysis ? "Refresh portfolio analysis" : "Analyze portfolio"}</button><button className="btn btnDanger clearButton" onClick={clearPortfolio} disabled={busy === "clearing"}>{busy === "clearing" ? "Clearing…" : "Clear portfolio"}</button></>}</div></div>
    {holdings.length === 0 ? <div className={styles.empty}>Add a holding manually or import the spreadsheet to begin.</div> : <div className={styles.holdingList}>{analysis && <div className={styles.metrics}><div><small>Total invested</small><strong>{money(analysis.total_invested)}</strong></div><div className={analysis.total_current >= analysis.total_invested ? styles.returnPositive : styles.returnNegative}><small>Current value</small><strong>{money(analysis.total_current)}</strong></div><div className={analysis.total_current >= analysis.total_invested ? styles.returnPositive : styles.returnNegative}><small>Total return</small><strong className={analysis.total_current >= analysis.total_invested ? styles.goodText : styles.badText}>{percent(returnPercent(analysis.total_current, analysis.total_invested))}</strong></div><div><small>Price coverage</small><strong>{pricedCount} of {holdings.length}</strong></div><div><small>Latest snapshot</small><strong className={styles.metricDetail}>{snapshotLabel || "Not available"}</strong><span className={styles.metricCaption}>{quoteSources.join(", ") || "No quote source"}</span></div></div>}{holdings.map((holding) => { const item = analysis?.positions.find((position) => position.holding.id === holding.id); const change = returnPercent(item?.current_amount, item?.invested_amount); const positive = change != null && change >= 0; const performanceClass = change == null ? styles.valueTile : positive ? styles.profitTile : styles.lossTile; const valueClass = `${styles.valueTile} ${performanceClass}`; return <article className={styles.stockCard} key={holding.id}><div className={styles.stockTop}><div><span className={styles.stockSymbol}>{holding.symbol}</span><span className={styles.stockName}>{holding.company_name}</span></div><button className={styles.removeButton} onClick={() => remove(holding.id)}>Remove</button></div><div className={styles.bentoGrid}><div><small>Quantity</small><strong>{holding.quantity ?? "—"}</strong></div><div><small>Average price</small><strong>{money(holding.buy_price)}</strong></div>{item && <><div><small>Market price</small><strong>{money(item.quote?.price)}</strong></div><div><small>Invested</small><strong>{money(item.invested_amount)}</strong></div><div className={valueClass}><small>Current value</small><strong>{money(item.current_amount)}</strong></div><div className={performanceClass}><small>Profit / loss</small><strong>{percent(change)}</strong></div></>}</div>{item?.error && <p className={styles.quoteError}>{item.error}</p>}</article>; })}</div>}
  </div>;
}
