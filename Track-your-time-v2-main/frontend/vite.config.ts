import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
import path from 'path'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      // injectManifest, NOT generateSW: we have a hand-written service worker
      // (push handling, notification action buttons, IndexedDB auth) that must
      // be preserved verbatim. This strategy compiles src/sw.ts through Vite —
      // which is also what lets it read VITE_API_URL instead of hardcoding a
      // backend hostname the way the old public/sw.js had to.
      strategies: 'injectManifest',
      srcDir: 'src',
      filename: 'sw.ts',
      // Output stays at /sw.js, so lib/sw-registration.ts needs no change.
      registerType: 'prompt',
      injectRegister: null,
      injectManifest: {
        globPatterns: ['**/*.{js,css,html,svg,png,ico,woff2}'],
        maximumFileSizeToCacheInBytes: 3_000_000,
      },
      devOptions: {
        enabled: true,
        type: 'module',
        navigateFallback: 'index.html',
      },
      manifest: {
        id: '/',
        name: 'SmartRemind',
        short_name: 'SmartRemind',
        description: 'Reminders that actually reach you.',
        start_url: '/?source=pwa',
        scope: '/',
        display: 'standalone',
        display_override: ['standalone', 'minimal-ui'],
        orientation: 'portrait',
        // Matches the app background so the status bar and splash read as one
        // surface. The purple lives in the icon, not the chrome.
        background_color: '#0a0a0f',
        theme_color: '#0a0a0f',
        lang: 'en',
        dir: 'ltr',
        categories: ['productivity', 'utilities'],
        icons: [
          { src: '/icons/pwa-64.png', sizes: '64x64', type: 'image/png' },
          { src: '/icons/pwa-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icons/pwa-512.png', sizes: '512x512', type: 'image/png' },
          { src: '/icons/maskable-192.png', sizes: '192x192', type: 'image/png', purpose: 'maskable' },
          { src: '/icons/maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
          { src: '/icons/icon.svg', sizes: 'any', type: 'image/svg+xml' },
        ],
        shortcuts: [
          { name: 'New reminder', short_name: 'New', url: '/?new=1' },
          { name: "Today's summary", short_name: 'Summary', url: '/summary' },
        ],
      },
    }),
  ],
  build: {
    rollupOptions: {
      input: 'index.html',
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  // Dev server only — `vite build` ignores this block entirely, so it has no
  // effect on the Vercel deployment.
  //
  // Bind IPv4 explicitly: Vite's default binds `localhost`, which on Windows
  // resolves to IPv6 ::1 first — the same fallback that cost ~205ms per request
  // against the API (see VITE_API_URL in .env.local). Keeping the whole local
  // loop on one stack avoids it.
  //
  // Set VITE_DEV_HOST=0.0.0.0 to expose the dev server on your LAN (e.g. to
  // test the PWA on a real phone), which 127.0.0.1 otherwise blocks.
  server: {
    port: 5173,
    host: process.env.VITE_DEV_HOST || '127.0.0.1',
  },
})
