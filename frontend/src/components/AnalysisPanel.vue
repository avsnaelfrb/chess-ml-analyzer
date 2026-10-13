<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import {
  analyzeMove,
  ApiError,
  ClassifyError,
  classifyFen,
  type AnalyzeMoveResponse,
  type ClassifyResponse,
  type MoveQuality,
  type PhaseLabel,
} from '../api/classify'

const props = defineProps<{
  fen: string
  lastMove?: { fenBefore: string; moveUci: string } | null
}>()

const PHASE_NAMES: Record<PhaseLabel, string> = {
  opening: 'Pembukaan',
  middlegame: 'Permainan Tengah',
  endgame: 'Akhir Permainan',
}

const QUALITY_NAMES: Record<MoveQuality, string> = {
  Good: 'Good',
  Inaccuracy: 'Inaccuracy',
  Mistake: 'Mistake',
  Blunder: 'Blunder',
}

const loading = ref(false)
const result = ref<ClassifyResponse | null>(null)
const error = ref<string | null>(null)
const moveResult = ref<AnalyzeMoveResponse | null>(null)
const moveError = ref<string | null>(null)
const moveLoading = ref(false)
let controller: AbortController | null = null
let moveController: AbortController | null = null

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

const moveQualityPercent = computed(() => {
  if (!moveResult.value) return 0
  return Math.round(moveResult.value.probabilities[moveResult.value.quality] * 100)
})

const moveProbabilityRows = computed(() => {
  if (!moveResult.value) return []
  const probs = moveResult.value.probabilities
  const keys: MoveQuality[] = ['Good', 'Inaccuracy', 'Mistake', 'Blunder']
  return keys.map((k) => ({ key: k, name: QUALITY_NAMES[k], percent: Math.round(probs[k] * 100) }))
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

async function analyzeLastMove() {
  if (!props.lastMove) return
  moveController?.abort()
  const current = new AbortController()
  moveController = current
  moveLoading.value = true
  moveError.value = null

  try {
    moveResult.value = await analyzeMove(props.lastMove.fenBefore, props.lastMove.moveUci, current.signal)
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') return
    moveResult.value = null
    moveError.value = err instanceof ApiError ? err.message : 'Terjadi kesalahan tak terduga.'
  } finally {
    if (moveController === current) {
      moveLoading.value = false
      moveController = null
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

watch(
  () => props.lastMove,
  () => {
    moveController?.abort()
    moveController = null
    moveLoading.value = false
    moveResult.value = null
    moveError.value = null
  },
  { deep: true },
)

onBeforeUnmount(() => {
  controller?.abort()
  moveController?.abort()
})
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

    <div class="section-head" style="margin-top: 1.5rem">
      <h2>Analisis langkah terakhir</h2>
      <span>MOVE</span>
    </div>
    <p class="analysis-desc">Analisis kualitas langkah yang baru dimainkan.</p>

    <button
      class="analysis-button"
      :disabled="!props.lastMove || moveLoading"
      @click="analyzeLastMove"
    >
      {{ moveLoading ? 'Menganalisis…' : 'Analisis langkah terakhir' }}
    </button>

    <div v-if="moveError" class="analysis-error">{{ moveError }}</div>

    <div v-else-if="moveResult" class="analysis-result">
      <div class="phase-label">
        <span>{{ QUALITY_NAMES[moveResult.quality] }}</span>
        <b>{{ moveQualityPercent }}%</b>
      </div>
      <div class="prob-list">
        <div v-for="row in moveProbabilityRows" :key="row.key" class="prob-row">
          <span class="prob-name">{{ row.name }}</span>
          <span class="prob-bar"><i :style="{ width: row.percent + '%' }"></i></span>
          <span class="prob-value">{{ row.percent }}%</span>
        </div>
      </div>
      <p class="model-version">
        model v{{ moveResult.model_version }}{{ moveResult.cp_loss !== null ? ` • cp_loss: ${moveResult.cp_loss}` : '' }}
      </p>
    </div>
  </div>
</template>
