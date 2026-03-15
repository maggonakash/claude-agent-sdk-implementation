/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'SF Mono', 'monospace'],
      },
      fontSize: {
        // Base scale bumped up ~10% from Tailwind defaults
        xs:   ['0.8rem',  { lineHeight: '1.1rem' }],
        sm:   ['0.925rem',{ lineHeight: '1.375rem' }],
        base: ['1.05rem', { lineHeight: '1.65rem' }],
        lg:   ['1.155rem',{ lineHeight: '1.815rem' }],
        xl:   ['1.265rem',{ lineHeight: '1.87rem' }],
        '2xl':['1.595rem',{ lineHeight: '2.2rem' }],
        '3xl':['1.98rem', { lineHeight: '2.42rem' }],
      },
      colors: {
        // TechChefz Digital brand palette
        tc: {
          bg:        '#1a1a1e',   // main dark background
          surface:   '#222228',   // card/panel surfaces
          border:    '#2e2e35',   // subtle borders
          blue:      '#00a8e8',   // primary cyan-blue accent
          'blue-dim':'#0077a8',   // darker blue for hover
          'blue-glow':'rgba(0,168,232,0.15)', // glow/ring
          green:     '#39e75f',   // secondary green accent (brand)
          text:      '#f0f0f0',   // primary text
          muted:     '#8a8a9a',   // muted text
          dim:       '#4a4a5a',   // very muted / disabled
        },
        sidebar: {
          bg:     '#111116',
          hover:  '#1c1c22',
          active: '#222228',
          border: '#2a2a33',
          text:   '#e8e8f0',
          muted:  '#5a5a6a',
        },
      },
      animation: {
        'fade-in':  'fadeIn 0.2s ease-out',
        'slide-up': 'slideUp 0.2s ease-out',
        'blink':    'blink 0.8s step-end infinite',
        'spin-slow':'spin 1s linear infinite',
        'pulse-dot':'pulseDot 1.4s ease-in-out infinite',
      },
      keyframes: {
        fadeIn: {
          from: { opacity: '0' },
          to:   { opacity: '1' },
        },
        slideUp: {
          from: { opacity: '0', transform: 'translateY(8px)' },
          to:   { opacity: '1', transform: 'translateY(0)' },
        },
        blink: {
          '50%': { opacity: '0' },
        },
        pulseDot: {
          '0%, 80%, 100%': { transform: 'scale(0.6)', opacity: '0.4' },
          '40%':           { transform: 'scale(1)',   opacity: '1'   },
        },
      },
    },
  },
  plugins: [],
}
