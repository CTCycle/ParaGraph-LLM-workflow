import { useEffect, type RefObject } from 'react'

const FOCUSABLE_SELECTOR = [
    'button:not([disabled])',
    'a[href]',
    'input:not([disabled])',
    'select:not([disabled])',
    'textarea:not([disabled])',
    '[tabindex]:not([tabindex="-1"])',
].join(',')

function getFocusableElements(root: HTMLElement): HTMLElement[] {
    return Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter(
        (element) => element.getAttribute('aria-hidden') !== 'true',
    )
}

export function useDialogFocus(
    isOpen: boolean,
    dialogRef: RefObject<HTMLElement>,
    initialFocusRef?: RefObject<HTMLElement>,
): void {
    useEffect(() => {
        if (!isOpen) {
            return
        }

        const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
        const focusTimer = globalThis.setTimeout(() => {
            const dialog = dialogRef.current
            if (!dialog) {
                return
            }
            const initialFocus = initialFocusRef?.current
            const firstFocusable = getFocusableElements(dialog)[0]
            ;(initialFocus ?? firstFocusable ?? dialog).focus()
        }, 0)

        const handleKeyDown = (event: KeyboardEvent): void => {
            if (event.key !== 'Tab') {
                return
            }

            const dialog = dialogRef.current
            if (!dialog) {
                return
            }

            const focusableElements = getFocusableElements(dialog)
            if (focusableElements.length === 0) {
                event.preventDefault()
                dialog.focus()
                return
            }

            const first = focusableElements[0]
            const last = focusableElements[focusableElements.length - 1]
            if (event.shiftKey && document.activeElement === first) {
                event.preventDefault()
                last.focus()
            } else if (!event.shiftKey && document.activeElement === last) {
                event.preventDefault()
                first.focus()
            }
        }

        document.addEventListener('keydown', handleKeyDown)
        return () => {
            globalThis.clearTimeout(focusTimer)
            document.removeEventListener('keydown', handleKeyDown)
            if (previousFocus?.isConnected) {
                previousFocus.focus()
            }
        }
    }, [dialogRef, initialFocusRef, isOpen])
}
