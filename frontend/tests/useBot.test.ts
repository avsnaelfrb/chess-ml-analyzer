import { afterEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { useBot } from '../src/composables/useBot'
import { useChess } from '../src/composables/useChess'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

afterEach(() => vi.unstubAllGlobals())

describe('useBot', () => {
  it('melangkah otomatis saat giliran hitam', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ move_uci: 'e7e5', model_version: 'Stockfish 19' }))
    vi.stubGlobal('fetch', fetchMock)

    const chess = useChess()
    const bot = useBot(chess)

    bot.enabled.value = true
    chess.playUci('e2e4') // sekarang giliran hitam
    const fenAfterWhite = chess.fen.value

    await vi.waitFor(() => expect(chess.turn.value).toBe('white'))

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0][0]).toBe('/api/best-move')
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ fen: fenAfterWhite })
    expect(chess.moves.value).toEqual(['e4', 'e5'])
    expect(bot.thinking.value).toBe(false)
    expect(bot.error.value).toBeNull()
  })

  it('menampilkan error dan tidak mengubah papan saat engine gagal', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse({ detail: 'Engine tidak tersedia' }, 503)),
    )

    const chess = useChess()
    const bot = useBot(chess)

    bot.enabled.value = true
    chess.playUci('e2e4')
    const fenAfterWhite = chess.fen.value

    await vi.waitFor(() => expect(bot.error.value).not.toBeNull())

    expect(bot.error.value).toBe('Engine tidak tersedia')
    expect(chess.fen.value).toBe(fenAfterWhite)
    expect(bot.thinking.value).toBe(false)
  })

  it('tidak memanggil engine saat mode nonaktif', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    const chess = useChess()
    useBot(chess)

    chess.playUci('e2e4')
    await nextTick()

    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('tidak memanggil engine saat papan sudah selesai', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    const chess = useChess()
    const bot = useBot(chess)

    for (const uci of ['f2f3', 'e7e5', 'g2g4', 'd8h4']) expect(chess.playUci(uci)).toBe(true)
    expect(chess.gameOver.value).toBe(true)

    bot.enabled.value = true
    await nextTick()

    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('cancel() membersihkan error dan thinking', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse({ detail: 'Engine tidak tersedia' }, 503)),
    )

    const chess = useChess()
    const bot = useBot(chess)

    bot.enabled.value = true
    chess.playUci('e2e4')
    await vi.waitFor(() => expect(bot.error.value).not.toBeNull())

    bot.cancel()

    expect(bot.error.value).toBeNull()
    expect(bot.thinking.value).toBe(false)
  })

  it('membatalkan request yang telat agar tidak ada error palsu (reset)', async () => {
    let resolveFetch!: (response: Response) => void
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(
        () => new Promise<Response>(resolve => (resolveFetch = resolve)),
      ),
    )

    const chess = useChess()
    const bot = useBot(chess)

    bot.enabled.value = true
    chess.playUci('e2e4')
    await nextTick() // request mulai terbang

    bot.cancel()
    chess.reset() // papan kembali ke posisi awal
    resolveFetch(jsonResponse({ move_uci: 'e7e5', model_version: 'Stockfish 19' }))
    await nextTick()
    await nextTick()

    expect(bot.error.value).toBeNull()
    expect(chess.turn.value).toBe('white')
  })

  it('lastHumanMove tetap langkah putih setelah bot membalas', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse({ move_uci: 'e7e5', model_version: 'Stockfish 19' })),
    )

    const chess = useChess()
    const bot = useBot(chess)

    bot.enabled.value = true
    chess.choose({ r: 6, c: 4 }) // e2
    chess.choose({ r: 4, c: 4 }) // e4 — langkah manusia

    await vi.waitFor(() => expect(chess.turn.value).toBe('white'))

    expect(chess.lastHumanMove.value?.moveUci).toBe('e2e4')
    expect(chess.lastMoveInfo.value?.moveUci).toBe('e7e5')
  })
})
