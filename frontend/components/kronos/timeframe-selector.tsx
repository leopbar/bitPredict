"use client";

import { cn } from "@/lib/utils";

const TIMEFRAMES = [
  { value: "15m", label: "15m" },
  { value: "1h",  label: "1h"  },
  { value: "4h",  label: "4h"  },
  { value: "8h",  label: "8h"  },
  { value: "1d",  label: "1D"  },
  { value: "1w",  label: "1W"  },
] as const;

interface Props {
  value: string;
  onChange: (tf: string) => void;
}

export function TimeframeSelector({ value, onChange }: Props) {
  return (
    <div className="flex gap-1 p-1 rounded-lg bg-bp-surface border border-bp-border w-fit">
      {TIMEFRAMES.map((tf) => (
        <button
          key={tf.value}
          onClick={() => onChange(tf.value)}
          className={cn(
            "px-3 py-1.5 text-xs font-medium rounded-md transition-colors",
            value === tf.value
              ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/30"
              : "text-zinc-400 hover:text-zinc-200 hover:bg-bp-surface-2",
          )}
        >
          {tf.label}
        </button>
      ))}
    </div>
  );
}
