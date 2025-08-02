import { ExcalidrawImageElement } from '@excalidraw/excalidraw/element/types'
import { BinaryFileData } from '@excalidraw/excalidraw/types'
import { Message, ToolCallFunctionName } from './types'

export enum SessionEventType {
  Error = 'error',
  Done = 'done',
  Info = 'info',
  ImageGenerated = 'image_generated',
  FileGenerated = 'file_generated',
  Delta = 'delta',
  ToolCall = 'tool_call',
  ToolCallArguments = 'tool_call_arguments',
  AllMessages = 'all_messages',
  ToolCallProgress = 'tool_call_progress',
}

export interface SessionBaseEvent {
  session_id: string
}

export interface SessionErrorEvent extends SessionBaseEvent {
  type: SessionEventType.Error
  error: string
}
export interface SessionDoneEvent extends SessionBaseEvent {
  type: SessionEventType.Done
}
export interface SessionInfoEvent extends SessionBaseEvent {
  type: SessionEventType.Info
  info: string
}
export interface SessionImageGeneratedEvent extends SessionBaseEvent {
  type: SessionEventType.ImageGenerated
  element: ExcalidrawImageElement
  file: BinaryFileData
  canvas_id: string
  image_url: string
}
export interface SessionFileGeneratedEvent extends SessionBaseEvent {
  type: SessionEventType.FileGenerated
  file_id: string
  file_path: string
  width: number
  height: number
  tool_call_id: string
  canvas_id?: string
  duration?: number  // 视频时长（秒）
  file_type?: string // 文件类型（'image' 或 'video'）
}
export interface SessionDeltaEvent extends SessionBaseEvent {
  type: SessionEventType.Delta
  text: string
}
export interface SessionToolCallEvent extends SessionBaseEvent {
  type: SessionEventType.ToolCall
  id: string
  name: ToolCallFunctionName
}
export interface SessionToolCallArgumentsEvent extends SessionBaseEvent {
  type: SessionEventType.ToolCallArguments
  id: string
  text: string
}
export interface SessionAllMessagesEvent extends SessionBaseEvent {
  type: SessionEventType.AllMessages
  messages: Message[]
}
export interface SessionToolCallProgressEvent extends SessionBaseEvent {
  type: SessionEventType.ToolCallProgress
  tool_call_id: string
  update: string
}

export type SessionUpdateEvent =
  | SessionDeltaEvent
  | SessionToolCallEvent
  | SessionToolCallArgumentsEvent
  | SessionToolCallProgressEvent
  | SessionImageGeneratedEvent
  | SessionFileGeneratedEvent
  | SessionAllMessagesEvent
  | SessionDoneEvent
  | SessionErrorEvent
  | SessionInfoEvent
