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

export function ChatPanel({
  onCollapse,
  openView,
}: {
  onCollapse?: () => void
  openView: OpenView
}) {
  const { notify } = useToast()
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
      notify('Conversation started.', 'success')
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

  const activeConversation = conversations.find((item) => item.id === activeId) ?? null

  return (
    <aside className="chat-panel" aria-label="AI chat">
      <header className="chat-head">
        <div className="chat-head-title">
          <span className="chat-avatar">
            <Icon name="sparkles" size={13} />
          </span>
          <div>
            <MicroLabel>AI Chat</MicroLabel>
            <span className="chat-head-sub">context assistant</span>
          </div>
        </div>
        <div className="chat-head-actions">
          <button
            type="button"
            className="icon-button"
            onClick={startConversation}
            disabled={creating}
            title="New conversation"
            aria-label="New conversation"
          >
            <Icon name="plus" size={13} />
          </button>
          {onCollapse && (
            <button
              type="button"
              className="icon-button"
              onClick={onCollapse}
              title="Collapse chat panel"
              aria-label="Collapse chat panel"
            >
              <Icon name="panel-right" size={13} />
            </button>
          )}
        </div>
      </header>

      <div className="chat-conversation-bar">
        <span className="select-label">THREAD</span>
        <select
          className="select chat-select"
          value={activeId}
          onChange={(event) => setActiveId(event.target.value)}
          disabled={conversations.length === 0}
          aria-label="Select conversation"
        >
          {conversations.length === 0 && <option value="">No conversations</option>}
          {conversations.map((conversation) => (
            <option key={conversation.id} value={conversation.id}>
              {conversation.title || `Conversation ${shortId(conversation.id, 4)}`}
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
            <h3>No conversation</h3>
            <p>
              Start a thread with the context assistant. Suggestions are advisory and require
              confirmation.
            </p>
            <button
              type="button"
              className="button small primary"
              onClick={startConversation}
              disabled={creating}
            >
              <Icon name="plus" size={12} /> {creating ? 'Starting…' : 'New conversation'}
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
              <p>Thread ready. Ask about your cards, dossiers, or pages.</p>
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
                  {message.role === 'user' ? 'YOU' : message.role === 'assistant' ? 'AI' : message.role.toUpperCase()}
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
        {suggestionsError && (
          <div className="suggestion-error">
            <Icon name="alert" size={11} />
            <span>Suggestions unavailable</span>
          </div>
        )}

        {suggestions.length > 0 && (
          <div className="suggestion-block">
            <div className="suggestion-label">
              <MicroLabel>Suggested</MicroLabel>
              <span>requires confirmation</span>
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
                  title={suggestion.description || suggestion.title}
                  onClick={() =>
                    setPendingSuggestion((current) =>
                      current?.id === suggestion.id ? null : suggestion,
                    )
                  }
                >
                  <Icon name="sparkles" size={10} />
                  <span>{suggestion.title}</span>
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
              activeId ? 'Ask the assistant…' : 'Start a conversation to ask…'
            }
            rows={2}
            disabled={!activeId || sending}
          />
          <button
            type="submit"
            className="chat-send"
            disabled={!activeId || sending || !input.trim()}
            aria-label="Send message"
          >
            <Icon name={sending ? 'refresh' : 'send'} size={15} />
          </button>
        </form>
        <div className="chat-compose-foot">
          <span>ENTER to send · SHIFT+ENTER newline</span>
          <span className="chat-advisory">
            <Icon name="alert" size={9} /> advisory only
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
  const target = resolveSuggestionTarget(suggestion)
  const payloadPreview =
    suggestion.action?.payload && Object.keys(suggestion.action.payload).length > 0
      ? JSON.stringify(suggestion.action.payload)
      : null

  return (
    <div className="suggestion-confirm" role="alertdialog" aria-label="Suggestion confirmation">
      <div className="suggestion-confirm-head">
        <span>
          <Icon name="alert" size={11} />
          Suggested action · confirmation required
        </span>
        <button
          type="button"
          className="icon-button"
          onClick={onCancel}
          aria-label="Dismiss suggestion"
        >
          <Icon name="x" size={11} />
        </button>
      </div>
      <strong>{suggestion.title}</strong>
      {suggestion.description && <p>{suggestion.description}</p>}
      <div className="suggestion-action-line">
        <Tag>{suggestion.kind}</Tag>
        <code>{suggestion.action?.type || 'unknown'}</code>
        {target && <span>review only</span>}
      </div>
      {payloadPreview && <code className="suggestion-payload">{payloadPreview}</code>}
      <p className="suggestion-disclaimer">
        Nothing is applied automatically. Suggested mutations are not executed from this panel.
      </p>
      <div className="suggestion-confirm-actions">
        <button type="button" className="button ghost small" onClick={onCancel}>
          Cancel
        </button>
        {target ? (
          <button
            type="button"
            className="button small primary"
            onClick={() => onReview(target)}
          >
            Review context <Icon name="arrow-up-right" size={11} />
          </button>
        ) : (
          <button type="button" className="button small" onClick={onCancel}>
            Acknowledge
          </button>
        )}
      </div>
    </div>
  )
}
