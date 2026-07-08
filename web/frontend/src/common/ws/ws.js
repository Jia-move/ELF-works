import * as WsConfig from '@/common/ws/ws-config.js'

export function buildWsUrl(path = '') {
  const base = (WsConfig.WS_BASE_URL || '').trim()
  const root = (WsConfig.WS_ROOT || '').trim()
  const scheme = location.protocol === 'https:' ? 'wss' : 'ws'
  if (base) {
    return `${base}${root}${path}`
  } else {
    return `${scheme}://${location.host}${root}${path}`
  }
}

/**
 * 创建支持自动重连的 WebSocket 连接
 *
 * @param {string}   options.path              - WebSocket 路径
 * @param {function} options.onJsonMessage     - 收到 JSON 消息时的回调
 * @param {function} options.onOpen            - 连接成功回调
 * @param {function} options.onError           - 错误回调
 * @param {function} options.onClose           - 关闭回调
 * @param {function} options.onStatusMessage   - 状态消息回调
 * @param {object}   options.reconnect         - 重连配置 { enabled, maxDelay }
 * @returns {{ close: function }}  - 返回可调用 close() 来主动关闭并停止重连
 */
export function createWebSocket({
  path = '',
  onJsonMessage,
  onOpen,
  onError,
  onClose,
  onStatusMessage,
  reconnect = { enabled: true, maxDelay: 15000 },
}) {
  let ws = null
  let reconnectTimer = null
  let reconnectDelay = 1000 // 初始 1 秒
  let closedByUser = false
  const maxDelay = reconnect.maxDelay || 15000

  function connect() {
    if (closedByUser) return

    const url = buildWsUrl(path)
    ws = new WebSocket(url)
    ws.binaryType = 'blob'

    ws.addEventListener('open', () => {
      // 连接成功，重置重连延迟
      reconnectDelay = 1000
      if (onStatusMessage) onStatusMessage({ kind: 'connected' })
      if (onOpen) onOpen(ws)
    })

    ws.addEventListener('message', async (evt) => {
      let text = ''
      if (typeof evt.data === 'string') {
        text = evt.data
      } else if (evt.data && typeof evt.data.text === 'function') {
        text = await evt.data.text()
      } else {
        text = String(evt.data || '')
      }
      const t = text ? text.trim() : ''
      if (!t) return
      const lower = t.toLowerCase()
      if (lower === 'connected') {
        if (onStatusMessage) onStatusMessage({ kind: 'connected', text: t })
        return
      }
      if (t.startsWith('error')) {
        if (onStatusMessage) onStatusMessage({ kind: 'error', text: t })
        return
      }
      try {
        const msg = JSON.parse(t)
        if (onJsonMessage) onJsonMessage(msg)
      } catch (e) {
        if (onStatusMessage) onStatusMessage({ kind: 'text', text: t })
      }
    })

    ws.addEventListener('error', (e) => {
      console.error('WS error:', e)
      if (onError) onError(e)
    })

    ws.addEventListener('close', () => {
      if (onClose) onClose()
      if (!closedByUser && reconnect.enabled) {
        scheduleReconnect()
      }
    })
  }

  function scheduleReconnect() {
    if (reconnectTimer) clearTimeout(reconnectTimer)
    if (onStatusMessage) {
      onStatusMessage({ kind: 'reconnecting', delay: reconnectDelay })
    }
    reconnectTimer = setTimeout(() => {
      connect()
      // 指数退避：1s, 2s, 4s, 8s, 15s (上限)
      reconnectDelay = Math.min(reconnectDelay * 2, maxDelay)
    }, reconnectDelay)
  }

  connect()

  return {
    close() {
      closedByUser = true
      if (reconnectTimer) {
        clearTimeout(reconnectTimer)
        reconnectTimer = null
      }
      if (ws) {
        ws.close()
        ws = null
      }
    },
  }
}
