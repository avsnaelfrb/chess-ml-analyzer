import { onBeforeUnmount, ref, watch } from 'vue'
import { ApiError, bestMove } from '../api/classify'
import type { useChess } from './useChess'

// Jeda minimal sebelum bot mengeksekusi langkah, agar terasa "berpikir".
const BOT_THINK_MS = 5000

/** Tunda ms; ditolak segera bila signal di-abort agar langkah tidak dipakai setelah reset. */
function wait(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) {
      reject(new DOMException('Dibatalkan', 'AbortError'))
      return
    }
    let timer: ReturnType<typeof setTimeout>
    const onAbort = () => {
      clearTimeout(timer)
      reject(new DOMException('Dibatalkan', 'AbortError'))
    }
    timer = setTimeout(() => {
      signal.removeEventListener('abort', onAbort)
      resolve()
    }, ms)
    signal.addEventListener('abort', onAbort, { once: true })
  })
}

/** Mode vs bot: manusia putih, Stockfish hitam. Bot melangkah otomatis saat giliran hitam. */
export function useBot(chess: ReturnType<typeof useChess>) {
  const enabled = ref(false);
  const thinking = ref(false);
  const error = ref<string | null>(null);
  let controller: AbortController | null = null;

  async function requestMove() {
    controller?.abort();
    const current = new AbortController();
    controller = current;
    thinking.value = true;
    error.value = null;
    const startedAt = Date.now();
    try {
      const { move_uci } = await bestMove(chess.fen.value, current.signal);
      // Engine sering menjawab instan; tahan agar bot terasa berpikir.
      const remaining = BOT_THINK_MS - (Date.now() - startedAt);
      if (remaining > 0) await wait(remaining, current.signal);
      if (current.signal.aborted) return;
      if (!chess.playUci(move_uci)) {
        error.value = "Engine memberi langkah yang tidak valid.";
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      if (current.signal.aborted) return;
      error.value =
        err instanceof ApiError
          ? err.message
          : "Terjadi kesalahan tak terduga.";
    } finally {
      if (controller === current) {
        thinking.value = false;
        controller = null;
      }
    }
  }

  /** Batalkan request berjalan dan bersihkan status bot. */
  function cancel() {
    controller?.abort();
    controller = null
    thinking.value = false
    error.value = null
  }

  watch([chess.turn, chess.gameOver, enabled], () => {
    if (!enabled.value) {
      cancel()
      return
    }
    if (!chess.gameOver.value && chess.turn.value === 'black' && !thinking.value) {
      void requestMove()
    }
  })

  onBeforeUnmount(() => controller?.abort())

  return { enabled, thinking, error, cancel }
}
