<script setup lang="ts">
defineProps<{ moves: string[] }>()
</script>

<template>
  <div class="history-card">
    <div class="section-head">
      <h2>Riwayat langkah</h2>
      <span>{{ moves.length }} langkah</span>
    </div>
    <div v-if="!moves.length" class="empty-history">Belum ada langkah dimainkan</div>
    <div v-else class="move-list">
      <div v-for="(_, index) in Math.ceil(moves.length / 2)" :key="index" class="move-row">
        <span>{{ index + 1 }}</span>
        <b>{{ moves[index * 2] || '—' }}</b>
        <b>{{ moves[index * 2 + 1] || '—' }}</b>
      </div>
    </div>
  </div>
</template>
