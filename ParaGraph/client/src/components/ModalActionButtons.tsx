type ModalActionButtonsProps = {
    cancelLabel: string
    confirmLabel: string
    onCancel: () => void
    onConfirm: () => void
    cancelDisabled?: boolean
    confirmDisabled?: boolean
}

export default function ModalActionButtons({
    cancelLabel,
    confirmLabel,
    onCancel,
    onConfirm,
    cancelDisabled = false,
    confirmDisabled = false,
}: ModalActionButtonsProps) {
    return (
        <>
            <button type="button" onClick={onCancel} disabled={cancelDisabled}>
                {cancelLabel}
            </button>
            <button type="button" onClick={onConfirm} disabled={confirmDisabled}>
                {confirmLabel}
            </button>
        </>
    )
}
