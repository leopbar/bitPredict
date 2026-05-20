"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { InfoTip } from "@/components/ui/tooltip";
import { formatUSD } from "@/lib/format";
import { useKronosSims, useKronosProgress } from "@/lib/hooks/use-kronos";
import type { KronosSimSample } from "@/lib/api/schemas";

// 30 fictional analysts alternating male/female
const ANALYSTS: { name: string; gender: "m" | "f" }[] = [
  { name: "Alex Chen",      gender: "m" },
  { name: "Sofia Martinez", gender: "f" },
  { name: "Marcus Webb",    gender: "m" },
  { name: "Emma Walsh",     gender: "f" },
  { name: "Jordan Blake",   gender: "m" },
  { name: "Isabella Reed",  gender: "f" },
  { name: "Ryan Torres",    gender: "m" },
  { name: "Olivia Grant",   gender: "f" },
  { name: "Daniel Kim",     gender: "m" },
  { name: "Ava Brooks",     gender: "f" },
  { name: "Noah Carter",    gender: "m" },
  { name: "Chloe Evans",    gender: "f" },
  { name: "Ethan Ross",     gender: "m" },
  { name: "Maya Patel",     gender: "f" },
  { name: "Lucas Hunt",     gender: "m" },
  { name: "Luna Scott",     gender: "f" },
  { name: "Samuel Park",    gender: "m" },
  { name: "Zoe Turner",     gender: "f" },
  { name: "Owen Clarke",    gender: "m" },
  { name: "Nora Quinn",     gender: "f" },
  { name: "Finn Bradley",   gender: "m" },
  { name: "Aria Hayes",     gender: "f" },
  { name: "Miles Cooper",   gender: "m" },
  { name: "Lily Foster",    gender: "f" },
  { name: "Caleb Stone",    gender: "m" },
  { name: "Jade Morgan",    gender: "f" },
  { name: "Zane Harper",    gender: "m" },
  { name: "Freya Bell",     gender: "f" },
  { name: "Dylan Cruz",     gender: "m" },
  { name: "Mia Rivera",     gender: "f" },
];

// Distinct palettes so analysts each get a unique color
const MALE_PALETTE   = ["#38bdf8","#818cf8","#34d399","#fb923c","#a78bfa","#22d3ee","#4ade80","#f472b6","#fbbf24","#60a5fa","#2dd4bf","#c084fc","#86efac","#fdba74","#93c5fd"];
const FEMALE_PALETTE = ["#f472b6","#fb7185","#e879f9","#a78bfa","#f9a8d4","#c084fc","#fb923c","#d946ef","#f43f5e","#e11d48","#db2777","#9333ea","#ec4899","#a855f7","#8b5cf6"];

function AnalystAvatar({ gender, index }: { gender: "m" | "f"; index: number }) {
  const palette = gender === "m" ? MALE_PALETTE : FEMALE_PALETTE;
  const color   = palette[index % palette.length];
  const bg      = color + "22"; // ~13% opacity background

  if (gender === "f") {
    return (
      <svg viewBox="0 0 36 36" width="30" height="30" className="shrink-0">
        {/* Circle background */}
        <circle cx="18" cy="18" r="18" fill={bg} />
        <circle cx="18" cy="18" r="17" fill="none" stroke={color} strokeWidth="1.5" />
        {/* Long hair behind */}
        <ellipse cx="18" cy="13" rx="7.5" ry="8" fill={color} opacity="0.55" />
        <rect x="10.5" y="13" width="3" height="11" rx="1.5" fill={color} opacity="0.55" />
        <rect x="22.5" y="13" width="3" height="11" rx="1.5" fill={color} opacity="0.55" />
        {/* Face */}
        <circle cx="18" cy="13" r="5.5" fill={color} opacity="0.9" />
        {/* Neck */}
        <rect x="16" y="18" width="4" height="3" fill={color} opacity="0.7" />
        {/* Shoulders / body */}
        <path d="M8 34 Q9 27 18 27 Q27 27 28 34 Z" fill={color} opacity="0.75" />
        {/* Smile */}
        <path d="M15.5 14.5 Q18 16.5 20.5 14.5" stroke="white" strokeWidth="1" fill="none" strokeLinecap="round" opacity="0.7" />
        {/* Eyes */}
        <circle cx="15.5" cy="12.5" r="0.8" fill="white" opacity="0.8" />
        <circle cx="20.5" cy="12.5" r="0.8" fill="white" opacity="0.8" />
      </svg>
    );
  }

  // Male
  return (
    <svg viewBox="0 0 36 36" width="30" height="30" className="shrink-0">
      {/* Circle background */}
      <circle cx="18" cy="18" r="18" fill={bg} />
      <circle cx="18" cy="18" r="17" fill="none" stroke={color} strokeWidth="1.5" />
      {/* Short hair / top of head */}
      <ellipse cx="18" cy="10" rx="5.5" ry="3" fill={color} opacity="0.7" />
      {/* Face */}
      <circle cx="18" cy="13" r="5.5" fill={color} opacity="0.9" />
      {/* Neck */}
      <rect x="16" y="18" width="4" height="3" fill={color} opacity="0.7" />
      {/* Shoulders / body – broader for male */}
      <path d="M6 34 Q8 26 18 26 Q28 26 30 34 Z" fill={color} opacity="0.75" />
      {/* Collar / tie hint */}
      <path d="M16 21 L18 25 L20 21" fill="white" opacity="0.3" />
      {/* Smile */}
      <path d="M15.5 14.5 Q18 16.5 20.5 14.5" stroke="white" strokeWidth="1" fill="none" strokeLinecap="round" opacity="0.7" />
      {/* Eyes */}
      <circle cx="15.5" cy="12.5" r="0.8" fill="white" opacity="0.8" />
      <circle cx="20.5" cy="12.5" r="0.8" fill="white" opacity="0.8" />
    </svg>
  );
}

interface Props {
  timeframe: string;
  refClose?: number | null;
}

function deltaPct(close: number, ref: number | null | undefined): string {
  if (!ref || ref === 0) return "—";
  const pct = ((close - ref) / ref) * 100;
  return `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`;
}

function SimRow({
  index,
  sample,
  refClose,
}: {
  index: number;
  sample: KronosSimSample;
  refClose: number | null | undefined;
}) {
  const analyst = ANALYSTS[(index - 1) % ANALYSTS.length];
  const isBull = refClose != null ? sample.close > refClose : sample.close > sample.open;
  const delta  = deltaPct(sample.close, refClose);
  const isPos  = refClose != null && sample.close > refClose;

  return (
    <tr className="border-b border-bp-border/30 hover:bg-white/[0.03] transition-colors">
      {/* Analyst */}
      <td className="px-3 py-2">
        <div className="flex items-center gap-2.5 min-w-0">
          <AnalystAvatar gender={analyst.gender} index={index - 1} />
          <span className="text-sm text-zinc-200 truncate leading-none font-medium">
            {analyst.name}
          </span>
        </div>
      </td>

      {/* Close */}
      <td className="px-3 py-2 font-mono text-sm font-semibold text-zinc-100 tabular-nums whitespace-nowrap">
        {formatUSD(sample.close)}
      </td>

      {/* Δ% */}
      <td className={`px-3 py-2 font-mono text-sm tabular-nums whitespace-nowrap font-semibold ${
        isPos ? "text-emerald-400" : refClose != null ? "text-red-400" : "text-zinc-500"
      }`}>
        {delta}
      </td>

      {/* Direction */}
      <td className="px-3 py-2 text-center text-base">
        {isBull
          ? <span className="text-emerald-400 font-bold">▲</span>
          : <span className="text-red-400 font-bold">▼</span>
        }
      </td>

      {/* Open / High / Low */}
      <td className="px-3 py-2 font-mono text-xs text-zinc-500 tabular-nums whitespace-nowrap">
        {formatUSD(sample.open)}
      </td>
      <td className="px-3 py-2 font-mono text-xs text-zinc-500 tabular-nums whitespace-nowrap">
        {formatUSD(sample.high)}
      </td>
      <td className="px-3 py-2 font-mono text-xs text-zinc-500 tabular-nums whitespace-nowrap">
        {formatUSD(sample.low)}
      </td>
    </tr>
  );
}

export function SimulationsCard({ timeframe, refClose }: Props) {
  const { data: sims, isLoading } = useKronosSims(timeframe);
  const { data: progress } = useKronosProgress(timeframe);

  const isRunning = progress?.state === "PROGRESS" || progress?.state === "STARTED";
  const current   = progress?.current ?? 0;
  const total     = progress?.total ?? 30;
  const pct       = total > 0 ? Math.round((current / total) * 100) : 0;

  const ref     = refClose ?? sims?.ref_close;
  const samples = sims?.samples ?? [];

  const bullCount = ref != null
    ? samples.filter((s) => s.close > ref).length
    : samples.filter((s) => s.close > s.open).length;
  const bearCount = samples.length - bullCount;

  const sortedCloses = [...samples].sort((a, b) => a.close - b.close);
  const median = sims?.available && sortedCloses.length > 0
    ? sortedCloses[Math.floor(sortedCloses.length / 2)]?.close
    : null;

  return (
    <Card className="bg-bp-surface border-bp-border flex flex-col h-full">
      <CardHeader className="pb-2 pt-3 px-4 shrink-0">
        <CardTitle className="text-sm font-semibold text-zinc-200 flex items-center gap-1">
          30 Stochastic Simulations
          <InfoTip text="Kronos runs 30 independent simulations, each starting from the same 512-candle context but with different random seeds. Each row is one possible future candle. The median of all 30 closes becomes the official prediction." />
          <span className="ml-auto text-xs font-normal text-zinc-500">
            {timeframe}
            {sims?.model_variant && (
              <span className="ml-1 text-zinc-600">· {sims.model_variant}</span>
            )}
          </span>
        </CardTitle>
      </CardHeader>

      <CardContent className="px-4 pb-4 flex flex-col flex-1 min-h-0">
        {/* Progress bar */}
        {isRunning && (
          <div className="mb-3 space-y-1 shrink-0">
            <div className="flex justify-between text-xs text-zinc-500">
              <span>Running simulation {current} of {total}…</span>
              <span>{pct}%</span>
            </div>
            <div className="w-full h-1.5 bg-bp-surface-2 rounded-full overflow-hidden">
              <div
                className="h-full bg-cyan-500 rounded-full transition-all duration-300"
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        )}

        {/* Consensus summary */}
        {samples.length > 0 && !isRunning && (
          <div className="mb-3 shrink-0 flex flex-wrap items-center gap-x-5 gap-y-1 text-xs text-zinc-400">
            <span>
              Median close:{" "}
              <span className="font-mono text-zinc-100 font-semibold">
                {median != null ? formatUSD(median) : "—"}
              </span>
            </span>
            <span>
              <span className="text-emerald-400 font-semibold">▲ {bullCount}</span>
              {" / "}
              <span className="text-red-400 font-semibold">▼ {bearCount}</span>
              <span className="text-zinc-600 ml-1">analysts</span>
            </span>
            {ref != null && (
              <span className="text-zinc-600">ref {formatUSD(ref)}</span>
            )}
          </div>
        )}

        {isLoading && samples.length === 0 ? (
          <div className="space-y-2 shrink-0">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-9 w-full" />
            ))}
          </div>
        ) : samples.length === 0 ? (
          <p className="text-sm text-zinc-600 py-4">
            {isRunning
              ? "Waiting for first simulation…"
              : "No simulation data yet. Trigger a prediction to populate this table."}
          </p>
        ) : (
          /* flex-1 + min-h-0 makes this div fill the remaining card height */
          <div className="flex-1 min-h-0 overflow-y-auto rounded border border-bp-border/30">
            <table className="w-full">
              <thead className="sticky top-0 bg-bp-surface z-10">
                <tr className="border-b border-bp-border">
                  <th className="px-3 py-2 text-left text-xs font-medium text-zinc-500">Analyst</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-zinc-500">
                    <span className="flex items-center gap-0.5">
                      Close <InfoTip text="The simulated close price for this run." />
                    </span>
                  </th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-zinc-500">
                    <span className="flex items-center gap-0.5">
                      Δ% <InfoTip text="Change vs the last actual close (reference price). Positive = bullish prediction." />
                    </span>
                  </th>
                  <th className="px-3 py-2 text-center text-xs font-medium text-zinc-500">Dir</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-zinc-500">Open</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-zinc-500">High</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-zinc-500">Low</th>
                </tr>
              </thead>
              <tbody>
                {samples.map((s, i) => (
                  <SimRow key={i} index={i + 1} sample={s} refClose={ref} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
