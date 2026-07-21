import type { DaoFaShuItem } from "@/lib/types";

export function DaoFaShu({ items }: { items: DaoFaShuItem[] }) {
  return (
    <section className="px-8 md:px-16 lg:px-24 py-24">
      <div className="max-w-7xl">
        <div className="mb-12 max-w-3xl">
          <div className="text-xs tracking-[0.2em] text-cyan-300/80 font-mono mb-4">
            §03 · FRAMING
          </div>
          <h2
            className="text-4xl md:text-5xl text-stone-50 mb-4"
            style={{ fontFamily: "Fraunces, Georgia, serif", fontWeight: 300 }}
          >
            <em className="italic text-cyan-300">Principle · Method · Tactic</em>
            <br />
            applied to AI systems.
          </h2>
          <p className="text-stone-400 leading-relaxed">
            The lens I use to keep architecture decisions honest. Principle
            constrains method; method constrains tactic.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-px bg-stone-800">
          {items.map((it) => (
            <div key={it.ch} className="bg-stone-950 p-10">
              <div
                className="text-7xl text-cyan-300 mb-2 leading-none"
                style={{
                  fontFamily: "Fraunces, Georgia, serif",
                  fontWeight: 300,
                }}
              >
                {it.ch}
              </div>
              <div className="font-mono text-xs text-stone-500 tracking-widest mb-6">
                {it.pinyin.toUpperCase()} · {it.en.toUpperCase()}
              </div>
              <p className="text-stone-300 leading-relaxed">{it.body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
