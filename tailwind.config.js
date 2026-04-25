/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          '"Inter Tight"',
          'Inter',
          'ui-sans-serif',
          'system-ui',
          '-apple-system',
          'Segoe UI',
          'Roboto',
          'sans-serif',
        ],
        display: [
          '"Inter Tight"',
          'Inter',
          'ui-sans-serif',
          'system-ui',
          'sans-serif',
        ],
      },
      letterSpacing: {
        tightest: '-0.04em',
      },
      fontSize: {
        'display-xs': ['2.5rem', { lineHeight: '1.05', letterSpacing: '-0.03em' }],
        'display-sm': ['3.25rem', { lineHeight: '1', letterSpacing: '-0.035em' }],
        'display-md': ['4.5rem', { lineHeight: '0.98', letterSpacing: '-0.04em' }],
        'display-lg': ['6rem', { lineHeight: '0.96', letterSpacing: '-0.04em' }],
        'display-xl': ['7.5rem', { lineHeight: '0.94', letterSpacing: '-0.045em' }],
      },
      colors: {
        // Nimbus = cool atmospheric blue/slate, drawn from the spectreAI cloudscape.
        nimbus: {
          50:  '#f3f6fa',
          100: '#e6edf5',
          200: '#cbd8e6',
          300: '#a6bcd2',
          400: '#7c98b8',
          500: '#5b7a9d',
          600: '#456082',
          700: '#374d68',
          800: '#293a4f',
          900: '#1a2533',
          950: '#0d1420',
        },
        ink: {
          DEFAULT: '#0a0a0a',
          50:  '#f4f4f5',
          100: '#e4e4e7',
          200: '#c8c8cc',
          300: '#a1a1aa',
          400: '#71717a',
          500: '#52525b',
          600: '#3f3f46',
          700: '#27272a',
          800: '#18181b',
          900: '#111111',
          950: '#0a0a0a',
        },
        // Aliases — legacy purple/pink usages adopt the new palette automatically.
        // These will be removed as components are migrated to the nimbus tokens.
        purple: {
          50:  '#f3f6fa',
          100: '#e6edf5',
          200: '#cbd8e6',
          300: '#a6bcd2',
          400: '#7c98b8',
          500: '#5b7a9d',
          600: '#374d68',
          700: '#293a4f',
          800: '#1a2533',
          900: '#0d1420',
        },
        pink: {
          50:  '#f3f6fa',
          100: '#e6edf5',
          200: '#cbd8e6',
          300: '#a6bcd2',
          400: '#7c98b8',
          500: '#5b7a9d',
          600: '#374d68',
        },
      },
      backdropBlur: {
        xs: '2px',
      },
      animation: {
        drift: 'drift 18s ease-in-out infinite',
        'drift-slow': 'drift 28s ease-in-out infinite',
      },
      keyframes: {
        drift: {
          '0%, 100%': { transform: 'translate3d(0, 0, 0) scale(1)' },
          '50%': { transform: 'translate3d(20px, -16px, 0) scale(1.04)' },
        },
      },
      boxShadow: {
        pill: '0 1px 0 rgba(255,255,255,0.08) inset, 0 8px 24px -12px rgba(10,20,32,0.45)',
        card: '0 1px 0 rgba(255,255,255,0.55) inset, 0 8px 32px -16px rgba(13,20,32,0.25)',
      },
    },
  },
  plugins: [],
}
