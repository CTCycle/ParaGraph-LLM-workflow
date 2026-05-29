import { type LucideIcon } from 'lucide-react'

import { NODE_CATEGORY_LABELS } from '../../workflow/schema/nodeCategory'
import { NodeCategory } from '../../workflow/schema/types'

type NodeCategoryFilterOptionProps = {
    category: NodeCategory
    count: number
    checked: boolean
    icon: LucideIcon
    onToggle: (category: NodeCategory) => void
}

export default function NodeCategoryFilterOption({
    category,
    count,
    checked,
    icon: Icon,
    onToggle,
}: NodeCategoryFilterOptionProps) {
    return (
        <label className="nodes-category-option">
            <input type="checkbox" checked={checked} onChange={() => onToggle(category)} />
            <span className="nodes-category-option-icon">
                <Icon size={15} strokeWidth={1.8} />
            </span>
            <span className="nodes-category-option-text">{NODE_CATEGORY_LABELS[category]}</span>
            <span className="nodes-category-option-count">{count}</span>
        </label>
    )
}
