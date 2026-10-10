<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { classifyFen, ClassifyError, type ClassifyResponse, type PhaseLabel } from '../api/classify'

const props = defineProps<{ fen: string }>()

const PHASE_NAMES: Record<PhaseLabel, string> = {
  opening: 'Pembukaan',
  middlegame: 'Permainan Tengah',
  endgame: 'Akhir Permainan',
}

const loading = ref(false)
const result = ref<ClassifyResponse | null>(null)
const error = ref<string | null>(null)
let controller: AbortController | null = null

const confidencePercent = computed(() =>
  result.value ? Math.round(result.value.confidence * 100) : 0,
)

const probabilityRows = computed(() => {
  if (!result.value) return []
  const probabilities = result.value.probabilities
  return (Object.keys(probabilities) as PhaseLabel[]).map(key => ({
    key,
    name: PHASE_NAMES[key],
    percent: Math.round(probabilities[key] * 100),
  }))
})

async function analyze() {
  controller?.abort()
  const current = new AbortController()
  controller = current
  loading.value = true
  error.value = null

  try {
    result.value = await classifyFen(props.fen, current.signal)
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') return
    result.value = null
    error.value = err instanceof ClassifyError ? err.message : 'Terjadi kesalahan tak terduga.'
  } finally {
    if (controller === current) {
      loading.value = false
      controller = null
    }
  }
}

// Hasil lama tidak relevan setelah posisi berubah.
watch(
  () => props.fen,
  () => {
    controller?.abort()
    controller = null
    loading.value = false
    result.value = null
    error.value = null
  },
)

onBeforeUnmount(() => controller?.abort())
</script>

<template>
  <div class="analysis-card">
    <div class="section-head">
      <h2>Analisis fase</h2>
      <span>MODEL</span>
    </div>
    <p class="analysis-desc">Klasifikasi fase permainan dari posisi saat ini.</p>

    <button class="analysis-button" :disabled="loading" @click="analyze">
      {{ loading ? 'Menganalisis…' : 'Analisis posisi' }}
    </button>

    <div v-if="error" class="analysis-error">{{ error }}</div>

    <div v-else-if="result" class="analysis-result">
      <div class="phase-label">
        <span>{{ PHASE_NAMES[result.label] }}</span>
        <b>{{ confidencePercent }}%</b>
      </div>
      <div class="prob-list">
        <div v-for="row in probabilityRows" :key="row.key" class="prob-row">
          <span class="prob-name">{{ row.name }}</span>
          <span class="prob-bar"><i :style="{ width: row.percent + '%' }"></i></span>
          <span class="prob-value">{{ row.percent }}%</span>
        </div>
      </div>
      <p class="model-version">model v{{ result.model_version }}</p>
    </div>
  </div>
</template>
