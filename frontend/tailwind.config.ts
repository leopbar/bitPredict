import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./pages/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./app/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Design system exact values
        "bp-base": "#0A0A0B",
        "bp-surface": "#131316",
        "bp-surface-2": "#1C1C20",
        "bp-border": "#27272A",
        "bp-border-strong": "#3F3F46",
        // Legacy oklch tokens
        background: "oklch(var(--background) / <alpha-value>)",
        surface: "oklch(var(--surface) / <alpha-value>)",
        "surface-2": "oklch(var(--surface-2) / <alpha-value>)",
        border: "oklch(var(--border) / <alpha-value>)",
        "text-primary": "oklch(var(--text-primary) / <alpha-value>)",
        "text-secondary": "oklch(var(--text-secondary) / <alpha-value>)",
        emerald: {
          DEFAULT: "#34d399",
          400: "#34d399",
          500: "#10b981",
        },
        coral: {
          DEFAULT: "#fb7185",
          400: "#fb7185",
          500: "#f43f5e",
        },
        amber: {
          DEFAULT: "#fbbf24",
          400: "#fbbf24",
          500: "#f59e0b",
        },
        cobalt: {
          DEFAULT: "#60a5fa",
          400: "#60a5fa",
          500: "#3b82f6",
        },
        cyan: {
          DEFAULT: "#22d3ee",
          400: "#22d3ee",
          500: "#06b6d4",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "Inter", "system-ui", "sans-serif"],
        mono: ["ui-monospace", "monospace"],
      },
      keyframes: {
        "pulse-slow": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.5" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
      },
      animation: {
        "pulse-slow": "pulse-slow 3s ease-in-out infinite",
        shimmer: "shimmer 1.5s infinite",
      },
      boxShadow: {
        card: "0 0 0 1px rgba(255,255,255,.03), 0 10px 30px rgba(0,0,0,.4)",
        "card-hover": "0 0 0 1px rgba(255,255,255,.05), 0 16px 40px rgba(0,0,0,.5)",
      },
    },
  },
  plugins: [],
};

export default config;
