/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./finbot/**/*.{html,js,py}",
    "./finbot/apps/**/*.{html,js}",
    "./finbot/templates/**/*.{html,js}",
    "./finbot/static/**/*.{html,js}",
  ],
  theme: {
    extend: {
      colors: {
        // CineFlow branding colors
        'cine-gold': '#D4AF37',
        'cine-dark': '#0F0F0F',
        'cine-gray': '#1A1A1A',
        'cine-light': '#F8F8F8',
        
        // CTF colors
        'ctf-green': '#10B981',
        'ctf-dark': '#111827',
        'ctf-gray': '#374151',
        
        // Admin portal colors
        'admin-primary': '#f59e0b',
        'admin-secondary': '#d97706',
        'admin-accent': '#fbbf24',
        'admin-danger': '#ef4444',
        'admin-success': '#22c55e',
        
        // Vendor portal colors
        'vendor-primary': '#00d4ff',
        'vendor-secondary': '#7c3aed',
        'vendor-accent': '#06ffa5',
        'vendor-warning': '#ffb800',
        'vendor-danger': '#ff3366',
        
        // Portal background colors
        'portal-bg-primary': '#0a0a0f',
        'portal-bg-secondary': '#151520',
        'portal-bg-tertiary': '#1a1a2e',
        
        // Text colors
        'text-primary': '#e2e8f0',
        'text-secondary': '#94a3b8',
        'text-bright': '#ffffff',
      },
      fontFamily: {
        'display': ['Playfair Display', 'serif'],
        'sans': ['Inter', 'system-ui', 'sans-serif'],
      },
      animation: {
        'fade-in': 'fadeIn 0.5s ease-in-out',
        'slide-up': 'slideUp 0.6s ease-out',
        'glow': 'glow 2s ease-in-out infinite alternate',
        
        // Error page animations
        'float': 'float 6s ease-in-out infinite',
        'pulse-slow': 'pulse 3s infinite',
        'bounce-slow': 'bounce 2s infinite',
        'wiggle': 'wiggle 1s ease-in-out infinite',
        'shake': 'shake 0.5s ease-in-out infinite',
        'spin-slow': 'spin 3s linear infinite',
        'glitch': 'glitch 2s infinite',
        'flicker': 'flicker 1.5s infinite',
        'sleep': 'sleep 3s ease-in-out infinite',
        'snore': 'snore 2s ease-in-out infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(20px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        glow: {
          '0%': { boxShadow: '0 0 5px rgba(212, 175, 55, 0.5)' },
          '100%': { boxShadow: '0 0 20px rgba(212, 175, 55, 1)' },
        },
        
        // Error page keyframes
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-20px)' },
        },
        wiggle: {
          '0%, 100%': { transform: 'rotate(-3deg)' },
          '50%': { transform: 'rotate(3deg)' },
        },
        shake: {
          '0%, 100%': { transform: 'translateX(0)' },
          '10%, 30%, 50%, 70%, 90%': { transform: 'translateX(-2px)' },
          '20%, 40%, 60%, 80%': { transform: 'translateX(2px)' },
        },
        glitch: {
          '0%, 100%': { transform: 'translate(0)' },
          '20%': { transform: 'translate(-2px, 2px)' },
          '40%': { transform: 'translate(-2px, -2px)' },
          '60%': { transform: 'translate(2px, 2px)' },
          '80%': { transform: 'translate(2px, -2px)' },
        },
        flicker: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.3' },
        },
        sleep: {
          '0%, 100%': { transform: 'rotate(-2deg)' },
          '50%': { transform: 'rotate(2deg)' },
        },
        snore: {
          '0%, 100%': { opacity: '0.3', transform: 'scale(0.8)' },
          '50%': { opacity: '1', transform: 'scale(1.2)' },
        },
      },
      zIndex: {
        '60': '60',
        '70': '70',
      },
    },
  },
  plugins: [],
}
