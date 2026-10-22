<script setup>
import { CheckCircle2, AlertCircle, Info } from 'lucide-vue-next'
import { toasts } from '../composables/useToast'

const icons = {
  success: CheckCircle2,
  error: AlertCircle,
  info: Info
}
</script>

<template>
  <div class="toast-host" aria-live="polite">
    <transition-group name="toast">
      <div v-for="toast in toasts" :key="toast.id" class="toast" :class="`toast-${toast.type}`">
        <component :is="icons[toast.type] || Info" :size="16" />
        <span>{{ toast.message }}</span>
      </div>
    </transition-group>
  </div>
</template>

<style scoped>
.toast-host {
  position: fixed;
  top: 22px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 999;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  pointer-events: none;
}

.toast {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid var(--border);
  box-shadow: 0 8px 24px rgba(16, 24, 40, 0.12);
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  pointer-events: auto;
}

.toast-success svg {
  color: var(--low);
}
.toast-error svg {
  color: var(--high);
}
.toast-info svg {
  color: var(--primary);
}

.toast-enter-active,
.toast-leave-active {
  transition: all 0.2s ease;
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
