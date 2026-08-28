import { RotateCcw } from 'lucide-react'
import { useEffect, useState } from 'react'

function prefersReducedMotion(): boolean {
    return typeof window !== 'undefined'
        && typeof window.matchMedia === 'function'
        && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

export default function TutorialMedia() {
    const [animationKey, setAnimationKey] = useState(0)
    const [isReducedMotion, setIsReducedMotion] = useState(prefersReducedMotion)
    const [isPlaying, setIsPlaying] = useState(() => !prefersReducedMotion())

    useEffect(() => {
        if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
            return
        }

        const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
        const handleChange = (event: MediaQueryListEvent): void => {
            setIsReducedMotion(event.matches)
            setIsPlaying(!event.matches)
        }
        mediaQuery.addEventListener('change', handleChange)
        return () => mediaQuery.removeEventListener('change', handleChange)
    }, [])

    function replay(): void {
        setAnimationKey((current) => current + 1)
        setIsPlaying(!isReducedMotion)
    }

    return (
        <div className="guidance-tutorial-media">
            <div
                key={animationKey}
                className={`guidance-connection-demo${isPlaying ? ' guidance-connection-demo-playing' : ''}`}
                role="img"
                aria-label="Illustration of dragging a connector from an output port to an input port"
                onAnimationEnd={() => setIsPlaying(false)}
            >
                <span className="guidance-demo-port guidance-demo-port-output" aria-hidden="true" />
                <span className="guidance-demo-connector" aria-hidden="true" />
                <span className="guidance-demo-port guidance-demo-port-input" aria-hidden="true" />
            </div>
            <button type="button" className="guidance-demo-replay" onClick={replay}>
                <RotateCcw size={13} aria-hidden="true" />
                {isPlaying ? 'Playing' : 'Replay demonstration'}
            </button>
        </div>
    )
}
