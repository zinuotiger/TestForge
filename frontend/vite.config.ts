import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    // 启用HTTPS开发服务器
    https: {
      key: '../ssl/key.pem',
      cert: '../ssl/cert.pem',
    },
    proxy: {
      "/api": {
        target: "https://localhost:9876",
        secure: false, // 自签名证书需要设置为false
        changeOrigin: true,
      },
      "/ws": {
        target: "wss://localhost:9876",
        ws: true,
        secure: false, // 自签名证书需要设置为false
        changeOrigin: true,
      },
    },
  },
});
