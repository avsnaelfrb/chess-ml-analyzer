<script setup lang="ts">
import { computed } from 'vue'
import AnalysisPanel from './components/AnalysisPanel.vue'
import ChessBoard from './components/ChessBoard.vue'
import GameControls from './components/GameControls.vue'
import MoveHistory from './components/MoveHistory.vue'
import PlayerCard from './components/PlayerCard.vue'
import PromotionModal from './components/PromotionModal.vue'
import StatusPanel from './components/StatusPanel.vue'
import { useBot } from './composables/useBot'
import { useChess } from './composables/useChess'
import type { Kind, Square } from './types/chess'

const chessApi = useChess()
const {
  board,
  turn,
  selected,
  legalTargets,
  checked,
  gameOver,
  fen,
  status,
  history,
  moves,
  promotion,
  lastMoveInfo,
  lastHumanMove,
  choose,
  makeMove,
  undo,
  reset,
} = chessApi

const bot = useBot(chessApi)

const canUndo = computed(() => history.value.length > 0 && !(bot.enabled.value && bot.thinking.value))

// Di mode vs bot, panel menganalisa langkah manusia (putih), bukan balasan bot.
const lastMoveForPanel = computed(() => (bot.enabled.value ? lastHumanMove.value : lastMoveInfo.value))

function promote(kind: Kind) {
  if (promotion.value) makeMove(promotion.value.move, kind)
}

// Manusia hanya boleh melangkah saat giliran putih dan bot tidak sibuk,
// kecuali bot sedang error (agar permainan tidak terkunci).
function onSelect(square: Square) {
  if (bot.enabled.value && !bot.error.value && (turn.value === 'black' || bot.thinking.value)) return
  choose(square)
}

function toggleBot() {
  bot.cancel()
  bot.enabled.value = !bot.enabled.value
  reset()
}

function onReset() {
  bot.cancel()
  reset()
}

function onUndo() {
  if (!bot.enabled.value) {
    undo()
    return
  }
  if (bot.thinking.value) return
  undo()
  while (turn.value === 'black' && history.value.length > 0) undo()
}
</script>

<template>
  <main class="app-shell">
    <header class="topbar">
      <div class="brand">
        <span class="brand-mark">♞</span>
        <div><strong>Checkmate</strong><small>LOCAL ARENA</small></div>
      </div>
      <div class="online"><i></i> {{ bot.enabled.value ? 'vs bot' : '2 pemain lokal' }}</div>
    </header>
    <section class="game-layout">
      <div class="board-column">
        <PlayerCard color="black" :active="turn === 'black' && !gameOver" />
        <ChessBoard
          :board="board"
          :selected="selected"
          :legal-targets="legalTargets"
          :checked="checked"
          :turn="turn"
          @select="onSelect"
        />
        <PlayerCard color="white" :active="turn === 'white' && !gameOver" bottom />
      </div>
      <aside class="side-panel">
        <StatusPanel :status="status" :game-over="gameOver" :checked="checked" />
        <AnalysisPanel :fen="fen" :last-move="lastMoveForPanel" />
        <MoveHistory :moves="moves" />
        <GameControls
          :can-undo="canUndo"
          :enabled="bot.enabled.value"
          :thinking="bot.thinking.value"
          :error="bot.error.value"
          @undo="onUndo"
          @reset="onReset"
          @toggle-bot="toggleBot"
        />
        <p class="tip"><span>✦</span> Klik bidak lalu pilih kotak yang disorot untuk bergerak.</p>
      </aside>
    </section>
    <footer>
      <span>CHECKMATE / LOCAL ARENA</span>
      <span>Permainan catur sederhana untuk dua pemain</span>
    </footer>
    <PromotionModal v-if="promotion" :color="turn" @select="promote" />
  </main>
</template>
