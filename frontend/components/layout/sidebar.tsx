"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Brain, LayoutDashboard, FlaskConical, Zap } from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/", label: "Home", icon: LayoutDashboard, disabled: false },
  { href: "/backtest", label: "Backtest", icon: FlaskConical, disabled: false },
  { href: "/rsi2", label: "RSI-2 Strategy", icon: Zap, disabled: true },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-[260px] shrink-0 border-r border-[#27272a] flex flex-col h-screen sticky top-0" style={{ background: "#0A0A0B" }}>
      <div className="p-5 border-b border-[#27272a]">
        <div className="flex items-center gap-2.5">
          <div className="h-9 w-9 rounded-xl bg-cyan-500/10 border border-cyan-500/25 flex items-center justify-center"
               style={{ boxShadow: "0 0 12px rgba(6,182,212,0.15)" }}>
            <Brain className="h-5 w-5 text-cyan-400" />
          </div>
          <div>
            <div className="text-[15px] font-bold text-zinc-100 leading-tight tracking-tight">
              <span className="text-cyan-400">BTC</span> PREDICT
            </div>
            <div className="text-[10px] text-zinc-500 uppercase tracking-widest">
              Powered by Kronos
            </div>
          </div>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto p-3 space-y-0.5">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive =
            !item.disabled &&
            (pathname === item.href ||
              (item.href !== "/" && pathname.startsWith(item.href)));

          if (item.disabled) {
            return (
              <div
                key={item.href}
                className="flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium border border-transparent cursor-not-allowed select-none text-zinc-700"
              >
                <Icon className="h-4 w-4 shrink-0" />
                <span>{item.label}</span>
              </div>
            );
          }

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium transition-all duration-150",
                isActive
                  ? "text-blue-400 border border-blue-500/25"
                  : "text-zinc-400 hover:text-zinc-100 hover:bg-white/[0.04] border border-transparent",
              )}
              style={isActive ? { background: "rgba(59,130,246,0.15)" } : undefined}
            >
              <Icon className="h-4 w-4 shrink-0" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
