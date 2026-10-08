<script setup lang="ts">
defineProps<{
  status: string
  gameOver: boolean
  checked: boolean
}>()
</script>

<template>
  <div class="status-card">
    <span class="eyebrow">GAME STATUS</span>
    <h1>{{ status }}</h1>
    <p>{{ gameOver ? 'Permainan telah selesai.' : 'Pilih bidak untuk melihat langkah yang tersedia.' }}</p>
    <span class="status-pill" :class="{ warning: checked }"
      ><i></i>{{ gameOver ? 'SELESAI' : checked ? 'DALAM SKAK' : 'PERMAINAN BERJALAN' }}</span
    >
  </div>
</template>
