import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import ts from 'typescript'
import { messages } from '../src/i18n/messages.ts'

const locales = ['zh-CN', 'en-US']
const zhKeys = Object.keys(messages['zh-CN']).sort()
const enKeys = Object.keys(messages['en-US']).sort()

test('zh-CN and en-US expose the same message keys', () => {
  assert.deepEqual(enKeys, zhKeys)
})

test('every locale has a non-empty message for every key', () => {
  for (const locale of locales) {
    for (const key of zhKeys) {
      assert.equal(typeof messages[locale][key], 'string', `${locale}:${key} must be a string`)
      assert.ok(messages[locale][key].trim().length > 0, `${locale}:${key} must not be empty`)
    }
  }
})

test('interpolation placeholders match across locales', () => {
  const placeholders = (value) => [...value.matchAll(/\{(\w+)\}/g)].map((match) => match[1]).sort()
  for (const key of zhKeys) {
    assert.deepEqual(
      placeholders(messages['en-US'][key]),
      placeholders(messages['zh-CN'][key]),
      `placeholder mismatch for ${key}`,
    )
  }
})

test('UI source files do not hardcode CJK copy outside the locale catalogue', () => {
  const root = path.resolve('src')
  const offenders = []
  const walk = (directory) => {
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      const file = path.join(directory, entry.name)
      if (entry.isDirectory()) {
        if (entry.name === 'i18n') continue
        walk(file)
      } else if (/\.(ts|tsx)$/.test(entry.name)) {
        const source = fs.readFileSync(file, 'utf8')
        if (/[\u4e00-\u9fff]/.test(source)) offenders.push(path.relative(root, file))
      }
    }
  }
  walk(root)
  assert.deepEqual(offenders, [])
})

test('visible JSX text and UI attributes do not bypass the catalogue', () => {
  const root = path.resolve('src')
  const offenders = []
  const allowedText = new Set([
    'Personal AI Workbench',
    'CTX',
    '⌘N',
    'KB ·',
    'knowledge_capture',
    'v',
    'P.',
    'P1.M1',
  ])
  const allowedMessages = new Set([
    'useToast must be used within ToastProvider',
    'useI18n must be used within I18nProvider',
  ])
  const isClassList = (value) => /^[a-z0-9-]+( [a-z0-9-]+)+$/.test(value)
  const isInsideTranslate = (node) => {
    for (let parent = node.parent; parent; parent = parent.parent) {
      if (ts.isCallExpression(parent) && parent.expression.getText() === 't') return true
    }
    return false
  }
  const isSentenceLiteral = (value) => {
    if (!/[A-Za-z]+\s+[A-Za-z]+/.test(value)) return false
    if (isClassList(value)) return false
    if (/^[MLz]\s/.test(value) || value.startsWith('url(') || value.startsWith('translate(')) return false
    return true
  }
  const walkFiles = (directory) => {
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      const file = path.join(directory, entry.name)
      if (entry.isDirectory()) {
        if (entry.name === 'i18n') continue
        walkFiles(file)
      } else if (entry.name.endsWith('.tsx')) {
        const source = fs.readFileSync(file, 'utf8')
        const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
        const report = (node, value) => {
          offenders.push(`${path.relative(root, file)}: ${JSON.stringify(value.trim())}`)
        }
        const visit = (node) => {
          if (ts.isJsxText(node)) {
            const value = node.text.replace(/\s+/g, ' ').trim()
            if (/[A-Za-z]/.test(value) && !allowedText.has(value)) report(node, value)
          }
          if (ts.isJsxAttribute(node)) {
            const name = node.name.getText()
            if (['title', 'aria-label', 'placeholder', 'alt'].includes(name) &&
                node.initializer && ts.isStringLiteral(node.initializer) &&
                /[A-Za-z]/.test(node.initializer.text) && !allowedText.has(node.initializer.text)) {
              report(node, node.initializer.text)
            }
          }
          if (ts.isStringLiteral(node) && !isInsideTranslate(node)) {
            const parent = node.parent
            if (ts.isImportDeclaration(parent) || ts.isExportDeclaration(parent)) return
            if (ts.isJsxAttribute(parent) &&
                ['className', 'id', 'role', 'type', 'name', 'href', 'src', 'd', 'fill', 'viewBox', 'stroke', 'xmlns', 'autoComplete', 'accept', 'form', 'htmlFor'].includes(parent.name.getText())) return
            if (isSentenceLiteral(node.text) && !allowedMessages.has(node.text) && !allowedText.has(node.text)) {
              report(node, node.text)
            }
          }
          ts.forEachChild(node, visit)
        }
        visit(sf)
      }
    }
  }
  walkFiles(root)
  assert.deepEqual(offenders, [])
})
