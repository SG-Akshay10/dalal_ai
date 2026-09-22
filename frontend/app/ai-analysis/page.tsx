"use client";

import { useEffect, useRef, useState } from "react";
import styles from "./ai-analysis.module.css";

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

export default function AiAnalysisPage() {
  // ---- Full analysis state ----
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [analysis, setAnalysis] = useState<PortfolioAnalysis | null>(null);
  const [riskReport, setRiskReport] = useState<RiskReport | null>(null);
  const [reportBusy, setReportBusy] = useState(false);
  const [reportError, setReportError] = useState("");
  const [reportLoaded, setReportLoaded] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);

  async function token() {
    const response = await fetch("/api/auth/token");
    return response.ok ? (await response.json()).token : null;
  }

  async function loadHoldings() {
    const auth = await token();
    if (!auth) return;
    const headers = { Authorization: `Bearer ${auth}` };
    const [holdingsResponse, portfolioResponse, cachedRiskResponse] = await Promise.all([
      fetch(`${API_URL}/api/holdings`, { headers }),
      fetch(`${API_URL}/api/analysis/portfolio`, { headers }),
      fetch(`${API_URL}/api/analysis/risk-profile`, { headers }),
    ]);
    if (holdingsResponse.ok) setHoldings(await holdingsResponse.json());
    if (portfolioResponse.ok) setAnalysis(await portfolioResponse.json());
    if (cachedRiskResponse.ok) {
      const cachedData = await cachedRiskResponse.json();
      if (cachedData && cachedData.summary) {
        setRiskReport(cachedData);
        setReportLoaded(true);
      }
    }
  }

  useEffect(() => {
    void loadHoldings();
  }, []);

  function killAnalysis() {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setReportBusy(false);
    setReportError("Analysis process killed by user.");
  }

  async function runFullAnalysis() {
    if (!holdings.length) return;
    setReportBusy(true);
    setReportError("");

    const controller = new AbortController();
    abortControllerRef.current = controller;

    const auth = await token();
    if (!auth) {
      setReportError("Your session has expired. Please sign in again.");
      setReportBusy(false);
      abortControllerRef.current = null;
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
        signal: controller.signal,
      });
      if (response.ok) {
        setRiskReport(await response.json());
        setReportLoaded(true);
      } else if (response.status === 429) {
        const errData = await response.json().catch(() => ({}));
        setReportError(errData.detail || "Rate limit reached: Each account can only generate 1 AI analysis per day.");
      } else if (response.status === 503) {
        setRiskReport(null);
        setReportError("AI analysis is temporarily unavailable. Please retry.");
      } else {
        setRiskReport(null);
        setReportError("Could not generate AI analysis. Please try again.");
      }
    } catch (err: any) {
      if (err?.name === "AbortError") {
        setReportError("Analysis process killed by user.");
      } else {
        setReportError("Could not reach the analysis service. Please try again.");
      }
    } finally {
      setReportBusy(false);
      abortControllerRef.current = null;
    }
  }

  return (
    <div className={styles.wrapper}>
      <header className={styles.header}>
        <div className={styles.eyebrow}>AI ANALYSIS</div>
        <h1 className={styles.title}>Your AI portfolio companion</h1>
        <p className={styles.subtitle}>
          Get a full AI-generated portfolio report based on your holdings. Educational insights only — never investment advice.
        </p>
      </header>

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
                <div className={styles.buttonGroup}>
                  <button className="btn" onClick={runFullAnalysis} disabled={reportBusy}>
                    {reportBusy ? "Analyzing…" : riskReport ? "Re-run full analysis" : "Run full analysis"}
                  </button>
                </div>
              </div>

              {reportError && <p className={styles.errorText}>{reportError}</p>}

              {reportBusy && (
                <div className={styles.loadingState}>
                  <div className={styles.loadingInfo}>
                    <span className={styles.spinner} />
                    <span>Crunching sector, risk, and diversification insights…</span>
                  </div>
                  <button type="button" className="btn btnDanger" onClick={killAnalysis}>
                    Stop Analysis
                  </button>
                </div>
              )}

              {!reportBusy && riskReport && (
                <div className={styles.aiPanel}>
                  {/* Summary Banner */}
                  <div className={styles.reportHeader}>
                    <div>
                      <div className={styles.eyebrowSmall}>PORTFOLIO EXECUTIVE SUMMARY</div>
                      <h2 className={styles.verdictTitle}>{riskReport.summary.diversification_verdict}</h2>
                    </div>
                    <div className={styles.riskBadgeWrapper}>
                      <span className={styles.riskBadgeLabel}>Portfolio Risk</span>
                      <span className={styles.riskBadge}>
                        {riskReport.summary.portfolio_risk_level}
                      </span>
                    </div>
                  </div>

                  <p className={styles.aiInsight}>
                    {riskReport.summary.sarvam_insight || "Risk analysis is based on your holdings, allocation, and available market data."}
                  </p>

                  {/* Top Stats Cards */}
                  <div className={styles.aiGrid}>
                    <div className={styles.statCard}>
                      <span className={styles.statLabel}>Overall Risk Rating</span>
                      <span className={styles.statValue}>{riskReport.summary.portfolio_risk_level}</span>
                    </div>
                    <div className={styles.statCard}>
                      <span className={styles.statLabel}>Concentration Flags</span>
                      <span className={styles.statValue}>
                        {riskReport.portfolio_diversification_analysis.concentration_flags.length || "0"} detected
                      </span>
                    </div>
                    <div className={styles.statCard}>
                      <span className={styles.statLabel}>Missing / Under-Exposed</span>
                      <span className={styles.statValue}>
                        {riskReport.portfolio_diversification_analysis.under_exposed_or_missing_sectors.length} sectors
                      </span>
                    </div>
                  </div>

                  {/* Executive Analysis */}
                  {riskReport.executive_report && (
                    <div className={styles.sectionBlock}>
                      <h3 className={styles.sectionHeading}>
                        <span className={styles.icon}>📊</span> Executive Narrative &amp; Breakdown
                      </h3>
                      <div className={styles.narrativeGrid}>
                        <div className={styles.narrativeCard}>
                          <h4>Sector Outlook</h4>
                          <p>{riskReport.executive_report.sector_commentary}</p>
                        </div>
                        {riskReport.executive_report.asset_commentary && (
                          <div className={styles.narrativeCard}>
                            <h4>Asset Analysis</h4>
                            <p>{riskReport.executive_report.asset_commentary}</p>
                          </div>
                        )}
                        <div className={styles.narrativeCard}>
                          <h4>Risk Diagnostics</h4>
                          <p>{riskReport.executive_report.risk_commentary}</p>
                        </div>
                      </div>

                      {riskReport.executive_report.recommendations && riskReport.executive_report.recommendations.length > 0 && (
                        <div className={styles.recommendationsCard}>
                          <h4>💡 Educational Action Points &amp; Next Steps</h4>
                          <ul>
                            {riskReport.executive_report.recommendations.map((item) => (
                              <li key={item}>{item}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Sector Macro Thesis */}
                  {riskReport.sector_thesis && riskReport.sector_thesis.findings.length > 0 && (
                    <div className={styles.sectionBlock}>
                      <h3 className={styles.sectionHeading}>
                        <span className={styles.icon}>🌐</span> Sector Micro &amp; Macro Thesis
                      </h3>
                      <div className={styles.sectorThesisList}>
                        {riskReport.sector_thesis.findings.map((item) => (
                          <div key={item.sector} className={styles.thesisBlock}>
                            <div className={styles.thesisHeader}>
                              <h4>{item.sector}</h4>
                            </div>
                            <p className={styles.thesisNarrative}>{item.narrative}</p>
                            <div className={styles.prosConsGrid}>
                              <div className={styles.proBox}>
                                <small className={styles.proLabel}>Growth Catalysts (Pros)</small>
                                {item.pros.map((pro) => (
                                  <div key={pro} className={styles.proItem}>
                                    <span className={styles.proBullet}>✓</span> {pro}
                                  </div>
                                ))}
                              </div>
                              <div className={styles.conBox}>
                                <small className={styles.conLabel}>Key Risks &amp; Drag (Cons)</small>
                                {item.cons.map((con) => (
                                  <div key={con} className={styles.conItem}>
                                    <span className={styles.conBullet}>✕</span> {con}
                                  </div>
                                ))}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Stock Level Thesis */}
                  {riskReport.stock_thesis && riskReport.stock_thesis.applicable && riskReport.stock_thesis.findings.length > 0 && (
                    <div className={styles.sectionBlock}>
                      <h3 className={styles.sectionHeading}>
                        <span className={styles.icon}>🔍</span> Individual Stock Breakdown
                      </h3>
                      <div className={styles.stockThesisGrid}>
                        {riskReport.stock_thesis.findings.map((item) => (
                          <div key={item.ticker} className={styles.stockThesisCard}>
                            <div className={styles.stockCardHeader}>
                              <span className={styles.tickerBadge}>{item.ticker}</span>
                              <span className={styles.stockSector}>{item.sector}</span>
                            </div>
                            <div className={styles.stockThesisList}>
                              {item.pros.map((pro) => (
                                <div key={pro} className={styles.proItem}>
                                  <span className={styles.proBullet}>+</span> {pro}
                                </div>
                              ))}
                              {item.cons.map((con) => (
                                <div key={con} className={styles.conItem}>
                                  <span className={styles.conBullet}>−</span> {con}
                                </div>
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

                  {/* Allocation & Risk Table */}
                  <div className={styles.sectionBlock}>
                    <h3 className={styles.sectionHeading}>
                      <span className={styles.icon}>📈</span> Portfolio Structure &amp; Risk Profiles
                    </h3>
                    <div className={styles.aiColumns}>
                      <div className={styles.columnBox}>
                        <h4>Sector Allocation Breakdown</h4>
                        <div className={styles.rowsList}>
                          {riskReport.portfolio_diversification_analysis.sector_allocation.map((item) => (
                            <div className={styles.aiRow} key={item.sector}>
                              <span>{item.sector}</span>
                              <strong className={styles.pctTag}>{item.allocation_pct.toFixed(1)}%</strong>
                            </div>
                          ))}
                        </div>
                      </div>
                      <div className={styles.columnBox}>
                        <h4>Stock Risk Ratings</h4>
                        <div className={styles.rowsList}>
                          {riskReport.stock_level_risk_profiles.map((item) => (
                            <div className={styles.aiRow} key={item.ticker}>
                              <span>
                                <strong>{item.ticker}</strong> <small>({item.sector})</small>
                              </span>
                              <span className={styles.ratingBadge}>{item.overall_risk_rating}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                    {riskReport.portfolio_diversification_analysis.under_exposed_or_missing_sectors?.length > 0 && (
                      <div className={styles.aiMissingBox}>
                        <span className={styles.missingTitle}>⚠️ Under-exposed or missing sectors:</span>
                        <div className={styles.missingBadges}>
                          {riskReport.portfolio_diversification_analysis.under_exposed_or_missing_sectors.map((sec) => (
                            <span key={sec} className={styles.missingBadge}>{sec}</span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {!reportBusy && !riskReport && !reportError && (
                <div className={styles.emptyState}>Click &quot;Run full analysis&quot; to generate your AI sector and stock insights.</div>
              )}
            </>
          )}
        </section>
    </div>
  );
}
