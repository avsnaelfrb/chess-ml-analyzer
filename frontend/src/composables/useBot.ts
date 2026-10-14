import { onBeforeUnmount, ref, watch } from 'vue'
import { ApiError, bestMove } from '../api/classify'
import type { useChess } from './useChess'

/** Mode vs bot: manusia putih, Stockfish hitam. Bot melangkah otomatis saat giliran hitam. */
export function useBot(chess: ReturnType<typeof useChess>) {
  const enabled = ref(false)
  const thinking = ref(false)
  const error = ref<string | null>(null)
  let controller: AbortController | null = null

  async function requestMove() {
    controller?.abort()
    const current = new AbortController()
    controller = current
    thinking.value = true
    error.value = null
    try {
      const { move_uci } = await bestMove(chess.fen.value, current.signal)
      if (current.signal.aborted) return
      if (!chess.playUci(move_uci)) {
        error.value = 'Engine memberi langkah yang tidak valid.'
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return
      if (current.signal.aborted) return
      error.value = err instanceof ApiError ? err.message : 'Terjadi kesalahan tak terduga.'
    } finally {
      if (controller === current) {
        thinking.value = false
        controller = null
      }
    }
  }

  watch([chess.turn, chess.gameOver, enabled], () => {
    if (!enabled.value) {
      controller?.abort()
      controller = null
      thinking.value = false
      return
    }
    if (!chess.gameOver.value && chess.turn.value === 'black' && !thinking.value) {
      void requestMove()
    }
  })

  onBeforeUnmount(() => controller?.abort())

  return { enabled, thinking, error }
}
