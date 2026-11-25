import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { messages } from '../src/i18n/messages.ts'

const LOCALES = ['zh-CN', 'en-US']

const RAG_TERM_KEYS = [
  'rag.term.dataset',
  'rag.term.document',
  'rag.term.chunk',
  'rag.term.chunking',
  'rag.term.embedding',
  'rag.term.retrieval',
  'rag.term.reranking',
  'rag.term.evaluation',
  'rag.term.experiment',
  'rag.term.run',
  'rag.term.step',
  'rag.term.job',
  'rag.term.attempt',
  'rag.term.event',
  'rag.term.artifact',
  'rag.term.dossier',
  'rag.term.groundTruth',
]

const RAG_ERROR_KEYS = [
  'rag.error.RAG_DOSSIER_NOT_FOUND',
  'rag.error.RAG_RUN_NOT_FOUND',
  'rag.error.RAG_DOSSIER_ARCHIVED',
  'rag.error.RAG_IDEMPOTENCY_CONFLICT',
  'rag.error.RAG_RUN_INCOMPLETE',
  'rag.error.RAG_RUN_NOT_CANCELLABLE',
  'rag.error.RAG_UNSUPPORTED_RUN_KIND',
  'rag.error.RAG_INVALID_RUN_PARAMS',
  'rag.error.RAG_IDEMPOTENCY_KEY_REQUIRED',
  'rag.error.RAG_INVALID_IDEMPOTENCY_KEY',
  'rag.error.RAG_VALIDATION_ERROR',
  'rag.error.RAG_INTERNAL_ERROR',
  'rag.error.RAG_EXECUTION_CONFLICT',
]

test('RAG Lab terminology and API error keys exist in both locales', () => {
  for (const locale of LOCALES) {
    for (const key of [...RAG_TERM_KEYS, ...RAG_ERROR_KEYS]) {
      assert.equal(typeof messages[locale][key], 'string', `${locale}:${key} must be a string`)
      assert.ok(messages[locale][key].trim().length > 0, `${locale}:${key} must not be empty`)
    }
  }
})

test('RAG Lab terminology is consistent and locale-distinct', () => {
  for (const key of RAG_TERM_KEYS) {
    assert.notEqual(messages['zh-CN'][key], messages['en-US'][key], `${key} should be localized`)
  }
  assert.equal(messages['zh-CN']['rag.term.dossier'], 'RAG 实验档案')
  assert.equal(messages['en-US']['rag.term.dossier'], 'RAG experiment dossier')
  // RAG Dossier must not reuse the M02 Personal Knowledge "档案集" term.
  assert.notEqual(messages['zh-CN']['rag.term.dossier'], messages['zh-CN']['common.dossiers'])
})

test('default locale remains zh-CN and en-US is supported', () => {
  const source = fs.readFileSync(path.resolve('src/i18n/index.tsx'), 'utf8')
  assert.match(source, /const DEFAULT_LOCALE: Locale = 'zh-CN'/)
  assert.match(source, /value === 'zh-CN' \|\| value === 'en-US'/)
})
