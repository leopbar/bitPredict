"use client";

import { cn } from "@/lib/utils";
import { useTimeframe, VALID_TIMEFRAMES, type AppTimeframe } from "@/lib/hooks/use-timeframe";

const LABELS: Record<AppTimeframe, string> = {
  "15m": "15m",
  "1h": "1h",
  "1d": "1d",
};

export function TimeframeToggle() {
  const [timeframe, setTimeframe] = useTimeframe();

  return (
    <div className="flex items-center gap-0.5 bg-zinc-900 border border-zinc-800 rounded-lg p-0.5">
      {VALID_TIMEFRAMES.map((tf) => (
        <button
          key={tf}
          onClick={() => setTimeframe(tf)}
          className={cn(
            "px-3 py-1 rounded-md text-xs font-semibold transition-all duration-150",
            timeframe === tf
              ? "bg-cyan-500/15 text-cyan-400 border border-cyan-500/30"
              : "text-zinc-500 hover:text-zinc-300 border border-transparent",
          )}
        >
          {LABELS[tf]}
        </button>
      ))}
    </div>
  );
}
