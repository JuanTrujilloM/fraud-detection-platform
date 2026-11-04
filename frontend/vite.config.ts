import { fileURLToPath, URL } from 'node:url';

import vue from '@vitejs/plugin-vue';
import { defineConfig } from 'vite';

const destino = process.env.VITE_PROXY_TARGET ?? 'http://localhost:8000';
// xfwd agrega X-Forwarded-For: el backend corre con NUM_PROXIES=1 en local.
const proxy = { target: destino, xfwd: true };

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    host: true,
    port: 5173,
    proxy: { '/api': proxy, '/admin': proxy, '/static': proxy },
  },
});
