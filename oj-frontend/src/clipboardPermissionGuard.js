export function setupClipboardPermissionGuard(clipboard = globalThis.navigator?.clipboard) {
  if (!clipboard || typeof clipboard.readText !== 'function' || clipboard.__ojReadTextGuarded) {
    return false
  }

  const originalReadText = clipboard.readText.bind(clipboard)

  Object.defineProperty(clipboard, '__ojReadTextGuarded', {
    value: true,
    configurable: true,
  })

  clipboard.readText = async () => {
    try {
      return await originalReadText()
    } catch (error) {
      if (error?.name === 'NotAllowedError') {
        return ''
      }
      throw error
    }
  }

  return true
}
