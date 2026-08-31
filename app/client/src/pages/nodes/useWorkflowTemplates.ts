import { useEffect, useState } from 'react'

import { fetchWorkflowTemplates } from '../../app/services/workflowsApi'
import { type WorkflowTemplateManifest } from '../../workflow/schema/types'

type UseWorkflowTemplatesParams = {
    getErrorMessage: (error: unknown, fallback: string) => string
}

type UseWorkflowTemplatesResult = {
    templates: WorkflowTemplateManifest[]
    templatesLoading: boolean
    templatesError: string | null
}

export function useWorkflowTemplates({ getErrorMessage }: UseWorkflowTemplatesParams): UseWorkflowTemplatesResult {
    const [templates, setTemplates] = useState<WorkflowTemplateManifest[]>([])
    const [templatesLoading, setTemplatesLoading] = useState(false)
    const [templatesError, setTemplatesError] = useState<string | null>(null)

    useEffect(() => {
        let active = true
        setTemplatesLoading(true)
        void fetchWorkflowTemplates()
            .then((payload) => {
                if (!active) {
                    return
                }
                setTemplates(payload.templates)
                setTemplatesError(null)
            })
            .catch((loadError) => {
                if (!active) {
                    return
                }
                setTemplatesError(getErrorMessage(loadError, 'Failed to load workflow templates'))
            })
            .finally(() => {
                if (active) {
                    setTemplatesLoading(false)
                }
            })

        return () => {
            active = false
        }
    }, [getErrorMessage])

    return {
        templates,
        templatesLoading,
        templatesError,
    }
}
