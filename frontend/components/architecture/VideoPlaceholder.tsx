import { Play } from "lucide-react";

/**
 * ⚠️  CODEX SWAP POINT
 * This is a static placeholder. When the architecture walk-through
 * video is recorded, replace the inner <div> with a real embed:
 *
 *   - Mux / Cloudflare Stream <iframe> for hosted
 *   - <video> tag for self-hosted (in /public)
 *   - YouTube/Vimeo iframe if going public
 *
 * Keep the aspect-video container and surrounding frame.
 */
export function VideoPlaceholder() {
  return (
    <section className="px-8 md:px-16 lg:px-24 pb-24">
      <div className="max-w-5xl">
        <div className="mb-6 flex items-baseline justify-between">
          <h2
            className="text-2xl text-stone-200"
            style={{ fontFamily: "Fraunces, Georgia, serif", fontWeight: 400 }}
          >
            <span className="text-stone-600 font-mono text-sm mr-3">00</span>
            Two-minute architecture walk-through
          </h2>
          <span className="text-xs text-stone-500 font-mono">2:14</span>
        </div>
        <div className="relative aspect-video bg-stone-900 border border-stone-800 group cursor-pointer overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-br from-cyan-950/40 via-stone-900 to-stone-950" />
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="w-20 h-20 rounded-full bg-cyan-400/90 flex items-center justify-center group-hover:scale-110 transition-transform">
              <Play
                className="w-8 h-8 text-stone-950 ml-1"
                fill="currentColor"
              />
            </div>
          </div>
          <div className="absolute bottom-6 left-6 text-xs font-mono text-stone-400">
            [ video placeholder · record with Loom or OBS ]
          </div>
        </div>
      </div>
    </section>
  );
}
