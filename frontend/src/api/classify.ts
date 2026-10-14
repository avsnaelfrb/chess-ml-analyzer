export type PhaseLabel = 'opening' | 'middlegame' | 'endgame'
export type MoveQuality = 'Good' | 'Inaccuracy' | 'Mistake' | 'Blunder'

export type ClassifyResponse = {
  label: PhaseLabel
  confidence: number
  probabilities: Record<PhaseLabel, number>
  model_version: string
}

export type AnalyzeMoveResponse = {
  quality: MoveQuality
  cp_loss: number | null
  probabilities: Record<MoveQuality, number>
  model_version: string
}

export type BestMoveResponse = {
  move_uci: string
  model_version: string
}

/** Error dari lapisan API, membawa status HTTP (0 untuk kegagalan jaringan). */
export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export class ClassifyError extends ApiError {
  constructor(message: string, status: number) {
    super(message, status)
    this.name = 'ClassifyError'
  }
}

// Kosong = pakai path relatif (proxy Vite saat dev). Bisa dioverride lewat
// VITE_API_BASE mis. "http://localhost:8000" bila tidak memakai proxy.
const API_BASE = (import.meta.env.VITE_API_BASE ?? '').replace(/\/$/, '')

async function readDetail(response: Response): Promise<string> {
  try {
    const data = (await response.json()) as { detail?: unknown }
    if (typeof data.detail === 'string') return data.detail
  } catch {
    // Respons bukan JSON; jatuhkan ke pesan default.
  }
  return `Permintaan gagal (HTTP ${response.status}).`
}

/** Kirim FEN ke backend dan kembalikan hasil klasifikasi fase. */
export async function classifyFen(fen: string, signal?: AbortSignal): Promise<ClassifyResponse> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}/api/classify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fen }),
      signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ClassifyError('Tidak dapat terhubung ke server klasifikasi.', 0)
  }

  if (!response.ok) {
    throw new ClassifyError(await readDetail(response), response.status)
  }

  return (await response.json()) as ClassifyResponse
}

export async function analyzeMove(
  fenBefore: string,
  moveUci: string,
  signal?: AbortSignal,
): Promise<AnalyzeMoveResponse> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}/api/analyze-move`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fen_before: fenBefore, move_uci: moveUci }),
      signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError('Tidak dapat terhubung ke server analisis.', 0)
  }

  if (!response.ok) {
    throw new ApiError(await readDetail(response), response.status)
  }

  return (await response.json()) as AnalyzeMoveResponse
}

/** Minta langkah terbaik dari engine untuk posisi (giliran yang harus melangkah). */
export async function bestMove(fen: string, signal?: AbortSignal): Promise<BestMoveResponse> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}/api/best-move`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fen }),
      signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError('Tidak dapat terhubung ke server engine.', 0)
  }

  if (!response.ok) {
    throw new ApiError(await readDetail(response), response.status)
  }

  return (await response.json()) as BestMoveResponse
}
