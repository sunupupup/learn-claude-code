import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import Markdown from 'react-markdown'
import { request, stream } from './api'
import { applyEvent } from './types'
import type { Item, Session } from './types'

const names: Record<string, string> = { query_orders: '查询订单', get_logistics: '查询物流', query_rules: '查询售后规则', request_action_confirmation: '准备操作确认' }
const suggestions = [
  { title: '查询订单', text: '查一下我昨天买的耳机，发货了吗？', icon: '↗' },
  { title: '催一下发货', text: '白色耳机明晚20点前能收到吗？能到就帮我催一下。', icon: '◷' },
  { title: '申请退款', text: '黑色耳机我不需要了，帮我申请退款。', icon: '↩' },
]
const money = (cents: number) => '¥' + (cents / 100).toFixed(2)

function ItemView({ item, disabled, choose, decide }: {
  item: Item; disabled: boolean; choose: (id: string) => void; decide: (id: string, value: boolean) => void
}) {
  if (item.kind === 'user') return <div className="user-message"><span>{item.text}</span><div className="avatar user-avatar">我</div></div>
  if (item.kind === 'assistant') {
    if (!item.text && item.status === 'complete') return null
    return <div className="assistant-message"><div className="avatar agent-avatar">✳</div><div className="answer">
      {item.text ? <Markdown>{item.text}</Markdown> : item.status === 'streaming' ? <span className="thinking">正在分析问题<span className="dots">…</span></span> : null}
      {item.status === 'streaming' && item.text && <span className="cursor" />}
      {item.status === 'interrupted' && <small className="interrupted">回复未完成，请重试</small>}
    </div></div>
  }
  if (item.kind === 'tool') return <details className="tool-card">
    <summary><span className={'tool-dot ' + item.status} /><strong>{names[item.name ?? ''] ?? item.name}</strong><span className="tool-state">{item.status === 'running' ? '执行中' : item.status === 'failed' ? '失败' : '已完成'}</span><span className="duration">{item.duration_ms !== undefined ? item.duration_ms + ' ms' : ''}</span><span className="chevron">⌄</span></summary>
    <div className="tool-detail"><label>调用参数</label><pre>{item.arguments}</pre>{item.result !== undefined && <><label>工具返回</label><pre>{JSON.stringify(item.result, null, 2)}</pre></>}</div>
  </details>
  if (item.kind === 'orders') return <section className="interaction-card">
    <div className="eyebrow">选择订单</div><h3>找到了多笔订单</h3><p className="muted">选择你想处理的一笔，我们再继续。</p>
    <div className="orders">{item.orders?.map(order => <button key={order.order_id} className={'order-option ' + (item.selected === order.order_id ? 'chosen' : '')}
      disabled={disabled || item.status !== 'waiting'} onClick={() => choose(order.order_id)}>
      <div className="product-icon">♫</div><div className="order-info"><strong>{order.product_name}</strong><small>{order.order_id} · {order.purchased_on}</small><span className="order-status">{order.status}</span></div>
      <div className="order-price">{money(order.amount_cents)}<small>{item.selected === order.order_id ? '已选择 ✓' : '选择 →'}</small></div>
    </button>)}</div>
  </section>
  if (item.kind === 'approval' && item.operation) {
    const op = item.operation
    const waiting = op.status === 'waiting'
    return <section className={'interaction-card approval-card ' + (waiting ? '' : 'resolved')}>
      <div className="eyebrow">{waiting ? '需要你的确认' : op.status === 'submitted' ? '申请已提交' : op.status === 'cancelled' ? '已取消' : '确认已失效'}</div>
      <h3>{op.action === 'refund' ? '申请退款' : '催发货'} <span className="mock-tag">模拟操作</span></h3>
      <div className="confirmation-product"><strong>{op.product_name}</strong><span>{op.order_id}</span></div>
      {op.action === 'refund' && <div className="refund-amount"><span>申请金额</span><strong>{money(op.amount_cents)}</strong></div>}
      <dl><dt>操作范围</dt><dd>{op.scope}</dd><dt>原因</dt><dd>{op.reason}</dd></dl>
      <p className="confirmation-note">{op.action === 'refund' ? '确认后仅提交退款申请，不代表退款已到账。' : '提交工单通知仓库，不保证发货或送达时间。'}</p>
      {waiting ? <div className="actions"><button className="secondary" disabled={disabled} onClick={() => decide(op.id, false)}>取消</button><button className="primary" disabled={disabled} onClick={() => decide(op.id, true)}>确认{op.action === 'refund' ? '申请退款' : '催发货'} →</button></div>
        : <p className="resolved-text">{op.message}{op.application_id && <><br />申请编号：{op.application_id}</>}</p>}
    </section>
  }
  return <div className={'notice ' + item.status} role="status">{item.text}</div>
}

export default function App() {
  const [session, setSession] = useState<Session | null>(null)
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const [manual, setManual] = useState(false)
  const [loading, setLoading] = useState(true)
  const scroller = useRef<HTMLDivElement>(null)
  const pinned = useRef(true)
  const input = useRef<HTMLTextAreaElement>(null)

  async function newSession() {
    setError(''); setLoading(true)
    try {
      const next = await request<Session>('/api/sessions', {})
      localStorage.setItem('order-support-session', next.id)
      setSession(next); setText(''); pinned.current = true
    } catch (e) { setError((e as Error).message) }
    finally { setLoading(false) }
  }

  useEffect(() => {
    const id = localStorage.getItem('order-support-session')
    if (!id) { void newSession(); return }
    request<Session>('/api/sessions/' + id).then(setSession).catch(e => {
      localStorage.removeItem('order-support-session')
      setError((e as Error).message)
    }).finally(() => setLoading(false))
  }, [])

  // 刷新时若旧请求尚在运行，读取同进程内快照；这不承诺后端重启恢复。
  useEffect(() => {
    if (!session?.busy || sending) return
    const timer = setInterval(() => {
      request<Session>('/api/sessions/' + session.id).then(setSession).catch(e => setError((e as Error).message))
    }, 1000)
    return () => clearInterval(timer)
  }, [session?.busy, session?.id, sending])

  useEffect(() => {
    if (!scroller.current) return
    if (!session?.items.length) scroller.current.scrollTop = 0
    else if (pinned.current) scroller.current.scrollTop = scroller.current.scrollHeight
  }, [session?.items, sending])

  useEffect(() => {
    if (!manual) return
    const previous = document.activeElement as HTMLElement | null
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setManual(false)
      // 这个说明弹窗只有一个按钮，避免 Tab 跑到遮罩背后的操作。
      if (event.key === 'Tab') event.preventDefault()
    }
    document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('keydown', onKey); previous?.focus() }
  }, [manual])

  async function send(action: 'messages' | 'select', body: unknown) {
    if (!session || sending || session.busy) return
    setSending(true); setError(''); pinned.current = true
    try {
      // 按 SSE 事件更新 UI；正文是模型真实增量，不是前端逐字播放完整答案。
      await stream('/api/sessions/' + session.id + '/' + action, body, event => setSession(previous => previous ? applyEvent(previous, event) : previous))
    } catch (e) {
      setError((e as Error).message)
      try { setSession(await request<Session>('/api/sessions/' + session.id)) } catch { /* 保留连接错误提示。 */ }
    } finally { setSending(false); input.current?.focus() }
  }

  async function decide(id: string, approved: boolean) {
    if (!session || sending || session.busy) return
    setSending(true); setError('')
    // 只发送操作 ID 和决定，金额与订单仍由服务端待确认记录决定。
    try { setSession(await request<Session>('/api/sessions/' + session.id + '/decide', { operation_id: id, approved })) }
    catch (e) { setError((e as Error).message) }
    finally { setSending(false) }
  }

  function submit(event?: FormEvent) {
    event?.preventDefault()
    if (!text.trim()) return
    const query = text.trim(); setText('')
    void send('messages', { text: query })
  }

  const busy = sending || Boolean(session?.busy) || loading
  const waiting = Boolean(session?.pending) || Boolean(session?.candidates.length)
  const empty = !session?.items.length

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark">✳</div><div>订单助手<small>AGENT PRACTICE</small></div></div>
      <button className="new-session" onClick={() => void newSession()} disabled={busy}>＋ 新建会话</button>
      <div className="sidebar-label">当前工作区</div><div className="workspace"><span>◉</span> 订单售后 <span className="workspace-tag">02</span></div>
      <div className="sidebar-note"><span className="live-dot" /> 本地模拟环境<p>可查询订单、查看物流，<br />确认后提交催单或退款申请。</p></div>
      <div className="sidebar-bottom"><div className="avatar user-avatar">演</div><div>演示用户<small>固定身份 · 无需登录</small></div></div>
    </aside>
    <main className="main">
      <header><div><span className="breadcrumb">实战工作台 /</span> 订单售后助手</div><div className="header-actions"><button className="mobile-new help-button" disabled={busy} onClick={() => void newSession()}>＋ 新会话</button><button className="help-button" onClick={() => setManual(true)}>联系人工 ↗</button></div></header>
      <div className="environment"><span className="live-dot" /> 模拟订单 · 所有操作均不涉及真实交易 <span className="memory-note">服务重启后会话清空</span></div>
      <div className="conversation" ref={scroller} onScroll={() => {
        const el = scroller.current
        if (el) pinned.current = el.scrollHeight - el.scrollTop - el.clientHeight < 100
      }}>
        <div className="conversation-inner">
          {empty && <section className="welcome"><div className="welcome-icon">✳</div><div className="eyebrow">你好，有什么可以帮你？</div><h1>查订单，处理售后。<br /><span>说出你的需求就好。</span></h1><p>我会查询实际订单，说明依据。<br />需要执行操作时，会先征求你的确认。</p>
            <div className="suggestions">{suggestions.map(s => <button key={s.title} disabled={busy || !session} onClick={() => void send('messages', { text: s.text })}><span>{s.icon}</span><strong>{s.title}</strong><small>{s.text}</small></button>)}</div>
            <p className="sample-note">可试商品：白色／黑色耳机、充电线、定制键帽</p>
          </section>}
          {session?.items.map(item => <ItemView key={item.id} item={item} disabled={busy} choose={id => void send('select', { order_id: id })} decide={(id, value) => void decide(id, value)} />)}
        </div>
      </div>
      <div className="composer-area">
        {error && <div className="error-banner" role="alert">{error}<button onClick={() => void (session ? request<Session>('/api/sessions/' + session.id).then(setSession).then(() => setError('')).catch(e => setError((e as Error).message)) : newSession())}>恢复状态</button></div>}
        <div className="composer-meta"><span className={busy ? 'working' : ''}>{loading ? '正在连接…' : busy ? '正在处理，请稍候…' : session?.pending ? '等待确认 · 请核对上方订单与金额' : session?.candidates.length ? '等待选择 · 请点击上方订单卡片' : '可以开始新的问题'}</span><span>DeepSeek · 流式回复</span></div>
        <form className="composer" onSubmit={submit}>
          <textarea ref={input} aria-label="输入你的订单问题" placeholder={waiting ? '先完成上方的选择或确认…' : '例如：昨天买的耳机还没发货，帮我查一下…'} value={text} onChange={e => setText(e.target.value)} disabled={busy || waiting || !session} maxLength={2000}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); submit() } }} />
          <button className="send-button" type="submit" aria-label="发送消息" disabled={busy || waiting || !session || !text.trim()}>↑</button>
        </form>
        <div className="composer-footer">Enter 发送 · Shift + Enter 换行<span>模型解释，程序执行，你来确认。</span></div>
      </div>
    </main>
    {manual && <div className="modal-backdrop" onClick={() => setManual(false)}><section className="manual-modal" role="dialog" aria-modal="true" aria-labelledby="manual-title" onClick={e => e.stopPropagation()}><div className="eyebrow">人工处理入口</div><h2 id="manual-title">这一步交给人工核查</h2><p>当前为本地演示，尚未接入真实客服。你可以提供下面的订单信息，由人工核对规则、状态和退款资格。</p><div className="manual-reference">当前订单：{session?.selected ?? '尚未选择'}<br />会话：{session?.id.slice(0, 8) ?? '未建立'}</div><button className="primary" autoFocus onClick={() => setManual(false)}>我知道了</button></section></div>}
  </div>
}
