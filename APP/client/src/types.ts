export interface DatasetProcessingConfig {
    datasetName: string
    sampleSize: number
    validationSize: number
    maxReportSize: number
    tokenizer: string
}

export interface DatasetPageState {
    config: DatasetProcessingConfig
    imageFolderPath: string
    uploadError: string | null
    isProcessing: boolean
}

export interface TrainingConfig {
    epochs: number
    batchSize: number
}

export interface TrainingDashboardState {
    isTraining: boolean
    currentEpoch: number
    totalEpochs: number
    progressPercent: number
}

export interface TrainingPageState {
    config: TrainingConfig
    selectedCheckpoint: string
    additionalEpochs: number
    dashboardState: TrainingDashboardState
}

export type GenerationMode = 'greedy_search' | 'beam_search'

export interface InferencePageState {
    selectedCheckpoint: string
    generationMode: GenerationMode
    generatedReport: string
    isGenerating: boolean
}
