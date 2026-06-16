import assert from 'node:assert/strict'
import { createEditorOptions } from './editorConfig.js'

const options = createEditorOptions()

assert.equal(options.contextmenu, false)
assert.equal(options.minimap.enabled, false)
assert.equal(options.automaticLayout, true)
