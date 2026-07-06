import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import * as workflowApi from '../app/services/providersApi'
import ModelsPage from './ModelsPage'
import {
    createHuggingFaceCatalog,
    createHuggingFaceModel,
    createOllamaCatalog,
} from '../test/fixtures'

vi.mock('../app/services/providersApi', () => ({
    fetchOllamaLibraryModels: vi.fn(),
    pullOllamaModel: vi.fn(),
    fetchHuggingFaceModels: vi.fn(),
    downloadHuggingFaceModel: vi.fn(),
    getHuggingFaceDownloadStatus: vi.fn(),
    cancelHuggingFaceDownload: vi.fn(),
}))

describe('ModelsPage download transitions', () => {
    afterEach(() => {
        vi.useRealTimers()
    })

    it('transitions Hugging Face downloads from running to completed state', async () => {
        const fetchOllamaLibraryModelsMock = vi.mocked(workflowApi.fetchOllamaLibraryModels)
        const pullOllamaModelMock = vi.mocked(workflowApi.pullOllamaModel)
        const fetchHuggingFaceModelsMock = vi.mocked(workflowApi.fetchHuggingFaceModels)
        const downloadHuggingFaceModelMock = vi.mocked(workflowApi.downloadHuggingFaceModel)
        const getHuggingFaceDownloadStatusMock = vi.mocked(workflowApi.getHuggingFaceDownloadStatus)

        fetchOllamaLibraryModelsMock.mockResolvedValue(createOllamaCatalog())
        pullOllamaModelMock.mockResolvedValue({ ok: true, model: 'llama3.2', message: 'Pull started' })

        const repoId = 'acme/model'
        fetchHuggingFaceModelsMock
            .mockResolvedValueOnce(createHuggingFaceCatalog([createHuggingFaceModel({ repo_id: repoId, downloaded: false })]))
            .mockResolvedValueOnce(createHuggingFaceCatalog([createHuggingFaceModel({ repo_id: repoId, downloaded: true })]))

        downloadHuggingFaceModelMock.mockResolvedValue({
            ok: true,
            repo_id: repoId,
            message: 'Download started',
            destination_path: 'app/resources/models/huggingface/acme--model',
            already_downloaded: false,
            job_id: 'job-1',
            status: 'running',
            progress: 0,
            downloaded_bytes: 0,
            total_bytes: 100,
            poll_interval: 0.1,
        })

        getHuggingFaceDownloadStatusMock.mockResolvedValue({
            job_id: 'job-1',
            repo_id: repoId,
            destination_path: 'app/resources/models/huggingface/acme--model',
            status: 'completed',
            progress: 100,
            message: 'Download complete.',
            downloaded_bytes: 100,
            total_bytes: 100,
            error: null,
        })

        render(<ModelsPage />)

        await screen.findByText('llama3.2')
        await screen.findByText(repoId)

        vi.useFakeTimers()
        fireEvent.click(screen.getByRole('button', { name: 'Download' }))
        expect(downloadHuggingFaceModelMock).toHaveBeenCalledWith(repoId)

        await vi.advanceTimersByTimeAsync(1500)

        expect(getHuggingFaceDownloadStatusMock).toHaveBeenCalledWith('job-1')
        expect(fetchHuggingFaceModelsMock).toHaveBeenCalledTimes(2)
    })

    it('shows provider errors without also showing empty-result copy', async () => {
        const fetchOllamaLibraryModelsMock = vi.mocked(workflowApi.fetchOllamaLibraryModels)
        const fetchHuggingFaceModelsMock = vi.mocked(workflowApi.fetchHuggingFaceModels)

        fetchOllamaLibraryModelsMock.mockRejectedValue(new Error('Unable to reach Ollama library'))
        fetchHuggingFaceModelsMock.mockRejectedValue(new Error('Unable to reach Hugging Face'))

        render(<ModelsPage />)

        await screen.findByText('Unable to reach Ollama library')
        await screen.findByText('Unable to reach Hugging Face')

        expect(screen.queryByText('No Ollama models match the active filters.')).not.toBeInTheDocument()
        expect(screen.queryByText('No models match the current query.')).not.toBeInTheDocument()
    })
})

