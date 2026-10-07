import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': {
    target: 'http://127.0.0.1:8765',
    // 本地开发请求通过同源 Vite 代理，后端仍只接受自己的 Origin。
    headers: { Origin: 'http://127.0.0.1:8765' },
  } } },
})
