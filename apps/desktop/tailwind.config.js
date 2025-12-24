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
        // Westworld Lab palette
        ivory: {
          50: '#FEFEFE',
          100: '#FAFAF8',
          200: '#F5F5F0',
          300: '#EEEEE6',
          400: '#E5E5DC',
          500: '#DDDDD2',
        },
        forge: {
          dark: '#1A1A1A',
          darker: '#0D0D0D',
          light: '#F5F5F0',
          accent: '#2A2A2A',
          muted: '#6B6B6B',
          border: '#E0E0D8',
          'border-dark': '#333333',
        },
        viral: {
          high: '#10B981',    // Green
          medium: '#F59E0B',  // Amber
          low: '#6B7280',     // Gray
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['Space Grotesk', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Menlo', 'Monaco', 'monospace'],
      },
      fontSize: {
        '2xs': ['0.625rem', { lineHeight: '0.875rem' }],
      },
      spacing: {
        '18': '4.5rem',
        '88': '22rem',
        '128': '32rem',
      },
      animation: {
        'door-open': 'doorOpen 0.5s cubic-bezier(0.4, 0, 0.2, 1)',
        'door-close': 'doorClose 0.5s cubic-bezier(0.4, 0, 0.2, 1)',
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.4s cubic-bezier(0.4, 0, 0.2, 1)',
        'pulse-subtle': 'pulseSubtle 2s ease-in-out infinite',
      },
      keyframes: {
        doorOpen: {
          '0%': { transform: 'scaleX(0)', transformOrigin: 'left' },
          '100%': { transform: 'scaleX(1)', transformOrigin: 'left' },
        },
        doorClose: {
          '0%': { transform: 'scaleX(1)', transformOrigin: 'right' },
          '100%': { transform: 'scaleX(0)', transformOrigin: 'right' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        pulseSubtle: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.7' },
        },
      },
      boxShadow: {
        'panel': '0 1px 3px 0 rgba(0, 0, 0, 0.05)',
        'panel-hover': '0 4px 6px -1px rgba(0, 0, 0, 0.05)',
        'card': '0 1px 2px 0 rgba(0, 0, 0, 0.03)',
      },
      borderWidth: {
        'hairline': '0.5px',
      },
    },
  },
  plugins: [],
};


