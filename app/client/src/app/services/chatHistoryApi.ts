import type {
    ChatHistoryHandle,
    ChatHistoryMessage,
} from '../../workflow/schema/types'
import { requestJson } from './api'

export interface ChatHistoryResponse {
    messages: ChatHistoryMessage[]
}

export function fetchChatHistory(handle: ChatHistoryHandle): Promise<ChatHistoryResponse> {
    const query = new URLSearchParams({
        workflow_id: handle.workflow_id,
        execution_session_id: handle.execution_session_id,
        node_id: handle.node_id,
        node_type: handle.node_type,
        max_messages: String(handle.max_messages),
        separator: handle.separator,
        keep_prompt_type: String(handle.keep_prompt_type),
    })
    if (handle.storage_backend) {
        query.set('storage_backend', handle.storage_backend)
    }
    return requestJson<ChatHistoryResponse>(`/chat-history?${query.toString()}`)
}

export function resetChatHistory(handle: ChatHistoryHandle): Promise<ChatHistoryResponse> {
    return requestJson<ChatHistoryResponse>('/chat-history/reset', {
        method: 'POST',
        body: JSON.stringify(handle),
    })
}
