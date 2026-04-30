import { useCallback, useState } from 'react'

type UseModalStateResult = {
    isOpen: boolean
    open: () => void
    close: () => void
}

export function useModalState(initialOpen = false): UseModalStateResult {
    const [isOpen, setIsOpen] = useState(initialOpen)

    const open = useCallback(() => {
        setIsOpen(true)
    }, [])

    const close = useCallback(() => {
        setIsOpen(false)
    }, [])

    return {
        isOpen,
        open,
        close,
    }
}
