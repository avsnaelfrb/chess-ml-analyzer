<script setup lang="ts">
import ChessBoard from './components/ChessBoard.vue'
import GameControls from './components/GameControls.vue'
import MoveHistory from './components/MoveHistory.vue'
import PlayerCard from './components/PlayerCard.vue'
import PromotionModal from './components/PromotionModal.vue'
import StatusPanel from './components/StatusPanel.vue'
import { useChess } from './composables/useChess'
import type { Kind } from './types/chess'

const {
  board,
  turn,
  selected,
  legalTargets,
  checked,
  gameOver,
  status,
  history,
  moves,
  promotion,
  choose,
  makeMove,
  undo,
  reset,
} = useChess()

function promote(kind: Kind) {
  if (promotion.value) makeMove(promotion.value.move, kind)
}
</script>

<template>
  <main class="app-shell">
    <header class="topbar">
      <div class="brand">
        <span class="brand-mark">♞</span>
        <div><strong>Checkmate</strong><small>LOCAL ARENA</small></div>
      </div>
      <div class="online"><i></i> 2 pemain lokal</div>
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
          @select="choose"
        />
        <PlayerCard color="white" :active="turn === 'white' && !gameOver" bottom />
      </div>
      <aside class="side-panel">
        <StatusPanel :status="status" :game-over="gameOver" :checked="checked" />
        <MoveHistory :moves="moves" />
        <GameControls :can-undo="history.length > 0" @undo="undo" @reset="reset" />
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
