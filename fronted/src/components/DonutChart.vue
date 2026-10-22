<script setup>
import { computed } from 'vue'

const props = defineProps({
  high: { type: Number, default: 0 },
  mid: { type: Number, default: 0 },
  low: { type: Number, default: 0 }
})

const radius = 46
const circumference = 2 * Math.PI * radius

const segments = computed(() => {
  const values = [props.high, props.mid, props.low]
  const total = values.reduce((acc, n) => acc + n, 0)
  if (!total) {
    return []
  }
  const colors = ['#DC2626', '#F59E0B', '#16A34A']
  let offset = 0
  return values
    .map((value, index) => {
      const length = (value / total) * circumference
      const segment = {
        color: colors[index],
        dasharray: `${length} ${circumference - length}`,
        dashoffset: -offset
      }
      offset += length
      return segment
    })
    .filter((segment) => segment.dasharray !== `0 ${circumference}`)
})
</script>

<template>
  <svg class="donut" viewBox="0 0 110 110" role="img" aria-label="风险等级分布">
    <circle cx="55" cy="55" :r="radius" fill="none" stroke="#F2F4F7" stroke-width="11" />
    <g transform="rotate(-90 55 55)">
      <circle
        v-for="(segment, index) in segments"
        :key="index"
        cx="55"
        cy="55"
        :r="radius"
        fill="none"
        :stroke="segment.color"
        stroke-width="11"
        :stroke-dasharray="segment.dasharray"
        :stroke-dashoffset="segment.dashoffset"
      />
    </g>
  </svg>
</template>

<style scoped>
.donut {
  width: 110px;
  height: 110px;
  display: block;
}
</style>
