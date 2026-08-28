import { expect, test } from '@playwright/test'

import { setupMockBackend } from './mockBackend'

test('Nodes page import modal validates payloads and handles success/error responses', async ({ page }) => {
    await setupMockBackend(page)

    await page.goto('/nodes')

    await page.getByRole('button', { name: 'Open custom node JSON import' }).click()
    const dialog = page.getByRole('dialog', { name: 'Custom node JSON import' })

    await dialog.getByRole('textbox').fill('{"bad":"payload"}')
    await dialog.getByRole('button', { name: 'Validate' }).click()
    await expect(dialog.getByRole('alert')).toContainText('JSON must contain a node manifest object')

    const validManifest = {
        id: 'CUSTOM_NODE',
        version: 1,
        name: 'Custom Node',
        category: 'processing',
        description: 'Custom processing node',
        inputs: [
            {
                name: 'input_text',
                data_type: 'TEXT',
                required: true,
                accepts_multiple: false,
                description: 'Input text',
            },
        ],
        outputs: [
            {
                name: 'result',
                data_type: 'TEXT',
                required: true,
                accepts_multiple: false,
                description: 'Output text',
            },
        ],
        parameters: [],
        ui: {
            default_width: 320,
            accent_color: '#4aa3ff',
            collapsed_by_default: false,
        },
        runtime: {
            executor_key: 'custom.executor',
            cacheable: false,
            deterministic: true,
            side_effecting: false,
            plugin: null,
        },
    }

    await dialog.getByRole('textbox').fill(JSON.stringify(validManifest))
    await dialog.getByRole('button', { name: 'Import Node' }).click()
    await expect(page.getByText('Imported CUSTOM_NODE v1')).toBeVisible()

    await page.getByRole('button', { name: 'Open custom node JSON import' }).click()
    const secondDialog = page.getByRole('dialog', { name: 'Custom node JSON import' })

    await secondDialog.getByRole('textbox').fill(
        JSON.stringify({
            ...validManifest,
            id: 'FAIL_NODE',
        }),
    )
    await secondDialog.getByRole('button', { name: 'Import Node' }).click()
    await expect(secondDialog.getByRole('alert')).toContainText('Duplicate node id/version')
})

test('Configurations and Models pages complete deterministic smoke flows', async ({ page }) => {
    await setupMockBackend(page)

    await page.goto('/config')

    await expect(page.getByText('Configuration loaded')).toBeVisible()

    await page.getByRole('button', { name: 'Load' }).click()
    const loadDialog = page.getByRole('dialog', { name: 'Load configuration' })
    await loadDialog.getByRole('button', { name: 'Load' }).click()
    await expect(page.getByText("Loaded configuration 'workstation'" )).toBeVisible()

    await page.getByRole('button', { name: 'Save' }).click()
    const saveDialog = page.getByRole('dialog', { name: 'Save configuration' })
    await saveDialog.getByRole('textbox', { name: 'Configuration name' }).fill('browser profile')
    await saveDialog.getByRole('button', { name: 'Save' }).click()
    await expect(page.getByText("Saved configuration 'browser profile'" )).toBeVisible()

    const ollamaPanel = page.locator('section.config-panel').filter({
        has: page.getByRole('heading', { name: 'Ollama' }),
    })
    await ollamaPanel.getByRole('button', { name: 'Check Status' }).click()
    await expect(page.getByText('Ollama reachable (mocked)')).toBeVisible()

    await page.getByRole('link', { name: 'Models' }).click()
    await expect(page.getByText('llama3.2')).toBeVisible()
    await expect(page.getByText('acme/model')).toBeVisible()

    await page.getByRole('button', { name: 'Pull llama3.2' }).click()
    await expect(page.locator('article', { hasText: 'llama3.2' }).getByText('Pulled')).toBeVisible()

    const modelRow = page.locator('article', { hasText: 'acme/model' })
    await modelRow.getByRole('button', { name: 'Download' }).click()

    await expect(page.getByText('Downloaded Hugging Face model')).toBeVisible()
    await expect(modelRow.getByText('Downloaded')).toBeVisible()
})
