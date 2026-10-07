export type Order = { order_id: string; product_name: string; amount_cents: number; status: string; purchased_on: string }
export type Operation = { id: string; status: string; action: 'refund' | 'expedite'; order_id: string; product_name: string; amount_cents: number; reason: string; scope: string; message?: string; application_id?: string }
export type Item = {
  id: string; kind: 'user' | 'assistant' | 'tool' | 'orders' | 'approval' | 'notice';
  text?: string; status?: string; name?: string; arguments?: string; result?: unknown;
  duration_ms?: number; orders?: Order[]; selected?: string; operation?: Operation;
}
export type Session = { id: string; items: Item[]; selected: string | null; candidates: string[]; pending: string | null; busy: boolean }
export type StreamEvent = { event: string; data: Record<string, unknown> }

export function applyEvent(state: Session, { event, data }: StreamEvent): Session {
  if (event === 'done') return data as unknown as Session
  if (event === 'state') return { ...state, ...data }
  if (event === 'item') return { ...state, items: [...state.items, data as unknown as Item] }
  if (event === 'patch' || event === 'delta') return {
    ...state, items: state.items.map(item => item.id !== data.id ? item :
      event === 'delta' ? { ...item, text: (item.text ?? '') + String(data.text ?? '') } : { ...item, ...data }),
  }
  return state
}
