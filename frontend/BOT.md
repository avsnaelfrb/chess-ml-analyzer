# BOT.md — Frontend: Mode "vs bot"

Spec ini untuk agent **frontend**. Kontrak API di bawah **BEKU**: disalin sama
persis dari `backend/BOT.md`. Jangan ubah sepihak.

## Tujuan

Menambah mode **vs bot**: manusia (putih) melawan Stockfish (hitam). Bot minta
langkah ke `POST /api/best-move`.

v1 sengaja sederhana:

- Manusia **selalu putih**, bot **selalu hitam**. Tidak ada pilih warna.
- Satu level saja (depth ditentukan backend lewat `ENGINE_DEPTH`).
- Bot otomatis melangkah begitu giliran hitam.

## Kontrak API (BEKU)

### `POST /api/best-move`

Request: `{ "fen": "..." }` (FEN posisi giliran yang harus melangkah).

Response `200`: `{ "move_uci": "e7e5", "model_version": "Stockfish 19" }`

- `422` FEN/posisi ilegal atau tidak ada langkah legal → `{ "detail": "..." }`.
- `503` engine tidak tersedia → `{ "detail": "..." }`.

`move_uci` huruf kecil, ada huruf promosi bila perlu (`e7e8q`, `b7b8n`).

## Scope frontend

### 1. `src/api/classify.ts`

Tambah tipe + client, tiru pola `analyzeMove`:

```ts
export type BestMoveResponse = { move_uci: string; model_version: string }

export async function bestMove(fen: string, signal?: AbortSignal): Promise<BestMoveResponse> {
  // fetch POST `${API_BASE}/api/best-move`, body { fen }, throw ApiError
}
```

Error jaringan/HTTP → `ApiError` (sudah ada). Abort → lempar `DOMException`
`AbortError` seperti `analyzeMove`.

### 2. `src/composables/useChess.ts`

Tambah dan expose **satu** fungsi; jangan ubah alur lain.

```ts
function playUci(uci: string): boolean
```

- Cari langkah legal di `allLegal(currentPosition(), turn.value)` yang petak
  `from` dan tujuannya cocok dengan 2 kotak pertama `uci` (pakai `squareName`).
- Promosi: `pseudoMoves` **selalu** set `promotion: 'queen'`, jadi
  underpromotion (mis. `b7b8n`) tidak ada di daftar. Ambil huruf ke-5 `uci`
  (`q|r|b|n` → `Kind`) dan oper sebagai `promotedKind` ke `makeMove`.
- `makeMove(move, promotedKind)`; kembalikan `true`. Kalau tak ada yang cocok,
  kembalikan `false` (jangan mengubah state).

### 3. `src/composables/useBot.ts` (file baru)

```ts
export function useBot(chess: ReturnType<typeof useChess>) {
  const enabled = ref(false)   // mode vs bot aktif
  const thinking = ref(false)  // bot sedang minta/menunggu langkah
  const error = ref<string | null>(null)
  // watch([chess.turn, chess.gameOver, enabled]) ->
  //   kalau enabled && !gameOver && turn === 'black' && !thinking:
  //     thinking = true; error = null
  //     try { const { move_uci } = await bestMove(chess.fen.value); chess.playUci(move_uci) }
  //     catch (e) { if (!abort) error = e message }
  //     finally { thinking = false }
  return { enabled, thinking, error }
}
```

- Pakai `AbortController` dan batalkan saat komponen unmount / mode dimatikan.
- Kalau bot gagal (mis. `503` engine tidak ada), isi `error`, jangan crash, dan
  **jangan** mengubah papan. Manusia tetap bisa main manual.

### 4. `src/App.vue`

- Panggil `useBot({ ...chessApi })` setelah `useChess()`.
- Guard input manusia: bungkus handler `@select` supaya `choose` **diabaikan**
  saat `bot.enabled && (turn === 'black' || bot.thinking)`. Manusia cuma boleh
  melangkah saat giliran putih dan bot tidak sibuk.
- Teruskan `enabled` + `thinking` + `error` ke `GameControls`.
- Reset mode: saat `enabled` di-toggle, panggil `reset()` supaya mulai dari
  posisi awal (turn = putih, jadi bot tidak jalan).

### 5. `src/components/GameControls.vue`

- Toggle "2 pemain" / "vs bot" (emit `update:mode` atau `@toggle-bot`).
- Indikator "Bot berpikir…" saat `thinking`.
- Tampilkan `error` (mis. "Engine belum tersedia") di dekat kontrol.
- `can-undo`:
  - mode 2 pemain: `history.length > 0` (seperti sekarang).
  - mode bot: `history.length > 0` **dan tidak** `thinking`.
- `undo` di mode bot = **undo sampai giliran putih lagi**:

  ```ts
  function undoToHuman() {
    if (thinking.value) return
    chess.undo()
    // habis undo langkah bot, giliran jadi hitam -> undo sekali lagi
    while (chess.turn.value === 'black' && chess.history.value.length > 0) chess.undo()
  }
  ```

  Ini menangani kasus bot belum sempat melangkah (mis. error 503) tanpa membuat
  pemain "terjebak" di giliran hitam.

## Edge case yang wajib benar

- Klik bidak saat giliran hitam / bot berpikir → tidak ada efek.
- Undo saat bot berpikir → tombol nonaktif.
- Papan selesai (skakmat/remis) → bot tidak dipanggil (`gameOver`).
- `503` engine tidak ada → muncul pesan, papan tidak berubah.
- Underpromotion bot → `playUci` mengoper `promotedKind` yang benar.
- Langkah bot lewat `makeMove` → `MoveHistory` dan `AnalysisPanel` (analisis
  langkah terakhir) otomatis ikut jalan. Pastikan tidak merusak itu.

## Verifikasi manual (tidak ada test runner frontend)

1. `deno task build` (type-check lolos).
2. Jalankan backend + `deno task dev`. Toggle ke "vs bot", main 1.e4 → bot
   balas dalam <2 detik, riwayat + panel analisis update.
3. Undo dua langkah → kembali ke giliran putih, riwayat bersih.
4. Matikan backend lalu toggle bot → muncul pesan error, papan tidak berubah.
5. Skakmat cepat (mis. Fool's mate) → bot tidak dipanggil lagi.

## Non-goals v1 (jangan dikerjakan)

- Pilih warna bot (manusia selalu putih).
- Pilih level/depth di UI.
- Engine di browser (WASM) atau engine selain Stockfish.
- Opening book / eval bar.
- Mengubah alur `/api/classify` dan `/api/analyze-move`.
