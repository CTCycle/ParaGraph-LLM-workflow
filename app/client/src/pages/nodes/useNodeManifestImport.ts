import { type FormEvent, useState } from 'react'

import { importNodeManifest } from '../../app/services/nodesApi'
import { type NodeManifest } from '../../workflow/schema/types'
import { isNodeManifest } from './nodeManifest'

type UseNodeManifestImportOptions = {
    getErrorMessage: (error: unknown, fallback: string) => string
    onImported: () => Promise<void>
}

type UseNodeManifestImportResult = {
    importStatus: string | null
    isImporting: boolean
    isImportModalOpen: boolean
    jsonText: string
    closeImportModal: () => void
    handleImport: (event: FormEvent<HTMLFormElement>) => Promise<void>
    handleJsonValidation: () => void
    openImportModal: () => void
    setJsonText: (value: string) => void
}

function parseNodeManifest(jsonText: string): NodeManifest {
    const parsed: unknown = JSON.parse(jsonText)
    if (!isNodeManifest(parsed)) {
        throw new Error('JSON must contain a node manifest object')
    }
    return parsed
}

export function useNodeManifestImport({
    getErrorMessage,
    onImported,
}: UseNodeManifestImportOptions): UseNodeManifestImportResult {
    const [jsonText, setJsonText] = useState('')
    const [importStatus, setImportStatus] = useState<string | null>(null)
    const [isImporting, setIsImporting] = useState(false)
    const [isImportModalOpen, setIsImportModalOpen] = useState(false)

    function closeImportModal(): void {
        setIsImportModalOpen(false)
    }

    function openImportModal(): void {
        setIsImportModalOpen(true)
    }

    function handleJsonValidation(): void {
        try {
            const manifest = parseNodeManifest(jsonText)
            setImportStatus(`Valid manifest: ${manifest.id} v${manifest.version}`)
        } catch (validationError) {
            setImportStatus(getErrorMessage(validationError, 'Invalid JSON payload'))
        }
    }

    async function handleImport(event: FormEvent<HTMLFormElement>): Promise<void> {
        event.preventDefault()
        setImportStatus(null)

        let manifest: NodeManifest
        try {
            manifest = parseNodeManifest(jsonText)
            setImportStatus(`Valid manifest: ${manifest.id} v${manifest.version}`)
        } catch (validationError) {
            setImportStatus(getErrorMessage(validationError, 'Invalid JSON payload'))
            return
        }

        setIsImporting(true)
        try {
            const created = await importNodeManifest(manifest)
            setImportStatus(`Imported ${created.id} v${created.version}`)
            await onImported()
            setJsonText('')
            setIsImportModalOpen(false)
        } catch (importError) {
            setImportStatus(getErrorMessage(importError, 'Failed to import node manifest'))
        } finally {
            setIsImporting(false)
        }
    }

    return {
        importStatus,
        isImporting,
        isImportModalOpen,
        jsonText,
        closeImportModal,
        handleImport,
        handleJsonValidation,
        openImportModal,
        setJsonText,
    }
}
