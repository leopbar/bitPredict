import { Rsi2SignalCard } from "./components/rsi2-signal-card";
import { Rsi2TradesTable } from "./components/rsi2-trades-table";
import { Rsi2EquityCurve } from "./components/rsi2-equity-curve";
import { Rsi2ManagementPanel } from "./components/rsi2-management-panel";
import { Rsi2DataInfo } from "./components/rsi2-data-info";

export default function Rsi2Page() {
  return (
    <div className="flex flex-col gap-6 p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-zinc-100 tracking-tight">
          Estratégia <span className="text-cyan-400">RSI-2</span>
        </h1>
        <p className="text-sm text-zinc-500 mt-1">
          Mean reversion em BTC Spot 15min · Long e Short · Sinal a cada 15 minutos
        </p>
      </div>

      {/* Main grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Signal card — full width on mobile, 1/3 on desktop */}
        <div className="lg:col-span-1">
          <Rsi2SignalCard />
        </div>

        {/* Backtesting metrics */}
        <div
          className="lg:col-span-2 rounded-2xl p-5 border border-zinc-800"
          style={{ background: "#0d0d0f" }}
        >
          <h2 className="text-sm font-semibold text-zinc-300 mb-4 uppercase tracking-widest">
            Resultados (Teste Lacrado)
          </h2>
          <Rsi2EquityCurve />
        </div>
      </div>

      {/* Management panel */}
      <div
        className="rounded-2xl p-5 border border-zinc-800"
        style={{ background: "#0d0d0f" }}
      >
        <h2 className="text-sm font-semibold text-zinc-300 mb-4 uppercase tracking-widest">
          Gerenciamento da Estratégia
        </h2>
        <p className="text-xs text-zinc-500 mb-4">
          Execute as etapas na ordem: ingestão → otimização → treino ML → seleção → teste lacrado.
        </p>
        {/* Dataset status */}
        <div className="mb-4">
          <Rsi2DataInfo />
        </div>
        <Rsi2ManagementPanel />
      </div>

      {/* Trades table */}
      <div
        className="rounded-2xl p-5 border border-zinc-800"
        style={{ background: "#0d0d0f" }}
      >
        <h2 className="text-sm font-semibold text-zinc-300 mb-4 uppercase tracking-widest">
          Histórico de Trades
        </h2>
        <Rsi2TradesTable />
      </div>
    </div>
  );
}
