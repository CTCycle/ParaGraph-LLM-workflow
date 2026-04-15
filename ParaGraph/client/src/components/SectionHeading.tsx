type SectionHeadingProps = {
    title: string
    description: string
    className?: string
    titleId?: string
    descriptionId?: string
}

export default function SectionHeading({
    title,
    description,
    className,
    titleId,
    descriptionId,
}: SectionHeadingProps) {
    return (
        <div className={className}>
            <h2 id={titleId}>{title}</h2>
            <p id={descriptionId}>{description}</p>
        </div>
    )
}
