import {
  CompileWorkflowResponse,
  CompiledExecutionPlan,
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

export interface WorkflowListItemResponse {
  workflow_id: string
  name: string
  updated_at: string
}

export interface WorkflowListResponse {
  workflows: WorkflowListItemResponse[]
}

export function listWorkflows(): Promise<WorkflowListResponse> {
  return requestJson<WorkflowListResponse>('/workflows')
}

export function fetchWorkflowTemplates(): Promise<WorkflowTemplateListResponse> {
  return requestJson<WorkflowTemplateListResponse>('/workflows/templates')
}

export function createWorkflow(payload: {
  name: string
  definition: WorkflowDefinition
  visual_graph: unknown
}): Promise<unknown> {
  return requestJson('/workflows', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateWorkflow(workflowId: string, payload: {
  name?: string
  definition: WorkflowDefinition
  visual_graph: unknown
}): Promise<unknown> {
  return requestJson(`/workflows/${encodeURIComponent(workflowId)}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function startWorkflowExecution(plan: CompiledExecutionPlan, workflowId?: string) {
  return requestJson('/executions', {
    method: 'POST',
    body: JSON.stringify({ workflow_id: workflowId ?? null, plan }),
  })
}
