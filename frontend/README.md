# bitPredict — Frontend

Next.js 15 dashboard for the bitPredict Kronos forecasting system.

## Stack

- **Next.js 15** (App Router) + **React 19**
- **TypeScript 5**
- **Tailwind CSS 4** — dark theme, OKLCH zinc palette
- **shadcn/ui** — Card, Badge, Button, Skeleton, Dialog primitives
- **TanStack Query v5** — data fetching with polling
- **lightweight-charts v4** — candlestick chart with predicted candle overlay
- **Zod** — API response validation
- **date-fns** — date formatting

## Pages

| Route | Description |
|---|---|
| `/` | Kronos multi-timeframe BTC forecast dashboard |
| `/rsi2` | RSI-2 mean-reversion strategy dashboard |

## Key components

| Component | Description |
|---|---|
| `kronos/kronos-chart.tsx` | Candlestick chart with real candles + predicted candle (Q10/Q90 wicks) |
| `kronos/kpi-cards.tsx` | Direction (with hist. accuracy badge), % Bullish, Price Target, Candle Range |
| `kronos/scoreboard-card.tsx` | Historical directional accuracy, avg/best/worst error |
| `kronos/history-table.tsx` | Paginated prediction history with direction ✓/✗ and color-coded error |
| `kronos/pipeline-progress-card.tsx` | Live inference progress bar with Stop button |
| `kronos/advanced-settings-dialog.tsx` | Manual prediction/backtest triggers with duration warning |

## Local development

```bash
cd frontend
npm install
npm run dev      # http://localhost:3000
npm run build    # production build
npm run lint
```

Build artifacts (`node_modules`, `.next`) are stored in named Docker volumes to avoid OneDrive sync issues.
