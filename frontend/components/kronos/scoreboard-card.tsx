"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { InfoTip } from "@/components/ui/tooltip";
import { useKronosScoreboard } from "@/lib/hooks/use-kronos";

interface Props {
  timeframe: string;
}

export function ScoreboardCard({ timeframe }: Props) {
  const { data, isLoading } = useKronosScoreboard(timeframe);

  const noData = !data || data.total_evaluated === 0;

  const dirCorrect = data
    ? Math.round((data.directional_accuracy ?? 0) * data.total_evaluated)
    : 0;
  const dirPct = data?.directional_accuracy != null
    ? Math.round(data.directional_accuracy * 100)
    : null;
  const dirColor =
    dirPct == null ? "text-zinc-400"
    : dirPct >= 55  ? "text-emerald-400"
    : dirPct >= 45  ? "text-yellow-400"
    : "text-red-400";

  return (
    <Card className="bg-bp-surface border-bp-border">
      <CardHeader className="pb-1 pt-3 px-4">
        <CardTitle className="text-xs font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1">
          Scoreboard
          <InfoTip text="Accuracy metrics across all predictions where the candle has already closed and the actual result is known." />
          <span className="ml-auto text-xs font-normal normal-case tracking-normal text-zinc-500">{timeframe}</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="px-4 pb-3">
        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-4 w-full" />
            ))}
          </div>
        ) : noData ? (
          <p className="text-xs text-zinc-500">
            No evaluated predictions yet. Results fill in automatically after each candle closes.
          </p>
        ) : (
          <table className="w-full text-xs">
            <tbody className="divide-y divide-bp-border/30">
              <Row
                label="Evaluated"
                value={`${data.total_evaluated} candles`}
                valueClass="text-zinc-300"
                tip="Total predictions where the candle already closed and we have the actual result."
              />
              <Row
                label="Direction"
                value={
                  dirPct != null
                    ? `${dirCorrect}/${data.total_evaluated} (${dirPct}%)`
                    : "—"
                }
                valueClass={dirColor}
                tip="How many times the model correctly predicted whether the candle would close higher or lower than it opened. Above 50% = better than a coin flip."
              />
              <Row
                label="Avg error"
                value={
                  data.avg_abs_error_pct != null
                    ? `${data.avg_abs_error_pct.toFixed(3)}%`
                    : "—"
                }
                valueClass="text-zinc-300"
                tip="Average absolute difference between predicted close and actual close, as a percentage."
              />
              <Row
                label="Best"
                value={
                  data.best_error_pct != null
                    ? `${data.best_error_pct.toFixed(3)}%`
                    : "—"
                }
                valueClass="text-emerald-400"
                tip="The closest price prediction ever — smallest absolute error."
              />
              <Row
                label="Worst"
                value={
                  data.worst_error_pct != null
                    ? `${data.worst_error_pct.toFixed(3)}%`
                    : "—"
                }
                valueClass="text-red-400"
                tip="The furthest price prediction ever — largest absolute error."
              />
            </tbody>
          </table>
        )}
      </CardContent>
    </Card>
  );
}

function Row({
  label,
  value,
  valueClass,
  tip,
}: {
  label: string;
  value: string;
  valueClass: string;
  tip: string;
}) {
  return (
    <tr>
      <td className="py-1 pr-4 text-zinc-500 whitespace-nowrap flex items-center gap-0.5">
        {label}
        <InfoTip text={tip} />
      </td>
      <td className={`py-1 font-mono font-medium ${valueClass}`}>{value}</td>
    </tr>
  );
}
