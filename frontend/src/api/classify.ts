export type PhaseLabel = 'opening' | 'middlegame' | 'endgame'

export type ClassifyResponse = {
  label: PhaseLabel
  confidence: number
  probabilities: Record<PhaseLabel, number>
  model_version: string
}

/** Error dari lapisan klasifikasi, membawa status HTTP (0 untuk kegagalan jaringan). */
export class ClassifyError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ClassifyError'
    this.status = status
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
