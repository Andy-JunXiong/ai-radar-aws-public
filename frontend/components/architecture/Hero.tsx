import { Circle, ArrowRight } from "lucide-react";

export function Hero() {
  return (
    <section className="relative px-8 pt-24 pb-32 md:px-16 lg:px-24 overflow-hidden">
      {/* Radar sweep background — see CODEX_HANDOFF for animation rationale */}
      <div className="absolute inset-0 pointer-events-none opacity-[0.18]">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[900px] h-[900px]">
          <div className="absolute inset-0 rounded-full border border-cyan-400/30" />
          <div className="absolute inset-[80px] rounded-full border border-cyan-400/20" />
          <div className="absolute inset-[180px] rounded-full border border-cyan-400/15" />
          <div className="absolute inset-[300px] rounded-full border border-cyan-400/10" />
          <div
            className="absolute inset-0 origin-center rounded-full"
            style={{
              background:
                "conic-gradient(from 0deg, transparent 0deg, rgba(34,211,238,0.18) 30deg, transparent 60deg)",
              animation: "sweep 8s linear infinite",
            }}
          />
        </div>
      </div>

      <div className="relative max-w-5xl">
        <div className="flex items-center gap-2 mb-8 text-xs tracking-[0.2em] text-cyan-300/80 font-mono">
          <Circle className="w-2 h-2 fill-cyan-400 text-cyan-400 animate-pulse" />
          AI RADAR · v0.7 · LIVE
        </div>

        <h1
          className="text-5xl md:text-7xl lg:text-8xl leading-[0.95] tracking-tight text-stone-50 mb-8"
          style={{ fontFamily: "Fraunces, Georgia, serif", fontWeight: 300 }}
        >
          A signal intelligence
          <br />
          engine for the{" "}
          <em className="italic text-cyan-300">cognitively sovereign</em>.
        </h1>

        <p className="text-lg md:text-xl text-stone-400 max-w-2xl leading-relaxed mb-10">
          Five layers — Signal, Insight, Reflection, Knowledge Engine, Project
          Engine — converging weak signals into authored judgement. Built around
          a single principle:{" "}
          <span className="text-stone-200">problem definition stays human-led</span>.
        </p>

        <div className="flex flex-wrap items-center gap-4">
          <a
            href="#flow"
            className="group inline-flex items-center gap-3 px-6 py-3 bg-cyan-400 text-stone-950 text-sm font-medium hover:bg-cyan-300 transition-colors"
          >
            Watch a signal flow through
            <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
          </a>
          <a
            href="#architecture"
            className="inline-flex items-center gap-3 px-6 py-3 border border-stone-700 text-stone-300 text-sm hover:border-stone-500 hover:text-stone-100 transition-colors"
          >
            Read the architecture
          </a>
        </div>
      </div>

      <style>{`
        @keyframes sweep {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </section>
  );
}
