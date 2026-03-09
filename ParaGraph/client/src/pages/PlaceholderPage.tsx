import './PlaceholderPage.css'

type PlaceholderPageProps = {
    title: string
    description: string
}

export default function PlaceholderPage({ title, description }: PlaceholderPageProps) {
    return (
        <section className="placeholder-page">
            <h1>{title}</h1>
            <p>{description}</p>
        </section>
    )
}
