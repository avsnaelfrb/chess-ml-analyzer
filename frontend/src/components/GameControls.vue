<script setup lang="ts">
defineProps<{ canUndo: boolean }>()

const emit = defineEmits<{ undo: []; reset: [] }>()
</script>

<template>
  <div class="controls">
    <button class="secondary" :disabled="!canUndo" @click="emit('undo')">
      ↶ <span>Undo langkah</span>
    </button>
    <button class="primary" @click="emit('reset')">↻ <span>Permainan baru</span></button>
  </div>
</template>
