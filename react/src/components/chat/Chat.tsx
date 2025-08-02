import { sendMessages, saveMessage } from '@/api/chat'
import Blur from '@/components/common/Blur'
import { ScrollArea } from '@/components/ui/scroll-area'
import { eventBus, TEvents } from '@/lib/event'
import { socketManager } from '@/lib/socket'
import {
  AssistantMessage,
  Message,
  Model,
  PendingType,
  Session,
} from '@/types/types'
import { useSearch } from '@tanstack/react-router'
import { produce } from 'immer'
import { motion } from 'motion/react'
import { nanoid } from 'nanoid'
import {
  Dispatch,
  SetStateAction,
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react'
import { useTranslation } from 'react-i18next'
import { PhotoProvider } from 'react-photo-view'
import { toast } from 'sonner'
import ShinyText from '../ui/shiny-text'
import ChatTextarea from './ChatTextarea'
import MessageRegular from './Message/Regular'
import ToolCallContent from './Message/ToolCallContent'
import ToolCallTag from './Message/ToolCallTag'
import SessionSelector from './SessionSelector'
import ChatSpinner from './Spinner'
import ToolcallProgressUpdate from './ToolcallProgressUpdate'

import { useConfigs } from '@/contexts/configs'
import 'react-photo-view/dist/react-photo-view.css'
import { DEFAULT_SYSTEM_PROMPT } from '@/constants'

type ChatInterfaceProps = {
  canvasId: string
  sessionList: Session[]
  setSessionList: Dispatch<SetStateAction<Session[]>>
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({
  canvasId,
  sessionList,
  setSessionList,
}) => {
  const { t } = useTranslation()
  const [session, setSession] = useState<Session | null>(null)
  const { initCanvas, setInitCanvas } = useConfigs()

  const search = useSearch({ from: '/canvas/$id' }) as {
    sessionId: string
  }
  const searchSessionId = search.sessionId || ''

  useEffect(() => {
    if (sessionList.length > 0) {
      let _session = null
      if (searchSessionId) {
        _session = sessionList.find((s) => s.id === searchSessionId) || null
      } else {
        _session = sessionList[0]
      }
      setSession(_session)
    } else {
      setSession(null)
    }
  }, [sessionList, searchSessionId])

  const [messages, setMessages] = useState<Message[]>([])
  const [pending, setPending] = useState<PendingType>(
    initCanvas ? 'text' : false
  )
  const [currentImageContext, setCurrentImageContext] = useState<string>('')

  const sessionId = session?.id

  const sessionIdRef = useRef<string>(session?.id || nanoid())
  const [expandingToolCalls, setExpandingToolCalls] = useState<string[]>([])

  const scrollRef = useRef<HTMLDivElement>(null)
  const isAtBottomRef = useRef(false)

  const scrollToBottom = useCallback(() => {
    if (!isAtBottomRef.current) {
      return
    }
    setTimeout(() => {
      scrollRef.current?.scrollTo({
        top: scrollRef.current!.scrollHeight,
        behavior: 'smooth',
      })
    }, 200)
  }, [])

  const handleDelta = useCallback(
    (data: TEvents['Socket::Session::Delta']) => {
      if (data.session_id && data.session_id !== sessionId) {
        return
      }

      setPending('text')
      setMessages(
        produce((prev) => {
          const last = prev.at(-1)
          if (
            last?.role === 'assistant' &&
            last.content != null &&
            last.tool_calls == null
          ) {
            if (typeof last.content === 'string') {
              last.content += data.text
            } else if (
              last.content &&
              last.content.at(-1) &&
              last.content.at(-1)!.type === 'text'
            ) {
              ;(last.content.at(-1) as { text: string }).text += data.text
            }
          } else {
            prev.push({
              role: 'assistant',
              content: data.text,
            })
          }
        })
      )
      scrollToBottom()
    },
    [sessionId, scrollToBottom]
  )

  const handleToolCall = useCallback(
    (data: TEvents['Socket::Session::ToolCall']) => {
      if (data.session_id && data.session_id !== sessionId) {
        return
      }

      const existToolCall = messages.find(
        (m) =>
          m.role === 'assistant' &&
          m.tool_calls &&
          m.tool_calls.find((t) => t.id == data.id)
      )

      if (existToolCall) {
        return
      }

      setMessages(
        produce((prev) => {
          console.log('👇tool_call event get', data)
          setPending('tool')
          prev.push({
            role: 'assistant',
            content: '',
            tool_calls: [
              {
                type: 'function',
                function: {
                  name: data.name,
                  arguments: '',
                },
                id: data.id,
              },
            ],
          })
        })
      )

      setExpandingToolCalls(
        produce((prev) => {
          prev.push(data.id)
        })
      )
    },
    [sessionId]
  )

  const handleToolCallArguments = useCallback(
    (data: TEvents['Socket::Session::ToolCallArguments']) => {
      if (data.session_id && data.session_id !== sessionId) {
        return
      }

      setMessages(
        produce((prev) => {
          setPending('tool')
          const lastMessage = prev.find(
            (m) =>
              m.role === 'assistant' &&
              m.tool_calls &&
              m.tool_calls.find((t) => t.id == data.id)
          ) as AssistantMessage

          if (lastMessage) {
            const toolCall = lastMessage.tool_calls!.find(
              (t) => t.id == data.id
            )
            if (toolCall) {
              toolCall.function.arguments += data.text
            }
          }
        })
      )
      scrollToBottom()
    },
    [sessionId, scrollToBottom]
  )

  const handleImageGenerated = useCallback(
    (data: TEvents['Socket::Session::ImageGenerated']) => {
      if (
        data.canvas_id &&
        data.canvas_id !== canvasId &&
        data.session_id !== sessionId
      ) {
        return
      }

      console.log('⭐️dispatching image_generated', data)
      setPending('image')
    },
    [canvasId, sessionId]
  )

  const handleFileGenerated = useCallback(
    async (data: TEvents['Socket::Session::FileGenerated']) => {
      console.log('🔍 handleFileGenerated called with data:', data)
      console.log('🔍 Current sessionId:', sessionId)

      if (data.session_id !== sessionId) {
        console.log('🔍 Session ID mismatch, ignoring file_generated event')
        return
      }

      console.log('⭐️file_generated', data)

      // 检查文件类型，为图片和视频创建不同的消息
      const fileUrl = `/api/file/${data.file_id}`
      const isVideo = data.file_type === 'video' || data.duration !== undefined

      let fileMessage: Message

      if (isVideo) {
        // 为视频文件创建下载链接消息
        fileMessage = {
          id: `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
          role: 'assistant',
          content: `✅ Video generated successfully!\n\n📹 **Video Details:**\n- File ID: \`${data.file_id}\`\n- Dimensions: ${data.width}x${data.height}\n- Duration: ${data.duration} seconds\n\n📥 **Download Video:**\n[Download ${data.file_id}](${fileUrl})\n\nThe video has been saved and is ready for download.`,
          timestamp: new Date().toISOString()
        }
      } else {
        // 为图片文件创建图像消息
        fileMessage = {
          id: `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
          role: 'assistant',
          content: [
            {
              type: 'image_url',
              image_url: {
                url: fileUrl
              }
            }
          ],
          timestamp: new Date().toISOString()
        }
      }

      setMessages(prev => [...prev, fileMessage])
      setPending(false)

      // 注意：后端工具已经保存了消息，这里不需要重复保存
      // 只是临时添加到前端状态，页面刷新时会从数据库重新加载
      console.log('📝 File message added to frontend state (backend tools handle database saving)')
    },
    [sessionId]
  )

  const handleAllMessages = useCallback(
    (data: TEvents['Socket::Session::AllMessages']) => {
      console.log(`🔍 handleAllMessages called: data.session_id=${data.session_id}, current sessionId=${sessionId}`)
      console.log(`🔍 DEBUG: Received messages:`, data.messages)

      if (data.session_id && data.session_id !== sessionId) {
        console.log(`🔍 Session ID mismatch, ignoring message update`)
        return
      }

      // 防止空消息覆盖已有消息
      if (!data.messages || data.messages.length === 0) {
        console.log(`🔍 DEBUG: Received empty messages, ignoring to prevent clearing existing messages`)
        return
      }

      console.log(`🔍 Updating messages with ${data.messages?.length || 0} messages`)
      setMessages(() => {
        console.log('👇all_messages', data.messages)

        // 缓存消息到本地存储，防止丢失
        if (data.messages && data.messages.length > 0) {
          try {
            localStorage.setItem(`session_${sessionId}_messages`, JSON.stringify(data.messages))
            localStorage.setItem(`session_${sessionId}_timestamp`, Date.now().toString())
          } catch (e) {
            console.warn('Failed to cache messages to localStorage:', e)
          }
        }

        return data.messages
      })
      scrollToBottom()
    },
    [sessionId, scrollToBottom]
  )

  const handleDone = useCallback(
    (data: TEvents['Socket::Session::Done']) => {
      if (data.session_id && data.session_id !== sessionId) {
        return
      }

      setPending(false)
      scrollToBottom()

      // 流式处理完成后，移除活跃会话以停止轮询
      if (sessionId) {
        socketManager.removeActiveSession(sessionId)
      }
    },
    [sessionId, scrollToBottom]
  )

  const handleError = useCallback((data: TEvents['Socket::Session::Error']) => {
    setPending(false)
    toast.error('Error: ' + data.error, {
      closeButton: true,
      duration: 3600 * 1000,
      style: { color: 'red' },
    })
  }, [])

  const handleInfo = useCallback((data: TEvents['Socket::Session::Info']) => {
    toast.info(data.info, {
      closeButton: true,
      duration: 10 * 1000,
    })
  }, [])

  useEffect(() => {
    const handleScroll = () => {
      if (scrollRef.current) {
        isAtBottomRef.current =
          scrollRef.current.scrollHeight - scrollRef.current.scrollTop <=
          scrollRef.current.clientHeight + 1
      }
    }
    const scrollEl = scrollRef.current
    scrollEl?.addEventListener('scroll', handleScroll)

    eventBus.on('Socket::Session::Delta', handleDelta)
    eventBus.on('Socket::Session::ToolCall', handleToolCall)
    eventBus.on('Socket::Session::ToolCallArguments', handleToolCallArguments)
    eventBus.on('Socket::Session::ImageGenerated', handleImageGenerated)
    eventBus.on('Socket::Session::FileGenerated', handleFileGenerated)
    eventBus.on('Socket::Session::AllMessages', handleAllMessages)
    eventBus.on('Socket::Session::Done', handleDone)
    eventBus.on('Socket::Session::Error', handleError)
    eventBus.on('Socket::Session::Info', handleInfo)
    return () => {
      scrollEl?.removeEventListener('scroll', handleScroll)

      eventBus.off('Socket::Session::Delta', handleDelta)
      eventBus.off('Socket::Session::ToolCall', handleToolCall)
      eventBus.off(
        'Socket::Session::ToolCallArguments',
        handleToolCallArguments
      )
      eventBus.off('Socket::Session::ImageGenerated', handleImageGenerated)
      eventBus.off('Socket::Session::FileGenerated', handleFileGenerated)
      eventBus.off('Socket::Session::AllMessages', handleAllMessages)
      eventBus.off('Socket::Session::Done', handleDone)
      eventBus.off('Socket::Session::Error', handleError)
      eventBus.off('Socket::Session::Info', handleInfo)
    }
  }, [
    handleDelta,
    handleToolCall,
    handleToolCallArguments,
    handleImageGenerated,
    handleFileGenerated,
    handleAllMessages,
    handleDone,
    handleError,
    handleInfo
  ])

  const initChat = useCallback(async () => {
    if (!sessionId) {
      return
    }

    sessionIdRef.current = sessionId

    try {
      const { getChatSession } = await import('@/api/chat')
      const { messages: msgs, lastImageId } = await getChatSession(sessionId)

      console.log(`🔍 DEBUG: initChat loaded ${msgs.length} messages for session ${sessionId}`)
      console.log(`🔍 DEBUG: Messages:`, msgs)
      console.log(`🔍 DEBUG: Last image ID:`, lastImageId)

      setMessages(msgs)
      setCurrentImageContext(lastImageId)

      if (msgs.length > 0) {
        setInitCanvas(false)
      }

      // 如果有图像上下文，在控制台输出调试信息
      if (lastImageId) {
        console.log(`📸 Loaded image context: ${lastImageId}`)
      }

      scrollToBottom()
    } catch (error) {
      console.error('Error loading chat session:', error)
      // 降级处理：直接调用原始API，使用认证头
      try {
        const { authenticatedFetch } = await import('@/api/auth')
        const resp = await authenticatedFetch('/api/chat_session/' + sessionId)

        if (!resp.ok) {
          console.error(`Failed to load session ${sessionId}: ${resp.status}`)
          setMessages([])
          setCurrentImageContext('')
          return
        }

        const data = await resp.json()

        let msgs = []
        if (Array.isArray(data)) {
          msgs = data
        } else if (data && data.messages) {
          msgs = data.messages
        }

        console.log(`🔍 Fallback loaded ${msgs.length} messages for session ${sessionId}`)
        setMessages(msgs)
        setCurrentImageContext('')

        if (msgs.length > 0) {
          setInitCanvas(false)
        }

        scrollToBottom()
      } catch (fallbackError) {
        console.error('Fallback API call also failed:', fallbackError)

        // 尝试从本地缓存恢复消息
        try {
          const cachedMessages = localStorage.getItem(`session_${sessionId}_messages`)
          const cachedTimestamp = localStorage.getItem(`session_${sessionId}_timestamp`)

          if (cachedMessages && cachedTimestamp) {
            const timestamp = parseInt(cachedTimestamp)
            const now = Date.now()
            // 如果缓存不超过1小时，使用缓存的消息
            if (now - timestamp < 60 * 60 * 1000) {
              const msgs = JSON.parse(cachedMessages)
              console.log(`🔍 Restored ${msgs.length} messages from cache for session ${sessionId}`)
              setMessages(msgs)
              setCurrentImageContext('')

              if (msgs.length > 0) {
                setInitCanvas(false)
              }

              scrollToBottom()
              return
            }
          }
        } catch (cacheError) {
          console.warn('Failed to restore from cache:', cacheError)
        }

        // 最后的降级：显示空消息列表但不报错
        console.log(`🔍 No cached messages available, showing empty session for ${sessionId}`)
        setMessages([])
        setCurrentImageContext('')
      }
    }
  }, [sessionId, scrollToBottom, setInitCanvas])

  useEffect(() => {
    // 检查会话是否正在处理中，如果是则显示提示
    const checkProcessingStatus = async () => {
      if (!sessionId) return

      try {
        const { authenticatedFetch } = await import('@/api/auth')
        const response = await authenticatedFetch(`/api/chat_session/${sessionId}/status`)
        if (response.ok) {
          const data = await response.json()
          if (data.is_processing) {
            // 显示处理中的提示
            toast.info('后台正在处理中，请耐心等待...', {
              closeButton: true,
              duration: 5000,
              style: {
                backgroundColor: '#3b82f6',
                color: 'white'
              },
            })
          }
        }
      } catch (error) {
        console.error('Error checking session status:', error)
      }
    }

    // 正常初始化聊天
    initChat()

    // 检查处理状态
    checkProcessingStatus()

    // 清理过期的缓存消息（超过24小时）
    const cleanupExpiredCache = () => {
      try {
        const keys = Object.keys(localStorage)
        const now = Date.now()

        keys.forEach(key => {
          if (key.startsWith('session_') && key.endsWith('_timestamp')) {
            const timestamp = parseInt(localStorage.getItem(key) || '0')
            if (now - timestamp > 24 * 60 * 60 * 1000) { // 24小时
              const sessionId = key.replace('session_', '').replace('_timestamp', '')
              localStorage.removeItem(`session_${sessionId}_messages`)
              localStorage.removeItem(`session_${sessionId}_timestamp`)
              console.log(`🧹 Cleaned up expired cache for session ${sessionId}`)
            }
          }
        })
      } catch (e) {
        console.warn('Failed to cleanup expired cache:', e)
      }
    }

    cleanupExpiredCache()
  }, [sessionId, initChat])

  // 管理轮询会话
  useEffect(() => {
    if (sessionId) {
      // 添加活跃会话（仅在WebSocket连接失败时启用轮询作为备用机制）
      socketManager.addActiveSession(sessionId)

      // 检查会话是否正在处理中，如果是则确保轮询启动
      const checkSessionStatus = async () => {
        try {
          const response = await fetch(`/api/chat_session/${sessionId}/status`)
          if (response.ok) {
            const data = await response.json()
            if (data.is_processing) {
              console.log(`🔄 Session ${sessionId} is processing, ensuring polling is active`)
              // 如果会话正在处理，强制启动轮询以确保能接收更新
              socketManager.forceStartPolling()
            }
          }
        } catch (error) {
          console.error('Error checking session status:', error)
        }
      }

      checkSessionStatus()
    }

    return () => {
      // 组件卸载时从轮询列表中移除
      if (sessionId) {
        socketManager.removeActiveSession(sessionId)
      }
    }
  }, [sessionId])

  const onSelectSession = (sessionId: string) => {
    setSession(sessionList.find((s) => s.id === sessionId) || null)
    window.history.pushState(
      {},
      '',
      `/canvas/${canvasId}?sessionId=${sessionId}`
    )
  }

  const onClickNewChat = () => {
    const newSession: Session = {
      id: nanoid(),
      title: t('chat:newChat'),
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      model: session?.model || 'gpt-4o',
      provider: session?.provider || 'openai',
    }

    setSessionList((prev) => [...prev, newSession])
    onSelectSession(newSession.id)
  }

  const onSendMessages = useCallback(
    (data: Message[], configs: { textModel: Model; imageModel: Model; videoModel?: Model }) => {
      setPending('text')
      setMessages(data)

      // 添加会话到活跃列表（仅在WebSocket连接失败时启用轮询作为备用机制）
      if (sessionId) {
        socketManager.addActiveSession(sessionId)
      }

      sendMessages({
        sessionId: sessionId!,
        canvasId: canvasId,
        newMessages: data,
        textModel: configs.textModel,
        imageModel: configs.imageModel,
        videoModel: configs.videoModel,
        systemPrompt:
          localStorage.getItem('system_prompt') || DEFAULT_SYSTEM_PROMPT,
      })

      if (searchSessionId !== sessionId) {
        window.history.pushState(
          {},
          '',
          `/canvas/${canvasId}?sessionId=${sessionId}`
        )
      }

      scrollToBottom()
    },
    [canvasId, sessionId, searchSessionId, scrollToBottom]
  )

  const handleCancelChat = useCallback(() => {
    setPending(false)
  }, [])

  return (
    <PhotoProvider>
      <div className="flex flex-col h-screen relative">
        {/* Chat messages */}

        <header className="flex px-2 py-2 absolute top-0 z-1 w-full">
          <SessionSelector
            session={session}
            sessionList={sessionList}
            onClickNewChat={onClickNewChat}
            onSelectSession={onSelectSession}
          />
          {currentImageContext && (
            <div className="flex items-center ml-2 px-2 py-1 bg-blue-100 dark:bg-blue-900 rounded-md text-xs text-blue-800 dark:text-blue-200">
              <span className="mr-1">🖼️</span>
              <span>Image context available</span>
            </div>
          )}
          <Blur className="absolute top-0 left-0 right-0 h-full" />
        </header>

        <ScrollArea className="h-[calc(100vh-45px)]" viewportRef={scrollRef}>
          {messages.length > 0 ? (
            <div className="flex-1 px-4 pb-50 pt-15">
              {/* Messages */}
              {messages.map((message, idx) => (
                <div key={`${idx}`}>
                  {/* Regular message content */}
                  {typeof message.content == 'string' &&
                    (message.role !== 'tool' ? (
                      <MessageRegular
                        message={message}
                        content={message.content}
                      />
                    ) : (
                      <ToolCallContent
                        expandingToolCalls={expandingToolCalls}
                        message={message}
                      />
                    ))}

                  {Array.isArray(message.content) &&
                    message.content.map((content, i) => (
                      <MessageRegular
                        key={i}
                        message={message}
                        content={content}
                      />
                    ))}

                  {message.role === 'assistant' &&
                    message.tool_calls &&
                    message.tool_calls.at(-1)?.function.name != 'finish' &&
                    message.tool_calls.map((toolCall, i) => {
                      return (
                        <ToolCallTag
                          key={toolCall.id}
                          toolCall={toolCall}
                          isExpanded={expandingToolCalls.includes(toolCall.id)}
                          onToggleExpand={() => {
                            if (expandingToolCalls.includes(toolCall.id)) {
                              setExpandingToolCalls((prev) =>
                                prev.filter((id) => id !== toolCall.id)
                              )
                            } else {
                              setExpandingToolCalls((prev) => [
                                ...prev,
                                toolCall.id,
                              ])
                            }
                          }}
                        />
                      )
                    })}
                </div>
              ))}
              {pending && <ChatSpinner pending={pending} />}
              {pending && sessionId && (
                <ToolcallProgressUpdate sessionId={sessionId} />
              )}
            </div>
          ) : (
            <motion.div className="flex flex-col h-full p-4 items-start justify-start pt-16 select-none">
              <motion.span
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5 }}
                className="text-muted-foreground text-3xl"
              >
                <ShinyText text="Hello, open gallary!" />
              </motion.span>
              <motion.span
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6 }}
                className="text-muted-foreground text-2xl"
              >
                <ShinyText text="How can I help you today?" />
              </motion.span>
            </motion.div>
          )}
        </ScrollArea>

        <div className="p-2 gap-2 sticky bottom-0">
          <ChatTextarea
            sessionId={sessionId!}
            pending={!!pending}
            messages={messages}
            onSendMessages={onSendMessages}
            onCancelChat={handleCancelChat}
          />
        </div>
      </div>
    </PhotoProvider>
  )
}

export default ChatInterface
