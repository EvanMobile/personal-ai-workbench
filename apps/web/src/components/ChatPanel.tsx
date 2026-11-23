import { useEffect, useRef, useState, type FormEvent } from 'react'
import { api, errorMessage } from '../api'
import type {
  ChatMessage,
  ChatSuggestion,
  ConversationSummary,
  OpenView,
  ViewKind,
} from '../types'
import { cx, isRecord, relativeTime, shortId } from '../utils'
import { Icon } from './Icon'
import { Markdown } from './Markdown'
import { useToast } from './Toast'
import { ErrorBanner, MicroLabel, Skeleton, Tag } from './ui'
import { useI18n } from '../i18n'

interface SuggestionTarget {
  kind: ViewKind
  id?: string
  title: string
}

function resolveSuggestionTarget(suggestion: ChatSuggestion): SuggestionTarget | null {
  const type = (suggestion.action?.type ?? '').toLowerCase()
  const kind = suggestion.kind.toLowerCase()
  const payload = suggestion.action?.payload
  const record = isRecord(payload) ? payload : {}

  const ids = [
    record.card_id,
    record.asset_id,
    record.page_id,
    record.dossier_id,
    record.draft_id,
    suggestion.related_id,
    record.id,
  ].filter((value): value is string => typeof value === 'string' && value.length > 0)

  const haystack = `${type} ${kind}`

  if (haystack.includes('dossier')) {
    return ids[0] ? { kind: 'dossier', id: ids[0], title: suggestion.title } : null
  }
  if (haystack.includes('page')) {
    return ids[0] ? { kind: 'page', id: ids[0], title: suggestion.title } : null
  }
  if (haystack.includes('draft')) {
    return ids[0] ? { kind: 'draft', id: ids[0], title: suggestion.title } : null
  }
  if (haystack.includes('card') || haystack.includes('asset')) {
    return ids[0] ? { kind: 'card', id: ids[0], title: suggestion.title } : null
  }
  if (haystack.includes('capture') || haystack.includes('ingest')) {
    return { kind: 'capture', title: suggestion.title }
  }
  if (ids[0]) {
    return { kind: 'card', id: ids[0], title: suggestion.title }
  }
  return null
}

function localizedSuggestion(
  suggestion: ChatSuggestion,
  t: ReturnType<typeof useI18n>['t'],
): { title: string; description?: string } {
  const haystack = `${suggestion.kind} ${suggestion.action?.type ?? ''}`.toLowerCase()
  const count = Number(suggestion.title.match(/\d+/)?.[0] ?? 0)
  if (haystack.includes('draft')) {
    return {
      title:
        count > 0
          ? t(count === 1 ? 'chat.reviewDraftOne' : 'chat.reviewDraftCount', { count })
          : t('chat.reviewDraft'),
      description: t('chat.reviewDraftBody'),
    }
  }
  if (haystack.includes('page')) {
    return { title: t('chat.reviewPage'), description: t('chat.reviewPageBody') }
  }
  if (haystack.includes('dossier')) {
    return { title: t('chat.reviewDossier'), description: t('chat.reviewDossierBody') }
  }
  if (haystack.includes('card') || haystack.includes('asset')) {
    return {
      title:
        count > 0
          ? t(count === 1 ? 'chat.reviewCardsOne' : 'chat.reviewCardsCount', { count })
          : t('chat.reviewCards'),
      description: t('chat.reviewCardsBody'),
    }
  }
  return { title: suggestion.title, description: suggestion.description }
}

export function ChatPanel({
  onCollapse,
  openView,
}: {
  onCollapse?: () => void
  openView: OpenView
}) {
  const { notify } = useToast()
  const { t } = useI18n()
  const [conversations, setConversations] = useState<ConversationSummary[]>([])
  const [activeId, setActiveId] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [conversationsLoading, setConversationsLoading] = useState(true)
  const [threadLoading, setThreadLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [threadError, setThreadError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [dingtalkInput, setDingtalkInput] = useState('')
  const [dingtalkSending, setDingtalkSending] = useState(false)
  const [dingtalkResult, setDingtalkResult] = useState<{ kind: 'success' | 'error'; text: string } | null>(null)
  const [suggestions, setSuggestions] = useState<ChatSuggestion[]>([])
  const [suggestionsError, setSuggestionsError] = useState<string | null>(null)
  const [pendingSuggestion, setPendingSuggestion] = useState<ChatSuggestion | null>(null)
  const [messagesRevision, setMessagesRevision] = useState(0)
  const [threadRevision, setThreadRevision] = useState(0)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let active = true
    const controller = new AbortController()
    setConversationsLoading(true)
    setError(null)
    api
      .conversations(controller.signal)
      .then((items) => {
        if (!active) return
        setConversations(items)
        setActiveId((current) => current || items[0]?.id || '')
        setConversationsLoading(false)
      })
      .catch((caught) => {
        if (!active || (caught instanceof DOMException && caught.name === 'AbortError')) return
        setError(errorMessage(caught))
        setConversationsLoading(false)
      })
    return () => {
      active = false
      controller.abort()
    }
  }, [messagesRevision])

  useEffect(() => {
    let active = true
    const controller = new AbortController()
    api
      .suggestions(controller.signal)
      .then((items) => {
        if (!active) return
        setSuggestions(items)
        setSuggestionsError(null)
      })
      .catch((caught) => {
        if (!active || (caught instanceof DOMException && caught.name === 'AbortError')) return
        setSuggestionsError(errorMessage(caught))
      })
    return () => {
      active = false
      controller.abort()
    }
  }, [])

  useEffect(() => {
    if (!activeId) {
      setMessages([])
      return
    }
    let active = true
    const controller = new AbortController()
    setThreadLoading(true)
    setThreadError(null)
    api
      .conversation(activeId, controller.signal)
      .then((detail) => {
        if (!active) return
        setMessages(detail.messages)
        setThreadLoading(false)
      })
      .catch((caught) => {
        if (!active || (caught instanceof DOMException && caught.name === 'AbortError')) return
        setThreadError(errorMessage(caught))
        setThreadLoading(false)
      })
    return () => {
      active = false
      controller.abort()
    }
  }, [activeId, threadRevision])

  useEffect(() => {
    const node = scrollRef.current
    if (node) node.scrollTop = node.scrollHeight
  }, [messages.length, threadLoading, activeId])

  const loadConversations = () => {
    setMessagesRevision((value) => value + 1)
  }

  const retryThread = () => {
    setThreadRevision((value) => value + 1)
  }

  const startConversation = async () => {
    setCreating(true)
    try {
      const conversation = await api.createConversation()
      setConversations((previous) => [conversation, ...previous.filter((item) => item.id !== conversation.id)])
      setActiveId(conversation.id)
      setThreadError(null)
      notify(t('chat.toastStarted'), 'success')
    } catch (caught) {
      notify(errorMessage(caught), 'danger')
    } finally {
      setCreating(false)
    }
  }

  const send = async (event: FormEvent) => {
    event.preventDefault()
    const content = input.trim()
    if (!content || !activeId || sending) return
    setSending(true)
    setThreadError(null)
    setPendingSuggestion(null)
    try {
      const exchange = await api.sendMessage(activeId, content)
      setMessages((previous) => [...previous, exchange.user, exchange.reply])
      setInput('')
      setConversations((previous) =>
        [...previous]
          .map((conversation) =>
            conversation.id === activeId
              ? { ...conversation, updated_at: new Date().toISOString() }
              : conversation,
          )
          .sort(
            (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
          ),
      )
      api
        .suggestions()
        .then(setSuggestions)
        .catch(() => undefined)
    } catch (caught) {
      const message = errorMessage(caught)
      setThreadError(message)
      notify(message, 'danger')
    } finally {
      setSending(false)
    }
  }

  const sendDingTalk = async (event: FormEvent) => {
    event.preventDefault()
    const content = dingtalkInput.trim()
    if (!content || dingtalkSending) return
    setDingtalkSending(true)
    setDingtalkResult(null)
    try {
      await api.sendDingTalkMessage(content)
      setDingtalkResult({ kind: 'success', text: t('chat.dingtalkSuccess') })
    } catch (caught) {
      setDingtalkResult({ kind: 'error', text: errorMessage(caught) })
    } finally {
      setDingtalkSending(false)
    }
  }

  useEffect(() => {
    if (!dingtalkInput) setDingtalkInput(t('chat.dingtalkDefault'))
  }, [dingtalkInput, t])

  const activeConversation = conversations.find((item) => item.id === activeId) ?? null

  return (
    <aside className="chat-panel" aria-label={t('chat.title')}>
      <header className="chat-head">
        <div className="chat-head-title">
          <span className="chat-avatar">
            <Icon name="sparkles" size={13} />
          </span>
          <div>
            <MicroLabel>{t('chat.title')}</MicroLabel>
            <span className="chat-head-sub">{t('chat.subtitle')}</span>
          </div>
        </div>
        <div className="chat-head-actions">
          <button
            type="button"
            className="icon-button"
            onClick={startConversation}
            disabled={creating}
            title={t('chat.newConversation')}
            aria-label={t('chat.newConversation')}
          >
            <Icon name="plus" size={13} />
          </button>
          {onCollapse && (
            <button
              type="button"
              className="icon-button"
              onClick={onCollapse}
              title={t('chat.collapse')}
              aria-label={t('chat.collapse')}
            >
              <Icon name="panel-right" size={13} />
            </button>
          )}
        </div>
      </header>

      <div className="chat-conversation-bar">
        <span className="select-label">{t('chat.thread')}</span>
        <select
          className="select chat-select"
          value={activeId}
          onChange={(event) => setActiveId(event.target.value)}
          disabled={conversations.length === 0}
          aria-label={t('chat.selectConversation')}
        >
          {conversations.length === 0 && <option value="">{t('chat.noConversations')}</option>}
          {conversations.map((conversation) => (
            <option key={conversation.id} value={conversation.id}>
              {conversation.title || t('chat.conversation', { id: shortId(conversation.id, 4) })}
            </option>
          ))}
        </select>
      </div>

      <div className="chat-messages" ref={scrollRef}>
        {error && (
          <div className="chat-inline-error">
            <ErrorBanner message={error} onRetry={loadConversations} />
          </div>
        )}

        {conversationsLoading && !error && (
          <div className="chat-loading">
            <Skeleton lines={3} />
            <div className="chat-msg-skeleton">
              <Skeleton lines={2} />
            </div>
            <Skeleton lines={4} />
          </div>
        )}

        {!conversationsLoading && conversations.length === 0 && !error && (
          <div className="chat-empty">
            <span className="chat-empty-icon">
              <Icon name="chat" size={24} />
            </span>
            <h3>{t('chat.noConversation')}</h3>
            <p>{t('chat.emptyBody')}</p>
            <button
              type="button"
              className="button small primary"
              onClick={startConversation}
              disabled={creating}
            >
              <Icon name="plus" size={12} /> {creating ? t('chat.starting') : t('chat.newConversation')}
            </button>
          </div>
        )}

        {threadError && <ErrorBanner message={threadError} onRetry={retryThread} />}

        {threadLoading && (
          <div className="chat-loading">
            <Skeleton lines={2} />
            <div className="chat-msg-skeleton">
              <Skeleton lines={3} />
            </div>
          </div>
        )}

        {!threadLoading &&
          !threadError &&
          activeConversation &&
          messages.length === 0 && (
            <div className="chat-thread-empty">
              <Icon name="terminal" size={16} />
              <p>{t('chat.threadReady')}</p>
            </div>
          )}

        {!threadLoading &&
          messages.map((message) => (
            <div
              key={message.id}
              className={cx('chat-message', `chat-message-${message.role}`)}
            >
              <div className="chat-message-meta">
                <span className="chat-role">
                  {message.role === 'user' ? t('chat.you') : message.role === 'assistant' ? t('chat.ai') : message.role.toUpperCase()}
                </span>
                <span>{relativeTime(message.created_at)}</span>
              </div>
              <div className="chat-bubble">
                {message.role === 'assistant' ? (
                  <Markdown source={message.content} />
                ) : (
                  <p className="chat-user-text">{message.content}</p>
                )}
              </div>
            </div>
          ))}
      </div>

      <div className="chat-compose">
        <section className="dingtalk-test" aria-label={t('chat.dingtalkTitle')}>
          <div className="dingtalk-test-head">
            <MicroLabel>{t('chat.dingtalkTitle')}</MicroLabel>
            <span>{t('chat.dingtalkGroup')}</span>
          </div>
          <form className="dingtalk-test-form" onSubmit={sendDingTalk}>
            <textarea
              className="chat-input dingtalk-input"
              value={dingtalkInput}
              onChange={(event) => setDingtalkInput(event.target.value)}
              rows={2}
              maxLength={2000}
              disabled={dingtalkSending}
              aria-label={t('chat.dingtalkMessage')}
            />
            <button
              type="submit"
              className="button small primary dingtalk-send"
              disabled={dingtalkSending || !dingtalkInput.trim()}
              aria-label={dingtalkSending ? t('chat.dingtalkSending') : t('chat.dingtalkSend')}
            >
              <Icon name={dingtalkSending ? 'refresh' : 'send'} size={12} />
              {dingtalkSending ? t('chat.dingtalkSending') : t('chat.dingtalkSend')}
            </button>
          </form>
          {dingtalkResult && (
            <div className={`dingtalk-result dingtalk-result-${dingtalkResult.kind}`} role="status" aria-live="polite">
              {dingtalkResult.text}
            </div>
          )}
        </section>
        {suggestionsError && (
          <div className="suggestion-error">
            <Icon name="alert" size={11} />
            <span>{t('chat.suggestionsUnavailable')}</span>
          </div>
        )}

        {suggestions.length > 0 && (
          <div className="suggestion-block">
            <div className="suggestion-label">
              <MicroLabel>{t('chat.suggested')}</MicroLabel>
              <span>{t('chat.requiresConfirmation')}</span>
            </div>
            <div className="suggestion-chips">
              {suggestions.slice(0, 5).map((suggestion) => (
                <button
                  key={suggestion.id}
                  type="button"
                  className={cx(
                    'suggestion-chip',
                    pendingSuggestion?.id === suggestion.id && 'suggestion-chip-active',
                  )}
                  title={localizedSuggestion(suggestion, t).description || localizedSuggestion(suggestion, t).title}
                  onClick={() =>
                    setPendingSuggestion((current) =>
                      current?.id === suggestion.id ? null : suggestion,
                    )
                  }
                >
                  <Icon name="sparkles" size={10} />
                  <span>{localizedSuggestion(suggestion, t).title}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {pendingSuggestion && (
          <SuggestionConfirmation
            suggestion={pendingSuggestion}
            onCancel={() => setPendingSuggestion(null)}
            onReview={(target) => {
              setPendingSuggestion(null)
              openView(target.kind, target.id ? { id: target.id } : undefined, target.title)
            }}
          />
        )}

        <form className="chat-input-row" onSubmit={send}>
          <textarea
            className="chat-input"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                event.currentTarget.form?.requestSubmit()
              }
            }}
            placeholder={
              activeId ? t('chat.placeholder') : t('chat.placeholderNoConversation')
            }
            rows={2}
            disabled={!activeId || sending}
          />
          <button
            type="submit"
            className="chat-send"
            disabled={!activeId || sending || !input.trim()}
            aria-label={t('chat.send')}
          >
            <Icon name={sending ? 'refresh' : 'send'} size={15} />
          </button>
        </form>
        <div className="chat-compose-foot">
          <span>{t('chat.enterHint')}</span>
          <span className="chat-advisory">
            <Icon name="alert" size={9} /> {t('chat.advisoryOnly')}
          </span>
        </div>
      </div>
    </aside>
  )
}

function SuggestionConfirmation({
  suggestion,
  onCancel,
  onReview,
}: {
  suggestion: ChatSuggestion
  onCancel: () => void
  onReview: (target: SuggestionTarget) => void
}) {
  const { t } = useI18n()
  const target = resolveSuggestionTarget(suggestion)
  const display = localizedSuggestion(suggestion, t)
  const payloadPreview =
    suggestion.action?.payload && Object.keys(suggestion.action.payload).length > 0
      ? JSON.stringify(suggestion.action.payload)
      : null

  return (
    <div className="suggestion-confirm" role="alertdialog" aria-label={t('chat.suggestionConfirmation')}>
      <div className="suggestion-confirm-head">
        <span>
          <Icon name="alert" size={11} />
          {t('chat.suggestedAction')}
        </span>
        <button
          type="button"
          className="icon-button"
          onClick={onCancel}
          aria-label={t('chat.dismissSuggestion')}
        >
          <Icon name="x" size={11} />
        </button>
      </div>
      <strong>{display.title}</strong>
      {display.description && <p>{display.description}</p>}
      <div className="suggestion-action-line">
        <Tag>{suggestion.kind}</Tag>
        <code>{suggestion.action?.type || 'unknown'}</code>
        {target && <span>{t('chat.reviewOnly')}</span>}
      </div>
      {payloadPreview && <code className="suggestion-payload">{payloadPreview}</code>}
      <p className="suggestion-disclaimer">{t('chat.disclaimer')}</p>
      <div className="suggestion-confirm-actions">
        <button type="button" className="button ghost small" onClick={onCancel}>
          {t('common.cancel')}
        </button>
        {target ? (
          <button
            type="button"
            className="button small primary"
            onClick={() => onReview({ ...target, title: display.title })}
          >
            {t('chat.reviewContext')} <Icon name="arrow-up-right" size={11} />
          </button>
        ) : (
          <button type="button" className="button small" onClick={onCancel}>
            {t('chat.acknowledge')}
          </button>
        )}
      </div>
    </div>
  )
}
