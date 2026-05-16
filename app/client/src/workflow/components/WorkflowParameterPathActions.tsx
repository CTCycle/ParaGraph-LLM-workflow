export type WorkflowParameterPathActionsProps = {
    isBrowsing: boolean
    hasValue: boolean
    onBrowse: () => void
    onClear: () => void
}

export function WorkflowParameterPathActions({
    isBrowsing,
    hasValue,
    onBrowse,
    onClear,
}: WorkflowParameterPathActionsProps) {
    return (
        <div className="workflow-node-parameter-actions">
            <button
                type="button"
                className="workflow-node-picker-button"
                disabled={isBrowsing}
                onClick={onBrowse}
            >
                {isBrowsing ? '...' : 'Browse'}
            </button>
            {hasValue && (
                <button
                    type="button"
                    className="workflow-node-picker-clear"
                    onClick={onClear}
                >
                    Clear
                </button>
            )}
        </div>
    )
}
