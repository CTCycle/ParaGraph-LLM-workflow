import {
  CompileWorkflowResponse,
  WorkflowDefinition,
  WorkflowTemplateListResponse,
} from '../../workflow/schema/types'
import { requestJson } from './api'

export function compileWorkflow(definition: WorkflowDefinition): Promise<CompileWorkflowResponse> {
  return requestJson<CompileWorkflowResponse>('/executions/compile', {
    method: 'POST',
    body: JSON.stringify({ definition }),
  })
}

export function fetchWorkflowTemplates(): Promise<WorkflowTemplateListResponse> {
  return requestJson<WorkflowTemplateListResponse>('/workflow-templates')
}
