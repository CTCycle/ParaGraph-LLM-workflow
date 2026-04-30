import { expect, test } from '@playwright/test'

import { setupMockBackend } from './mockBackend'

function buildWorkflowBundleJson(): string {
    const promptManifest = {
        id: 'PROMPT',
        version: 1,
        name: 'Prompt',
        category: 'input',
        description: 'Static prompt',
        inputs: [],
        outputs: [
            {
                name: 'text',
                data_type: 'TEXT',
                required: true,
                accepts_multiple: false,
                description: 'Prompt text',
            },
        ],
        parameters: [
            {
                name: 'prompt_text',
                data_type: 'TEXT',
                default: 'Hello from import',
                constraints: {},
                ui_control: 'text',
                description: 'Prompt value',
            },
        ],
        ui: {
            default_width: 320,
            accent_color: '#4aa3ff',
            collapsed_by_default: false,
        },
        runtime: {
            executor_key: 'prompt',
            cacheable: false,
            deterministic: true,
            side_effecting: false,
            plugin: null,
        },
    }

    const textOutputManifest = {
        id: 'TEXT_OUTPUT',
        version: 1,
        name: 'Text Output',
        category: 'output',
        description: 'Terminal text output node',
        inputs: [
            {
                name: 'text',
                data_type: 'TEXT',
                required: true,
                accepts_multiple: false,
                description: 'Input text',
            },
        ],
        outputs: [],
        parameters: [],
        ui: {
            default_width: 320,
            accent_color: '#4aa3ff',
            collapsed_by_default: false,
        },
        runtime: {
            executor_key: 'text_output',
            cacheable: false,
            deterministic: true,
            side_effecting: false,
            plugin: null,
        },
    }

    return JSON.stringify(
        {
            bundle_version: 1,
            app: 'ParaGraph',
            created_at: '2026-03-24T00:00:00Z',
            workflow: {
                name: 'Shared Workflow',
                definition: {
                    schema_version: 2,
                    nodes: [
                        {
                            node_id: 'prompt_1',
                            node_type: 'PROMPT',
                            node_version: 1,
                            parameters: { prompt_text: 'Hello from import' },
                        },
                        {
                            node_id: 'output_1',
                            node_type: 'TEXT_OUTPUT',
                            node_version: 1,
                            parameters: {},
                        },
                    ],
                    connections: [
                        {
                            from_node: 'prompt_1',
                            connection_type: 'data',
                            from_output: 'text',
                            to_node: 'output_1',
                            to_input: 'text',
                        },
                    ],
                    metadata: {},
                },
                visual_graph: {
                    schema_version: 2,
                    nodes: [
                        { node_id: 'prompt_1', x: 80, y: 120, width: 320, height: 190, collapsed: false },
                        { node_id: 'output_1', x: 520, y: 120, width: 320, height: 190, collapsed: false },
                    ],
                    groups: [],
                    comments: [],
                },
            },
            required_nodes: [promptManifest, textOutputManifest],
        },
        null,
        2,
    )
}

test('Workflow page imports bundle and runs through deterministic mocked execution', async ({ page }) => {
    const state = await setupMockBackend(page, 'Hello deterministic output')

    await page.goto('/')

    const fileChooserPromise = page.waitForEvent('filechooser')
    await page.getByRole('button', { name: 'Import JSON' }).click()
    const fileChooser = await fileChooserPromise
    await fileChooser.setFiles({
        name: 'workflow.json',
        mimeType: 'application/json',
        buffer: Buffer.from(buildWorkflowBundleJson(), 'utf-8'),
    })

    await expect(page.getByText(/Imported workflow "Shared Workflow"/)).toBeVisible()

    await page.getByRole('button', { name: 'Run Workflow' }).click()

    await expect(page.getByText('Workflow completed')).toBeVisible()
    await expect(page.getByText('Hello deterministic output')).toBeVisible()

    expect(state.compileCalls).toBeGreaterThan(0)
    expect(state.startCalls).toBeGreaterThan(0)
    expect(state.pollCalls).toBeGreaterThan(0)

    const wsUrls = await page.evaluate(() => {
        return (window as unknown as { __paragraphWsUrls?: string[] }).__paragraphWsUrls || []
    })
    expect(wsUrls.some((url) => url.includes('/executions/ws/runs/run-e2e'))).toBeTruthy()
})

test('Workflow run action ignores rapid repeated clicks while a run is in progress', async ({ page }) => {
    const state = await setupMockBackend(page, 'Hello lock output')

    await page.goto('/')

    const fileChooserPromise = page.waitForEvent('filechooser')
    await page.getByRole('button', { name: 'Import JSON' }).click()
    const fileChooser = await fileChooserPromise
    await fileChooser.setFiles({
        name: 'workflow.json',
        mimeType: 'application/json',
        buffer: Buffer.from(buildWorkflowBundleJson(), 'utf-8'),
    })

    await expect(page.getByText(/Imported workflow "Shared Workflow"/)).toBeVisible()

    await page.evaluate(() => {
        const runButton = Array.from(document.querySelectorAll('button')).find(
            (button) => button.textContent?.trim() === 'Run Workflow',
        )
        if (!runButton) {
            throw new Error('Run Workflow button not found')
        }
        runButton.click()
        runButton.click()
        runButton.click()
        runButton.click()
    })

    await expect(page.getByText('Workflow completed')).toBeVisible()
    expect(state.compileCalls).toBe(1)
    expect(state.startCalls).toBe(1)
})

test('Workflow import cancel does not leave a banner message behind', async ({ page }) => {
    await setupMockBackend(page)

    await page.goto('/')

    const fileChooserPromise = page.waitForEvent('filechooser')
    await page.getByRole('button', { name: 'Import JSON' }).click()
    const fileChooser = await fileChooserPromise
    await fileChooser.setFiles([])

    await expect(page.getByText('Workflow import cancelled')).toHaveCount(0)
    await expect(page.getByText('Ready')).toBeVisible()
})

function buildWorkflowConnectedBundleJson(): string {
    const promptManifest = {
        id: 'PROMPT',
        version: 1,
        name: 'Prompt',
        category: 'input',
        description: 'Prompt source',
        inputs: [],
        outputs: [{ name: 'text', data_type: 'TEXT', required: true, accepts_multiple: false, description: 'Text output' }],
        parameters: [{ name: 'prompt_text', data_type: 'TEXT', default: 'Hi', constraints: {}, ui_control: 'text', description: 'Prompt value' }],
        ui: { default_width: 320, accent_color: '#4aa3ff', collapsed_by_default: false },
        runtime: { executor_key: 'prompt', cacheable: false, deterministic: true, side_effecting: false, plugin: null },
    }

    const llmChatManifest = {
        id: 'LLM_CHAT',
        version: 1,
        name: 'LLM Chat',
        category: 'processing',
        description: 'Chat node',
        inputs: [{ name: 'user_prompt', data_type: 'TEXT', required: false, accepts_multiple: false, description: 'User prompt' }],
        outputs: [{ name: 'response', data_type: 'TEXT', required: true, accepts_multiple: false, description: 'Model response' }],
        controllers: [{ name: 'model', required: false, description: 'Model binding' }],
        parameters: [
            { name: 'context_window', data_type: 'NUMBER', default: 0, constraints: { min: 0, max: 64000, step: 1 }, ui_control: 'number', description: 'Context window' },
            { name: 'max_tokens', data_type: 'NUMBER', default: 64, constraints: { min: 1, max: 4096, step: 1 }, ui_control: 'number', description: 'Maximum tokens' },
            { name: 'use_reasoning', data_type: 'BOOLEAN', default: false, constraints: {}, ui_control: 'toggle', description: 'Use reasoning mode' },
        ],
        ui: { default_width: 360, accent_color: '#4aa3ff', collapsed_by_default: false },
        runtime: { executor_key: 'llm_chat', cacheable: false, deterministic: false, side_effecting: false, plugin: null },
    }

    const textOutputManifest = {
        id: 'TEXT_OUTPUT',
        version: 1,
        name: 'Text Output',
        category: 'output',
        description: 'Terminal text output node',
        inputs: [{ name: 'text', data_type: 'TEXT', required: true, accepts_multiple: false, description: 'Input text' }],
        outputs: [],
        parameters: [],
        ui: { default_width: 320, accent_color: '#4aa3ff', collapsed_by_default: false },
        runtime: { executor_key: 'text_output', cacheable: false, deterministic: true, side_effecting: false, plugin: null },
    }

    return JSON.stringify(
        {
            bundle_version: 1,
            app: 'ParaGraph',
            created_at: '2026-03-24T00:00:00Z',
            workflow: {
                name: 'Connection Drag Workflow',
                definition: {
                    schema_version: 2,
                    nodes: [
                        { node_id: 'prompt_1', node_type: 'PROMPT', node_version: 1, parameters: { prompt_text: 'Hello' } },
                        { node_id: 'chat_1', node_type: 'LLM_CHAT', node_version: 1, parameters: { context_window: 0, max_tokens: 64, use_reasoning: false } },
                        { node_id: 'output_1', node_type: 'TEXT_OUTPUT', node_version: 1, parameters: {} },
                    ],
                    connections: [
                        {
                            from_node: 'prompt_1',
                            connection_type: 'data',
                            from_output: 'text',
                            to_node: 'chat_1',
                            to_input: 'user_prompt',
                        },
                        {
                            from_node: 'chat_1',
                            connection_type: 'data',
                            from_output: 'response',
                            to_node: 'output_1',
                            to_input: 'text',
                        },
                    ],
                    metadata: {},
                },
                visual_graph: {
                    schema_version: 2,
                    nodes: [
                        { node_id: 'prompt_1', x: 160, y: 180, width: 320, height: 210, collapsed: false },
                        { node_id: 'chat_1', x: 430, y: 190, width: 360, height: 230, collapsed: false },
                        { node_id: 'output_1', x: 700, y: 200, width: 320, height: 190, collapsed: false },
                    ],
                    groups: [],
                    comments: [],
                },
            },
            required_nodes: [promptManifest, llmChatManifest, textOutputManifest],
        },
        null,
        2,
    )
}

test('Workflow canvas renders imported links and clears them through the UI', async ({ page }) => {
    await setupMockBackend(page)
    await page.goto('/')

    const fileChooserPromise = page.waitForEvent('filechooser')
    await page.getByRole('button', { name: 'Import JSON' }).click()
    const fileChooser = await fileChooserPromise
    await fileChooser.setFiles({
        name: 'workflow-connectors.json',
        mimeType: 'application/json',
        buffer: Buffer.from(buildWorkflowConnectedBundleJson(), 'utf-8'),
    })

    await expect(page.getByText(/Imported workflow "Connection Drag Workflow"/)).toBeVisible()
    await expect(page.locator('.react-flow__edge-path')).toHaveCount(2)

    await page.getByRole('button', { name: 'Clear Links' }).click()
    await expect(page.locator('.react-flow__edge-path')).toHaveCount(0)
})

test('Workflow mobile layout keeps actions and canvas usable', async ({ page }) => {
    await setupMockBackend(page)
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/')

    const runButton = page.getByRole('button', { name: 'Run Workflow' })
    await expect(runButton).toBeVisible()
    await expect(runButton).toBeInViewport()

    const canvasPanelBounds = await page.locator('.workflow-canvas-panel').boundingBox()
    expect(canvasPanelBounds).not.toBeNull()
    expect((canvasPanelBounds as { height: number }).height).toBeGreaterThan(320)
    await expect(page.locator('.workflow-canvas-panel')).toBeInViewport()
})

test('Workflow status area renders long compile diagnostics without truncating content', async ({ page }) => {
    await setupMockBackend(page)
    const longDiagnostic =
        'Compilation failed: Invalid metadata filter JSON at node PROMPT_1; expected object with key-value pairs but received malformed input. Keep this full message visible for debugging.'

    await page.route('**/api/executions/compile', async (route) => {
        await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
                valid: false,
                diagnostics: [{ message: longDiagnostic }],
                plan: null,
            }),
        })
    })

    await page.goto('/')
    const fileChooserPromise = page.waitForEvent('filechooser')
    await page.getByRole('button', { name: 'Import JSON' }).click()
    const fileChooser = await fileChooserPromise
    await fileChooser.setFiles({
        name: 'workflow.json',
        mimeType: 'application/json',
        buffer: Buffer.from(buildWorkflowBundleJson(), 'utf-8'),
    })

    await page.getByRole('button', { name: 'Run Workflow' }).click()
    await expect(page.locator('.workflow-toolbar-status strong')).toHaveText(longDiagnostic)
})

test('Workflow prevents re-run while execution error modal is open', async ({ page }) => {
    await setupMockBackend(page)

    await page.route('**/api/executions/run-e2e', async (route) => {
        await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
                run_id: 'run-e2e',
                workflow_id: null,
                plan_id: 'plan-e2e',
                status: 'failed',
                created_at: '2026-03-24T00:00:00Z',
                updated_at: '2026-03-24T00:00:00Z',
                progress: 100,
                steps: [],
                outputs: {},
                error: 'Deterministic execution failure for modal test',
            }),
        })
    })

    await page.goto('/')
    const fileChooserPromise = page.waitForEvent('filechooser')
    await page.getByRole('button', { name: 'Import JSON' }).click()
    const fileChooser = await fileChooserPromise
    await fileChooser.setFiles({
        name: 'workflow.json',
        mimeType: 'application/json',
        buffer: Buffer.from(buildWorkflowBundleJson(), 'utf-8'),
    })

    await page.getByRole('button', { name: 'Run Workflow' }).click()
    await expect(page.getByRole('dialog', { name: 'Workflow execution error' })).toBeVisible()

    const runButton = page.getByRole('button', { name: 'Run Workflow' })
    await expect(runButton).toBeDisabled()

    await page.getByRole('button', { name: 'Close error dialog' }).click()
    await expect(page.getByRole('dialog', { name: 'Workflow execution error' })).toHaveCount(0)
    await expect(runButton).toBeEnabled()
})
