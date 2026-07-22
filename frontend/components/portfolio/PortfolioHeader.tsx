"use client";

import Link from "next/link";
import { useSyncExternalStore } from "react";

import styles from "@/app/portfolio/portfolio.module.css";

type BackgroundTheme = "light" | "deep";

const BACKGROUND_THEME_STORAGE_KEY = "ai-radar-bg-theme";
const PORTFOLIO_THEME_CHANGED_EVENT = "ai-radar-portfolio-theme-changed";

function subscribeToTheme(onStoreChange: () => void) {
  window.addEventListener(PORTFOLIO_THEME_CHANGED_EVENT, onStoreChange);
  window.addEventListener("storage", onStoreChange);
  return () => {
    window.removeEventListener(PORTFOLIO_THEME_CHANGED_EVENT, onStoreChange);
    window.removeEventListener("storage", onStoreChange);
  };
}

function getThemeSnapshot(): BackgroundTheme {
  return document.documentElement.dataset.bgTheme === "deep" ? "deep" : "light";
}

function getServerThemeSnapshot(): BackgroundTheme {
  return "light";
}

export default function PortfolioHeader() {
  const backgroundTheme = useSyncExternalStore(
    subscribeToTheme,
    getThemeSnapshot,
    getServerThemeSnapshot,
  );

  function handleThemeChange(nextTheme: BackgroundTheme) {
    document.documentElement.dataset.bgTheme = nextTheme;
    try {
      window.localStorage.setItem(BACKGROUND_THEME_STORAGE_KEY, nextTheme);
    } catch {
      // The selected theme still applies for the current session.
    }
    window.dispatchEvent(new Event(PORTFOLIO_THEME_CHANGED_EVENT));
  }

  return (
    <header className={styles.publicHeader}>
      <Link className={styles.publicBrand} href="/portfolio">
        <span>AI Radar</span>
        <small>Evidence Portfolio</small>
      </Link>
      <nav className={styles.publicNav} aria-label="Portfolio navigation">
        <Link href="/portfolio#case-studies">Case studies</Link>
        <Link href="/portfolio#evidence-boundary">Evidence boundary</Link>
        <a href="https://app.ai-radar-lab.com" target="_blank" rel="noreferrer">
          Live product
        </a>
        <a
          href="https://github.com/Andy-JunXiong/ai-radar-aws-public"
          target="_blank"
          rel="noreferrer"
        >
          GitHub
        </a>
        <a
          href="https://www.linkedin.com/in/jun-xiong-48123856/"
          target="_blank"
          rel="noreferrer"
        >
          LinkedIn
        </a>
      </nav>
      <div className={styles.themeSwitch} aria-label="Portfolio color theme">
        <button
          type="button"
          aria-pressed={backgroundTheme === "light"}
          onClick={() => handleThemeChange("light")}
        >
          Light
        </button>
        <button
          type="button"
          aria-pressed={backgroundTheme === "deep"}
          onClick={() => handleThemeChange("deep")}
        >
          Navy
        </button>
      </div>
    </header>
  );
}
