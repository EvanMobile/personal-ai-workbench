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
import { useI18n } from '../i18n'

export function CaptureView({ openView }: { openView: OpenView }) {
  const { notify } = useToast()
  const { t } = useI18n()
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
      notify(t('capture.toastStored'), 'success')
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
      notify(t('capture.toastDigest'), 'success')
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
          eyebrow={t('capture.eyebrow')}
          title={t('capture.title')}
          description={t('capture.description')}
        />

        <div className="capture-layout">
          <form className="capture-form" onSubmit={handleSubmit}>
            <div className="segmented" role="tablist" aria-label={t('capture.inputType')}>
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
                <Icon name="file" size={12} /> {t('capture.text')}
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
                <Icon name="upload" size={12} /> {t('capture.file')}
              </button>
            </div>

            {mode === 'text' ? (
              <div className="field">
                <div className="field-label-row">
                  <label htmlFor="capture-content" className="field-label">
                    {t('capture.rawContent')}
                  </label>
                  <span className="field-counter">{content.length.toLocaleString()} {t('common.chars')}</span>
                </div>
                <textarea
                  id="capture-content"
                  className="textarea capture-textarea"
                  placeholder={t('capture.contentPlaceholder')}
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
                <span className="field-hint">{t('capture.contentHint')}</span>
              </div>
            ) : (
              <div className="field">
                <span className="field-label">{t('capture.sourceFile')}</span>
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
                        {(file.size / 1024).toFixed(1)} KB · {file.type || t('capture.unknownType')}
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
                        {t('capture.clearFile')}
                      </button>
                    </>
                  ) : (
                    <>
                      <span className="drop-icon">
                        <Icon name="upload" size={22} />
                      </span>
                      <strong>{t('capture.dropFile')}</strong>
                      <span className="drop-meta">{t('capture.fileHint')}</span>
                    </>
                  )}
                </div>
              </div>
            )}

            <div className="field">
              <label className="field-label" htmlFor="capture-intent">
                {t('capture.intent')}
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
              <span className="field-hint">{t('capture.intentHint')}</span>
            </div>

            {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

            <div className="form-actions">
              <span className="form-status">
                <span className="status-dot" />
                {t('capture.ready')}
              </span>
              <button type="submit" className="button primary" disabled={!canSubmit}>
                {submitting ? <Spinner /> : <Icon name="bolt" size={13} />}
                {submitting ? t('capture.capturing') : t('capture.capture')}
              </button>
            </div>
          </form>

          <aside className="capture-aside">
            <div className="aside-panel">
              <MicroLabel>{t('capture.pipeline')}</MicroLabel>
              <ol className="pipeline-list">
                <li className="pipeline-list-item active">
                  <span className="pipeline-index">01</span>
                  <div>
                    <strong>{t('capture.capture')}</strong>
                    <span>{t('capture.rawStored')}</span>
                  </div>
                </li>
                <li className={cx('pipeline-list-item', result && 'active')}>
                  <span className="pipeline-index">02</span>
                  <div>
                    <strong>{t('capture.digest')}</strong>
                    <span>{t('capture.digestHint')}</span>
                  </div>
                </li>
                <li className={cx('pipeline-list-item', draft && 'active')}>
                  <span className="pipeline-index">03</span>
                  <div>
                    <strong>{t('capture.publish')}</strong>
                    <span>{t('capture.publishHint')}</span>
                  </div>
                </li>
              </ol>
            </div>

            {result && (
              <div className="aside-panel receipt-panel">
                <div className="receipt-head">
                  <MicroLabel>{t('capture.receipt')}</MicroLabel>
                  <Tag tone="success">{t('common.stored')}</Tag>
                </div>
                <dl className="meta-list">
                  <div>
                    <dt>{t('capture.receiptCapture')}</dt>
                    <dd title={result.capture_id}>{shortId(result.capture_id, 12)}</dd>
                  </div>
                  <div>
                    <dt>{t('capture.receiptRaw')}</dt>
                    <dd title={result.raw_content_id}>{shortId(result.raw_content_id, 12)}</dd>
                  </div>
                  <div>
                    <dt>{t('capture.receiptStatus')}</dt>
                    <dd>{result.status === 'stored' ? t('common.stored') : result.status}</dd>
                  </div>
                  <div>
                    <dt>{t('capture.receiptSource')}</dt>
                    <dd>{result.source_type}</dd>
                  </div>
                </dl>
                <p className="receipt-message">{t('capture.rawStored')}</p>

                {!draft && (
                  <button
                    type="button"
                    className="button full"
                    onClick={handleDigest}
                    disabled={digesting}
                  >
                    {digesting ? <Spinner /> : <Icon name="sparkles" size={13} />}
                    {digesting ? t('capture.digesting') : t('capture.runDigest')}
                  </button>
                )}

                {digestError && <ErrorBanner message={digestError} />}

                {draft && (
                  <div className="digest-result">
                    <div className="digest-result-head">
                      <Icon name="check" size={13} />
                      <span>{t('capture.draftGenerated')}</span>
                    </div>
                    <strong>{draft.title}</strong>
                    <p>{draft.summary || t('capture.noSummary')}</p>
                    <div className="digest-meta">
                      <Tag>{draft.category || t('home.uncategorized')}</Tag>
                      <span>v{draft.version}</span>
                      <span>{formatDateTime(draft.updated_at)}</span>
                    </div>
                    <button
                      type="button"
                      className="button primary full"
                      onClick={() =>
                        openView('draft', { id: draft.id, title: draft.title }, t('tabs.draft'))
                      }
                    >
                      {t('capture.openDraft')}
                      <Icon name="arrow-up-right" size={12} />
                    </button>
                  </div>
                )}
              </div>
            )}

            {!result && (
              <div className="aside-note">
                <Icon name="terminal" size={13} />
                <p>{t('capture.note')}</p>
              </div>
            )}
          </aside>
        </div>
      </div>
    </div>
  )
}
