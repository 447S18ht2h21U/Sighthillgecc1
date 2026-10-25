import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  root: process.cwd(),
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    strictPort: true,
    proxy: {},
  },
});
