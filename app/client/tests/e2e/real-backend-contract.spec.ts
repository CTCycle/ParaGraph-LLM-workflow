import { expect, test } from '@playwright/test'

test('loads the live catalog and compiles a real prompt-to-output graph', async ({ page }) => {
    await expect.poll(
        async () => (await page.request.get('/api/nodes/catalog')).ok(),
        { timeout: 60_000, intervals: [500, 1_000, 2_000] },
    ).toBeTruthy()
    const catalogResponse = await page.request.get('/api/nodes/catalog')
    expect(catalogResponse.ok()).toBeTruthy()
    const catalog = await catalogResponse.json() as { nodes: Array<{ id: string; version: number }> }
    expect(catalog.nodes.some((node) => node.id === 'HTTP_REQUEST' && node.version === 1)).toBeTruthy()
    expect(catalog.nodes.some((node) => node.id === 'API_CALL')).toBeFalsy()

    const compileResponse = await page.request.post('/api/executions/compile', {
        data: {
            definition: {
                schema_version: 2,
                nodes: [
                    {
                        node_id: 'prompt_live',
                        node_type: 'PROMPT',
                        node_version: 1,
                        parameters: { prompt_text: 'Live contract check' },
                    },
                    {
                        node_id: 'output_live',
                        node_type: 'TEXT_OUTPUT',
                        node_version: 1,
                        parameters: {},
                    },
                ],
                connections: [
                    {
                        from_node: 'prompt_live',
                        from_output: 'text',
                        to_node: 'output_live',
                        to_input: 'text',
                    },
                ],
                metadata: {},
            },
        },
    })
    expect(compileResponse.ok()).toBeTruthy()
    const compiled = await compileResponse.json() as { valid: boolean; diagnostics: Array<{ level: string }> }
    expect(compiled.valid).toBeTruthy()
    expect(compiled.diagnostics.filter((item) => item.level === 'error')).toHaveLength(0)

    await page.goto('/')
    await page.getByRole('button', { name: 'Show node tree' }).click()
    await page.getByRole('button', { name: /Web/ }).click()
    await expect(page.getByRole('tree', { name: 'Node catalog tree' })).toBeVisible()
    await expect(page.getByText('Secure HTTP Request')).toBeVisible()
})
