import { HelpCircle, X } from 'lucide-react'
import { createPortal } from 'react-dom'
import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from 'react'

type HelpPopoverProps = {
    title: string
    triggerLabel: string
    children: ReactNode
}

type PopoverPosition = {
    top: number
    left: number
}

const VIEWPORT_EDGE = 16
const POPOVER_GAP = 10

export default function HelpPopover({ title, triggerLabel, children }: HelpPopoverProps) {
    const [isOpen, setIsOpen] = useState(false)
    const [position, setPosition] = useState<PopoverPosition | null>(null)
    const triggerRef = useRef<HTMLButtonElement | null>(null)
    const popoverRef = useRef<HTMLDivElement | null>(null)
    const closeButtonRef = useRef<HTMLButtonElement | null>(null)
    const popoverId = useId()

    const closePopover = useCallback((): void => {
        setIsOpen(false)
        globalThis.setTimeout(() => triggerRef.current?.focus(), 0)
    }, [])

    const updatePosition = useCallback((): void => {
        const trigger = triggerRef.current
        const popover = popoverRef.current
        if (!trigger || !popover) {
            return
        }

        const triggerRect = trigger.getBoundingClientRect()
        const popoverRect = popover.getBoundingClientRect()
        const popoverWidth = popoverRect.width || Math.min(320, window.innerWidth - VIEWPORT_EDGE * 2)
        const popoverHeight = popoverRect.height || 180
        let left = triggerRect.left
        let top = triggerRect.bottom + POPOVER_GAP

        if (left + popoverWidth > window.innerWidth - VIEWPORT_EDGE) {
            left = triggerRect.right - popoverWidth
        }
        if (top + popoverHeight > window.innerHeight - VIEWPORT_EDGE) {
            top = triggerRect.top - popoverHeight - POPOVER_GAP
        }

        const maxLeft = Math.max(VIEWPORT_EDGE, window.innerWidth - popoverWidth - VIEWPORT_EDGE)
        const maxTop = Math.max(VIEWPORT_EDGE, window.innerHeight - popoverHeight - VIEWPORT_EDGE)
        setPosition({
            left: Math.min(Math.max(left, VIEWPORT_EDGE), maxLeft),
            top: Math.min(Math.max(top, VIEWPORT_EDGE), maxTop),
        })
    }, [])

    useLayoutEffect(() => {
        if (!isOpen) {
            setPosition(null)
            return
        }

        updatePosition()
        const frame = window.requestAnimationFrame(updatePosition)
        window.addEventListener('resize', updatePosition)
        window.addEventListener('scroll', updatePosition, true)
        const resizeObserver = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(updatePosition)
        if (resizeObserver) {
            if (triggerRef.current) {
                resizeObserver.observe(triggerRef.current)
            }
            if (popoverRef.current) {
                resizeObserver.observe(popoverRef.current)
            }
        }

        return () => {
            window.cancelAnimationFrame(frame)
            window.removeEventListener('resize', updatePosition)
            window.removeEventListener('scroll', updatePosition, true)
            resizeObserver?.disconnect()
        }
    }, [isOpen, updatePosition])

    useEffect(() => {
        if (!isOpen) {
            return
        }

        const focusTimer = globalThis.setTimeout(() => closeButtonRef.current?.focus(), 0)
        const handlePointerDown = (event: PointerEvent): void => {
            const target = event.target as Node
            if (triggerRef.current?.contains(target) || popoverRef.current?.contains(target)) {
                return
            }
            closePopover()
        }
        const handleKeyDown = (event: KeyboardEvent): void => {
            if (event.key === 'Escape') {
                event.preventDefault()
                closePopover()
            }
        }

        document.addEventListener('pointerdown', handlePointerDown)
        document.addEventListener('keydown', handleKeyDown)
        return () => {
            globalThis.clearTimeout(focusTimer)
            document.removeEventListener('pointerdown', handlePointerDown)
            document.removeEventListener('keydown', handleKeyDown)
        }
    }, [closePopover, isOpen])

    return (
        <>
            <button
                ref={triggerRef}
                type="button"
                className="guidance-popover-trigger"
                aria-label={triggerLabel}
                aria-expanded={isOpen}
                aria-controls={isOpen ? popoverId : undefined}
                aria-haspopup="dialog"
                onPointerDown={(event) => event.stopPropagation()}
                onMouseDown={(event) => event.stopPropagation()}
                onClick={() => setIsOpen((current) => !current)}
            >
                <HelpCircle size={14} aria-hidden="true" />
            </button>
            {isOpen && createPortal(
                <div
                    ref={popoverRef}
                    id={popoverId}
                    className="guidance-popover"
                    role="dialog"
                    aria-label={title}
                    style={{
                        top: position?.top ?? VIEWPORT_EDGE,
                        left: position?.left ?? VIEWPORT_EDGE,
                        visibility: position ? 'visible' : 'hidden',
                    }}
                    onPointerDown={(event) => event.stopPropagation()}
                >
                    <div className="guidance-popover-header">
                        <h2>{title}</h2>
                        <button type="button" className="guidance-icon-button" aria-label={`Close ${title}`} onClick={closePopover}>
                            <X size={14} aria-hidden="true" />
                        </button>
                    </div>
                    <div className="guidance-popover-body">{children}</div>
                </div>,
                document.body,
            )}
        </>
    )
}
