import { useEffect } from 'react'

type UseEscapeToCloseParams = {
    enabled: boolean
    onClose: () => void
}

export function useEscapeToClose({ enabled, onClose }: UseEscapeToCloseParams): void {
    useEffect(() => {
        if (!enabled) {
            return
        }

        const handleKeyDown = (event: KeyboardEvent): void => {
            if (event.key !== 'Escape') {
                return
            }
            event.preventDefault()
            onClose()
        }

        window.addEventListener('keydown', handleKeyDown)
        return () => window.removeEventListener('keydown', handleKeyDown)
    }, [enabled, onClose])
}
