"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useSession, signOut } from "next-auth/react";
import styles from "./Navbar.module.css";

export default function Navbar() {
  const { data: session, status } = useSession();
  const [isAccountMenuOpen, setIsAccountMenuOpen] = useState(false);
  const accountMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const savedTheme = window.localStorage.getItem("portfolio-theme");
    const shouldUseDark = savedTheme === "dark";
    document.documentElement.dataset.theme = shouldUseDark ? "dark" : "light";
  }, []);

  useEffect(() => {
    function closeAccountMenu(event: MouseEvent) {
      if (!accountMenuRef.current?.contains(event.target as Node)) setIsAccountMenuOpen(false);
    }

    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setIsAccountMenuOpen(false);
    }

    document.addEventListener("mousedown", closeAccountMenu);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeAccountMenu);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, []);

  function toggleTheme() {
    const nextIsDark = document.documentElement.dataset.theme !== "dark";
    document.documentElement.dataset.theme = nextIsDark ? "dark" : "light";
    window.localStorage.setItem("portfolio-theme", nextIsDark ? "dark" : "light");
  }

  const userInitial = (session?.user?.name || session?.user?.email || "U").trim().charAt(0).toUpperCase();

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
          title="Toggle light and dark mode"
        >
          <svg className={styles.sunIcon} viewBox="0 0 24 24" aria-hidden="true">
            <circle cx="12" cy="12" r="4" />
            <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
          </svg>
          <svg className={styles.moonIcon} viewBox="0 0 24 24" aria-hidden="true">
            <path d="M20.6 15.79A9 9 0 0 1 8.21 3.4 9 9 0 1 0 20.6 15.79Z" />
          </svg>
        </button>
        {status === "authenticated" ? (
          <div className={styles.accountMenu} ref={accountMenuRef}>
            <button
              type="button"
              className={styles.avatar}
              onClick={() => setIsAccountMenuOpen((isOpen) => !isOpen)}
              aria-label="Open account menu"
              aria-expanded={isAccountMenuOpen}
              aria-haspopup="menu"
              title={session.user?.name || session.user?.email || "User"}
            >
              {userInitial}
            </button>
            {isAccountMenuOpen && (
              <div className={styles.accountDropdown} role="menu">
                <button
                  type="button"
                  className={styles.logoutBtn}
                  role="menuitem"
                  onClick={() => { window.dispatchEvent(new Event("portfolio-signout")); signOut({ callbackUrl: "/" }); }}
                >
                  Sign out
                </button>
              </div>
            )}
          </div>
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
