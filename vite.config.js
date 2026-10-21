import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => ({
  plugins: [react()],
  // Synthetic builds must never copy the local, rights-pending public/data.
  publicDir: mode === 'demo' ? 'demo/public' : 'public',
  build: { outDir: mode === 'demo' ? 'dist-demo' : 'dist' },
}))
