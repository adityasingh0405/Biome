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
        dark: {
          950: '#04060A',
          900: '#080C14',
          850: '#0C121E',
          800: '#111927',
          750: '#172235',
          700: '#1E2D44',
        },
        biome: {
          emerald: '#10B981',
          neon: '#00FF87',
          mint: '#34D399',
          darkgreen: '#064E3B',
          glow: 'rgba(16, 185, 129, 0.15)',
          border: 'rgba(16, 185, 129, 0.25)',
        }
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      boxShadow: {
        'green-glow': '0 0 25px -5px rgba(16, 185, 129, 0.25)',
        'green-glow-lg': '0 0 50px -10px rgba(16, 185, 129, 0.35)',
        'glass-card': '0 8px 32px 0 rgba(0, 0, 0, 0.45)',
      },
      animation: {
        'pulse-subtle': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'float': 'float 6s ease-in-out infinite',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-8px)' },
        }
      }
    },
  },
  plugins: [],
}
