export const colors = {
  background: "#0a0a0f",
  surface: "#111118",
  surface2: "#18181f",
  border: "#27272e",
  textPrimary: "#f4f4f5",
  textSecondary: "#a1a1aa",

  emerald: "#34d399",
  coral: "#fb7185",
  amber: "#fbbf24",
  cobalt: "#60a5fa",
  cyan: "#22d3ee",

  chart: {
    historical: "#34d399",
    forecast: "#22d3ee",
    band: "rgba(34, 211, 238, 0.12)",
    grid: "#27272e",
    crosshair: "#52525b",
    up: "#34d399",
    down: "#fb7185",
  },
} as const;

export type Colors = typeof colors;
