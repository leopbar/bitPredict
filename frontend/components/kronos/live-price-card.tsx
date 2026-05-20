"use client";

import { TrendingUp, TrendingDown } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatUSD, formatPercent } from "@/lib/format";
import { useTicker } from "@/lib/hooks/use-klines";

export function LivePriceCard() {
  const { data: ticker, isLoading } = useTicker();

  return (
    <Card className="bg-bp-surface border-bp-border" title="Live BTC/USDT price from Binance, refreshed every 5 seconds">
      <CardHeader className="pb-1 pt-3 px-4">
        <CardTitle className="text-xs font-medium text-zinc-400 uppercase tracking-wide">
          BTC / USDT
        </CardTitle>
      </CardHeader>
      <CardContent className="px-4 pb-3">
        {isLoading ? (
          <Skeleton className="h-8 w-36 mt-1" />
        ) : !ticker ? (
          <p className="text-sm text-zinc-500 mt-1">Unavailable</p>
        ) : (
          <div className="mt-1">
            <p className="text-lg font-bold text-zinc-100 font-mono">
              {formatUSD(ticker.price)}
            </p>
            <div className={`flex items-center gap-1 mt-0.5 text-xs ${ticker.price_change_pct_24h >= 0 ? "text-emerald-400" : "text-red-400"}`}>
              {ticker.price_change_pct_24h >= 0 ? (
                <TrendingUp className="w-3 h-3" />
              ) : (
                <TrendingDown className="w-3 h-3" />
              )}
              <span>{formatPercent(ticker.price_change_pct_24h)}</span>
              <span className="text-zinc-600">24h</span>
            </div>
            <div className="mt-1.5 grid grid-cols-2 gap-x-2 text-[10px] text-zinc-500">
              <span title="24h high">H {formatUSD(ticker.high_24h)}</span>
              <span title="24h low">L {formatUSD(ticker.low_24h)}</span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
