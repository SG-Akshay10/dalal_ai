"use client";

import { ChangeEvent, useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import styles from "./dashboard.module.css";

type Holding = { id: string; symbol: string; company_name: string; quantity?: number; buy_price?: number; exchange: string };
type Analysis = { holding: Holding; quote: { price?: number; previous_close?: number; day_change_pct?: number; source?: string; error?: string }; performance: { return_pct?: number; cost_basis?: number; market_value?: number }; sentiment: { overall: string; news_count: number; counts: Record<string, number> }; pros: string[]; cons: string[]; news: { title: string; summary: string; sentiment: string; url: string }[]; disclaimer: string };
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function DashboardPage() {
  const { data: session } = useSession();
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [symbol, setSymbol] = useState(""); const [quantity, setQuantity] = useState(""); const [buyPrice, setBuyPrice] = useState(""); const [file, setFile] = useState<File | null>(null);
  const [analysis, setAnalysis] = useState<Record<string, Analysis>>({}); const [busy, setBusy] = useState(""); const [message, setMessage] = useState("");
  async function token() { const response = await fetch("/api/auth/token"); return response.ok ? (await response.json()).token : null; }
  async function load() { const auth = await token(); if (!auth) return; const response = await fetch(`${API_URL}/api/holdings`, { headers: { Authorization: `Bearer ${auth}` } }); if (response.ok) setHoldings(await response.json()); }
  // Initial portfolio hydration is an intentional external-data sync.
  // eslint-disable-next-line react-hooks/set-state-in-effect, react-hooks/exhaustive-deps
  useEffect(() => { load(); }, []);
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
      setMessage("Holding added. Select Analyze when you’re ready.");
      await load();
    } else {
      setMessage("Please enter a valid symbol, quantity, and average price.");
    }
    setBusy("");
  }
  async function importFile() { if (!file) return; setBusy("importing"); const auth = await token(); const body = new FormData(); body.append("file", file); const response = await fetch(`${API_URL}/api/holdings/import`, { method: "POST", headers: { Authorization: `Bearer ${auth}` }, body }); const data = await response.json(); setMessage(response.ok ? `${data.count} equity holdings imported.` : data.detail || "Import failed."); if (response.ok) { setFile(null); await load(); } setBusy(""); }
  async function analyze(holding: Holding) { setBusy(holding.id); setMessage(""); const auth = await token(); const response = await fetch(`${API_URL}/api/analysis/${holding.id}`, { headers: { Authorization: `Bearer ${auth}` } }); if (response.ok) { const result = await response.json(); setAnalysis((current) => ({ ...current, [holding.id]: result })); } else setMessage("Analysis could not be completed. Please try again."); setBusy(""); }
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
    setAnalysis((items) => {
      const next = { ...items };
      delete next[id];
      return next;
    });
  }
  const money = (value?: number) => value == null ? "—" : `₹${value.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
  return <div className={styles.wrapper}>
    <div className={styles.disclaimerBanner}>Insights only · Prices may be delayed · This tool never recommends buying or selling.</div>
    <header className={styles.header}><div><div className={styles.eyebrow}>PORTFOLIO INTELLIGENCE</div><h1 className={styles.title}>Understand what you own.</h1><p className={styles.subtitle}>Add your holdings, then choose Analyze for a grounded view of performance and recent sentiment.</p></div></header>
    <section className={styles.panel}><div className={styles.sectionIntro}><div><h2 className={styles.panelTitle}>Build your portfolio</h2><p className={styles.helper}>Only symbol, average price, and quantity are used.</p></div></div>
      <form className={styles.quickAddForm} onSubmit={addManual}><input className={styles.symbolInput} placeholder="Symbol (e.g. INFY)" value={symbol} onChange={(e) => setSymbol(e.target.value)} required /><input className={styles.numberInput} type="number" min="0" step="any" placeholder="Quantity" value={quantity} onChange={(e) => setQuantity(e.target.value)} required /><input className={styles.numberInput} type="number" min="0" step="any" placeholder="Avg price ₹" value={buyPrice} onChange={(e) => setBuyPrice(e.target.value)} required /><button className="btn" disabled={busy === "adding"}>{busy === "adding" ? "Adding…" : "Add holding"}</button></form>
      <div className={styles.importRow}><label className={styles.fileLabel}>Import .xlsx<input type="file" accept=".xlsx" onChange={(e: ChangeEvent<HTMLInputElement>) => setFile(e.target.files?.[0] || null)} /></label><span className={styles.fileName}>{file?.name || "Combined sheet data will be read automatically"}</span><button className="btn btnOutline" onClick={importFile} disabled={!file || busy === "importing"}>{busy === "importing" ? "Importing…" : "Import spreadsheet"}</button></div>
      {message && <p className={styles.message}>{message}</p>}
    </section>
    <div className={styles.sectionHeading}><div><div className={styles.eyebrow}>YOUR HOLDINGS</div><h2>Ready for analysis <span className={styles.count}>{holdings.length}</span></h2></div><span className={styles.helper}>{session?.user?.email}</span></div>
    {holdings.length === 0 ? <div className={styles.empty}>Add a holding manually or import the spreadsheet to begin.</div> : <div className={styles.holdingList}>{holdings.map((holding) => { const item = analysis[holding.id]; const positive = (item?.performance.return_pct ?? 0) >= 0; return <article className={styles.stockCard} key={holding.id}><div className={styles.stockTop}><div><span className={styles.stockSymbol}>{holding.symbol}</span><span className={styles.stockName}>{holding.company_name}</span></div><div className={styles.stockActions}><button className="btn" onClick={() => analyze(holding)} disabled={busy === holding.id}>{busy === holding.id ? "Analyzing…" : item ? "Refresh analysis" : "Analyze"}</button><button className={styles.removeButton} onClick={() => remove(holding.id)}>Remove</button></div></div><div className={styles.holdingMeta}><span>{holding.quantity ?? "—"} shares</span><span>Avg {money(holding.buy_price)}</span>{item && <span className={positive ? styles.goodText : styles.badText}>{item.performance.return_pct == null ? "Return unavailable" : `${positive ? "+" : ""}${item.performance.return_pct.toFixed(2)}% vs avg`}</span>}</div>{item && <div className={styles.analysis}><div className={styles.metrics}><div><small>Live price</small><strong>{money(item.quote.price)}</strong><em>{item.quote.source || item.quote.error}</em></div><div><small>Position value</small><strong>{money(item.performance.market_value)}</strong><em>{item.sentiment.news_count} recent news items</em></div><div><small>News sentiment</small><strong className={item.sentiment.overall === "positive" ? styles.goodText : item.sentiment.overall === "negative" ? styles.badText : ""}>{item.sentiment.overall}</strong><em>{item.sentiment.counts.positive} positive · {item.sentiment.counts.negative} negative</em></div></div><div className={styles.insightColumns}><div><h3>What may help</h3>{item.pros.map((text) => <p key={text}>+ {text}</p>)}</div><div><h3>What to watch</h3>{item.cons.map((text) => <p key={text}>− {text}</p>)}</div></div><p className={styles.disclaimer}>{item.disclaimer}</p>{item.news.length > 0 && <details><summary>See news signals used</summary>{item.news.map((news) => <p className={styles.newsSignal} key={news.title}><b>{news.sentiment}</b> {news.title}</p>)}</details>}</div>}</article>; })}</div>}
  </div>;
}
