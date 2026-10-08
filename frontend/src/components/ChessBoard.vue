<script setup lang="ts">
import { files, icons } from '../lib/chess/constants'
import type { Board, Color, Move, Square } from '../types/chess'

defineProps<{
  board: Board
  selected: Square | null
  legalTargets: Move[]
  checked: boolean
  turn: Color
}>()

const emit = defineEmits<{ select: [square: Square] }>()
</script>

<template>
  <div class="board-wrap">
    <div class="board" role="grid">
      <template v-for="r in 8" :key="r">
        <button
          v-for="c in 8"
          :key="`${r}-${c}`"
          class="square"
          :class="[
            {
              light: (r + c) % 2 === 0,
              dark: (r + c) % 2 !== 0,
              selected: selected && selected.r === r - 1 && selected.c === c - 1,
              target: legalTargets.some(m => m.r === r - 1 && m.c === c - 1),
              check:
                checked &&
                board[r - 1][c - 1]?.kind === 'king' &&
                board[r - 1][c - 1]?.color === turn,
            },
          ]"
          @click="emit('select', { r: r - 1, c: c - 1 })"
        >
          <span v-if="c === 1" class="rank-label">{{ 9 - r }}</span>
          <span v-if="r === 8" class="file-label">{{ files[c - 1] }}</span>
          <span v-if="board[r - 1][c - 1]" class="piece" :class="board[r - 1][c - 1]!.color">{{
            icons[board[r - 1][c - 1]!.color][board[r - 1][c - 1]!.kind]
          }}</span>
          <span
            v-if="legalTargets.some(m => m.r === r - 1 && m.c === c - 1)"
            class="move-dot"
          ></span>
        </button>
      </template>
    </div>
  </div>
</template>
