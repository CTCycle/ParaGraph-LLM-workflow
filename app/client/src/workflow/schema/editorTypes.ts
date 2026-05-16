import type { NodeManifest, ProviderModelDefinition } from './types'

export type WorkflowNodeData = {
    manifest: NodeManifest
    parameters: Record<string, unknown>
    collapsed: boolean
    itemsExpanded: boolean
    selectedItemKey: string | null
    pinged: boolean
    skipped: boolean
    isGlobal: boolean
    isActive: boolean
    glowLevel: number
    runtimeOutput: Record<string, unknown> | null
    runtimeStepOutput: Record<string, unknown> | null
    providerModels: ProviderModelDefinition[]
    onParameterChange: (parameterName: string, value: unknown) => void
    onSaveNodeBrowseSelection: (selection: SaveNodeBrowserSelection | null) => void
    onStatusChange: (message: string) => void
    onTogglePing: () => void
    onToggleCollapse: () => void
    onToggleItemsExpanded: () => void
    onToggleGlobal: () => void
    onSelectItem: (itemKey: string | null) => void
}

export type SaveNodeBrowserSelection =
    | { kind: 'file'; fileHandle: FileSystemFileHandle }
    | { kind: 'folder'; directoryHandle: FileSystemDirectoryHandle }
