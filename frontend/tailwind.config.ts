import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        leaf: {
          50: "#f3f8f2",
          100: "#e4f0e1",
          200: "#c9dfc3",
          300: "#9fc598",
          400: "#6aa35f",
          500: "#3d7a3a",
          600: "#2f7d4a",
          700: "#24633b",
          800: "#1d4d2f",
          900: "#163824",
        },
        cream: {
          50: "#fffcf6",
          100: "#f7f3ea",
          200: "#efe8d6",
        },
      },
      boxShadow: {
        soft: "0 10px 30px rgba(36, 99, 59, 0.08)",
      },
    },
  },
  plugins: [],
};

export default config;
