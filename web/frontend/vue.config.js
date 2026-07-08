const { defineConfig } = require('@vue/cli-service')
module.exports = defineConfig({
  transpileDependencies: true,
  publicPath: '/',
  outputDir: 'dist',
  assetsDir: 'assets',
  devServer: {
    port: 8081,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      },
      '/ws/events': {
        target: 'ws://127.0.0.1:8000',
        ws: true,
        changeOrigin: true
      }
    },
    historyApiFallback: true
  }
})
