import { Message, Model } from '@/types/types'
import { authenticatedFetch } from './auth'

export const getChatSession = async (sessionId: string) => {
  const response = await authenticatedFetch(`/api/chat_session/${sessionId}`)
  if (!response.ok) {
    throw new Error(`Failed to get chat session: ${response.status}`)
  }
  const data = await response.json()

  // 处理新的API响应格式
  if (data && typeof data === 'object' && data.messages) {
    // 新格式：{messages: [...], last_image_id: "..."}
    return {
      messages: data.messages as Message[],
      lastImageId: data.last_image_id as string
    }
  } else if (Array.isArray(data)) {
    // 兼容旧格式：直接是消息数组
    return {
      messages: data as Message[],
      lastImageId: ''
    }
  }

  return {
    messages: [],
    lastImageId: ''
  }
}

export const sendMessages = async (payload: {
  sessionId: string
  canvasId: string
  newMessages: Message[]
  textModel: Model
  imageModel: Model
  systemPrompt: string | null
}) => {
  // 添加调试日志
  console.log('🔍 DEBUG: Sending to backend - imageModel:', payload.imageModel)

  const response = await authenticatedFetch(`/api/chat`, {
    method: 'POST',
    body: JSON.stringify({
      messages: payload.newMessages,
      canvas_id: payload.canvasId,
      session_id: payload.sessionId,
      text_model: payload.textModel,
      image_model: payload.imageModel,
      system_prompt: payload.systemPrompt,
    }),
  })
  if (!response.ok) {
    throw new Error(`Failed to send messages: ${response.status}`)
  }
  const data = await response.json()
  return data as Message[]
}

export const cancelChat = async (sessionId: string) => {
  const response = await authenticatedFetch(`/api/cancel/${sessionId}`, {
    method: 'POST',
  })
  if (!response.ok) {
    throw new Error(`Failed to cancel chat: ${response.status}`)
  }
  return await response.json()
}
