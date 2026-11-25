import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        railway: {
          950: "#060a12",
          900: "#0b1120",
          850: "#0f172a",
          800: "#1e293b",
          700: "#334155",
          600: "#475569",
        },
        ink: { 0: "var(--ink-0)", 1: "var(--ink-1)", 2: "var(--ink-2)" },
        fg: { 1: "var(--fg-1)", 2: "var(--fg-2)", 3: "var(--fg-3)" },
        line: { DEFAULT: "var(--line)", strong: "var(--line-strong)" },
        champagne: "var(--champagne)",
        bronze: "var(--bronze)",
        violet: "var(--violet)",
        indigo: "var(--indigo)",
        magenta: "var(--magenta)",
        clear: "var(--clear)",
        caution: "var(--caution)",
        conflict: "var(--conflict)",
        info: "var(--info)",
        signal: {
          green: "#10b981",
          amber: "#f59e0b",
          red: "#ef4444",
          blue: "#3b82f6",
          cyan: "#06b6d4",
          purple: "#8b5cf6",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        mono: [
          "var(--font-mono)",
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Monaco",
          "Consolas",
          "Liberation Mono",
          "Courier New",
          "monospace",
        ],
      },
    },
  },
  plugins: [],
};

export default config;
