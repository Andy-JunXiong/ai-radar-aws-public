import Link from "next/link";
import { Circle } from "lucide-react";

export function ArchitectureNav() {
  return (
    <nav className="px-8 md:px-16 lg:px-24 py-6 flex items-center justify-between border-b border-stone-900">
      <Link href="/" className="flex items-center gap-3">
        <div className="w-6 h-6 rounded-full border-2 border-cyan-400 flex items-center justify-center">
          <Circle className="w-1.5 h-1.5 fill-cyan-400 text-cyan-400" />
        </div>
        <span
          className="text-lg text-stone-100 tracking-tight"
          style={{ fontFamily: "Fraunces, Georgia, serif", fontWeight: 500 }}
        >
          AI Radar
        </span>
      </Link>
      <div className="hidden md:flex items-center gap-8 font-mono text-xs text-stone-400">
        <a
          href="#architecture"
          className="hover:text-cyan-300 transition-colors"
        >
          Architecture
        </a>
        <a href="#flow" className="hover:text-cyan-300 transition-colors">
          Signal flow
        </a>
        <Link
          href="/architecture/adrs"
          className="hover:text-cyan-300 transition-colors"
        >
          ADRs
        </Link>
        <a href="#" className="hover:text-cyan-300 transition-colors">
          Notebook
        </a>
      </div>
    </nav>
  );
}

export function ArchitectureFooter() {
  return (
    <footer className="px-8 md:px-16 lg:px-24 py-16 border-t border-stone-900">
      <div className="max-w-7xl flex flex-wrap items-end justify-between gap-8">
        <div>
          <div
            className="text-2xl text-stone-100 mb-2"
            style={{ fontFamily: "Fraunces, Georgia, serif", fontWeight: 400 }}
          >
            AI Radar
          </div>
          <div className="font-mono text-xs text-stone-500">
            Built by Andy (Jun Xiong) · Sydney · 2026
          </div>
        </div>
        <div className="flex gap-6 font-mono text-xs text-stone-500">
          <a href="#" className="hover:text-cyan-300 transition-colors">
            GitHub
          </a>
          <a href="#" className="hover:text-cyan-300 transition-colors">
            LinkedIn
          </a>
          <Link
            href="/architecture/adrs"
            className="hover:text-cyan-300 transition-colors"
          >
            ADR Index
          </Link>
        </div>
      </div>
    </footer>
  );
}
