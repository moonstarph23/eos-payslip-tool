/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Primary Accent - Deep Purple (EOS Brand)
        'primary': '#430045',
        'primary-container': '#5e1a5e',
        'primary-fixed': '#ffd7f7',
        'primary-fixed-dim': '#ffaaf6',
        'on-primary': '#ffffff',
        'on-primary-container': '#d685cf',
        'on-primary-fixed': '#380039',
        'on-primary-fixed-variant': '#6f2b6e',
        
        // Secondary
        'secondary': '#5d5c74',
        'secondary-container': '#e2e0fc',
        'secondary-fixed': '#e2e0fc',
        'secondary-fixed-dim': '#c6c4df',
        'on-secondary': '#ffffff',
        'on-secondary-container': '#63627a',
        'on-secondary-fixed': '#1a1a2e',
        'on-secondary-fixed-variant': '#45455b',
        
        // Surfaces
        'surface': '#fff7f9',
        'surface-dim': '#e3d7dd',
        'surface-bright': '#fff7f9',
        'surface-variant': '#ecdfe6',
        'surface-card': '#FFFFFF',
        'canvas': '#F5F5F7',
        'surface-container': '#f7eaf1',
        'surface-container-low': '#fdf0f7',
        'surface-container-lowest': '#ffffff',
        'surface-container-high': '#f1e5eb',
        'surface-container-highest': '#ecdfe6',
        'surface-tint': '#8b4388',
        
        // Dark surfaces
        'on-secondary-fixed': '#1a1a2e',
        'on-secondary-fixed-variant': '#45455b',
        
        // Text
        'text-primary': '#1E1E2E',
        'text-secondary': '#6B7280',
        'text-muted': '#9CA3AF',
        'on-surface': '#201a1e',
        'on-surface-variant': '#50434d',
        'on-background': '#201a1e',
        
        // Semantic
        'success': '#10B981',
        'warning': '#F59E0B',
        'error': '#EF4444',
        'error-container': '#ffdad6',
        'on-error': '#ffffff',
        'on-error-container': '#93000a',
        
        // Borders
        'border-light': '#E5E7EB',
        'outline': '#81737d',
        'outline-variant': '#d3c2cd',
        
        // Inverse
        'inverse-primary': '#ffaaf6',
        'inverse-surface': '#352e33',
        'inverse-on-surface': '#faedf4',
      },
      fontFamily: {
        'geist': ['Geist', 'sans-serif'],
        'mono': ['JetBrains Mono', 'monospace'],
        'headline': ['Geist', 'sans-serif'],
        'body': ['Geist', 'sans-serif'],
        'label': ['Geist', 'sans-serif'],
      },
      fontSize: {
        'headline-lg': ['24px', { lineHeight: '32px', letterSpacing: '-0.02em', fontWeight: '700' }],
        'headline-md': ['20px', { lineHeight: '28px', letterSpacing: '-0.01em', fontWeight: '600' }],
        'headline-sm': ['16px', { lineHeight: '24px', fontWeight: '600' }],
        'body-md': ['14px', { lineHeight: '1.5', fontWeight: '400' }],
        'body-sm': ['13px', { lineHeight: '1.5', fontWeight: '400' }],
        'label-md': ['14px', { lineHeight: '20px', fontWeight: '500' }],
        'mono-sm': ['13px', { lineHeight: '20px', fontWeight: '400' }],
      },
      spacing: {
        'sidebar-width': '280px',
        'max-content-width': '1200px',
        'gutter': '32px',
        'card-padding': '24px',
        'element-gap': '16px',
        'log-panel-height': '200px',
      },
      borderRadius: {
        'card': '16px',
        'input': '8px',
        'button': '8px',
      },
      boxShadow: {
        'card': '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
        'card-hover': '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
        'premium': '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
      },
      animation: {
        'shimmer': 'shimmer 2s infinite',
        'fade-in': 'fadeIn 0.2s ease-out',
        'slide-up': 'slideUp 0.3s ease-out',
      },
      keyframes: {
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
}
