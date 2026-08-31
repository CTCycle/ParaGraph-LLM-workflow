import { Page } from '@playwright/test'

type AnyRecord = Record<string, unknown>

export type MockBackendState = {
    compileCalls: number
    startCalls: number
    pollCalls: number
    nodeCatalog: AnyRecord[]
}

function buildPromptManifest(): AnyRecord {
    return {
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
                default: 'hello',
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
}

function buildTextOutputManifest(): AnyRecord {
    return {
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
}

function buildConfigurationPayload(): AnyRecord {
    return {
        session_name: 'default',
        provider_configurations: [
            {
                provider: 'openai',
                api_key: 'sk-test',
                has_api_key: true,
                base_url: null,
                metadata: {},
            },
            {
                provider: 'huggingface',
                api_key: 'hf-test',
                has_api_key: true,
                base_url: null,
                metadata: {},
            },
            {
                provider: 'ollama',
                api_key: null,
                has_api_key: false,
                base_url: 'http://127.0.0.1:11434',
                metadata: {
                    chat_model: 'llama3.2',
                    embedding_model: 'nomic-embed-text',
                },
            },
        ],
    }
}

function buildProviderCatalog(): AnyRecord[] {
    return [
        {
            provider: 'ollama',
            label: 'Ollama',
            configuration_kind: 'local',
            model_source: 'live',
            default_base_url: 'http://127.0.0.1:11434',
            default_chat_model: 'llama3.2',
            default_embedding_model: 'nomic-embed-text',
            requires_api_key: false,
            supports_status_check: true,
            supports_chat: true,
            supports_embeddings: true,
            supports_structured_output: true,
            supports_streaming: true,
            supports_tool_calling: false,
            supports_tool_selection: true,
            supports_native_tool_protocol: false,
        },
        {
            provider: 'openai',
            label: 'OpenAI',
            configuration_kind: 'cloud',
            model_source: 'hosted_registry',
            default_base_url: 'https://api.openai.com/v1',
            default_chat_model: null,
            default_embedding_model: null,
            requires_api_key: true,
            supports_status_check: false,
            supports_chat: true,
            supports_embeddings: true,
            supports_structured_output: true,
            supports_streaming: true,
            supports_tool_calling: false,
            supports_tool_selection: true,
            supports_native_tool_protocol: false,
        },
        {
            provider: 'gemini',
            label: 'Google Gemini',
            configuration_kind: 'cloud',
            model_source: 'hosted_registry',
            default_base_url: 'https://generativelanguage.googleapis.com/v1beta',
            default_chat_model: null,
            default_embedding_model: null,
            requires_api_key: true,
            supports_status_check: false,
            supports_chat: true,
            supports_embeddings: true,
            supports_structured_output: true,
            supports_streaming: true,
            supports_tool_calling: false,
            supports_tool_selection: true,
            supports_native_tool_protocol: false,
        },
        {
            provider: 'claude',
            label: 'Anthropic Claude',
            configuration_kind: 'cloud',
            model_source: 'hosted_registry',
            default_base_url: 'https://api.anthropic.com/v1',
            default_chat_model: null,
            default_embedding_model: null,
            requires_api_key: true,
            supports_status_check: false,
            supports_chat: true,
            supports_embeddings: false,
            supports_structured_output: true,
            supports_streaming: true,
            supports_tool_calling: false,
            supports_tool_selection: true,
            supports_native_tool_protocol: false,
        },
        {
            provider: 'deepseek',
            label: 'DeepSeek',
            configuration_kind: 'cloud',
            model_source: 'hosted_registry',
            default_base_url: 'https://api.deepseek.com',
            default_chat_model: null,
            default_embedding_model: null,
            requires_api_key: true,
            supports_status_check: false,
            supports_chat: true,
            supports_embeddings: false,
            supports_structured_output: true,
            supports_streaming: true,
            supports_tool_calling: false,
            supports_tool_selection: true,
            supports_native_tool_protocol: false,
        },
        {
            provider: 'huggingface',
            label: 'Hugging Face',
            configuration_kind: 'remote',
            model_source: 'downloaded_filesystem',
            default_base_url: null,
            default_chat_model: null,
            default_embedding_model: null,
            requires_api_key: true,
            supports_status_check: false,
            supports_chat: true,
            supports_embeddings: true,
            supports_structured_output: true,
            supports_streaming: false,
            supports_tool_calling: false,
            supports_tool_selection: true,
            supports_native_tool_protocol: false,
        },
        {
            provider: 'lmstudio',
            label: 'LM Studio',
            configuration_kind: 'local',
            model_source: 'live',
            default_base_url: 'http://localhost:1234/v1',
            default_chat_model: 'local-model',
            default_embedding_model: 'local-embedding-model',
            requires_api_key: false,
            supports_status_check: true,
            supports_chat: true,
            supports_embeddings: true,
            supports_structured_output: true,
            supports_streaming: true,
            supports_tool_calling: false,
            supports_tool_selection: true,
            supports_native_tool_protocol: false,
        },
        {
            provider: 'llama',
            label: 'llama.cpp',
            configuration_kind: 'local',
            model_source: 'live',
            default_base_url: 'http://localhost:8080/v1',
            default_chat_model: 'local-model',
            default_embedding_model: 'local-embedding-model',
            requires_api_key: false,
            supports_status_check: true,
            supports_chat: true,
            supports_embeddings: true,
            supports_structured_output: true,
            supports_streaming: true,
            supports_tool_calling: false,
            supports_tool_selection: true,
            supports_native_tool_protocol: false,
        },
    ]
}

function extractJsonPayload(raw: string | null): AnyRecord {
    if (!raw) {
        return {}
    }
    try {
        return JSON.parse(raw) as AnyRecord
    } catch {
        return {}
    }
}

function reply(route: Parameters<Page['route']>[1] extends (arg: infer T) => unknown ? T : never, status: number, body: unknown): Promise<void> {
    return route.fulfill({
        status,
        contentType: 'application/json',
        body: JSON.stringify(body),
    })
}

export async function setupMockBackend(page: Page, workflowOutputText = 'Hello from mocked workflow'): Promise<MockBackendState> {
    const state: MockBackendState = {
        compileCalls: 0,
        startCalls: 0,
        pollCalls: 0,
        nodeCatalog: [buildPromptManifest()],
    }

    const configurationPayload = buildConfigurationPayload()
    const providerCatalog = buildProviderCatalog()
    const profiles = new Map<string, AnyRecord>([
        ['workstation', buildConfigurationPayload()],
        ['travel', buildConfigurationPayload()],
    ])

    const ollamaModels = [
        {
            model: 'llama3.2',
            description: 'Local text model',
            homepage: 'https://ollama.com/library/llama3.2',
            pulled: false,
        },
    ]

    let hfDownloaded = false
    const downloadJobs = new Map<string, { repoId: string; polls: number; status: 'running' | 'completed' | 'cancelled' }>()

    await page.addInitScript(() => {
        const stepEvent = {
            event_type: 'execution.step.started',
            run_id: 'run-e2e',
            step_id: 'output_step',
            sequence: 1,
            timestamp: '2026-03-24T00:00:00Z',
            payload: { node_id: 'output_1' },
        }

        const trackedUrls: string[] = []

        class MockWebSocket {
            onmessage: ((event: MessageEvent<string>) => void) | null = null
            onerror: ((event: Event) => void) | null = null
            readyState = 1
            url: string

            constructor(url: string) {
                this.url = url
                trackedUrls.push(url)
                window.setTimeout(() => {
                    this.onmessage?.({ data: JSON.stringify(stepEvent) } as MessageEvent<string>)
                }, 1)
            }

            close(): void {
                this.readyState = 3
            }
        }

        ;(window as unknown as { __paragraphWsUrls: string[] }).__paragraphWsUrls = trackedUrls
        ;(window as unknown as { WebSocket: typeof MockWebSocket }).WebSocket = MockWebSocket
    })

    await page.route('**/api/**', async (route) => {
        const request = route.request()
        const url = new URL(request.url())
        const rawPath = url.pathname
        const normalizedPath = rawPath.startsWith('/api') ? rawPath.slice(4) || '/' : rawPath
        const method = request.method().toUpperCase()

        if (normalizedPath === '/providers/models' && method === 'GET') {
            return reply(route, 200, {
                models: [
                    {
                        provider: 'ollama',
                        model: 'llama3.2',
                        label: 'ollama:llama3.2',
                        supports_image: false,
                        supports_reasoning: false,
                        supports_structured_output: true,
                    },
                ],
            })
        }

        if (normalizedPath === '/providers/catalog' && method === 'GET') {
            return reply(route, 200, { providers: providerCatalog })
        }

        if (normalizedPath === '/nodes/catalog' && method === 'GET') {
            return reply(route, 200, { nodes: state.nodeCatalog })
        }

        if (normalizedPath === '/nodes/import' && method === 'POST') {
            const payload = extractJsonPayload(request.postData())
            if (payload.id === 'FAIL_NODE') {
                return reply(route, 400, { detail: 'Duplicate node id/version' })
            }
            if (typeof payload.id !== 'string' || typeof payload.version !== 'number') {
                return reply(route, 400, { detail: 'Invalid manifest payload' })
            }
            const alreadyExists = state.nodeCatalog.some((item) => item.id === payload.id && item.version === payload.version)
            if (!alreadyExists) {
                state.nodeCatalog.push(payload)
            }
            return reply(route, 200, payload)
        }

        if (normalizedPath === '/configurations' && method === 'GET') {
            return reply(route, 200, configurationPayload)
        }

        if (normalizedPath === '/configurations' && method === 'PUT') {
            const payload = extractJsonPayload(request.postData())
            return reply(route, 200, payload)
        }

        if (normalizedPath === '/configurations/profiles' && method === 'GET') {
            return reply(route, 200, {
                session_name: 'default',
                profiles: Array.from(profiles.keys()).map((profileName) => ({
                    profile_name: profileName,
                    created_at: '2026-03-24T10:00:00Z',
                    updated_at: '2026-03-24T10:00:00Z',
                })),
            })
        }

        if (normalizedPath.startsWith('/configurations/profiles/') && method === 'GET') {
            const profileName = decodeURIComponent(normalizedPath.replace('/configurations/profiles/', ''))
            const profile = profiles.get(profileName)
            if (!profile) {
                return reply(route, 404, { detail: `Profile not found: ${profileName}` })
            }
            return reply(route, 200, profile)
        }

        if (normalizedPath.startsWith('/configurations/profiles/') && method === 'PUT') {
            const profileName = decodeURIComponent(normalizedPath.replace('/configurations/profiles/', ''))
            const payload = extractJsonPayload(request.postData())
            profiles.set(profileName, payload)
            return reply(route, 200, payload)
        }

        if (normalizedPath === '/configurations/ollama/ping' && method === 'POST') {
            return reply(route, 200, {
                ok: true,
                message: 'Ollama reachable (mocked)',
                base_url: 'http://127.0.0.1:11434',
                model_count: 1,
            })
        }

        if (normalizedPath === '/providers/ollama/library' && method === 'GET') {
            return reply(route, 200, {
                models: ollamaModels,
                total_count: ollamaModels.length,
                pulled_count: ollamaModels.filter((item) => item.pulled).length,
                refreshed_at: '2026-03-24T00:00:00Z',
                source: 'mock',
            })
        }

        if (normalizedPath === '/providers/ollama/pull' && method === 'POST') {
            const payload = extractJsonPayload(request.postData())
            const modelName = String(payload.model || '').trim()
            const target = ollamaModels.find((item) => item.model === modelName)
            if (target) {
                target.pulled = true
            }
            return reply(route, 200, {
                ok: true,
                model: modelName,
                message: `Pulled ${modelName}`,
            })
        }

        if (normalizedPath === '/providers/huggingface/models' && method === 'GET') {
            return reply(route, 200, {
                models: [
                    {
                        repo_id: 'acme/model',
                        author: 'acme',
                        task: 'text-generation',
                        library: 'transformers',
                        likes: 5,
                        downloads: 100,
                        visibility: 'public',
                        private: false,
                        gated: false,
                        last_modified: '2026-03-24T00:00:00Z',
                        url: 'https://huggingface.co/acme/model',
                        downloaded: hfDownloaded,
                        size_bytes: 123456,
                    },
                ],
                page: 1,
                page_size: 25,
                has_more: false,
                using_token: false,
                warning: null,
                available_tasks: ['text-generation'],
                available_libraries: ['transformers'],
            })
        }

        if (normalizedPath === '/providers/huggingface/download' && method === 'POST') {
            const payload = extractJsonPayload(request.postData())
            const repoId = String(payload.repo_id || '').trim()
            const jobId = 'job-1'
            downloadJobs.set(jobId, { repoId, polls: 0, status: 'running' })
            return reply(route, 200, {
                ok: true,
                repo_id: repoId,
                message: 'Download started',
                destination_path: `app/resources/models/huggingface/${repoId.replace('/', '--')}`,
                already_downloaded: false,
                job_id: jobId,
                status: 'running',
                progress: 0,
                downloaded_bytes: 0,
                total_bytes: 100,
                poll_interval: 0.1,
            })
        }

        if (normalizedPath.startsWith('/providers/huggingface/download/') && method === 'GET') {
            const jobId = decodeURIComponent(normalizedPath.replace('/providers/huggingface/download/', ''))
            const job = downloadJobs.get(jobId)
            if (!job) {
                return reply(route, 404, { detail: `Unknown download job: ${jobId}` })
            }

            if (job.status === 'running') {
                job.polls += 1
                if (job.polls >= 1) {
                    job.status = 'completed'
                    hfDownloaded = true
                    return reply(route, 200, {
                        job_id: jobId,
                        repo_id: job.repoId,
                        destination_path: `app/resources/models/huggingface/${job.repoId.replace('/', '--')}`,
                        status: 'completed',
                        progress: 100,
                        message: 'Downloaded Hugging Face model',
                        downloaded_bytes: 100,
                        total_bytes: 100,
                        error: null,
                    })
                }
            }

            return reply(route, 200, {
                job_id: jobId,
                repo_id: job.repoId,
                destination_path: `app/resources/models/huggingface/${job.repoId.replace('/', '--')}`,
                status: 'running',
                progress: 50,
                message: 'Downloading...',
                downloaded_bytes: 50,
                total_bytes: 100,
                error: null,
            })
        }

        if (normalizedPath.startsWith('/providers/huggingface/download/') && method === 'DELETE') {
            const jobId = decodeURIComponent(normalizedPath.replace('/providers/huggingface/download/', ''))
            const job = downloadJobs.get(jobId)
            if (job) {
                job.status = 'cancelled'
            }
            return reply(route, 200, {
                ok: true,
                job_id: jobId,
                repo_id: job?.repoId || 'unknown',
                message: 'Download cancelled',
            })
        }

        if (normalizedPath === '/executions/compile' && method === 'POST') {
            state.compileCalls += 1
            return reply(route, 200, {
                valid: true,
                diagnostics: [],
                plan: {
                    plan_id: 'plan-e2e',
                    schema_version: 1,
                    step_order: ['output_step'],
                    steps: [
                        {
                            step_id: 'output_step',
                            node_id: 'output_1',
                            node_type: 'TEXT_OUTPUT',
                            node_version: 1,
                            category: 'output',
                            executor_key: 'text_output',
                            parameters: {},
                            bindings: [],
                            retries: 0,
                            cacheable: false,
                        },
                    ],
                    metadata: {},
                },
            })
        }

        if (normalizedPath === '/executions' && method === 'POST') {
            state.startCalls += 1
            state.pollCalls = 0
            return reply(route, 202, {
                run_id: 'run-e2e',
                status: 'running',
                poll_interval: 0.01,
            })
        }

        if (normalizedPath === '/executions/run-e2e' && method === 'GET') {
            state.pollCalls += 1
            const status = state.pollCalls >= 3 ? 'completed' : state.pollCalls === 2 ? 'running' : 'queued'
            const progress = status === 'completed' ? 100 : status === 'running' ? 55 : 0
            return reply(route, 200, {
                run_id: 'run-e2e',
                workflow_id: null,
                plan_id: 'plan-e2e',
                status,
                created_at: '2026-03-24T00:00:00Z',
                updated_at: '2026-03-24T00:00:00Z',
                progress,
                steps: [
                    {
                        step_id: 'output_step',
                        node_id: 'output_1',
                        node_type: 'TEXT_OUTPUT',
                        status: status === 'queued' ? 'queued' : status === 'running' ? 'running' : 'completed',
                        started_at: '2026-03-24T00:00:00Z',
                        completed_at: status === 'completed' ? '2026-03-24T00:00:01Z' : null,
                        output: status === 'completed' ? { text: workflowOutputText } : {},
                        error: null,
                    },
                ],
                outputs: status === 'completed' ? { output_1: { text: workflowOutputText } } : {},
                error: null,
            })
        }

        return reply(route, 404, { detail: `No mock route for ${method} ` })
    })

    return state
}
