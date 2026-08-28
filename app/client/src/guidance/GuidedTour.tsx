import { Check, ChevronLeft, ChevronRight, X } from 'lucide-react'
import { createPortal } from 'react-dom'
import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from 'react'

import { useEscapeToClose } from '../app/hooks/useEscapeToClose'
import { EDITOR_TOUR_STEPS, GUIDANCE_CONTENT_VERSIONS } from './guidanceContent'
import { useGuidance } from './GuidanceContext'
import TutorialMedia from './TutorialMedia'
import { useDialogFocus } from './useDialogFocus'
import type { GuidanceTourId, TourPlacement, TourStepDefinition } from './types'

type GuidedTourProps = {
    isOpen: boolean
    tourId: GuidanceTourId
    steps?: TourStepDefinition[]
    onRequestClose: () => void
}

type Rect = {
    top: number
    left: number
    width: number
    height: number
}

type TourLayout = {
    top: number
    left: number
    spotlight: Rect | null
}

const VIEWPORT_EDGE = 16
const TOUR_GAP = 14

function getPlacementCandidate(target: Rect, width: number, height: number, placement: TourPlacement): { top: number; left: number } {
    switch (placement) {
        case 'top':
            return { top: target.top - height - TOUR_GAP, left: target.left + (target.width - width) / 2 }
        case 'right':
            return { top: target.top + (target.height - height) / 2, left: target.left + target.width + TOUR_GAP }
        case 'left':
            return { top: target.top + (target.height - height) / 2, left: target.left - width - TOUR_GAP }
        case 'bottom':
        default:
            return { top: target.top + target.height + TOUR_GAP, left: target.left + (target.width - width) / 2 }
    }
}

function isWithinViewport(candidate: { top: number; left: number }, width: number, height: number): boolean {
    return (
        candidate.left >= VIEWPORT_EDGE &&
        candidate.top >= VIEWPORT_EDGE &&
        candidate.left + width <= window.innerWidth - VIEWPORT_EDGE &&
        candidate.top + height <= window.innerHeight - VIEWPORT_EDGE
    )
}

function resolveTourLayout(targetElement: Element | null, card: HTMLElement | null, placement: TourPlacement): TourLayout {
    const cardRect = card?.getBoundingClientRect()
    const cardWidth = cardRect?.width || Math.min(360, window.innerWidth - VIEWPORT_EDGE * 2)
    const cardHeight = cardRect?.height || 260
    const fallback = {
        top: Math.max(VIEWPORT_EDGE, (window.innerHeight - cardHeight) / 2),
        left: Math.max(VIEWPORT_EDGE, (window.innerWidth - cardWidth) / 2),
    }

    if (!targetElement) {
        return { ...fallback, spotlight: null }
    }

    const targetBounds = targetElement.getBoundingClientRect()
    if (targetBounds.width <= 0 || targetBounds.height <= 0) {
        return { ...fallback, spotlight: null }
    }

    const target: Rect = {
        top: targetBounds.top,
        left: targetBounds.left,
        width: targetBounds.width,
        height: targetBounds.height,
    }
    const placements: TourPlacement[] = [
        placement,
        placement === 'top' ? 'bottom' : 'top',
        placement === 'right' ? 'left' : 'right',
        'bottom',
    ]
    const candidate = placements
        .map((item) => getPlacementCandidate(target, cardWidth, cardHeight, item))
        .find((item) => isWithinViewport(item, cardWidth, cardHeight)) ?? fallback

    return {
        top: Math.min(Math.max(candidate.top, VIEWPORT_EDGE), Math.max(VIEWPORT_EDGE, window.innerHeight - cardHeight - VIEWPORT_EDGE)),
        left: Math.min(Math.max(candidate.left, VIEWPORT_EDGE), Math.max(VIEWPORT_EDGE, window.innerWidth - cardWidth - VIEWPORT_EDGE)),
        spotlight: {
            top: Math.max(0, target.top - 6),
            left: Math.max(0, target.left - 6),
            width: target.width + 12,
            height: target.height + 12,
        },
    }
}

function getGuidanceId(tourId: GuidanceTourId): 'editor-tour' {
    return tourId === 'editor' ? 'editor-tour' : 'editor-tour'
}

export default function GuidedTour({ isOpen, tourId, steps = EDITOR_TOUR_STEPS, onRequestClose }: GuidedTourProps) {
    const { markCompleted, markSeen, markSkipped } = useGuidance()
    const [stepIndex, setStepIndex] = useState(0)
    const [layout, setLayout] = useState<TourLayout | null>(null)
    const cardRef = useRef<HTMLDivElement | null>(null)
    const dialogRef = useRef<HTMLDivElement | null>(null)
    const closeButtonRef = useRef<HTMLButtonElement | null>(null)
    const titleId = useId()
    const descriptionId = useId()
    const progressId = useId()
    const currentStep = steps[stepIndex]
    const guidanceId = getGuidanceId(tourId)
    const contentVersion = GUIDANCE_CONTENT_VERSIONS[guidanceId]

    const handleFinish = useCallback((): void => {
        markCompleted(guidanceId, contentVersion)
        onRequestClose()
    }, [contentVersion, guidanceId, markCompleted, onRequestClose])

    const handleSkip = useCallback((): void => {
        markSkipped(guidanceId, contentVersion)
        onRequestClose()
    }, [contentVersion, guidanceId, markSkipped, onRequestClose])

    useEscapeToClose({ enabled: isOpen, onClose: handleSkip })
    useDialogFocus(isOpen, dialogRef, closeButtonRef)

    useEffect(() => {
        if (!isOpen) {
            return
        }
        setStepIndex(0)
        markSeen(guidanceId, contentVersion)
    }, [contentVersion, guidanceId, isOpen, markSeen])

    const updateLayout = useCallback((): void => {
        if (!currentStep) {
            return
        }
        const target = document.querySelector(`[data-guidance-target="${currentStep.target}"]`)
        setLayout(resolveTourLayout(target, cardRef.current, currentStep.placement))
    }, [currentStep])

    useLayoutEffect(() => {
        if (!isOpen || !currentStep) {
            setLayout(null)
            return
        }

        const frame = window.requestAnimationFrame(updateLayout)
        window.addEventListener('resize', updateLayout)
        window.addEventListener('scroll', updateLayout, true)
        const resizeObserver = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(updateLayout)
        const target = document.querySelector(`[data-guidance-target="${currentStep.target}"]`)
        if (resizeObserver) {
            resizeObserver.observe(document.body)
            if (cardRef.current) {
                resizeObserver.observe(cardRef.current)
            }
            if (target) {
                resizeObserver.observe(target)
            }
        }

        return () => {
            window.cancelAnimationFrame(frame)
            window.removeEventListener('resize', updateLayout)
            window.removeEventListener('scroll', updateLayout, true)
            resizeObserver?.disconnect()
        }
    }, [currentStep, isOpen, updateLayout])

    if (!isOpen || !currentStep) {
        return null
    }

    const isLastStep = stepIndex === steps.length - 1

    return createPortal(
        <div className="guidance-tour-layer">
            {layout?.spotlight && (
                <div
                    className="guidance-tour-spotlight"
                    aria-hidden="true"
                    style={{
                        top: layout.spotlight.top,
                        left: layout.spotlight.left,
                        width: layout.spotlight.width,
                        height: layout.spotlight.height,
                    }}
                />
            )}
            <div
                ref={cardRef}
                className={`guidance-tour-card${layout?.spotlight ? '' : ' guidance-tour-card-fallback'}`}
                role="dialog"
                aria-modal="true"
                aria-labelledby={titleId}
                aria-describedby={descriptionId}
                aria-label="Editor walkthrough"
                style={layout?.spotlight ? { top: layout.top, left: layout.left } : undefined}
            >
                <div ref={dialogRef} className="guidance-tour-dialog" tabIndex={-1}>
                    <div className="guidance-tour-header">
                        <div>
                            <span id={progressId} className="guidance-tour-progress" aria-live="polite">
                                {stepIndex + 1} of {steps.length}
                            </span>
                            <h2 id={titleId}>{currentStep.title}</h2>
                        </div>
                        <button
                            ref={closeButtonRef}
                            type="button"
                            className="guidance-dialog-close"
                            aria-label="Close editor walkthrough"
                            onClick={handleSkip}
                        >
                            <X size={16} aria-hidden="true" />
                        </button>
                    </div>
                    <p id={descriptionId} className="guidance-tour-copy">{currentStep.body}</p>
                    {currentStep.media === 'connect-ports' && <TutorialMedia />}
                    <div className="guidance-tour-footer">
                        <button type="button" className="guidance-secondary-button" onClick={handleSkip}>Skip tour</button>
                        <div className="guidance-tour-navigation">
                            <button
                                type="button"
                                className="guidance-secondary-button guidance-tour-back"
                                disabled={stepIndex === 0}
                                aria-describedby={progressId}
                                onClick={() => setStepIndex((current) => Math.max(0, current - 1))}
                            >
                                <ChevronLeft size={14} aria-hidden="true" />
                                Back
                            </button>
                            {isLastStep ? (
                                <button type="button" className="guidance-primary-button" onClick={handleFinish}>
                                    Finish
                                    <Check size={14} aria-hidden="true" />
                                </button>
                            ) : (
                                <button type="button" className="guidance-primary-button" onClick={() => setStepIndex((current) => Math.min(steps.length - 1, current + 1))}>
                                    Next
                                    <ChevronRight size={14} aria-hidden="true" />
                                </button>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>,
        document.body,
    )
}
