import { Dispatch, SetStateAction, useEffect, useState } from 'react'

export type WorkflowTextEditorBinding = {
    nodeId: string | null
    text: string
    editable: boolean
    parameterName: string | null
}

export type UseWorkflowTextEditorDraftResult = {
    editorTextDraft: string
    setEditorTextDraft: Dispatch<SetStateAction<string>>
}

export function useWorkflowTextEditorDraft(
    editorBinding: WorkflowTextEditorBinding,
): UseWorkflowTextEditorDraftResult {
    const [editorTextDraft, setEditorTextDraft] = useState('')

    useEffect(() => {
        setEditorTextDraft(editorBinding.text)
    }, [editorBinding.nodeId, editorBinding.parameterName, editorBinding.text])

    return { editorTextDraft, setEditorTextDraft }
}
