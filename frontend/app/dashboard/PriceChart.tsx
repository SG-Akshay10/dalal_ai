"use client";

import { useEffect, useRef } from "react";
import { CandlestickSeries, ColorType, CrosshairMode, HistogramSeries, LineSeries, createChart } from "lightweight-charts";
import styles from "./dashboard.module.css";

type Candle = { time: string; open: number; high: number; low: number; close: number; volume: number; sma50?: number | null; sma200?: number | null; bollinger_upper?: number | null; bollinger_lower?: number | null };

export default function PriceChart({ data }: { data: Candle[] }) {
  const container = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!container.current || !data.length) return;
    const chart = createChart(container.current, {
      width: container.current.clientWidth,
      height: 360,
      layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: "#94a3b8" },
      grid: { vertLines: { color: "rgba(148,163,184,.08)" }, horzLines: { color: "rgba(148,163,184,.08)" } },
      rightPriceScale: { borderColor: "rgba(148,163,184,.18)" }, timeScale: { borderColor: "rgba(148,163,184,.18)", timeVisible: false },
      crosshair: { mode: CrosshairMode.Normal },
      handleScroll: true,
      handleScale: true,
    });
    const candle = chart.addSeries(CandlestickSeries, { upColor: "#34d399", downColor: "#f87171", borderVisible: false, wickUpColor: "#34d399", wickDownColor: "#f87171" });
    const volume = chart.addSeries(HistogramSeries, { priceFormat: { type: "volume" }, priceScaleId: "volume", color: "rgba(96,165,250,.35)" });
    volume.priceScale().applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
    const sma50 = chart.addSeries(LineSeries, { color: "#fbbf24", lineWidth: 1 });
    const sma200 = chart.addSeries(LineSeries, { color: "#a78bfa", lineWidth: 1 });
    const upper = chart.addSeries(LineSeries, { color: "rgba(56,189,248,.8)", lineWidth: 1 });
    const lower = chart.addSeries(LineSeries, { color: "rgba(56,189,248,.8)", lineWidth: 1 });
    candle.setData(data.map((row) => ({ time: row.time, open: row.open, high: row.high, low: row.low, close: row.close })));
    volume.setData(data.map((row) => ({ time: row.time, value: row.volume, color: row.close >= row.open ? "rgba(52,211,153,.35)" : "rgba(248,113,113,.35)" })));
    const line = (key: keyof Candle) => data.filter((row) => row[key] != null).map((row) => ({ time: row.time, value: row[key] as number }));
    sma50.setData(line("sma50")); sma200.setData(line("sma200")); upper.setData(line("bollinger_upper")); lower.setData(line("bollinger_lower"));
    chart.timeScale().fitContent();
    const observer = new ResizeObserver(() => chart.applyOptions({ width: container.current?.clientWidth || 700 }));
    observer.observe(container.current);
    return () => { observer.disconnect(); chart.remove(); };
  }, [data]);
  return <section className={styles.chartWrap} aria-label="Two-year interactive price chart"><div className={styles.chart} ref={container} /><div className={styles.legend} aria-label="Chart legend"><span className={styles.legendPrice}>● Price</span><span className={styles.legendSma50}>━ SMA 50</span><span className={styles.legendSma200}>━ SMA 200</span><span className={styles.legendBand}>━ Bollinger (20, 2)</span><span className={styles.legendVolume}>▮ Volume</span></div></section>;
}
