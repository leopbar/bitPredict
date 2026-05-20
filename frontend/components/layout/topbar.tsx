"use client";

import { useEffect, useState } from "react";
import { Menu } from "lucide-react";

interface TopbarProps {
  title?: string;
  subtitle?: string;
}

function useClientTime() {
  const [time, setTime] = useState<string | null>(null);

  useEffect(() => {
    function tick() {
      const now = new Date();
      setTime(
        `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}:${String(now.getSeconds()).padStart(2, "0")} UTC`,
      );
    }
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  return time;
}

export function Topbar({
  title = "bitPredict",
  subtitle = "BTC price forecasting powered by Kronos",
}: TopbarProps) {
  const lastUpdate = useClientTime();

  return (
    <header
      className="sticky top-0 z-30 backdrop-blur-md border-b border-[#27272a] px-6 py-3"
      style={{ background: "rgba(10,10,11,0.85)" }}
    >
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <button className="lg:hidden p-2 hover:bg-white/[0.04] rounded-xl text-zinc-400">
            <Menu className="h-5 w-5" />
          </button>
          <div>
            <h1 className="text-[20px] font-bold text-zinc-100 tracking-tight">{title}</h1>
            <p className="text-[12px] text-zinc-500">{subtitle}</p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="hidden md:flex items-center gap-2 text-xs">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-400" />
            </span>
            <div>
              <div className="text-zinc-300 font-medium">Online</div>
              <div className="text-zinc-500 text-[10px]" suppressHydrationWarning>
                {lastUpdate ?? "—"}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 pl-3 border-l border-[#27272a]">
            <div className="h-9 w-9 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center text-sm font-bold text-zinc-950">
              K
            </div>
            <div className="hidden md:block text-sm">
              <div className="text-zinc-100 font-medium">Analyst</div>
              <div className="text-[10px] text-zinc-500">Pro</div>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
