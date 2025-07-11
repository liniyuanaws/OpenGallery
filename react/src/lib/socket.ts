import * as ISocket from '@/types/socket'
import { io, Socket } from 'socket.io-client'
import { eventBus } from './event'
import { getAccessToken, getUserProfile } from '@/api/auth'

export interface SocketConfig {
  serverUrl?: string
  autoConnect?: boolean
}

export class SocketIOManager {
  private socket: Socket | null = null
  private connected = false
  private reconnectAttempts = 0
  private maxReconnectAttempts = 10  // 增加重连次数
  private reconnectDelay = 3000      // 增加重连延迟

  // HTTP轮询相关
  private pollingEnabled = false
  private pollingInterval: number | null = null
  private pollingDelay = 2000  // 轮询间隔2秒
  private activeSessions = new Set<string>()  // 活跃的会话ID

  constructor(private config: SocketConfig = {}) {
    if (config.autoConnect !== false) {
      this.connect()
    }
  }

  connect(serverUrl?: string): Promise<boolean> {
    return new Promise(async (resolve, reject) => {
      const url = serverUrl || this.config.serverUrl

      if (this.socket) {
        this.socket.disconnect()
      }

      // Prepare authentication data
      const token = getAccessToken()
      let authData: any = {}

      if (token) {
        authData.token = token
        try {
          const userInfo = await getUserProfile()
          authData.user_info = userInfo
        } catch (error) {
          console.warn('Failed to get user profile for WebSocket auth:', error)
        }
      }

      this.socket = io(url, {
        transports: ['websocket'],
        upgrade: false,
        reconnection: true,
        reconnectionAttempts: this.maxReconnectAttempts,
        reconnectionDelay: this.reconnectDelay,
        reconnectionDelayMax: 10000,  // 最大重连延迟10秒
        timeout: 30000,               // 连接超时30秒
        forceNew: true,               // 强制创建新连接
        auth: authData,               // 添加身份验证数据
      })

      this.socket.on('connect', () => {
        console.log('✅ Socket.IO connected:', this.socket?.id)
        this.connected = true
        this.reconnectAttempts = 0
        resolve(true)
      })

      this.socket.on('connect_error', (error: any) => {
        console.error('❌ Socket.IO connection error:', error)
        this.connected = false
        this.reconnectAttempts++

        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
          console.log('🔄 WebSocket failed, starting HTTP polling fallback')
          this.startPolling()
          reject(
            new Error(
              `Failed to connect after ${this.maxReconnectAttempts} attempts`
            )
          )
        }
      })

      this.socket.on('disconnect', (reason: any) => {
        console.log('🔌 Socket.IO disconnected:', reason)
        this.connected = false
        // 如果WebSocket断开，启动轮询
        if (this.activeSessions.size > 0) {
          console.log('🔄 WebSocket disconnected, starting HTTP polling fallback')
          this.startPolling()
        }
      })

      this.registerEventHandlers()
    })
  }

  private registerEventHandlers() {
    if (!this.socket) return

    this.socket.on('connected', (data: any) => {
      console.log('🔗 Socket.IO connection confirmed:', data)
      // WebSocket连接成功，但保持轮询作为备用机制
      console.log('🔄 Keeping HTTP polling as backup mechanism')
    })

    this.socket.on('init_done', (data: any) => {
      console.log('🔗 Server initialization done:', data)
    })

    this.socket.on('session_update', (data: any) => {
      this.handleSessionUpdate(data)
    })

    this.socket.on('pong', (data: any) => {
      console.log('🔗 Pong received:', data)
    })
  }

  private handleSessionUpdate(data: ISocket.SessionUpdateEvent) {
    const { session_id, type } = data

    if (!session_id) {
      console.warn('⚠️ Session update missing session_id:', data)
      return
    }

    switch (type) {
      case ISocket.SessionEventType.Delta:
        eventBus.emit('Socket::Session::Delta', data)
        break
      case ISocket.SessionEventType.ToolCall:
        eventBus.emit('Socket::Session::ToolCall', data)
        break
      case ISocket.SessionEventType.ToolCallArguments:
        eventBus.emit('Socket::Session::ToolCallArguments', data)
        break
      case ISocket.SessionEventType.ToolCallProgress:
        eventBus.emit('Socket::Session::ToolCallProgress', data)
        break
      case ISocket.SessionEventType.ImageGenerated:
        eventBus.emit('Socket::Session::ImageGenerated', data)
        break
      case ISocket.SessionEventType.FileGenerated:
        eventBus.emit('Socket::Session::FileGenerated', data)
        break
      case ISocket.SessionEventType.AllMessages:
        eventBus.emit('Socket::Session::AllMessages', data)
        break
      case ISocket.SessionEventType.Done:
        eventBus.emit('Socket::Session::Done', data)
        break
      case ISocket.SessionEventType.Error:
        eventBus.emit('Socket::Session::Error', data)
        break
      case ISocket.SessionEventType.Info:
        eventBus.emit('Socket::Session::Info', data)
        break
      default:
        console.log('⚠️ Unknown session update type:', type)
    }
  }

  ping(data: unknown) {
    if (this.socket && this.connected) {
      this.socket.emit('ping', data)
    }
  }

  disconnect() {
    if (this.socket) {
      this.socket.disconnect()
      this.socket = null
      this.connected = false
      console.log('🔌 Socket.IO manually disconnected')
    }
  }

  isConnected(): boolean {
    return this.connected
  }

  getSocketId(): string | undefined {
    return this.socket?.id
  }

  getSocket(): Socket | null {
    return this.socket
  }

  // HTTP轮询相关方法
  addActiveSession(sessionId: string) {
    this.activeSessions.add(sessionId)
    console.log(`📝 Added active session: ${sessionId}`)

    // 总是启动轮询作为备用机制（即使WebSocket连接正常）
    if (!this.pollingEnabled) {
      this.startPolling()
    }
  }

  removeActiveSession(sessionId: string) {
    this.activeSessions.delete(sessionId)
    console.log(`🗑️ Removed active session: ${sessionId}`)

    // 如果没有活跃会话，停止轮询
    if (this.activeSessions.size === 0) {
      this.stopPolling()
    }
  }

  private startPolling() {
    if (this.pollingEnabled || this.activeSessions.size === 0) {
      return
    }

    this.pollingEnabled = true
    console.log('🔄 Starting HTTP polling for session updates')

    this.pollingInterval = window.setInterval(async () => {
      await this.pollForUpdates()
    }, this.pollingDelay)
  }

  private stopPolling() {
    if (!this.pollingEnabled) {
      return
    }

    this.pollingEnabled = false
    if (this.pollingInterval) {
      clearInterval(this.pollingInterval)
      this.pollingInterval = null
    }
    console.log('⏹️ Stopped HTTP polling')
  }

  private async pollForUpdates() {
    if (this.activeSessions.size === 0) {
      return
    }

    try {
      for (const sessionId of this.activeSessions) {
        await this.pollSessionUpdates(sessionId)
      }
    } catch (error) {
      console.error('❌ Polling error:', error)
    }
  }

  private async pollSessionUpdates(sessionId: string) {
    try {
      // Use authenticated fetch for polling
      const token = getAccessToken()
      const headers: Record<string, string> = {}
      if (token) {
        headers['Authorization'] = `Bearer ${token}`
      }

      const response = await fetch(`/api/chat_session/${sessionId}/status`, {
        headers
      })
      if (!response.ok) {
        return
      }

      const data = await response.json()

      // 发送消息更新事件
      eventBus.emit('Socket::Session::AllMessages', {
        session_id: sessionId,
        type: ISocket.SessionEventType.AllMessages,
        messages: data.messages
      })

      // 如果处理完成，发送完成事件
      if (!data.is_processing) {
        eventBus.emit('Socket::Session::Done', {
          session_id: sessionId,
          type: ISocket.SessionEventType.Done
        })

        // 如果会话处理完成，可以从活跃会话中移除
        // this.removeActiveSession(sessionId)
      }

    } catch (error) {
      console.error(`❌ Failed to poll session ${sessionId}:`, error)
    }
  }

  // 检查是否正在使用轮询
  isPolling(): boolean {
    return this.pollingEnabled
  }
}

// 获取当前主机名，动态构建后端 URL
const getServerUrl = () => {
  if (typeof window === 'undefined') return 'http://localhost:57988'

  const hostname = window.location.hostname
  const port = window.location.port
  const protocol = window.location.protocol

  // 如果当前访问的是 EC2 域名或其他远程地址，使用相同的主机名
  if (hostname.includes('amazonaws.com') || hostname.includes('ec2-') || hostname !== 'localhost') {
    // 使用当前访问的主机名，但端口改为后端端口 57988
    return `${protocol}//${hostname}:57988`
  }

  // 本地开发环境使用 localhost
  return 'http://localhost:57988'
}

export const socketManager = new SocketIOManager({
  serverUrl: getServerUrl(),
})
