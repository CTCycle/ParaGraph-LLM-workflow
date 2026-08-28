import { useState, type FormEvent, type KeyboardEvent } from 'react'

import HelpPopover from '../../guidance/HelpPopover'
import type { ChatHistoryMessage } from '../schema/types'

type ChatNodeControlsProps = {
    history: ChatHistoryMessage[]
    historyLoading: boolean
    historyError: string | null
    running: boolean
    historyConnected: boolean
    onSubmit: (message: string) => void
    onReset: () => void
}

export function ChatNodeControls({
    history,
    historyLoading,
    historyError,
    running,
    historyConnected,
    onSubmit,
    onReset,
}: ChatNodeControlsProps) {
    const [draft, setDraft] = useState('')

    function submit(): void {
        const message = draft.trim()
        if (!message || running || !historyConnected) {
            return
        }
        setDraft('')
        onSubmit(message)
    }

    function handleSubmit(event: FormEvent<HTMLFormElement>): void {
        event.preventDefault()
        submit()
    }

    function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>): void {
        event.stopPropagation()
        if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
            event.preventDefault()
            submit()
        }
    }

    return (
        <div className="workflow-chat-controls nodrag nopan">
            <div className="workflow-chat-heading">
                <span>Conversation</span>
                <HelpPopover title="About Chat history" triggerLabel="Conversation help">
                    <p>Each send runs the current workflow once.</p>
                    <p>Connect the same history controller to LLM Chat when earlier turns should reach the model.</p>
                    <p>Successful terminal output becomes the assistant reply. Reset clears only this Chat scope.</p>
                </HelpPopover>
            </div>
            <div className="workflow-chat-history" aria-live="polite">
                {historyLoading && <span className="workflow-chat-history-empty">Loading conversation...</span>}
                {!historyLoading && history.length === 0 && (
                    <span className="workflow-chat-history-empty">
                        {historyConnected ? 'No messages yet.' : 'Connect a Chat History node to Chat’s history port to enable messages.'}
                    </span>
                )}
                {!historyLoading && history.map((message, index) => (
                    <div key={`${message.timestamp}-${index}`} className={`workflow-chat-message workflow-chat-message-${message.role}`}>
                        <span className="workflow-chat-message-role">{message.role}</span>
                        <p>{message.content}</p>
                    </div>
                ))}
            </div>
            {historyError && <p className="workflow-chat-error" role="alert">{historyError}</p>}
            <form className="workflow-chat-form" onSubmit={handleSubmit}>
                <textarea
                    rows={2}
                    className="workflow-chat-input"
                    value={draft}
                    placeholder={historyConnected ? 'Send a message...' : 'Connect chat history first'}
                    aria-label="Chat message"
                    disabled={running || !historyConnected}
                    onPointerDown={(event) => event.stopPropagation()}
                    onMouseDown={(event) => event.stopPropagation()}
                    onKeyDown={handleKeyDown}
                    onChange={(event) => setDraft(event.target.value)}
                />
                <div className="workflow-chat-actions">
                    <button type="submit" disabled={running || !historyConnected || !draft.trim()}>
                        {running ? 'Running...' : 'Send'}
                    </button>
                    <button type="button" onClick={onReset} disabled={running || !historyConnected || history.length === 0}>
                        Reset
                    </button>
                </div>
            </form>
            <small className="workflow-chat-hint">Ctrl/Cmd + Enter to send</small>
        </div>
    )
}
