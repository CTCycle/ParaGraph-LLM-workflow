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
    const plan = (compiled as { plan?: unknown }).plan
    expect(plan).toBeTruthy()

    const startResponse = await page.request.post('/api/executions', {
        data: {
            workflow_id: 'browser-live-contract',
            execution_session_id: 'browser-live-session',
            plan,
        },
    })
    expect(startResponse.status()).toBe(202)
    const started = await startResponse.json() as {
        run_id: string
        status: string
        execution_session_id: string
    }
    expect(started.status).toBe('queued')
    expect(started.execution_session_id).toBe('browser-live-session')

    await expect.poll(
        async () => {
            const response = await page.request.get(`/api/executions/${started.run_id}`)
            expect(response.ok()).toBeTruthy()
            const payload = await response.json() as { status: string }
            return payload.status
        },
        { timeout: 60_000, intervals: [250, 500, 1_000] },
    ).toBe('completed')

    const runResponse = await page.request.get(`/api/executions/${started.run_id}`)
    expect(runResponse.ok()).toBeTruthy()
    const run = await runResponse.json() as {
        status: string
        execution_session_id: string
        outputs: Record<string, Record<string, unknown>>
    }
    expect(run.status).toBe('completed')
    expect(run.execution_session_id).toBe('browser-live-session')
    expect(run.outputs).toEqual({ output_live: { text: 'Live contract check' } })

    const eventsResponse = await page.request.get(`/api/executions/${started.run_id}/events`)
    expect(eventsResponse.ok()).toBeTruthy()
    const eventsPayload = await eventsResponse.json() as {
        events: Array<{ event_type: string; sequence: number }>
    }
    const eventTypes = eventsPayload.events.map((event) => event.event_type)
    expect(eventTypes[0]).toBe('execution.queued')
    expect(eventTypes.at(-1)).toBe('execution.completed')
    expect(eventTypes.filter((eventType) => eventType === 'execution.started')).toHaveLength(1)
    expect(eventsPayload.events.map((event) => event.sequence)).toEqual(
        eventsPayload.events.map((_, index) => index + 1),
    )

    await page.goto('/')
    await page.getByRole('button', { name: 'Show node tree' }).click()
    await page.getByRole('button', { name: /Web/ }).click()
    await expect(page.getByRole('tree', { name: 'Node catalog tree' })).toBeVisible()
    await expect(page.getByText('Secure HTTP Request')).toBeVisible()
})
