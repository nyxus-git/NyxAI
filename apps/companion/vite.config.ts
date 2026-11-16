import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 19421,
    host: '127.0.0.1',
    proxy: {
      '/chat': {
        target: 'http://127.0.0.1:19420',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://127.0.0.1:19420',
        changeOrigin: true,
      },
      '/memory': {
        target: 'http://127.0.0.1:19420',
        changeOrigin: true,
      },
      '/avatar': {
        target: 'http://127.0.0.1:19420',
        changeOrigin: true,
      },
      '/voice': {
        target: 'ws://127.0.0.1:19420',
        ws: true,
      },
    },
  },
  preview: {
    port: 19421,
    host: '127.0.0.1',
  },
});
