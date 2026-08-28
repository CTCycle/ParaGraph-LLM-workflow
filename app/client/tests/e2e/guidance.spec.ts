import path from 'node:path'

import { expect, test } from '@playwright/test'

import { setupMockBackend } from './mockBackend'

const qaRoot = path.resolve(process.cwd(), '../../assets/QA')

function buildChatBundleJson(): string {
    return JSON.stringify({
        bundle_version: 1,
        app: 'ParaGraph',
        created_at: '2026-08-26T00:00:00Z',
        workflow: {
            name: 'Chat Guidance Workflow',
            definition: {
                schema_version: 2,
                nodes: [
                    { node_id: 'chat_1', node_type: 'CHAT_INPUT', node_version: 1, parameters: { message: '' } },
                ],
                connections: [],
                metadata: {},
            },
            visual_graph: {
                schema_version: 2,
                nodes: [{ node_id: 'chat_1', x: 220, y: 160, width: 360, height: 280, collapsed: false }],
                groups: [],
                comments: [],
            },
        },
        required_nodes: [
            {
                id: 'CHAT_INPUT',
                version: 1,
                name: 'Chat',
                category: 'input',
                description: 'Submit a transient message into the workflow.',
                inputs: [],
                outputs: [
                    {
                        name: 'text',
                        data_type: 'TEXT',
                        required: true,
                        accepts_multiple: false,
                        description: 'Transient chat message',
                    },
                ],
                controllers: [
                    {
                        name: 'history',
                        data_type: 'CHAT_HISTORY',
                        required: true,
                        description: 'Chat history controller',
                    },
                ],
                parameters: [
                    {
                        name: 'message',
                        data_type: 'TEXT',
                        default: '',
                        constraints: {},
                        ui_control: 'chat-input',
                        description: 'Message to send',
                    },
                ],
                ui: { default_width: 360, accent_color: '#d98b4a', collapsed_by_default: false },
                runtime: {
                    executor_key: 'chat_input',
                    cacheable: false,
                    deterministic: false,
                    side_effecting: false,
                    plugin: null,
                },
            },
        ],
    }, null, 2)
}

test('blank workflow onboarding launches the editor tour and stays dismissed after reload', async ({ page }) => {
    await setupMockBackend(page)
    await page.goto('/')

    const onboarding = page.getByRole('note', { name: 'Workflow getting started' })
    await expect(onboarding).toBeVisible()
    await page.screenshot({ path: path.join(qaRoot, 'guidance-01-empty-workflow.png'), fullPage: true })

    await onboarding.getByRole('button', { name: 'Show me' }).click()
    const tour = page.locator('.guidance-tour-card[role="dialog"]')
    await expect(tour).toBeVisible()
    await expect(tour).toContainText('1 of 4')
    await expect(page.locator('.workflow-library-shell')).toBeVisible()
    await page.screenshot({ path: path.join(qaRoot, 'guidance-02-editor-tour-library.png'), fullPage: true })

    await tour.getByRole('button', { name: 'Next' }).click()
    await expect(tour).toContainText('2 of 4')
    await tour.getByRole('button', { name: 'Next' }).click()
    await expect(tour).toContainText('3 of 4')
    await expect(tour.getByRole('img', { name: /dragging a connector/i })).toBeVisible()
    await page.screenshot({ path: path.join(qaRoot, 'guidance-03-editor-tour-connect.png'), fullPage: true })

    await tour.getByRole('button', { name: 'Next' }).click()
    await expect(tour).toContainText('4 of 4')
    await tour.getByRole('button', { name: 'Finish' }).click()
    await expect(tour).toHaveCount(0)

    await page.reload()
    await expect(page.getByText('Ready')).toBeVisible()
    await expect(page.getByRole('note', { name: 'Workflow getting started' })).toHaveCount(0)
})

test('blank workflow onboarding can jump to the template section', async ({ page }) => {
    await setupMockBackend(page)
    await page.goto('/')

    await page.getByRole('note', { name: 'Workflow getting started' }).getByRole('button', { name: 'Browse templates' }).click()
    await expect(page).toHaveURL(/\/nodes#workflow-templates$/)
    await expect(page.locator('#workflow-templates')).toBeInViewport()
})

test('Help opens Tips & Tricks from the primary routes and configuration guidance persists', async ({ page }) => {
    await setupMockBackend(page)
    await page.setViewportSize({ width: 1024, height: 768 })
    await page.goto('/config')

    await expect(page.getByText('Configuration loaded')).toBeVisible()
    const setupTip = page.getByRole('note', { name: 'Set up a provider before running' })
    await expect(setupTip).toBeVisible()
    await page.screenshot({ path: path.join(qaRoot, 'guidance-06-config-tip-1024.png'), fullPage: true })
    await setupTip.getByRole('button', { name: 'Dismiss', exact: true }).click()
    await page.reload()
    await expect(page.getByText('Configuration loaded')).toBeVisible()
    await expect(page.getByRole('note', { name: 'Set up a provider before running' })).toHaveCount(0)

    for (const route of ['/', '/nodes', '/models', '/config']) {
        await page.goto(route)
        await page.getByRole('button', { name: 'Help' }).click()
        const dialog = page.locator('.guidance-dialog[role="dialog"]')
        await expect(dialog).toBeVisible()
        await expect(dialog).toContainText('Start with a template')
        if (route === '/') {
            await page.screenshot({ path: path.join(qaRoot, 'guidance-05-tips-tricks.png'), fullPage: true })
        }
        if (route === '/nodes') {
            await dialog.getByRole('button', { name: 'Replay editor tour' }).click()
            await expect(page).toHaveURL(/\/$/)
            const tour = page.locator('.guidance-tour-card[role="dialog"]')
            await expect(tour).toContainText('1 of 4')
            await tour.getByRole('button', { name: 'Skip tour' }).click()
            await expect(tour).toHaveCount(0)
        } else {
            await dialog.getByRole('button', { name: 'Close Tips and tricks' }).click()
            await expect(dialog).toHaveCount(0)
        }
    }
})

test('Chat guidance explains disconnected history without opening automatically', async ({ page }) => {
    await setupMockBackend(page)
    await page.goto('/')

    const fileChooserPromise = page.waitForEvent('filechooser')
    await page.getByRole('button', { name: 'Import JSON' }).click()
    const fileChooser = await fileChooserPromise
    await fileChooser.setFiles({
        name: 'chat-guidance.json',
        mimeType: 'application/json',
        buffer: Buffer.from(buildChatBundleJson(), 'utf-8'),
    })

    await expect(page.getByText(/Imported workflow "Chat Guidance Workflow"/)).toBeVisible()
    await expect(page.getByText(/Connect a Chat History node to Chat’s history port/)).toBeVisible()
    await expect(page.getByRole('dialog', { name: 'About Chat history' })).toHaveCount(0)

    await page.getByRole('button', { name: 'Conversation help' }).click()
    const popover = page.getByRole('dialog', { name: 'About Chat history' })
    await expect(popover).toBeVisible()
    await expect(popover).toContainText('Each send runs the current workflow once.')
    await page.screenshot({ path: path.join(qaRoot, 'guidance-04-chat-help-popover.png'), fullPage: true })
    await page.keyboard.press('Escape')
    await expect(popover).toHaveCount(0)
})

test('tour and connection demonstration stay within the 1024px viewport with reduced motion', async ({ page }) => {
    await setupMockBackend(page)
    await page.setViewportSize({ width: 1024, height: 768 })
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.goto('/')

    await page.getByRole('note', { name: 'Workflow getting started' }).getByRole('button', { name: 'Show me' }).click()
    const tour = page.locator('.guidance-tour-card[role="dialog"]')
    await tour.getByRole('button', { name: 'Next' }).click()
    await tour.getByRole('button', { name: 'Next' }).click()

    const bounds = await tour.evaluate((element) => {
        const rect = element.getBoundingClientRect()
        const styles = getComputedStyle(element)
        return { left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom, height: rect.height, topStyle: styles.top, maxHeight: styles.maxHeight }
    })
    expect(bounds.left).toBeGreaterThanOrEqual(0)
    expect(bounds.top).toBeGreaterThanOrEqual(0)
    expect(bounds.right).toBeLessThanOrEqual(1024)
    expect(bounds.bottom).toBeLessThanOrEqual(768)
    expect(await page.evaluate(() => Math.max(document.body.scrollWidth, document.documentElement.scrollWidth))).toBeLessThanOrEqual(1024)
    await expect(page.locator('.guidance-demo-connector')).toHaveCSS('animation-name', 'none')
    await expect(page.locator('.guidance-demo-connector')).toHaveCSS('opacity', '0.9')
    await expect(tour.getByRole('button', { name: 'Replay demonstration' })).toBeVisible()
})
