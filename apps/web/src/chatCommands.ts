// The command is a user-facing Chinese token; escaped to keep it out of UI copy.
export const DINGTALK_TEST_COMMAND = '\u9489\u9489\u6d4b\u8bd5'

export function normalizedChatInput(value: string): string {
  return value.trim()
}

export function isDingTalkTestCommand(value: string): boolean {
  return normalizedChatInput(value) === DINGTALK_TEST_COMMAND
}

export type ChatSubmission =
  | { kind: 'dingtalk'; content: string }
  | { kind: 'chat'; content: string }
  | null

export function resolveChatSubmission(value: string): ChatSubmission {
  const content = normalizedChatInput(value)
  if (!content) return null
  return isDingTalkTestCommand(content)
    ? { kind: 'dingtalk', content }
    : { kind: 'chat', content }
}
