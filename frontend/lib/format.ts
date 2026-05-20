import { format, formatDistanceToNow, parseISO } from "date-fns";
import { ptBR } from "date-fns/locale";

export function formatUSD(value: number, decimals = 0): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

export function formatBRL(value: number, decimals = 0): string {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

export function formatPercent(value: number, decimals = 2): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(decimals)}%`;
}

export function formatNumber(value: number, decimals = 2): string {
  if (Math.abs(value) >= 1_000_000_000) {
    return `${(value / 1_000_000_000).toFixed(decimals)}B`;
  }
  if (Math.abs(value) >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(decimals)}M`;
  }
  if (Math.abs(value) >= 1_000) {
    return `${(value / 1_000).toFixed(decimals)}K`;
  }
  return value.toFixed(decimals);
}

export function formatDateTime(dateStr: string | Date): string {
  const date = typeof dateStr === "string" ? parseISO(dateStr) : dateStr;
  return format(date, "dd/MM/yyyy HH:mm", { locale: ptBR });
}

export function formatDate(dateStr: string | Date): string {
  const date = typeof dateStr === "string" ? parseISO(dateStr) : dateStr;
  return format(date, "dd/MM/yyyy", { locale: ptBR });
}

export function formatTimeAgo(dateStr: string | Date): string {
  const date = typeof dateStr === "string" ? parseISO(dateStr) : dateStr;
  return formatDistanceToNow(date, { addSuffix: true, locale: ptBR });
}

export function formatConfidence(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}
