import assert from 'node:assert/strict'
import test from 'node:test'
import {
  DINGTALK_TEST_COMMAND,
  isDingTalkTestCommand,
  resolveChatSubmission,
} from '../src/chatCommands.ts'

const command = '\u9489\u9489\u6d4b\u8bd5'

test('DingTalk test command is exact', () => {
  assert.equal(DINGTALK_TEST_COMMAND, command)
  assert.equal(isDingTalkTestCommand(command), true)
  assert.equal(isDingTalkTestCommand(`  ${command}  `), true)
  assert.equal(isDingTalkTestCommand(''), false)
  assert.equal(isDingTalkTestCommand('我要进行钉钉测试'), false)
  assert.equal(isDingTalkTestCommand('钉钉测试一下'), false)
  assert.equal(isDingTalkTestCommand('测试钉钉'), false)
})

test('chat submission routes exact command to DingTalk', () => {
  assert.deepEqual(resolveChatSubmission(command), { kind: 'dingtalk', content: command })
  assert.deepEqual(resolveChatSubmission(`  ${command}\n`), { kind: 'dingtalk', content: command })
})

test('chat submission routes all other text to chat', () => {
  for (const text of ['我要进行钉钉测试', '钉钉测试一下', '测试钉钉', 'hello']) {
    assert.deepEqual(resolveChatSubmission(text), { kind: 'chat', content: text })
  }
  assert.equal(resolveChatSubmission('   '), null)
})
