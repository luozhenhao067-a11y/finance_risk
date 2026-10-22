import { reactive } from 'vue'

export const toasts = reactive([])
let seq = 0

export function pushToast(message, type = 'success') {
  const id = ++seq
  toasts.push({ id, message, type })
  window.setTimeout(() => {
    const index = toasts.findIndex((item) => item.id === id)
    if (index > -1) toasts.splice(index, 1)
  }, 2800)
}

export function useToast() {
  return { toasts, pushToast }
}
