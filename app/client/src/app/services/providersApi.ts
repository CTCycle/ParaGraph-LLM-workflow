import {
  HuggingFaceModelCatalogResponse,
  HuggingFaceModelDownloadCancelResponse,
  HuggingFaceModelDownloadResponse,
  HuggingFaceModelDownloadStatusResponse,
  HuggingFaceSortBy,
  ModelVisibilityFilter,
  OllamaLibraryCatalogResponse,
  OllamaModelPullResponse,
  ProviderModelCatalogResponse,
  ProviderCatalogResponse,
} from '../../workflow/schema/types'
import { requestJson } from './api'

export interface OllamaLibraryQueryOptions {
  sessionName?: string
  search?: string
  refresh?: boolean
}

export interface HuggingFaceModelQueryOptions {
  sessionName?: string
  search?: string
  task?: string
  library?: string
  author?: string
  visibility?: ModelVisibilityFilter
  sort?: HuggingFaceSortBy
  page?: number
  pageSize?: number
  refresh?: boolean
}

export function fetchProviderCatalog(): Promise<ProviderCatalogResponse> {
  return requestJson<ProviderCatalogResponse>('/providers/catalog')
}

export function fetchProviderModels(sessionName = 'default'): Promise<ProviderModelCatalogResponse> {
  const params = new URLSearchParams({ session_name: sessionName })
  return requestJson<ProviderModelCatalogResponse>(`/providers/models?${params.toString()}`)
}

export function fetchOllamaLibraryModels(options: OllamaLibraryQueryOptions = {}): Promise<OllamaLibraryCatalogResponse> {
  const params = new URLSearchParams()
  params.set('session_name', options.sessionName || 'default')
  if (options.search && options.search.trim()) {
    params.set('search', options.search.trim())
  }
  if (options.refresh) {
    params.set('refresh', 'true')
  }
  return requestJson<OllamaLibraryCatalogResponse>(`/providers/ollama/library?${params.toString()}`)
}

export function pullOllamaModel(model: string, sessionName = 'default'): Promise<OllamaModelPullResponse> {
  const params = new URLSearchParams({ session_name: sessionName })
  return requestJson<OllamaModelPullResponse>(`/providers/ollama/pull?${params.toString()}`, {
    method: 'POST',
    body: JSON.stringify({ model }),
  })
}

export function fetchHuggingFaceModels(
  options: HuggingFaceModelQueryOptions,
  init?: RequestInit,
): Promise<HuggingFaceModelCatalogResponse> {
  const params = new URLSearchParams()
  params.set('session_name', options.sessionName || 'default')

  const search = options.search?.trim()
  const task = options.task?.trim()
  const library = options.library?.trim()
  const author = options.author?.trim()
  if (search) params.set('search', search)
  if (task) params.set('task', task)
  if (library) params.set('library', library)
  if (author) params.set('author', author)

  params.set('visibility', options.visibility || 'all')
  params.set('sort', options.sort || 'relevance')
  params.set('page', String(options.page || 1))
  params.set('page_size', String(options.pageSize || 25))
  if (options.refresh) params.set('refresh', 'true')

  return requestJson<HuggingFaceModelCatalogResponse>(`/providers/huggingface/models?${params.toString()}`, init)
}

export function downloadHuggingFaceModel(repoId: string, sessionName = 'default'): Promise<HuggingFaceModelDownloadResponse> {
  const normalizedRepoId = repoId.trim()
  if (!normalizedRepoId) {
    throw new Error('Repository id is required')
  }
  const params = new URLSearchParams({ session_name: sessionName })
  return requestJson<HuggingFaceModelDownloadResponse>(`/providers/huggingface/download?${params.toString()}`, {
    method: 'POST',
    body: JSON.stringify({ repo_id: normalizedRepoId }),
  })
}

export function getHuggingFaceDownloadStatus(jobId: string): Promise<HuggingFaceModelDownloadStatusResponse> {
  const normalizedJobId = jobId.trim()
  if (!normalizedJobId) {
    throw new Error('Download job id is required')
  }
  return requestJson<HuggingFaceModelDownloadStatusResponse>(`/providers/huggingface/download/${encodeURIComponent(normalizedJobId)}`)
}

export function cancelHuggingFaceDownload(jobId: string): Promise<HuggingFaceModelDownloadCancelResponse> {
  const normalizedJobId = jobId.trim()
  if (!normalizedJobId) {
    throw new Error('Download job id is required')
  }
  return requestJson<HuggingFaceModelDownloadCancelResponse>(`/providers/huggingface/download/${encodeURIComponent(normalizedJobId)}`, {
    method: 'DELETE',
  })
}
