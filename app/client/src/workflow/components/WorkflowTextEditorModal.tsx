import { useCallback } from 'react'

import { useEscapeToClose } from '../../app/hooks/useEscapeToClose'
import {
    type WorkflowTextEditorBinding,
    useWorkflowTextEditorDraft,
} from '../hooks/useWorkflowTextEditorDraft'

type WorkflowTextEditorModalProps = {
    binding: WorkflowTextEditorBinding | null
    title: string
    onApply: (value: string) => void
    onCancel: () => void
}

export function WorkflowTextEditorModal({
    binding,
    title,
    onApply,
    onCancel,
}: WorkflowTextEditorModalProps) {
    const activeBinding = binding ?? {
        nodeId: null,
        text: '',
        editable: false,
        parameterName: null,
    }
    const { editorTextDraft, setEditorTextDraft } = useWorkflowTextEditorDraft(activeBinding)
    const close = useCallback(() => onCancel(), [onCancel])

    useEscapeToClose({ enabled: binding !== null, onClose: close })

    if (!binding) {
        return null
    }

    return (
        <div
            className="workflow-text-editor-modal-backdrop"
            role="presentation"
            onMouseDown={(event) => {
                if (event.target === event.currentTarget) {
                    onCancel()
                }
            }}
        >
            <div
                className="workflow-text-editor-modal"
                role="dialog"
                aria-modal="true"
                aria-label={title}
                onMouseDown={(event) => event.stopPropagation()}
            >
                <div className="workflow-text-editor-modal-header">
                    <div>
                        <h2>{title}</h2>
                        <p>Edit the draft, then apply the change to the node once.</p>
                    </div>
                    <button type="button" aria-label="Close text editor" onClick={onCancel}>×</button>
                </div>
                <textarea
                    className="workflow-text-editor-modal-textarea"
                    value={editorTextDraft}
                    autoFocus
                    onChange={(event) => setEditorTextDraft(event.target.value)}
                />
                <div className="workflow-text-editor-modal-actions">
                    <button type="button" onClick={onCancel}>Cancel</button>
                    <button type="button" onClick={() => onApply(editorTextDraft)}>Apply</button>
                </div>
            </div>
        </div>
    )
}
