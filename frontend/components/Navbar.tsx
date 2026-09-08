"use client";

import Link from "next/link";
import { useEffect } from "react";
import { useSession, signOut } from "next-auth/react";
import styles from "./Navbar.module.css";

export default function Navbar() {
  const { data: session, status } = useSession();

  useEffect(() => {
    const savedTheme = window.localStorage.getItem("portfolio-theme");
    const shouldUseDark = savedTheme === "dark";
    document.documentElement.dataset.theme = shouldUseDark ? "dark" : "light";
  }, []);

  function toggleTheme() {
    const nextIsDark = document.documentElement.dataset.theme !== "dark";
    document.documentElement.dataset.theme = nextIsDark ? "dark" : "light";
    window.localStorage.setItem("portfolio-theme", nextIsDark ? "dark" : "light");
  }

  return (
    <nav className={styles.nav}>
      <Link href="/" className={styles.brand}>
        dalal.ai
      </Link>
      <div className={styles.links}>
        <button
          type="button"
          className={styles.themeToggle}
          onClick={toggleTheme}
          aria-label="Toggle light and dark mode"
        >
          Theme
        </button>
        {status === "authenticated" ? (
          <>
            <span className={styles.userEmail}>{session.user?.email}</span>
            <Link href="/dashboard" className={styles.link}>
              Dashboard
            </Link>
            <button
              className={styles.logoutBtn}
              onClick={() => { window.dispatchEvent(new Event("portfolio-signout")); signOut({ callbackUrl: "/" }); }}
            >
              Logout
            </button>
          </>
        ) : (
          <>
            <Link href="/login" className={styles.link}>
              Login
            </Link>
            <Link href="/register" className={styles.linkPrimary}>
              Register
            </Link>
          </>
        )}
      </div>
    </nav>
  );
}
