"use client";

import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Settings, X, Play, FlaskConical, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useKronosTrigger, useKronosTriggerBacktest } from "@/lib/hooks/use-kronos";
import { cn } from "@/lib/utils";

const TIMEFRAMES = ["15m", "1h", "4h", "8h", "1d", "1w"] as const;

const VARIANT_LABELS: Record<string, string> = {
  "15m": "small",
  "1h": "base",
  "4h": "base",
  "8h": "base",
  "1d": "base",
  "1w": "base",
};

const BACKTEST_EST: Record<string, string> = {
  "15m": "~17 h (500 candles × small)",
  "1h":  "~27 h (200 candles × base)",
  "4h":  "~27 h (200 candles × base)",
  "8h":  "~27 h (200 candles × base)",
  "1d":  "~27 h (200 candles × base)",
  "1w":  "~58 h (430 candles × base)",
};

interface Props {
  timeframe: string;
}

export function AdvancedSettingsDialog({ timeframe }: Props) {
  const [open, setOpen] = useState(false);
  const [confirmBacktest, setConfirmBacktest] = useState(false);
  const trigger = useKronosTrigger();
  const triggerBacktest = useKronosTriggerBacktest();

  function handleOpen(v: boolean) {
    setOpen(v);
    if (!v) setConfirmBacktest(false);
  }

  function handleRunBacktest() {
    if (!confirmBacktest) {
      setConfirmBacktest(true);
      return;
    }
    triggerBacktest.mutate({ timeframe });
    setOpen(false);
    setConfirmBacktest(false);
  }

  return (
    <Dialog.Root open={open} onOpenChange={handleOpen}>
      <Dialog.Trigger asChild>
        <Button variant="ghost" size="sm" className="text-zinc-400 hover:text-zinc-200 gap-1.5">
          <Settings className="w-4 h-4" />
          Advanced
        </Button>
      </Dialog.Trigger>

      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40" />
        <Dialog.Content
          className={cn(
            "fixed z-50 top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2",
            "w-full max-w-md bg-bp-surface border border-bp-border rounded-xl shadow-2xl",
            "p-6 focus:outline-none",
          )}
        >
          <div className="flex items-center justify-between mb-5">
            <Dialog.Title className="text-sm font-semibold text-zinc-100">
              Advanced Settings
            </Dialog.Title>
            <Dialog.Close asChild>
              <button className="text-zinc-500 hover:text-zinc-300 transition-colors">
                <X className="w-4 h-4" />
              </button>
            </Dialog.Close>
          </div>

          {/* Model variants reference table */}
          <section className="mb-5">
            <h3 className="text-xs font-medium text-zinc-400 uppercase tracking-wide mb-2">
              Model Variants
            </h3>
            <div className="rounded-lg border border-bp-border overflow-hidden">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-bp-surface-2">
                    <th className="px-3 py-2 text-left text-zinc-500">Timeframe</th>
                    <th className="px-3 py-2 text-left text-zinc-500">Variant</th>
                    <th className="px-3 py-2 text-left text-zinc-500">Predict est.</th>
                  </tr>
                </thead>
                <tbody>
                  {TIMEFRAMES.map((tf) => (
                    <tr key={tf} className={`border-t border-bp-border ${tf === timeframe ? "bg-cyan-950/20" : ""}`}>
                      <td className="px-3 py-2 text-zinc-300 font-mono">{tf}</td>
                      <td className="px-3 py-2">
                        <Badge variant="zinc" className="text-xs py-0">
                          {VARIANT_LABELS[tf]}
                        </Badge>
                      </td>
                      <td className="px-3 py-2 text-zinc-500">
                        {VARIANT_LABELS[tf] === "small" ? "~2 min" : "~8 min"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-xs text-zinc-600 mt-2">
              Override variants via the <code className="text-zinc-400">parameters</code> table
              (keys: <code className="text-zinc-400">kronos.variant.&#123;tf&#125;</code>).
            </p>
          </section>

          {/* Inference config */}
          <section className="mb-5">
            <h3 className="text-xs font-medium text-zinc-400 uppercase tracking-wide mb-2">
              Inference Config
            </h3>
            <div className="grid grid-cols-3 gap-2 text-xs">
              {[
                { key: "kronos.sample_count", label: "Samples", default: "30" },
                { key: "kronos.temperature", label: "Temperature", default: "0.8" },
                { key: "kronos.context_length", label: "Context", default: "512" },
              ].map((c) => (
                <div key={c.key} className="bg-bp-surface-2 rounded-lg px-3 py-2 border border-bp-border">
                  <p className="text-zinc-500">{c.label}</p>
                  <p className="text-zinc-200 font-mono mt-0.5">{c.default}</p>
                </div>
              ))}
            </div>
          </section>

          {/* Manual triggers */}
          <section>
            <h3 className="text-xs font-medium text-zinc-400 uppercase tracking-wide mb-2">
              Manual Triggers — {timeframe}
            </h3>

            {confirmBacktest && (
              <div className="mb-3 rounded-lg border border-amber-500/30 bg-amber-950/20 px-3 py-2.5 text-xs text-amber-300">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                  <div>
                    <p className="font-medium">Estimated duration: {BACKTEST_EST[timeframe]}</p>
                    <p className="text-amber-500 mt-0.5">
                      Runs in the background queue. Click again to confirm.
                    </p>
                  </div>
                </div>
              </div>
            )}

            <div className="flex gap-2">
              <Button
                size="sm"
                variant="secondary"
                className="border-cyan-500/30 text-cyan-400 hover:bg-cyan-950/30 gap-1.5 flex-1"
                onClick={() => { trigger.mutate(timeframe); setOpen(false); }}
                disabled={trigger.isPending}
              >
                <Play className="w-3 h-3" />
                Run Prediction
              </Button>
              <Button
                size="sm"
                variant="secondary"
                className={cn(
                  "gap-1.5 flex-1",
                  confirmBacktest
                    ? "border-amber-500/40 text-amber-400 hover:bg-amber-950/30"
                    : "border-zinc-700 text-zinc-400 hover:bg-bp-surface-2",
                )}
                onClick={handleRunBacktest}
                disabled={triggerBacktest.isPending}
              >
                <FlaskConical className="w-3 h-3" />
                {confirmBacktest ? "Confirm Backtest" : "Run Backtest"}
              </Button>
            </div>
          </section>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
