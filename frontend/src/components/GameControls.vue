<script setup lang="ts">
defineProps<{
  canUndo: boolean
  enabled: boolean
  thinking: boolean
  error: string | null
}>()

const emit = defineEmits<{ undo: []; reset: []; 'toggle-bot': [] }>()
</script>

<template>
  <div class="mode-toggle">
    <button class="secondary" :class="{ active: !enabled }" @click="enabled && emit('toggle-bot')">
      2 pemain
    </button>
    <button class="secondary" :class="{ active: enabled }" @click="!enabled && emit('toggle-bot')">
      vs bot
    </button>
  </div>

  <div v-if="enabled && thinking" class="bot-thinking">Bot berpikir…</div>
  <div v-else-if="enabled && error" class="analysis-error">{{ error }}</div>

  <div class="controls">
    <button class="secondary" :disabled="!canUndo" @click="emit('undo')">
      ↶ <span>Undo langkah</span>
    </button>
    <button class="primary" @click="emit('reset')">↻ <span>Permainan baru</span></button>
  </div>
</template>
