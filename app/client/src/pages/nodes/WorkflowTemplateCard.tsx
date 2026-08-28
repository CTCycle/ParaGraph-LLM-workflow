import { type WorkflowOpenIntent, type WorkflowTemplate } from '../../workflow/schema/types'

type WorkflowTemplateCardProps = {
    template: WorkflowTemplate
    flowPreview: string[]
    onUseTemplate: (intent: WorkflowOpenIntent) => void
}

export default function WorkflowTemplateCard({
    template,
    flowPreview,
    onUseTemplate,
}: WorkflowTemplateCardProps): JSX.Element {
    return (
        <article className="nodes-template-card" role="listitem">
            <div className="nodes-template-card-header">
                <h3>{template.name}</h3>
                <button
                    type="button"
                    onClick={() =>
                        onUseTemplate({
                            type: 'load-template',
                            template,
                        })
                    }
                >
                    Use template
                </button>
            </div>
            <p>{template.description}</p>
            <p className="nodes-template-flow" aria-label={`${template.name} flow preview`}>
                {flowPreview.join(' -> ')}
            </p>
        </article>
    )
}
