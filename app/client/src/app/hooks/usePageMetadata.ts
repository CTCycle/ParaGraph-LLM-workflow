import { useEffect } from 'react'

type PageMetadata = {
    title: string
    description: string
}

const APP_NAME = 'ParaGraph'

function ensureDescriptionTag(): HTMLMetaElement {
    const existing = document.querySelector('meta[name="description"]')
    if (existing instanceof HTMLMetaElement) {
        return existing
    }
    const created = document.createElement('meta')
    created.name = 'description'
    document.head.appendChild(created)
    return created
}

export function usePageMetadata({ title, description }: PageMetadata): void {
    useEffect(() => {
        document.title = `${title} | ${APP_NAME}`
        ensureDescriptionTag().setAttribute('content', description)
    }, [description, title])
}
