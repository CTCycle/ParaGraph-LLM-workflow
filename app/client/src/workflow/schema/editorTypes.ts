import type {
    ChatHistoryMessage,
    NodeManifest,
    ProviderModelDefinition,
    VectorStoreCapabilities,
} from './types'

export type WorkflowNodeData = {
    manifest: NodeManifest
    parameters: Record<string, unknown>
    collapsed: boolean
    itemsExpanded: boolean
    selectedItemKey: string | null
    pinged: boolean
    skipped: boolean
    boundInputNames: string[]
    isActive: boolean
    glowLevel: number
    runtimeOutput: Record<string, unknown> | null
    runtimeStepOutput: Record<string, unknown> | null
    providerModels: ProviderModelDefinition[]
    vectorStoreCapabilities: VectorStoreCapabilities[]
    chatHistory: ChatHistoryMessage[]
    chatHistoryLoading: boolean
    chatHistoryError: string | null
    chatRunning: boolean
    chatHistoryConnected: boolean
    onParameterChange: (parameterName: string, value: unknown) => void
    onSaveNodeBrowseSelection: (selection: SaveNodeBrowserSelection | null) => void
    onStatusChange: (message: string) => void
    onTogglePing: () => void
    onToggleCollapse: () => void
    onToggleItemsExpanded: () => void
    onSelectItem: (itemKey: string | null) => void
    onOpenTextEditor: (parameterName: string) => void
    onChatSubmit: (message: string) => void
    onChatReset: () => void
}

export type SaveNodeBrowserSelection =
    | { kind: 'file'; fileHandle: FileSystemFileHandle }
    | { kind: 'folder'; directoryHandle: FileSystemDirectoryHandle }
