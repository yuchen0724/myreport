import request from "@/utils/request"

export interface Subscription {
  id: number
  name: string
  template_id: number
  cron_expression: string
  recipients: string[]
  is_active: boolean
  created_at: string
}

export function getSubscriptionList(): Promise<Subscription[]> {
  return request({ url: "/subscriptions", method: "get" }) as Promise<Subscription[]>
}

export function createSubscription(data: Partial<Subscription>): Promise<Subscription> {
  return request({ url: "/subscriptions", method: "post", data }) as Promise<Subscription>
}

export function updateSubscription(id: number, data: Partial<Subscription>): Promise<Subscription> {
  return request({ url: `/subscriptions/${id}`, method: "put", data }) as Promise<Subscription>
}

export function deleteSubscription(id: number): Promise<void> {
  return request({ url: `/subscriptions/${id}`, method: "delete" }) as Promise<void>
}

// ── Legacy name aliases ───────────────────────────────────
export const listSubscriptions = getSubscriptionList
export function runSubscription(id: number): Promise<void> {
  return request({ url: `/subscriptions/${id}/run`, method: "post" }) as Promise<void>
}
export function toggleSubscription(id: number, is_active: boolean): Promise<void> {
  return request({ url: `/subscriptions/${id}`, method: "put", data: { is_active } }) as Promise<void>
}
export function getNextRunTime(cronExpression: string): Promise<{ next_run: string }> {
  return request({ url: "/subscriptions/next-run", method: "post", data: { cron_expression: cronExpression } }) as Promise<{ next_run: string }>
}
export function getExecutions(subscriptionId: number): Promise<Record<string, unknown>[]> {
  return request({ url: `/subscriptions/${subscriptionId}/executions`, method: "get" }) as Promise<Record<string, unknown>[]>
}
