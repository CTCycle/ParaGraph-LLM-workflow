import { describe, expect, it } from 'vitest'

import type { NodeManifest, ProviderModelDefinition } from '../workflow/schema/types'
import {
    collectNodeItems,
    getDynamicModelOptions,
    getDynamicTokenizerOptions,
    resolveExecutionSessionId,
} from './WorkflowPage'

import textEmbeddingManifestJson from '../../../resources/nodes/text_embedding_v1.json'
import vectorStoreManifestJson from '../../../resources/nodes/vector_store_v1.json'
import rerankManifestJson from '../../../resources/nodes/rerank_results_v1.json'
import similaritySearchManifestJson from '../../../resources/nodes/similarity_search_v1.json'
import chatHistoryMemoryManifestJson from '../../../resources/nodes/chat_history_memory_v1.json'
import chatHistoryPersistedManifestJson from '../../../resources/nodes/chat_history_persisted_v1.json'
import crudCreateManifestJson from '../../../resources/nodes/crud_create_v1.json'
import crudReadManifestJson from '../../../resources/nodes/crud_read_v1.json'
import crudUpdateManifestJson from '../../../resources/nodes/crud_update_v1.json'
import crudDeleteManifestJson from '../../../resources/nodes/crud_delete_v1.json'
import customSqlQueryManifestJson from '../../../resources/nodes/custom_sql_query_v1.json'

const textEmbeddingManifest = textEmbeddingManifestJson as NodeManifest
const vectorStoreManifest = vectorStoreManifestJson as NodeManifest
const rerankManifest = rerankManifestJson as NodeManifest
const similaritySearchManifest = similaritySearchManifestJson as NodeManifest
const chatHistoryMemoryManifest = chatHistoryMemoryManifestJson as NodeManifest
const chatHistoryPersistedManifest = chatHistoryPersistedManifestJson as NodeManifest
const databaseOperationManifests = [
    crudCreateManifestJson,
    crudReadManifestJson,
    crudUpdateManifestJson,
    crudDeleteManifestJson,
    customSqlQueryManifestJson,
] as NodeManifest[]

function getOptions(manifest: NodeManifest, parameterName: string): string[] {
    const parameter = manifest.parameters.find((item) => item.name === parameterName)
    const rawOptions = parameter?.constraints.options
    return Array.isArray(rawOptions) ? rawOptions.filter((item): item is string => typeof item === 'string') : []
}

describe('WorkflowPage manifest-driven provider and retrieval behavior', () => {
    it('TEXT_EMBEDDING exposes explicit providers and never shows cloud', () => {
        const providerOptions = getOptions(textEmbeddingManifest, 'provider')
        expect(providerOptions).toEqual(['openai', 'gemini', 'huggingface', 'ollama', 'lmstudio', 'llama'])
        expect(providerOptions).not.toContain('cloud')
        expect(textEmbeddingManifest.parameters.find((item) => item.name === 'provider')?.default).toBe('ollama')
        expect(textEmbeddingManifest.parameters.find((item) => item.name === 'model_name')?.default).toBe('nomic-embed-text')
    })

    it('TEXT_EMBEDDING exposes a Hugging Face tokenizer selector only for Hugging Face', () => {
        const tokenizerParameter = textEmbeddingManifest.parameters.find((item) => item.name === 'tokenizer_name')
        expect(tokenizerParameter?.ui_control).toBe('select')
        expect(tokenizerParameter?.constraints.visible_when).toEqual({ provider: 'huggingface' })
    })

    it('VECTOR_STORE provider options include faiss', () => {
        const providerOptions = getOptions(vectorStoreManifest, 'provider')
        expect(providerOptions).toContain('faiss')
    })

    it('RERANK_RESULTS manifest renders required controls with no page-level special casing', () => {
        const parameterNames = rerankManifest.parameters.map((item) => item.name)
        expect(parameterNames).toEqual([
            'strategy',
            'score_mode',
            'metadata_field',
            'metadata_value',
            'original_score_weight',
            'term_overlap_weight',
            'phrase_boost',
            'metadata_boost',
            'top_k',
        ])
    })

    it('SIMILARITY_SEARCH exposes native-first engine options from manifest', () => {
        const searchModeOptions = getOptions(similaritySearchManifest, 'search_mode')
        const searchEngineOptions = getOptions(similaritySearchManifest, 'search_engine')
        const metricOptions = getOptions(similaritySearchManifest, 'similarity_strategy')

        expect(searchModeOptions).toEqual(['vector', 'keyword', 'hybrid'])
        expect(searchEngineOptions).toEqual(['native', 'faiss_augmented'])
        expect(metricOptions).toEqual(['cosine', 'euclidean', 'dot'])
    })

    it('chat history manifests expose expected parameters', () => {
        expect(chatHistoryMemoryManifest.parameters.map((item) => item.name)).toEqual([
            'max_messages',
            'separator',
            'keep_prompt_type',
        ])
        expect(chatHistoryPersistedManifest.parameters.map((item) => item.name)).toEqual([
            'max_messages',
            'separator',
            'keep_prompt_type',
            'storage_backend',
        ])
    })

    it('database operation manifests expose connection controllers and dataset outputs', () => {
        for (const manifest of databaseOperationManifests) {
            expect(manifest.category).toBe('database')
            expect(manifest.controllers?.map((controller) => controller.name)).toContain('connection')
            expect(manifest.controllers?.find((controller) => controller.name === 'connection')?.data_type).toBe('DATABASE_CONNECTION')
            expect(manifest.outputs).toEqual([
                {
                    name: 'dataset',
                    data_type: 'DATASET',
                    required: true,
                },
            ])
        }
    })

    it('node item previews include database dataset rows', () => {
        const items = collectNodeItems(crudReadManifestJson as NodeManifest, {}, {
            ports: {
                dataset: {
                    columns: ['id', 'label', 'status'],
                    rows: [
                        { id: 1, label: 'alpha', status: 'updated' },
                    ],
                },
            },
        })

        expect(items).toHaveLength(1)
        expect(items[0].label).toBe('Row 1')
        expect(items[0].preview).toContain('"status":"updated"')
    })

    it('node item previews include retrieval hits with source labels and scores', () => {
        const items = collectNodeItems(similaritySearchManifest, {}, {
            ports: {
                results: {
                    query: 'drug induced liver injury',
                    hits: [
                        {
                            id: 'hit-1',
                            score: 0.8754,
                            text: 'DILI relevant passage',
                            source_uri: 'C:\\docs\\study.pdf',
                            metadata: { file_name: 'study.pdf' },
                        },
                    ],
                },
            },
        })

        expect(items).toHaveLength(1)
        expect(items[0].label).toBe('study.pdf (0.875)')
        expect(items[0].preview).toBe('DILI relevant passage')
    })

    it('embedding model options are provider-catalog driven and update on provider switch', () => {
        const providerModels: ProviderModelDefinition[] = [
            {
                provider: 'ollama',
                model: 'nomic-embed-text',
                label: 'nomic-embed-text',
                supports_image: false,
                supports_embeddings: true,
                supports_reasoning: false,
                supports_structured_output: false,
            },
            {
                provider: 'openai',
                model: 'custom-openai-embed',
                label: 'Custom OpenAI Embed',
                supports_image: false,
                supports_embeddings: true,
                supports_reasoning: false,
                supports_structured_output: false,
            },
            {
                provider: 'openai',
                model: 'gpt-5.4',
                label: 'GPT-5.4',
                supports_image: true,
                supports_embeddings: false,
                supports_reasoning: true,
                supports_structured_output: true,
            },
            {
                provider: 'gemini',
                model: 'gemini-embedding-001',
                label: 'Gemini Embedding 001',
                supports_image: false,
                supports_embeddings: true,
                supports_reasoning: false,
                supports_structured_output: false,
            },
        ]

        const ollamaModels = getDynamicModelOptions(textEmbeddingManifest, { provider: 'ollama' }, providerModels)
        const openaiModels = getDynamicModelOptions(textEmbeddingManifest, { provider: 'openai' }, providerModels)
        const geminiModels = getDynamicModelOptions(textEmbeddingManifest, { provider: 'gemini' }, providerModels)

        expect(ollamaModels.map((item) => item.model)).toEqual(['nomic-embed-text'])
        expect(openaiModels.map((item) => item.model)).toEqual(['custom-openai-embed'])
        expect(geminiModels.map((item) => item.model)).toEqual(['gemini-embedding-001'])
    })

    it('Hugging Face tokenizer options include non-embedding Hugging Face models', () => {
        const providerModels: ProviderModelDefinition[] = [
            {
                provider: 'huggingface',
                model: 'sentence-transformers/all-MiniLM-L6-v2',
                label: 'all-MiniLM-L6-v2',
                supports_image: false,
                supports_embeddings: true,
                supports_reasoning: false,
                supports_structured_output: false,
            },
            {
                provider: 'huggingface',
                model: 'bert-base-uncased',
                label: 'bert-base-uncased',
                supports_image: false,
                supports_embeddings: false,
                supports_reasoning: false,
                supports_structured_output: false,
            },
            {
                provider: 'openai',
                model: 'text-embedding-3-small',
                label: 'Text Embedding 3 Small',
                supports_image: false,
                supports_embeddings: true,
                supports_reasoning: false,
                supports_structured_output: false,
            },
        ]

        const embeddingModels = getDynamicModelOptions(textEmbeddingManifest, { provider: 'huggingface' }, providerModels)
        const tokenizerModels = getDynamicTokenizerOptions(textEmbeddingManifest, { provider: 'huggingface' }, providerModels)
        const nonHfTokenizerModels = getDynamicTokenizerOptions(textEmbeddingManifest, { provider: 'openai' }, providerModels)

        expect(embeddingModels.map((item) => item.model)).toEqual(['sentence-transformers/all-MiniLM-L6-v2'])
        expect(tokenizerModels.map((item) => item.model)).toEqual([
            'sentence-transformers/all-MiniLM-L6-v2',
            'bert-base-uncased',
        ])
        expect(nonHfTokenizerModels).toEqual([])
    })

    it('execution session id stays stable until reset', () => {
        let sequence = 0
        const factory = () => `session-${++sequence}`
        const first = resolveExecutionSessionId(null, { idFactory: factory })
        const second = resolveExecutionSessionId(first, { idFactory: factory })
        const third = resolveExecutionSessionId(second, { reset: true, idFactory: factory })

        expect(first).toBe('session-1')
        expect(second).toBe('session-1')
        expect(third).toBe('session-2')
    })
})
