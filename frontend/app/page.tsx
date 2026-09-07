import Link from "next/link";
import styles from "./page.module.css";

export default function Home() {
  return (
    <div className={styles.hero}>
      <div className={styles.content}>
        <div className={styles.eyebrow}>
          <span>dalal.ai intelligence, made considered</span>
        </div>
        <h1 className={styles.title}>
          Keep a closer eye on what you own.
        </h1>
        <p className={styles.subtitle}>
          A focused brief of the news, filings, and signals that matter to your portfolio—without the noise.
        </p>

        <div className={styles.actions}>
          <Link href="/register" className={styles.btnPrimary}>
            Start tracking
          </Link>
          <Link href="/login" className={styles.btnSecondary}>
            Sign In
          </Link>
        </div>
        <div className={styles.preview} aria-label="Example portfolio briefing">
          <div className={styles.previewHeader}>
            <span>Your market brief</span>
            <span>Today</span>
          </div>
          <div className={styles.previewItem}>
            <span className={styles.stock}>RELIANCE</span>
            <span>Quarterly results</span>
            <span className={styles.positive}>Positive</span>
          </div>
          <div className={styles.previewItem}>
            <span className={styles.stock}>TCS</span>
            <span>Board meeting</span>
            <span className={styles.neutral}>Watch</span>
          </div>
        </div>
      </div>
    </div>
  );
}
