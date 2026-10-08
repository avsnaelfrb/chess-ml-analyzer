<script setup lang="ts">
import { icons } from '../lib/chess/constants'
import type { Color, Kind } from '../types/chess'

defineProps<{ color: Color }>()

const emit = defineEmits<{ select: [kind: Kind] }>()

const kinds: Kind[] = ['queen', 'rook', 'bishop', 'knight']
</script>

<template>
  <div class="modal-backdrop">
    <div class="promotion-modal">
      <span class="eyebrow">PROMOSI BIDAK</span>
      <h2>Pilih bidak Anda</h2>
      <div class="promotion-options">
        <button v-for="kind in kinds" :key="kind" @click="emit('select', kind)">
          {{ icons[color][kind] }}
        </button>
      </div>
    </div>
  </div>
</template>
