import { useRef, useState, type DragEvent, type FormEvent } from 'react'
import { api, errorMessage } from '../api'
import { Icon } from '../components/Icon'
import { useToast } from '../components/Toast'
import {
  ErrorBanner,
  MicroLabel,
  Spinner,
  Tag,
  ViewHeader,
} from '../components/ui'
import type { CaptureResponse, Draft, OpenView } from '../types'
import { cx, formatDateTime, shortId } from '../utils'

export function CaptureView({ openView }: { openView: OpenView }) {
  const { notify } = useToast()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [mode, setMode] = useState<'text' | 'file'>('text')
  const [content, setContent] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [intent, setIntent] = useState('knowledge_capture')
  const [dragging, setDragging] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<CaptureResponse | null>(null)
  const [digesting, setDigesting] = useState(false)
  const [digestError, setDigestError] = useState<string | null>(null)
  const [draft, setDraft] = useState<Draft | null>(null)

  const canSubmit =
    !submitting && intent.trim().length > 0 && (mode === 'text' ? content.trim().length > 0 : Boolean(file))

  const resetResult = () => {
    setResult(null)
    setDraft(null)
    setDigestError(null)
    setError(null)
  }

  const readFile = (candidate: File | undefined) => {
    if (!candidate) return
    setFile(candidate)
    resetResult()
  }

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setDragging(false)
    readFile(event.dataTransfer.files?.[0])
  }

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    if (!canSubmit) return
    setSubmitting(true)
    setError(null)
    setDigestError(null)
    setDraft(null)
    setResult(null)
    try {
      const response =
        mode === 'text'
          ? await api.captureText({
              input_type: 'text',
              content: content.trim(),
              intent: intent.trim(),
            })
          : await api.captureFile(file as File, intent.trim())
      setResult(response)
      setContent('')
      setFile(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
      notify('Capture stored. Raw content is ready for digest.', 'success')
    } catch (caught) {
      const message = errorMessage(caught)
      setError(message)
      notify(message, 'danger')
    } finally {
      setSubmitting(false)
    }
  }

  const handleDigest = async () => {
    if (!result) return
    setDigesting(true)
    setDigestError(null)
    try {
      const response = await api.digest(result.raw_content_id)
      setDraft(response.draft)
      notify('Digest complete. A draft is ready for review.', 'success')
    } catch (caught) {
      const message = errorMessage(caught)
      setDigestError(message)
      notify(message, 'danger')
    } finally {
      setDigesting(false)
    }
  }

  return (
    <div className="view-scroll">
      <div className="view-inner view-inner-narrow">
        <ViewHeader
          eyebrow="Ingestion / Capture"
          title="Capture context"
          description="Send raw text or a file into the pipeline. Nothing is generated until you run a digest."
        />

        <div className="capture-layout">
          <form className="capture-form" onSubmit={handleSubmit}>
            <div className="segmented" role="tablist" aria-label="Capture input type">
              <button
                type="button"
                role="tab"
                aria-selected={mode === 'text'}
                className={cx('segment', mode === 'text' && 'segment-active')}
                onClick={() => {
                  setMode('text')
                  resetResult()
                }}
              >
                <Icon name="file" size={12} /> Text
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={mode === 'file'}
                className={cx('segment', mode === 'file' && 'segment-active')}
                onClick={() => {
                  setMode('file')
                  resetResult()
                }}
              >
                <Icon name="upload" size={12} /> File
              </button>
            </div>

            {mode === 'text' ? (
              <div className="field">
                <div className="field-label-row">
                  <label htmlFor="capture-content" className="field-label">
                    Raw content
                  </label>
                  <span className="field-counter">{content.length.toLocaleString()} chars</span>
                </div>
                <textarea
                  id="capture-content"
                  className="textarea capture-textarea"
                  placeholder={
                    'Paste notes, a passage, a decision, or anything worth retaining…\n\nMarkdown is preserved through the pipeline.'
                  }
                  value={content}
                  rows={14}
                  onChange={(event) => {
                    setContent(event.target.value)
                    resetResult()
                  }}
                  onKeyDown={(event) => {
                    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
                      event.currentTarget.form?.requestSubmit()
                    }
                  }}
                />
                <span className="field-hint">⌘↵ to capture · plain text or Markdown</span>
              </div>
            ) : (
              <div className="field">
                <span className="field-label">Source file</span>
                <div
                  className={cx('drop-zone', dragging && 'drop-zone-active', file && 'drop-zone-filled')}
                  onDragOver={(event) => {
                    event.preventDefault()
                    setDragging(true)
                  }}
                  onDragLeave={() => setDragging(false)}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault()
                      fileInputRef.current?.click()
                    }
                  }}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    className="visually-hidden"
                    accept=".txt,.md,.markdown,.pdf,text/plain,text/markdown,application/pdf"
                    onChange={(event) => readFile(event.target.files?.[0])}
                  />
                  {file ? (
                    <>
                      <span className="drop-icon">
                        <Icon name="file" size={22} />
                      </span>
                      <strong>{file.name}</strong>
                      <span className="drop-meta">
                        {(file.size / 1024).toFixed(1)} KB · {file.type || 'unknown type'}
                      </span>
                      <button
                        type="button"
                        className="text-button"
                        onClick={(event) => {
                          event.stopPropagation()
                          setFile(null)
                          resetResult()
                          if (fileInputRef.current) fileInputRef.current.value = ''
                        }}
                      >
                        Clear file
                      </button>
                    </>
                  ) : (
                    <>
                      <span className="drop-icon">
                        <Icon name="upload" size={22} />
                      </span>
                      <strong>Drop a file here or browse</strong>
                      <span className="drop-meta">TXT, MD, PDF · one file at a time</span>
                    </>
                  )}
                </div>
              </div>
            )}

            <div className="field">
              <label className="field-label" htmlFor="capture-intent">
                Intent
              </label>
              <input
                id="capture-intent"
                className="input mono-input"
                value={intent}
                onChange={(event) => {
                  setIntent(event.target.value)
                  resetResult()
                }}
                placeholder="knowledge_capture"
                autoComplete="off"
                spellCheck={false}
              />
              <span className="field-hint">
                Routed to the backend ingestion service. Default: knowledge_capture
              </span>
            </div>

            {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

            <div className="form-actions">
              <span className="form-status">
                <span className="status-dot" />
                Ready to ingest
              </span>
              <button type="submit" className="button primary" disabled={!canSubmit}>
                {submitting ? <Spinner /> : <Icon name="bolt" size={13} />}
                {submitting ? 'Capturing…' : 'Capture'}
              </button>
            </div>
          </form>

          <aside className="capture-aside">
            <div className="aside-panel">
              <MicroLabel>Pipeline</MicroLabel>
              <ol className="pipeline-list">
                <li className="pipeline-list-item active">
                  <span className="pipeline-index">01</span>
                  <div>
                    <strong>Capture</strong>
                    <span>Raw content is stored with source metadata.</span>
                  </div>
                </li>
                <li className={cx('pipeline-list-item', result && 'active')}>
                  <span className="pipeline-index">02</span>
                  <div>
                    <strong>Digest</strong>
                    <span>Generate a structured draft from the raw input.</span>
                  </div>
                </li>
                <li className={cx('pipeline-list-item', draft && 'active')}>
                  <span className="pipeline-index">03</span>
                  <div>
                    <strong>Publish</strong>
                    <span>Turn the draft into a card and artifact.</span>
                  </div>
                </li>
              </ol>
            </div>

            {result && (
              <div className="aside-panel receipt-panel">
                <div className="receipt-head">
                  <MicroLabel>Capture receipt</MicroLabel>
                  <Tag tone="success">stored</Tag>
                </div>
                <dl className="meta-list">
                  <div>
                    <dt>capture</dt>
                    <dd title={result.capture_id}>{shortId(result.capture_id, 12)}</dd>
                  </div>
                  <div>
                    <dt>raw content</dt>
                    <dd title={result.raw_content_id}>{shortId(result.raw_content_id, 12)}</dd>
                  </div>
                  <div>
                    <dt>status</dt>
                    <dd>{result.status}</dd>
                  </div>
                  <div>
                    <dt>source</dt>
                    <dd>{result.source_type}</dd>
                  </div>
                </dl>
                <p className="receipt-message">{result.message}</p>

                {!draft && (
                  <button
                    type="button"
                    className="button full"
                    onClick={handleDigest}
                    disabled={digesting}
                  >
                    {digesting ? <Spinner /> : <Icon name="sparkles" size={13} />}
                    {digesting ? 'Digesting…' : 'Run digest'}
                  </button>
                )}

                {digestError && <ErrorBanner message={digestError} />}

                {draft && (
                  <div className="digest-result">
                    <div className="digest-result-head">
                      <Icon name="check" size={13} />
                      <span>Draft generated</span>
                    </div>
                    <strong>{draft.title}</strong>
                    <p>{draft.summary || 'No summary returned.'}</p>
                    <div className="digest-meta">
                      <Tag>{draft.category || 'uncategorized'}</Tag>
                      <span>v{draft.version}</span>
                      <span>{formatDateTime(draft.updated_at)}</span>
                    </div>
                    <button
                      type="button"
                      className="button primary full"
                      onClick={() =>
                        openView('draft', { id: draft.id, title: draft.title }, 'Draft')
                      }
                    >
                      Open draft
                      <Icon name="arrow-up-right" size={12} />
                    </button>
                  </div>
                )}
              </div>
            )}

            {!result && (
              <div className="aside-note">
                <Icon name="terminal" size={13} />
                <p>
                  Capture is non-destructive. Raw inputs remain available after a draft is
                  generated and published.
                </p>
              </div>
            )}
          </aside>
        </div>
      </div>
    </div>
  )
}
