import { isDataUIPart, type UIMessage } from 'ai'

export type CitationPayload = {
  citationIndex: number
  chunkId: string
  excerpt: string
  title?: string | null
  ticker: string | null
  companyName?: string | null
  form: string | null
  filingDate: string | null
  page?: string
  section?: string
}

export type PipelineStage =
  | 'analyzing'
  | 'searching'
  | 'reading'
  | 'verifying'
  | 'streaming'

export type PipelineStatus = {
  stage: PipelineStage
  message: string
}

function isCitationData(data: unknown): data is CitationPayload {
  if (typeof data !== 'object' || data === null) {
    return false
  }

  const record = data as Record<string, unknown>
  const isStringOrNull = (value: unknown): value is string | null =>
    value === null || typeof value === 'string'
  return (
    typeof record.citationIndex === 'number' &&
    typeof record.chunkId === 'string' &&
    typeof record.excerpt === 'string' &&
    isStringOrNull(record.ticker) &&
    isStringOrNull(record.form) &&
    isStringOrNull(record.filingDate)
  )
}

export function isCitationPart(
  part: UIMessage['parts'][number],
): part is UIMessage['parts'][number] & { type: 'data-citation'; data: CitationPayload } {
  return isDataUIPart(part) && part.type === 'data-citation' && isCitationData(part.data)
}

export function isStatusPart(
  part: unknown,
): part is { type: 'data-status'; data: PipelineStatus } {
  if (typeof part !== 'object' || part === null) {
    return false
  }

  const record = part as Record<string, unknown>
  if (record.type !== 'data-status' || typeof record.data !== 'object' || record.data === null) {
    return false
  }

  const data = record.data as Record<string, unknown>
  return typeof data.stage === 'string' && typeof data.message === 'string'
}

export function citationsFromMessage(message: UIMessage): CitationPayload[] {
  return message.parts
    .filter(isCitationPart)
    .map((part) => part.data)
    .sort((a, b) => a.citationIndex - b.citationIndex)
}

export function textFromMessage(message: UIMessage): string {
  return message.parts
    .filter((part) => part.type === 'text')
    .map((part) => part.text)
    .join('')
}

export function citationLabel(citation: CitationPayload): string {
  const parts = [citation.ticker, citation.form, citation.filingDate]
  if (citation.page) {
    parts.push(`p.${citation.page}`)
  }
  return parts.filter(Boolean).join(' · ') || citation.title || 'Document'
}

export function citationHeader(citation: CitationPayload): string {
  const name = citation.companyName ?? citation.title ?? citation.ticker
  const parts = [name, citation.form, citation.filingDate ? `filed ${citation.filingDate}` : null]
  return parts.filter(Boolean).join(' · ')
}

export function citationSubtitle(citation: CitationPayload): string | null {
  const parts: string[] = []
  if (citation.page) {
    parts.push(`Page ${citation.page}`)
  }
  if (citation.section) {
    parts.push(citation.section)
  }
  return parts.length > 0 ? parts.join(' · ') : null
}

export function citationByIndex(
  citations: CitationPayload[],
  index: number,
): CitationPayload | undefined {
  return citations.find((citation) => citation.citationIndex === index)
}
