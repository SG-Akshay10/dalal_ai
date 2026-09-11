"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import styles from "./ai-analysis.module.css";

type ChatMessage = { role: "user" | "assistant"; content: string };
type Holding = { id: string; symbol: string; company_name: string; quantity?: number; buy_price?: number; exchange: string };
type Position = { holding: Holding; invested_amount: number; current_amount?: number | null; quote?: { price?: number }; sector?: string | null };
type PortfolioAnalysis = { positions: Position[] };
type StockThesisFinding = { ticker: string; sector: string; pros: string[]; cons: string[]; narrative?: string };
type StockThesis = { applicable: boolean; reason_if_not_applicable?: string; findings: StockThesisFinding[] };
type SectorThesisFinding = { sector: string; pros: string[]; cons: string[]; narrative: string };
type SectorThesis = { findings: SectorThesisFinding[] };
type RiskReport = {
  summary: { portfolio_risk_level: string; diversification_verdict: string; sarvam_insight?: string | null };
  executive_report?: { sector_commentary: string; asset_commentary: string; risk_commentary: string; recommendations: string[] };
  stock_level_risk_profiles: Array<{ ticker: string; sector: string; overall_risk_rating: string }>;
  stock_thesis?: StockThesis;
  sector_thesis?: SectorThesis;
  portfolio_diversification_analysis: { sector_allocation: Array<{ sector: string; allocation_pct: number }>; concentration_flags: Array<{ sector: string; allocation_pct: number }>; under_exposed_or_missing_sectors: string[] };
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const STARTER_PROMPTS = [
  "How diversified is my portfolio?",
  "What are the biggest risks in my holdings?",
  "Explain RSI and how to read it.",
];

type Tab = "full" | "chat";

export default function AiAnalysisPage() {
  const [tab, setTab] = useState<Tab>("full");

  // ---- Full analysis state ----
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [analysis, setAnalysis] = useState<PortfolioAnalysis | null>(null);
  const [riskReport, setRiskReport] = useState<RiskReport | null>(null);
  const [reportBusy, setReportBusy] = useState(false);
  const [reportError, setReportError] = useState("");
  const [reportLoaded, setReportLoaded] = useState(false);

  // ---- Chat state ----
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content:
        "Hi! I'm your dalal.ai portfolio assistant. Ask me about your holdings, sector allocation, risk, or general market concepts. I provide educational insights only — never investment advice.",
    },
  ]);
  const [input, setInput] = useState("");
  const [chatBusy, setChatBusy] = useState(false);
  const [chatError, setChatError] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, chatBusy]);

  async function token() {
    const response = await fetch("/api/auth/token");
    return response.ok ? (await response.json()).token : null;
  }

  async function loadHoldings() {
    const auth = await token();
    if (!auth) return;
    const headers = { Authorization: `Bearer ${auth}` };
    const [holdingsResponse, portfolioResponse] = await Promise.all([
      fetch(`${API_URL}/api/holdings`, { headers }),
      fetch(`${API_URL}/api/analysis/portfolio`, { headers }),
    ]);
    if (holdingsResponse.ok) setHoldings(await holdingsResponse.json());
    if (portfolioResponse.ok) setAnalysis(await portfolioResponse.json());
  }

  useEffect(() => {
    void loadHoldings();
  }, []);

  async function runFullAnalysis() {
    if (!holdings.length) return;
    setReportBusy(true);
    setReportError("");
    const auth = await token();
    if (!auth) {
      setReportError("Your session has expired. Please sign in again.");
      setReportBusy(false);
      return;
    }
    const headers = { Authorization: `Bearer ${auth}` };
    try {
      const response = await fetch(`${API_URL}/api/analysis/risk-profile`, {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({
          holdings: holdings.map((holding, index) => ({
            ticker: holding.symbol,
            quantity: holding.quantity,
            buy_price: holding.buy_price,
            current_price: analysis?.positions?.[index]?.quote?.price ?? holding.buy_price,
          })),
          include_llm_insight: true,
        }),
      });
      if (response.ok) {
        setRiskReport(await response.json());
      } else if (response.status === 503) {
        setRiskReport(null);
        setReportError("AI analysis is temporarily unavailable. Please retry.");
      } else {
        setRiskReport(null);
        setReportError("Could not generate AI analysis. Please try again.");
      }
    } catch {
      setReportError("Could not reach the analysis service. Please try again.");
    }
    setReportBusy(false);
    setReportLoaded(true);
  }

  async function sendMessage(text: string) {
    const trimmed = text.trim();
    if (!trimmed || chatBusy) return;
    setChatError("");
    const nextMessages: ChatMessage[] = [...messages, { role: "user", content: trimmed }];
    setMessages(nextMessages);
    setInput("");
    setChatBusy(true);

    const auth = await token();
    if (!auth) {
      setChatError("Your session has expired. Please sign in again.");
      setChatBusy(false);
      return;
    }

    try {
      const response = await fetch(`${API_URL}/api/analysis/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${auth}` },
        body: JSON.stringify({
          message: trimmed,
          history: nextMessages.slice(0, -1).map((message) => ({ role: message.role, content: message.content })),
        }),
      });
      if (response.ok) {
        const data = await response.json();
        setMessages((current) => [...current, { role: "assistant", content: data.reply }]);
      } else if (response.status === 503) {
        setChatError("AI chat is temporarily unavailable. Please retry.");
      } else {
        setChatError("Could not get a response. Please try again.");
      }
    } catch {
      setChatError("Could not reach the AI assistant. Please try again.");
    }
    setChatBusy(false);
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    void sendMessage(input);
  }

  return (
    <div className={styles.wrapper}>
      <header className={styles.header}>
        <div className={styles.eyebrow}>AI ANALYSIS</div>
        <h1 className={styles.title}>Your AI portfolio companion</h1>
        <p className={styles.subtitle}>
          Get a full AI-generated portfolio report, or ask direct questions about your holdings. Educational insights only — never investment advice.
        </p>
      </header>

      <div className={styles.tabBar} role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={tab === "full"}
          className={tab === "full" ? styles.tabActive : styles.tab}
          onClick={() => setTab("full")}
        >
          <span className={styles.tabIcon}>📊</span> Full analysis
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "chat"}
          className={tab === "chat" ? styles.tabActive : styles.tab}
          onClick={() => setTab("chat")}
        >
          <span className={styles.tabIcon}>💬</span> Ask questions
        </button>
      </div>

      {tab === "full" && (
        <section className={styles.fullPanel}>
          {holdings.length === 0 ? (
            <div className={styles.emptyState}>Add holdings from the dashboard to generate a full AI analysis.</div>
          ) : (
            <>
              <div className={styles.fullActionsRow}>
                <p className={styles.helperText}>
                  {reportLoaded
                    ? "Report generated from your current holdings, allocation, and market data."
                    : "Generate a sector, stock, and diversification report based on your current holdings."}
                </p>
                <button className="btn" onClick={runFullAnalysis} disabled={reportBusy}>
                  {reportBusy ? "Analyzing…" : riskReport ? "Re-run full analysis" : "Run full analysis"}
                </button>
              </div>

              {reportError && <p className={styles.errorText}>{reportError}</p>}

              {reportBusy && (
                <div className={styles.loadingState}>
                  <span className={styles.spinner} />
                  Crunching sector, risk, and diversification insights…
                </div>
              )}

              {!reportBusy && riskReport && (
                <div className={styles.aiPanel}>
                  <div className={styles.eyebrowSmall}>PORTFOLIO REPORT</div>
                  <h2>{riskReport.summary.diversification_verdict}</h2>
                  <p className={styles.aiInsight}>
                    {riskReport.summary.sarvam_insight || "Risk analysis is based on your holdings, allocation, and available market data."}
                  </p>
                  <div className={styles.aiGrid}>
                    <div>
                      <small>Overall risk</small>
                      <strong>{riskReport.summary.portfolio_risk_level}</strong>
                    </div>
                    <div>
                      <small>Concentration flags</small>
                      <strong>{riskReport.portfolio_diversification_analysis.concentration_flags.length || "None"}</strong>
                    </div>
                    <div>
                      <small>Missing / low exposure</small>
                      <strong>{riskReport.portfolio_diversification_analysis.under_exposed_or_missing_sectors.length}</strong>
                    </div>
                  </div>

                  {riskReport.executive_report && (
                    <div className={styles.aiNarrative}>
                      <h3>Sector outlook</h3>
                      <p>{riskReport.executive_report.sector_commentary}</p>
                      {riskReport.executive_report.asset_commentary && (
                        <>
                          <h3>Asset analysis</h3>
                          <p>{riskReport.executive_report.asset_commentary}</p>
                        </>
                      )}
                      <h3>Risk diagnostics</h3>
                      <p>{riskReport.executive_report.risk_commentary}</p>
                      <h3>Educational next steps</h3>
                      <ul>
                        {riskReport.executive_report.recommendations.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {riskReport.sector_thesis && riskReport.sector_thesis.findings.length > 0 && (
                    <div className={styles.aiNarrative}>
                      <h3>Why sectors are growing or not (policy, geopolitics, earnings)</h3>
                      {riskReport.sector_thesis.findings.map((item) => (
                        <div key={item.sector} className={styles.thesisBlock}>
                          <h4>{item.sector}</h4>
                          <p>{item.narrative}</p>
                          <div className={styles.prosConsGrid}>
                            <div>
                              <small>Pros</small>
                              {item.pros.map((pro) => (
                                <span key={pro} className={styles.pro}>+ {pro}</span>
                              ))}
                            </div>
                            <div>
                              <small>Cons</small>
                              {item.cons.map((con) => (
                                <span key={con} className={styles.con}>− {con}</span>
                              ))}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {riskReport.stock_thesis && riskReport.stock_thesis.applicable && riskReport.stock_thesis.findings.length > 0 && (
                    <div className={styles.aiNarrative}>
                      <h3>Stock pros &amp; cons</h3>
                      <div className={styles.stockThesisGrid}>
                        {riskReport.stock_thesis.findings.map((item) => (
                          <div key={item.ticker} className={styles.stockThesisCard}>
                            <strong>{item.ticker}</strong>
                            <small>{item.sector}</small>
                            <div className={styles.stockThesisList}>
                              {item.pros.map((pro) => (
                                <span key={pro} className={styles.pro}>+ {pro}</span>
                              ))}
                              {item.cons.map((con) => (
                                <span key={con} className={styles.con}>− {con}</span>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {riskReport.stock_thesis && !riskReport.stock_thesis.applicable && (
                    <p className={styles.helperText}>{riskReport.stock_thesis.reason_if_not_applicable}</p>
                  )}

                  <div className={styles.aiColumns}>
                    <div>
                      <h3>Sector allocation</h3>
                      {riskReport.portfolio_diversification_analysis.sector_allocation.map((item) => (
                        <div className={styles.aiRow} key={item.sector}>
                          <span>{item.sector}</span>
                          <strong>{item.allocation_pct.toFixed(1)}%</strong>
                        </div>
                      ))}
                    </div>
                    <div>
                      <h3>Stock risk ratings</h3>
                      {riskReport.stock_level_risk_profiles.map((item) => (
                        <div className={styles.aiRow} key={item.ticker}>
                          <span>
                            {item.ticker} <small>{item.sector}</small>
                          </span>
                          <strong>{item.overall_risk_rating}</strong>
                        </div>
                      ))}
                    </div>
                  </div>
                  <p className={styles.aiMissing}>
                    <b>Under-exposed or missing:</b>{" "}
                    {riskReport.portfolio_diversification_analysis.under_exposed_or_missing_sectors.join(", ") || "None identified"}
                  </p>
                </div>
              )}

              {!reportBusy && !riskReport && !reportError && (
                <div className={styles.emptyState}>Click &quot;Run full analysis&quot; to generate your AI sector and stock insights.</div>
              )}
            </>
          )}
        </section>
      )}

      {tab === "chat" && (
        <div className={styles.chatCard}>
          <div className={styles.messages} ref={scrollRef}>
            {messages.map((message, index) => (
              <div key={index} className={message.role === "user" ? styles.userBubbleRow : styles.assistantBubbleRow}>
                <div className={message.role === "user" ? styles.userBubble : styles.assistantBubble}>{message.content}</div>
              </div>
            ))}
            {chatBusy && (
              <div className={styles.assistantBubbleRow}>
                <div className={styles.assistantBubble}>
                  <span className={styles.typingDot} />
                  <span className={styles.typingDot} />
                  <span className={styles.typingDot} />
                </div>
              </div>
            )}
          </div>

          {messages.length <= 1 && (
            <div className={styles.starterRow}>
              {STARTER_PROMPTS.map((prompt) => (
                <button key={prompt} type="button" className={styles.starterChip} onClick={() => void sendMessage(prompt)} disabled={chatBusy}>
                  {prompt}
                </button>
              ))}
            </div>
          )}

          {chatError && <p className={styles.errorText}>{chatError}</p>}

          <form className={styles.inputRow} onSubmit={handleSubmit}>
            <input
              className={styles.input}
              placeholder="Ask about your portfolio…"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              disabled={chatBusy}
            />
            <button className="btn" type="submit" disabled={chatBusy || !input.trim()}>
              {chatBusy ? "Thinking…" : "Send"}
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
