"use client";

import { useState } from "react";
import { ChevronDown, ArrowRight } from "lucide-react";
import Link from "next/link";
import type { Layer, LayerId } from "@/lib/types";
import { ArchitectureIcon } from "./icon-map";

interface Props {
  layers: Layer[];
  /** Initial expanded layer; null = all collapsed. */
  defaultExpanded?: LayerId | null;
}

export function ArchitectureOverview({
  layers,
  defaultExpanded = "signal",
}: Props) {
  const [expanded, setExpanded] = useState<LayerId | null>(defaultExpanded);

  return (
    <section
      id="architecture"
      className="px-8 md:px-16 lg:px-24 pb-24"
    >
      <div className="max-w-7xl">
        <div className="mb-12 max-w-3xl">
          <div className="text-xs tracking-[0.2em] text-cyan-300/80 font-mono mb-4">
            §01 · ARCHITECTURE
          </div>
          <h2
            className="text-4xl md:text-5xl text-stone-50 mb-4"
            style={{ fontFamily: "Fraunces, Georgia, serif", fontWeight: 300 }}
          >
            Five layers, one direction:
            <br />
            <em className="italic text-cyan-300">
              signal → judgement → action
            </em>
            .
          </h2>
          <p className="text-stone-400 leading-relaxed">
            Each layer answers a single question. Click any layer to see the
            why, the how, and the stack.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-px bg-stone-800">
          {layers.map((layer) => {
            const isExpanded = expanded === layer.id;
            return (
              <button
                key={layer.id}
                onClick={() => setExpanded(isExpanded ? null : layer.id)}
                className={`relative text-left p-6 transition-colors ${
                  isExpanded
                    ? "bg-stone-900"
                    : "bg-stone-950 hover:bg-stone-900"
                }`}
              >
                <div className="font-mono text-xs text-stone-600 mb-4">
                  {layer.num}
                </div>
                <ArchitectureIcon
                  name={layer.icon}
                  className={`w-6 h-6 mb-4 ${
                    isExpanded ? "text-cyan-300" : "text-stone-400"
                  }`}
                />
                <div
                  className="text-xl text-stone-100 mb-2"
                  style={{
                    fontFamily: "Fraunces, Georgia, serif",
                    fontWeight: 400,
                  }}
                >
                  {layer.name}
                </div>
                <div className="text-xs text-stone-500 leading-relaxed">
                  {layer.tagline}
                </div>
                <ChevronDown
                  className={`absolute top-6 right-6 w-4 h-4 text-stone-600 transition-transform ${
                    isExpanded ? "rotate-180" : ""
                  }`}
                />
              </button>
            );
          })}
        </div>

        {expanded && (
          <ExpandedDetail
            layer={layers.find((l) => l.id === expanded) as Layer}
          />
        )}
      </div>
    </section>
  );
}

function ExpandedDetail({ layer }: { layer: Layer }) {
  return (
    <div className="bg-stone-900 border-x border-b border-stone-800 p-8 md:p-12 animate-[fadeIn_0.3s_ease-out]">
      <div className="grid md:grid-cols-3 gap-12">
        <div>
          <div className="flex items-center gap-3 mb-4">
            <ArchitectureIcon
              name={layer.icon}
              className="w-5 h-5 text-cyan-300"
            />
            <span className="font-mono text-xs text-stone-500 tracking-widest">
              LAYER {layer.num} / WHY
            </span>
          </div>
          <p
            className="text-xl text-stone-100 leading-snug"
            style={{
              fontFamily: "Fraunces, Georgia, serif",
              fontWeight: 300,
            }}
          >
            {layer.why}
          </p>
        </div>

        <div>
          <div className="font-mono text-xs text-stone-500 tracking-widest mb-4">
            HOW
          </div>
          <ul className="space-y-3">
            {layer.how.map((h, i) => (
              <li
                key={i}
                className="flex gap-3 text-stone-300 text-sm leading-relaxed"
              >
                <span className="text-cyan-400/60 font-mono mt-1">─</span>
                <span>{h}</span>
              </li>
            ))}
          </ul>
        </div>

        <div>
          <div className="font-mono text-xs text-stone-500 tracking-widest mb-4">
            STACK
          </div>
          <div className="flex flex-wrap gap-2">
            {layer.stack.map((s) => (
              <span
                key={s}
                className="px-2.5 py-1 text-xs font-mono text-cyan-200/90 border border-cyan-400/20 bg-cyan-400/5"
              >
                {s}
              </span>
            ))}
          </div>
          <Link
            href={`/architecture/adrs/${layer.adr_slug}`}
            className="inline-flex items-center gap-2 mt-8 text-xs font-mono text-stone-500 hover:text-cyan-300 transition-colors"
          >
            Read the ADR
            <ArrowRight className="w-3 h-3" />
          </Link>
        </div>
      </div>

      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(-4px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}
