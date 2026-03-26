import {
    AppConfigurationPayload,
    HuggingFaceModelCatalogResponse,
    HuggingFaceModelDefinition,
    NodeManifest,
    OllamaLibraryCatalogResponse,
} from '../workflow/schema/types'

export function createNodeManifest(overrides: Partial<NodeManifest> = {}): NodeManifest {
    return {
        id: 'PROMPT',
        version: 1,
        name: 'Prompt',
        category: 'prompt',
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
        ...overrides,
    }
}

export function createConfigurationPayload(overrides: Partial<AppConfigurationPayload> = {}): AppConfigurationPayload {
    return {
        session_name: 'default',
        access_keys: [
            {
                provider: 'openai',
                api_key: 'sk-test',
                base_url: null,
                metadata: {},
            },
            {
                provider: 'huggingface',
                api_key: 'hf-test',
                base_url: null,
                metadata: {},
            },
        ],
        ollama: {
            base_url: 'http://127.0.0.1:11434',
            chat_model: 'llama3.2',
            embedding_model: 'nomic-embed-text',
        },
        ...overrides,
    }
}

export function createOllamaCatalog(overrides?: Partial<OllamaLibraryCatalogResponse>): OllamaLibraryCatalogResponse {
    return {
        models: [
            {
                model: 'llama3.2',
                description: 'General purpose local model',
                homepage: 'https://ollama.com/library/llama3.2',
                pulled: false,
            },
        ],
        total_count: 1,
        pulled_count: 0,
        refreshed_at: '2026-03-24T00:00:00Z',
        source: 'stub',
        ...overrides,
    }
}

export function createHuggingFaceModel(overrides?: Partial<HuggingFaceModelDefinition>): HuggingFaceModelDefinition {
    return {
        repo_id: 'acme/model',
        author: 'acme',
        task: 'text-generation',
        library: 'transformers',
        likes: 1,
        downloads: 10,
        visibility: 'public',
        private: false,
        gated: false,
        last_modified: '2026-03-24T00:00:00Z',
        url: 'https://huggingface.co/acme/model',
        downloaded: false,
        size_bytes: 1024,
        ...overrides,
    }
}

export function createHuggingFaceCatalog(
    models: HuggingFaceModelDefinition[],
    overrides?: Partial<HuggingFaceModelCatalogResponse>,
): HuggingFaceModelCatalogResponse {
    return {
        models,
        page: 1,
        page_size: 25,
        has_more: false,
        using_token: false,
        warning: null,
        available_tasks: ['text-generation'],
        available_libraries: ['transformers'],
        ...overrides,
    }
}
