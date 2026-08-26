import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'

import FeatureTip from './FeatureTip'
import GuidanceDialog from './GuidanceDialog'
import GuidedTour from './GuidedTour'
import HelpPopover from './HelpPopover'
import { GuidanceProvider, useGuidance } from './GuidanceContext'
import { GUIDANCE_SCHEMA_VERSION, GUIDANCE_STORAGE_KEY, readGuidanceState } from './guidancePersistence'
import type { TourStepDefinition } from './types'

describe('guidance primitives', () => {
    it('renders and dismisses an inline feature tip', async () => {
        const user = userEvent.setup()
        const onDismiss = vi.fn()

        render(
            <FeatureTip title="Helpful hint" onDismiss={onDismiss}>
                <p>Short contextual guidance.</p>
            </FeatureTip>,
        )

        expect(screen.getByRole('note', { name: 'Helpful hint' })).toBeVisible()
        await user.click(screen.getByRole('button', { name: 'Dismiss' }))
        expect(onDismiss).toHaveBeenCalledOnce()
    })

    it('restores focus after closing the accessible dialog with Escape', async () => {
        const user = userEvent.setup()

        function DialogHarness() {
            const [isOpen, setIsOpen] = useState(false)
            return (
                <>
                    <button type="button" onClick={() => setIsOpen(true)}>Launch help</button>
                    <GuidanceDialog
                        isOpen={isOpen}
                        ariaLabel="Example dialog"
                        title="Example dialog"
                        description="Dialog description"
                        onRequestClose={() => setIsOpen(false)}
                        actions={<button type="button">Done</button>}
                    >
                        <p>Dialog content</p>
                    </GuidanceDialog>
                </>
            )
        }

        render(<DialogHarness />)
        const launcher = screen.getByRole('button', { name: 'Launch help' })
        await user.click(launcher)

        const dialog = screen.getByRole('dialog', { name: 'Example dialog' })
        expect(dialog).toHaveAttribute('aria-modal', 'true')
        expect(screen.getByRole('button', { name: 'Close Example dialog' })).toBeInTheDocument()

        await user.keyboard('{Escape}')
        await waitFor(() => {
            expect(screen.queryByRole('dialog', { name: 'Example dialog' })).toBeNull()
            expect(launcher).toHaveFocus()
        })
    })

    it('opens a manual popover and closes it with Escape', async () => {
        const user = userEvent.setup()
        render(
            <>
                <HelpPopover title="About Chat" triggerLabel="Conversation help">
                    <p>Each send runs the current workflow once.</p>
                </HelpPopover>
                <button type="button">Outside</button>
            </>,
        )

        const trigger = screen.getByRole('button', { name: 'Conversation help' })
        await user.click(trigger)
        expect(screen.getByRole('dialog', { name: 'About Chat' })).toBeInTheDocument()
        await user.click(screen.getByRole('button', { name: 'Outside' }))

        await waitFor(() => {
            expect(screen.queryByRole('dialog', { name: 'About Chat' })).toBeNull()
            expect(trigger).toHaveFocus()
        })

        await user.click(trigger)
        await user.keyboard('{Escape}')

        await waitFor(() => {
            expect(screen.queryByRole('dialog', { name: 'About Chat' })).toBeNull()
            expect(trigger).toHaveFocus()
        })
    })

    it('reopens guidance only when its content version advances', () => {
        window.localStorage.setItem(
            GUIDANCE_STORAGE_KEY,
            JSON.stringify({
                schemaVersion: GUIDANCE_SCHEMA_VERSION,
                items: {
                    'editor-tour': { contentVersion: 1, status: 'dismissed' },
                },
            }),
        )

        function VersionProbe() {
            const { shouldShow } = useGuidance()
            return (
                <>
                    <output data-testid="same-version">{String(shouldShow('editor-tour', 1))}</output>
                    <output data-testid="new-version">{String(shouldShow('editor-tour', 2))}</output>
                </>
            )
        }

        render(
            <GuidanceProvider>
                <VersionProbe />
            </GuidanceProvider>,
        )

        expect(screen.getByTestId('same-version')).toHaveTextContent('false')
        expect(screen.getByTestId('new-version')).toHaveTextContent('true')
    })

    it('uses a centered fallback and focuses the close control when a tour target is missing', async () => {
        render(
            <GuidedTour
                isOpen
                tourId="editor"
                steps={[{ id: 'missing', target: 'missing-target', title: 'Missing target', body: 'Fallback body', placement: 'right' }]}
                onRequestClose={vi.fn()}
            />,
        )

        const dialog = screen.getByRole('dialog', { name: 'Missing target' })
        expect(dialog).toHaveClass('guidance-tour-card-fallback')
        await waitFor(() => {
            expect(screen.getByRole('button', { name: 'Close editor walkthrough' })).toHaveFocus()
        })
    })

    it('supports tour navigation and persists completion state', async () => {
        const user = userEvent.setup()
        const steps: TourStepDefinition[] = [
            { id: 'first', target: 'tour-first', title: 'First step', body: 'First body', placement: 'bottom' },
            { id: 'second', target: 'tour-second', title: 'Second step', body: 'Second body', placement: 'bottom' },
        ]

        render(
            <GuidanceProvider>
                <button type="button">Launcher</button>
                <div data-guidance-target="tour-first">First target</div>
                <div data-guidance-target="tour-second">Second target</div>
                <GuidedTour isOpen tourId="editor" steps={steps} onRequestClose={vi.fn()} />
            </GuidanceProvider>,
        )

        expect(screen.getByText('1 of 2')).toBeVisible()
        await user.click(screen.getByRole('button', { name: 'Next' }))
        expect(screen.getByText('2 of 2')).toBeVisible()
        await user.click(screen.getByRole('button', { name: 'Back' }))
        expect(screen.getByText('1 of 2')).toBeVisible()
        await user.click(screen.getByRole('button', { name: 'Next' }))
        await user.click(screen.getByRole('button', { name: 'Finish' }))

        await waitFor(() => {
            expect(readGuidanceState().items['editor-tour']).toEqual({ contentVersion: 1, status: 'completed' })
        })
    })
})
