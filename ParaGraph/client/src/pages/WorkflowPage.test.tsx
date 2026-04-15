import { describe, expect, it } from 'vitest'

import type { NodeManifest, ProviderModelDefinition } from '../workflow/schema/types'
import { getDynamicModelOptions } from './WorkflowPage'

import textEmbeddingManifestJson from '../../../resources/nodes/text_embedding_v1.json'
import vectorStoreManifestJson from '../../../resources/nodes/vector_store_v1.json'
import rerankManifestJson from '../../../resources/nodes/rerank_results_v1.json'
import similaritySearchManifestJson from '../../../resources/nodes/similarity_search_v1.json'

const textEmbeddingManifest = textEmbeddingManifestJson as NodeManifest
const vectorStoreManifest = vectorStoreManifestJson as NodeManifest
const rerankManifest = rerankManifestJson as NodeManifest
const similaritySearchManifest = similaritySearchManifestJson as NodeManifest

function getOptions(manifest: NodeManifest, parameterName: string): string[] {
    const parameter = manifest.parameters.find((item) => item.name === parameterName)
    const rawOptions = parameter?.constraints.options
    return Array.isArray(rawOptions) ? rawOptions.filter((item): item is string => typeof item === 'string') : []
}

describe('WorkflowPage manifest-driven provider and retrieval behavior', () => {
    it('TEXT_EMBEDDING exposes explicit providers and never shows cloud', () => {
        const providerOptions = getOptions(textEmbeddingManifest, 'provider')
        expect(providerOptions).toEqual(['openai', 'gemini', 'huggingface', 'ollama'])
        expect(providerOptions).not.toContain('cloud')
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

        expect(searchModeOptions).toEqual(['vector', 'hybrid'])
        expect(searchEngineOptions).toEqual(['native', 'faiss_augmented'])
        expect(metricOptions).toEqual(['cosine', 'euclidean', 'dot'])
    })

    it('embedding model options are provider-catalog driven and update on provider switch', () => {
        const providerModels: ProviderModelDefinition[] = [
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

        const openaiModels = getDynamicModelOptions(textEmbeddingManifest, { provider: 'openai' }, providerModels)
        const geminiModels = getDynamicModelOptions(textEmbeddingManifest, { provider: 'gemini' }, providerModels)

        expect(openaiModels.map((item) => item.model)).toEqual(['custom-openai-embed'])
        expect(geminiModels.map((item) => item.model)).toEqual(['gemini-embedding-001'])
    })
})
