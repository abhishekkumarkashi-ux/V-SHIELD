/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        shield: {
          900: '#070b14',
          850: '#0d1322',
          800: '#111a30',
          700: '#1a2747',
          600: '#253866',
        },
        crimson: {
          500: '#ef4444',
          600: '#dc2626',
          900: '#450a0a',
        },
        amber: {
          500: '#f59e0b',
          600: '#d97706',
          900: '#451a03',
        },
        emerald: {
          500: '#10b981',
          600: '#059669',
          900: '#064e3b',
        }
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'radar-sweep': 'sweep 4s linear infinite',
      },
      keyframes: {
        sweep: {
          '0%': { transform: 'rotate(0deg)' },
          '100%': { transform: 'rotate(360deg)' },
        }
      }
    },
  },
  plugins: [],
}
