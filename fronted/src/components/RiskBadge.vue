<script setup>
import { computed } from 'vue'
import { riskInfo } from '../utils/format'

const props = defineProps({
  level: { type: String, default: 'none' },
  white: { type: Boolean, default: false }
})

const info = computed(() => riskInfo(props.level))
</script>

<template>
  <span class="badge" :class="[info.className, { 'badge-white': white }]">{{ info.text }}</span>
</template>
