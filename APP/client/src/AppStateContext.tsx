import { createContext, ReactNode, useCallback, useContext, useMemo, useState } from 'react'
import { DatasetPageState, InferencePageState, TrainingPageState } from './types'

const DEFAULT_DATASET_STATE: DatasetPageState = {
    config: {
        datasetName: '',
        sampleSize: 1,
        validationSize: 0.2,
        maxReportSize: 200,
        tokenizer: 'generic-tokenizer',
    },
    imageFolderPath: '',
    uploadError: null,
    isProcessing: false,
}

const DEFAULT_TRAINING_STATE: TrainingPageState = {
    config: {
        epochs: 10,
        batchSize: 32,
    },
    selectedCheckpoint: '',
    additionalEpochs: 10,
    dashboardState: {
        isTraining: false,
        currentEpoch: 0,
        totalEpochs: 0,
        progressPercent: 0,
    },
}

const DEFAULT_INFERENCE_STATE: InferencePageState = {
    selectedCheckpoint: '',
    generationMode: 'greedy_search',
    generatedReport: '',
    isGenerating: false,
}

interface AppStateContextType {
    datasetPageState: DatasetPageState
    setDatasetPageState: (updater: DatasetPageState | ((prev: DatasetPageState) => DatasetPageState)) => void
    trainingPageState: TrainingPageState
    setTrainingPageState: (updater: TrainingPageState | ((prev: TrainingPageState) => TrainingPageState)) => void
    inferencePageState: InferencePageState
    setInferencePageState: (updater: InferencePageState | ((prev: InferencePageState) => InferencePageState)) => void
}

const AppStateContext = createContext<AppStateContextType | null>(null)

type AppStateProviderProps = Readonly<{ children: ReactNode }>

export function AppStateProvider({ children }: AppStateProviderProps) {
    const [datasetPageState, setDatasetPageState] = useState<DatasetPageState>(DEFAULT_DATASET_STATE)
    const [trainingPageState, setTrainingPageState] = useState<TrainingPageState>(DEFAULT_TRAINING_STATE)
    const [inferencePageState, setInferencePageState] = useState<InferencePageState>(DEFAULT_INFERENCE_STATE)

    const value = useMemo(
        () => ({
            datasetPageState,
            setDatasetPageState,
            trainingPageState,
            setTrainingPageState,
            inferencePageState,
            setInferencePageState,
        }),
        [datasetPageState, trainingPageState, inferencePageState],
    )

    return <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>
}

function useAppState() {
    const context = useContext(AppStateContext)
    if (!context) {
        throw new Error('useAppState must be used within an AppStateProvider')
    }
    return context
}

export function useDatasetPageState() {
    const { datasetPageState, setDatasetPageState } = useAppState()

    const setImageFolderPath = useCallback(
        (path: string) => setDatasetPageState((prev) => ({ ...prev, imageFolderPath: path })),
        [setDatasetPageState],
    )
    const setUploadError = useCallback(
        (error: string | null) => setDatasetPageState((prev) => ({ ...prev, uploadError: error })),
        [setDatasetPageState],
    )
    const setIsProcessing = useCallback(
        (isProcessing: boolean) => setDatasetPageState((prev) => ({ ...prev, isProcessing })),
        [setDatasetPageState],
    )
    const updateConfig = useCallback(
        (key: keyof DatasetPageState['config'], value: string | number) =>
            setDatasetPageState((prev) => ({
                ...prev,
                config: { ...prev.config, [key]: value },
            })),
        [setDatasetPageState],
    )

    return {
        state: datasetPageState,
        setImageFolderPath,
        setUploadError,
        setIsProcessing,
        updateConfig,
    }
}

export function useTrainingPageState() {
    const { trainingPageState, setTrainingPageState } = useAppState()

    const updateConfig = useCallback(
        (key: keyof TrainingPageState['config'], value: number) =>
            setTrainingPageState((prev) => ({
                ...prev,
                config: { ...prev.config, [key]: value },
            })),
        [setTrainingPageState],
    )
    const setDashboard = useCallback(
        (dashboardState: TrainingPageState['dashboardState']) =>
            setTrainingPageState((prev) => ({ ...prev, dashboardState })),
        [setTrainingPageState],
    )
    const setSelectedCheckpoint = useCallback(
        (selectedCheckpoint: string) =>
            setTrainingPageState((prev) => ({ ...prev, selectedCheckpoint })),
        [setTrainingPageState],
    )

    return {
        state: trainingPageState,
        updateConfig,
        setDashboard,
        setSelectedCheckpoint,
    }
}

export function useInferencePageState() {
    const { inferencePageState, setInferencePageState } = useAppState()

    const setGeneratedReport = useCallback(
        (generatedReport: string) =>
            setInferencePageState((prev) => ({ ...prev, generatedReport })),
        [setInferencePageState],
    )
    const setIsGenerating = useCallback(
        (isGenerating: boolean) =>
            setInferencePageState((prev) => ({ ...prev, isGenerating })),
        [setInferencePageState],
    )

    return {
        state: inferencePageState,
        setGeneratedReport,
        setIsGenerating,
    }
}
