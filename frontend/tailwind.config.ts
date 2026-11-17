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
        mono: [
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
