"use client";

import { useState, useEffect, useRef } from "react";
import { Play, Pause, Sparkles } from "lucide-react";
import type { Layer, FlowStep } from "@/lib/types";
import { getIcon } from "./icon-map";

interface Props {
  layers: Layer[];
  steps: FlowStep[];
  /** Auto-advance interval in ms when playing. */
  intervalMs?: number;
}

/**
 * ⚠️  CODEX SWAP POINT
 * The `steps` prop is currently sourced from /content/flow-steps.json.
 * To show a real live trace, replace the call site (page.tsx) with a
 * fetch from /api/flow/sample or similar. Keep the FlowStep[] shape.
 */
export function SignalFlow({ layers, steps, intervalMs = 1800 }: Props) {
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (playing) {
      intervalRef.current = setInterval(() => {
        setStep((s) => {
          if (s >= steps.length - 1) {
            setPlaying(false);
            return s;
          }
          return s + 1;
        });
      }, intervalMs);
    } else if (intervalRef.current) {
      clearInterval(intervalRef.current);
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [playing, intervalMs, steps.length]);

  const reset = () => {
    setPlaying(false);
    setStep(0);
  };

  const current = steps[step];
  const currentLayer = layers.find((l) => l.id === current.layer)!;

  return (
    <section
      id="flow"
      className="px-8 md:px-16 lg:px-24 py-24 bg-gradient-to-b from-stone-950 via-stone-950 to-cyan-950/10 border-y border-stone-900"
    >
      <div className="max-w-7xl mx-auto">
        <div className="mb-12 max-w-3xl">
          <div className="text-xs tracking-[0.2em] text-cyan-300/80 font-mono mb-4">
            §02 · SIGNAL FLOW
          </div>
          <h2
            className="text-4xl md:text-5xl text-stone-50 mb-4"
            style={{ fontFamily: "Fraunces, Georgia, serif", fontWeight: 300 }}
          >
            Watch one signal travel
            <br />
            <em className="italic text-cyan-300">all five layers</em>.
          </h2>
          <p className="text-stone-400 leading-relaxed">
            A live trace of one AI Radar signal from collector intake to
            reviewable project outcome. Press play, or step through manually.
          </p>
        </div>

        {/* Timeline */}
        <div className="relative mb-10">
          <div className="absolute top-5 left-0 right-0 h-px bg-stone-800" />
          <div
            className="absolute top-5 left-0 h-px bg-cyan-400 transition-all duration-700"
            style={{
              width: `${(step / (steps.length - 1)) * 100}%`,
            }}
          />
          <div className="relative grid grid-cols-5 gap-4">
            {steps.map((s, i) => {
              const layer = layers.find((l) => l.id === s.layer)!;
              const Icon = getIcon(layer.icon);
              const isActive = i === step;
              const isPast = i < step;
              return (
                <button
                  key={i}
                  onClick={() => {
                    setPlaying(false);
                    setStep(i);
                  }}
                  className="relative text-left group"
                >
                  <div
                    className={`relative z-10 w-10 h-10 mx-auto rounded-full flex items-center justify-center border-2 transition-all ${
                      isActive
                        ? "bg-cyan-400 border-cyan-400 scale-110"
                        : isPast
                        ? "bg-cyan-400/20 border-cyan-400"
                        : "bg-stone-950 border-stone-700 group-hover:border-stone-500"
                    }`}
                  >
                    <Icon
                      className={`w-4 h-4 ${
                        isActive
                          ? "text-stone-950"
                          : isPast
                          ? "text-cyan-300"
                          : "text-stone-500"
                      }`}
                    />
                  </div>
                  <div
                    className={`mt-3 font-mono text-[10px] tracking-widest text-center ${
                      isActive ? "text-cyan-300" : "text-stone-500"
                    }`}
                  >
                    {layer.num} · {layer.name.toUpperCase()}
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-3 mb-8">
          <button
            onClick={() => {
              if (step >= steps.length - 1) reset();
              setPlaying(!playing);
            }}
            className="inline-flex items-center gap-2 px-4 py-2 bg-cyan-400 text-stone-950 text-sm font-medium hover:bg-cyan-300 transition-colors"
          >
            {playing ? (
              <>
                <Pause className="w-4 h-4" />
                Pause
              </>
            ) : (
              <>
                <Play className="w-4 h-4" fill="currentColor" />
                {step >= steps.length - 1 ? "Replay" : "Run a signal"}
              </>
            )}
          </button>
          <button
            onClick={reset}
            className="px-4 py-2 text-sm text-stone-400 hover:text-stone-200 transition-colors"
          >
            Reset
          </button>
          <div className="ml-auto font-mono text-xs text-stone-500">
            STEP {step + 1} / {steps.length}
          </div>
        </div>

        {/* Snapshot panel */}
        <div className="grid md:grid-cols-2 gap-px bg-stone-800">
          <div className="bg-stone-900 p-8">
            <div className="font-mono text-xs text-stone-500 tracking-widest mb-3">
              {currentLayer.num} · {currentLayer.name.toUpperCase()}
            </div>
            <h3
              className="text-2xl text-stone-50 mb-3"
              style={{
                fontFamily: "Fraunces, Georgia, serif",
                fontWeight: 400,
              }}
            >
              {current.title}
            </h3>
            <p className="text-stone-400 leading-relaxed">{current.detail}</p>

            <div className="mt-8 pt-6 border-t border-stone-800">
              <div className="font-mono text-[10px] tracking-widest text-stone-600 mb-2">
                WHY THIS STEP MATTERS
              </div>
              <p className="text-sm text-stone-400 leading-relaxed italic">
                {currentLayer.why}
              </p>
            </div>
          </div>

          <div className="bg-stone-950 p-8">
            <div className="font-mono text-xs text-stone-500 tracking-widest mb-4 flex items-center gap-2">
              <Sparkles className="w-3 h-3" />
              DATA SNAPSHOT
            </div>
            <pre className="font-mono text-xs text-stone-300 leading-relaxed whitespace-pre-wrap break-words">
{JSON.stringify(current.snapshot, null, 2)}
            </pre>
          </div>
        </div>
      </div>
    </section>
  );
}
