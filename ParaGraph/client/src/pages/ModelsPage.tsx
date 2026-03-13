import { usePageMetadata } from '../app/hooks/usePageMetadata'
import './ModelsPage.css'

export default function ModelsPage() {
    usePageMetadata({
        title: 'Models',
        description: 'Track upcoming model management capabilities planned for ParaGraph.',
    })

    return (
        <section className="models-page">
            <header className="models-page-header">
                <h1>Models</h1>
                <p>Model management tools will be added here in a future release.</p>
            </header>

            <div className="models-page-empty" aria-hidden="true" />
        </section>
    )
}
