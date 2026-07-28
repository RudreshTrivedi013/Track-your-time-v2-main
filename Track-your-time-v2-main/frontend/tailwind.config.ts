import type { Config } from 'tailwindcss'
import animate from 'tailwindcss-animate'

/**
 * Near-monochrome dark theme.
 *
 * The primary action colour is WHITE. Hue is reserved for meaning only —
 * green = done, amber = snoozed, red = overdue/destructive. There is no brand
 * indigo or cyan in the UI any more; the purple bolt app icon is the only
 * saturated colour in the product, and it lives on the home screen, not here.
 *
 * The `--foo` variables are declared in src/index.css and consumed by the
 * shadcn/ui components; the named colours below are the same palette kept
 * available to plain Tailwind markup.
 */
const config: Config = {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // ── shadcn/ui token surface ──
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))',
        },
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',

        // ── App-specific names, unchanged values ──
        bg: {
          DEFAULT: '#0a0a0f',
          surface: '#111118',
          elevated: '#1a1a24',
        },
        border: { DEFAULT: '#2a2a3a', subtle: '#1e1e2e' },

        // Status colours — the ONLY hues in the app.
        success: '#10b981',
        warning: '#f59e0b',
        danger: '#ef4444',

        text: {
          primary: '#f1f5f9',
          secondary: '#94a3b8',
          muted: '#475569',
        },
      },
      borderRadius: {
        xl: 'calc(var(--radius) + 4px)',
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      keyframes: {
        fadeIn: { '0%': { opacity: '0' }, '100%': { opacity: '1' } },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        'fade-in': 'fadeIn 0.2s ease-out',
        'slide-up': 'slideUp 0.2s ease-out',
      },
    },
  },
  plugins: [animate],
}

export default config
