/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
      colors: {
        brand: {
          50:  '#eff6ff',
          100: '#dbeafe',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
        },
        violet: {
          50:  '#f5f3ff',
          100: '#ede9fe',
          500: '#8b5cf6',
          600: '#7c3aed',
          700: '#6d28d9',
        },
      },
      boxShadow: {
        'sm':  '0 1px 3px rgba(0,0,0,.06), 0 1px 2px rgba(0,0,0,.04)',
        'md':  '0 4px 16px rgba(0,0,0,.08), 0 2px 6px rgba(0,0,0,.05)',
        'lg':  '0 20px 40px rgba(0,0,0,.10), 0 8px 16px rgba(0,0,0,.06)',
        'brand': '0 4px 14px rgba(37,99,235,.4)',
      },
      borderRadius: {
        'xl':  '12px',
        '2xl': '16px',
        '3xl': '20px',
      },
      animation: {
        'fade-up':  'fadeUp .4s ease both',
        'fade-in':  'fadeIn .3s ease both',
        'scale-in': 'scaleIn .25s ease both',
      },
      keyframes: {
        fadeUp:  { from: { opacity: '0', transform: 'translateY(16px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
        fadeIn:  { from: { opacity: '0' }, to: { opacity: '1' } },
        scaleIn: { from: { opacity: '0', transform: 'scale(.95)' }, to: { opacity: '1', transform: 'scale(1)' } },
      },
      backgroundImage: {
        'gradient-brand': 'linear-gradient(135deg, #2563eb, #7c3aed)',
        'gradient-dark':  'linear-gradient(180deg, #0f172a 0%, #1e1b4b 100%)',
      },
    },
  },
  plugins: [],
}
