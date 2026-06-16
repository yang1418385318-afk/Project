import assert from 'node:assert/strict'
import { setupClipboardPermissionGuard } from './clipboardPermissionGuard.js'

const deniedClipboard = {
  async readText() {
    const error = new Error('Read permission denied')
    error.name = 'NotAllowedError'
    throw error
  },
}

assert.equal(setupClipboardPermissionGuard(deniedClipboard), true)
assert.equal(await deniedClipboard.readText(), '')
assert.equal(setupClipboardPermissionGuard(deniedClipboard), false)

const failingClipboard = {
  async readText() {
    throw new Error('Unexpected failure')
  },
}

setupClipboardPermissionGuard(failingClipboard)
await assert.rejects(() => failingClipboard.readText(), /Unexpected failure/)
