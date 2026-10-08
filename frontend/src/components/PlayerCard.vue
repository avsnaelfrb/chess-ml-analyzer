<script setup lang="ts">
import { icons } from '../lib/chess/constants'
import type { Color } from '../types/chess'

withDefaults(defineProps<{ color: Color; active: boolean; bottom?: boolean }>(), {
  bottom: false,
})
</script>

<template>
  <div class="player-card" :class="{ active, bottom }">
    <span class="avatar" :class="color === 'black' ? 'black-avatar' : 'white-avatar'">{{
      icons[color].pawn
    }}</span>
    <div>
      <b>{{ color === 'black' ? 'Hitam' : 'Putih' }}</b>
      <small>{{ color === 'black' ? 'Black player' : 'White player' }}</small>
    </div>
    <span v-if="active" class="turn-dot"></span>
  </div>
</template>
