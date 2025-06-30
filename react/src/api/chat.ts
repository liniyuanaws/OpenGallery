import { Message, Model } from '@/types/types'

export const getChatSession = async (sessionId: string) => {
  const response = await fetch(`/api/chat_session/${sessionId}`)
  const data = await response.json()
  return data as Message[]
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

  const response = await fetch(`/api/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      messages: payload.newMessages,
      canvas_id: payload.canvasId,
      session_id: payload.sessionId,
      text_model: payload.textModel,
      image_model: payload.imageModel,
      system_prompt: payload.systemPrompt,
    }),
  })
  const data = await response.json()
  return data as Message[]
}

export const cancelChat = async (sessionId: string) => {
  const response = await fetch(`/api/cancel/${sessionId}`, {
    method: 'POST',
  })
  return await response.json()
}
