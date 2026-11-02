import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, bestMove, classifyTactic } from '../src/api/classify'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('classifyTactic', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('mengirim FEN dan mengembalikan label motif', async () => {
    const body = {
      labels: [{ label: 'fork', probability: 0.61 }],
      model_version: '0.1.0',
    }
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(body))
    vi.stubGlobal('fetch', fetchMock)

    const result = await classifyTactic('some-fen')

    expect(result).toEqual(body)
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/classify-tactic',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ fen: 'some-fen' }),
      }),
    )
  })

  it('memberi pesan ramah saat model belum dilatih', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse({ detail: 'Model taktis belum tersedia.' }, 503)),
    )

    await expect(classifyTactic('some-fen')).rejects.toMatchObject({
      name: 'ApiError',
      status: 503,
      message: 'Model taktis belum tersedia.',
    })
  })
})

describe('bestMove', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('mengirim FEN dan mengembalikan langkah engine', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ move_uci: 'e7e5', model_version: 'Stockfish 19' }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await bestMove('some-fen')

    expect(result).toEqual({ move_uci: 'e7e5', model_version: 'Stockfish 19' })
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/best-move',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ fen: 'some-fen' }),
      }),
    )
  })

  it('melempar ApiError dengan status saat HTTP gagal', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse({ detail: 'Engine tidak tersedia' }, 503)),
    )

    await expect(bestMove('some-fen')).rejects.toMatchObject({
      name: 'ApiError',
      status: 503,
      message: 'Engine tidak tersedia',
    })
    await expect(bestMove('some-fen')).rejects.toBeInstanceOf(ApiError)
  })

  it('melempar ApiError status 0 saat jaringan gagal', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('network down')))

    await expect(bestMove('some-fen')).rejects.toMatchObject({ name: 'ApiError', status: 0 })
  })

  it('meneruskan AbortError apa adanya', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockRejectedValue(new DOMException('dibatalkan', 'AbortError')),
    )

    await expect(bestMove('some-fen')).rejects.toMatchObject({ name: 'AbortError' })
  })
})
