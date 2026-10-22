<script setup>
import { computed } from 'vue'
import { statusInfo } from '../utils/format'

const props = defineProps({
  status: { type: String, default: 'draft' }
})

const info = computed(() => statusInfo(props.status))
</script>

<template>
  <span class="badge" :class="info.className">{{ info.text }}</span>
</template>
