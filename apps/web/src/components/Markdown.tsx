import type { ReactNode } from 'react'

interface MarkdownProps {
  source: string | null | undefined
  className?: string
}

type Block =
  | { type: 'heading'; level: number; text: string }
  | { type: 'paragraph'; text: string }
  | { type: 'ul'; items: string[] }
  | { type: 'ol'; items: string[] }
  | { type: 'quote'; text: string }
  | { type: 'code'; lang: string; text: string }
  | { type: 'hr' }

/**
 * A deliberately small Markdown renderer. It emits React elements only:
 * raw HTML is never interpreted and therefore cannot be injected.
 */
function parseBlocks(source: string): Block[] {
  const lines = source.replace(/\r\n/g, '\n').split('\n')
  const blocks: Block[] = []
  let paragraph: string[] = []
  let list: { type: 'ul' | 'ol'; items: string[] } | null = null
  let code: { lang: string; lines: string[] } | null = null

  const flushParagraph = () => {
    if (paragraph.length > 0) {
      blocks.push({ type: 'paragraph', text: paragraph.join(' ') })
      paragraph = []
    }
  }

  const flushList = () => {
    if (list) {
      blocks.push({ type: list.type, items: list.items })
      list = null
    }
  }

  const flushAll = () => {
    flushParagraph()
    flushList()
  }

  for (const line of lines) {
    if (code) {
      if (/^\s*```/.test(line)) {
        blocks.push({ type: 'code', lang: code.lang, text: code.lines.join('\n') })
        code = null
      } else {
        code.lines.push(line)
      }
      continue
    }

    const fence = line.match(/^\s*```(\w*)\s*$/)
    if (fence) {
      flushAll()
      code = { lang: fence[1] ?? '', lines: [] }
      continue
    }

    if (!line.trim()) {
      flushAll()
      continue
    }

    const heading = line.match(/^(#{1,6})\s+(.+)$/)
    if (heading) {
      flushAll()
      blocks.push({
        type: 'heading',
        level: heading[1].length,
        text: heading[2].trim(),
      })
      continue
    }

    if (/^\s*([-*_])\s*\1\s*\1[\s\S]*$/.test(line) || /^\s*---+\s*$/.test(line)) {
      flushAll()
      blocks.push({ type: 'hr' })
      continue
    }

    const unordered = line.match(/^\s*[-*+]\s+(.+)$/)
    if (unordered) {
      flushParagraph()
      if (!list || list.type !== 'ul') {
        flushList()
        list = { type: 'ul', items: [] }
      }
      list.items.push(unordered[1].trim())
      continue
    }

    const ordered = line.match(/^\s*\d+[.)]\s+(.+)$/)
    if (ordered) {
      flushParagraph()
      if (!list || list.type !== 'ol') {
        flushList()
        list = { type: 'ol', items: [] }
      }
      list.items.push(ordered[1].trim())
      continue
    }

    const quote = line.match(/^\s*>\s?(.*)$/)
    if (quote) {
      flushAll()
      blocks.push({ type: 'quote', text: quote[1].trim() })
      continue
    }

    if (list) flushList()
    paragraph.push(line.trim())
  }

  if (code) {
    blocks.push({ type: 'code', lang: code.lang, text: code.lines.join('\n') })
  }
  flushAll()
  return blocks
}

const INLINE_PATTERN =
  /(`[^`\n]+`|\*\*[^*\n]+\*\*|__[^_\n]+__|\*[^*\n]+\*|_[^_\n]+_|\[[^\]\n]+\]\([^)\n]+\))/g

function safeHref(raw: string): string | null {
  const href = raw.trim()
  if (/^https?:\/\//i.test(href) || href.startsWith('/') || href.startsWith('#')) {
    return href
  }
  return null
}

function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = []
  let lastIndex = 0
  let match: RegExpExecArray | null
  INLINE_PATTERN.lastIndex = 0

  while ((match = INLINE_PATTERN.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index))
    }
    const token = match[0]
    const key = `${keyPrefix}-${match.index}`
    const link = token.match(/^\[([^\]]+)\]\(([^)]+)\)$/)

    if (link) {
      const href = safeHref(link[2])
      nodes.push(
        href ? (
          <a
            key={key}
            href={href}
            target={href.startsWith('http') ? '_blank' : undefined}
            rel={href.startsWith('http') ? 'noreferrer noopener' : undefined}
          >
            {link[1]}
          </a>
        ) : (
          <span key={key}>{link[1]}</span>
        ),
      )
    } else if (token.startsWith('`')) {
      nodes.push(<code key={key}>{token.slice(1, -1)}</code>)
    } else if (token.startsWith('**') || token.startsWith('__')) {
      nodes.push(
        <strong key={key}>
          {renderInline(token.slice(2, -2), key)}
        </strong>,
      )
    } else if (token.startsWith('*') || token.startsWith('_')) {
      nodes.push(
        <em key={key}>{renderInline(token.slice(1, -1), key)}</em>,
      )
    } else {
      nodes.push(token)
    }
    lastIndex = match.index + token.length
  }

  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex))
  }
  return nodes
}

function inline(text: string, blockKey: string): ReactNode[] {
  // Preserve explicit line breaks inside a block.
  return text.split('\n').flatMap((line, index) => {
    const children = renderInline(line, `${blockKey}-${index}`)
    if (index === text.split('\n').length - 1) return children
    return [...children, <br key={`${blockKey}-br-${index}`} />]
  })
}

export function Markdown({ source, className }: MarkdownProps) {
  if (!source || !source.trim()) {
    return <p className={`md md-empty ${className ?? ''}`.trim()}>No content recorded.</p>
  }

  const blocks = parseBlocks(source)
  return (
    <div className={`md ${className ?? ''}`.trim()}>
      {blocks.map((block, index) => {
        const key = `block-${index}`
        switch (block.type) {
          case 'heading': {
            const level = Math.min(block.level, 4)
            const Heading = `h${level}` as 'h1' | 'h2' | 'h3' | 'h4'
            return <Heading key={key}>{inline(block.text, key)}</Heading>
          }
          case 'paragraph':
            return <p key={key}>{inline(block.text, key)}</p>
          case 'ul':
            return (
              <ul key={key}>
                {block.items.map((item, itemIndex) => (
                  <li key={`${key}-${itemIndex}`}>{inline(item, `${key}-${itemIndex}`)}</li>
                ))}
              </ul>
            )
          case 'ol':
            return (
              <ol key={key}>
                {block.items.map((item, itemIndex) => (
                  <li key={`${key}-${itemIndex}`}>{inline(item, `${key}-${itemIndex}`)}</li>
                ))}
              </ol>
            )
          case 'quote':
            return <blockquote key={key}>{inline(block.text, key)}</blockquote>
          case 'code':
            return (
              <pre key={key}>
                <code>{block.text}</code>
              </pre>
            )
          case 'hr':
            return <hr key={key} />
          default:
            return null
        }
      })}
    </div>
  )
}
