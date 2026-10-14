# BOT.md — Backend: Langkah Bot (mode "vs bot")

Spec ini untuk agent **backend**. Kontrak API di bawah **BEKU**: disalin sama
persis di `frontend/BOT.md`. Jangan ubah sepihak; kalau perlu ubah, ubah kedua
file dulu.

## Tujuan

Menambah **satu endpoint** supaya frontend bisa meminta langkah terbaik dari
engine Stockfish. Ini dasar mode "vs bot".

Penting: langkah bot dipilih **engine Stockfish**, **bukan** model klasifikasi
fase. Model fase cuma menebak fase, tidak bisa memilih langkah. Jangan latih
model baru untuk ini.

## Kontrak API (BEKU)

### `POST /api/best-move`

Request (JSON):

```json
{ "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1" }
```

- `fen`: posisi giliran yang harus melangkah (6 field FEN; harus posisi legal).

Response `200`:

```json
{ "move_uci": "e7e5", "model_version": "Stockfish 19" }
```

Aturan:

- `move_uci`: langkah terbaik engine, huruf kecil semua, tambah huruf promosi
  bila perlu (`e7e8q`, `b7b8n`) — sama gaya dengan `/api/analyze-move`.
- `model_version`: nama engine (mis. `"Stockfish 19"`), dari
  `MoveAnalyzer.model_version` — **sama** dengan yang dipakai `/api/analyze-move`.
- FEN tidak valid / posisi ilegal → `422` `{ "detail": "..." }`.
- Tidak ada langkah legal (skakmat / remis) → `422` `{ "detail": "..." }`.
- Engine belum tersedia (biner hilang) → `503` `{ "detail": "..." }`.

## Scope backend

### 1. `app/api.py` (satu-satunya modul yang berubah)

Pola sudah ada di `/api/analyze-move`; tiru apa adanya.

- Skema:
  - `BestMoveRequest`: `fen: str` (Field `min_length=1`, beri `description` +
    `examples` seperti skema lain).
  - `BestMoveResponse`: `move_uci: str`, `model_version: str`.
- Method baru di `MoveAnalyzer`:

  ```python
  def best_move(self, fen: str) -> str:
      board = chess.Board(fen)          # ValueError -> FEN tidak valid
      if not board.is_valid():
          raise ValueError("posisi fen tidak legal")
      if not any(board.legal_moves):
          raise ValueError("tidak ada langkah legal")
      engine = self._ensure_engine()    # bisa ModelNotLoadedError (503)
      limit = chess.engine.Limit(depth=self._depth)
      try:
          with self._lock:
              result = engine.play(board, limit)
      except chess.engine.EngineError as exc:
          self._engine = None           # buang agar request berikutnya spawn ulang
          raise ModelNotLoadedError(f"Engine gagal mencari langkah: {exc}") from exc
      return result.move.uci()
  ```

- Route baru `@router.post("/best-move", response_model=BestMoveResponse)`:
  panggil `analyzer.best_move(payload.fen)`, tangkap `ValueError` → `422` dan
  `ModelNotLoadedError` → `503` (`HTTPException`), persis pola `analyze_move`.

Catatan: cek "tidak ada langkah legal" pakai `not any(board.legal_moves)`, bukan
`board.is_game_over()` — `is_game_over()` juga true untuk material tidak cukup
(mis. Raja vs Raja), aturan 75 langkah, dan repetisi lima kali, padahal posisi
seperti itu masih punya langkah legal. (`LegalMoveGenerator` di python-chess
1.11.2 tidak punya `.any()`.)

### 2. `app/config.py`

Tidak berubah. Pakai `STOCKFISH_PATH` dan `ENGINE_DEPTH` yang sudah ada. Level
kesulitan bot = `ENGINE_DEPTH` (default 12). Tidak ada parameter depth di API.

### 3. Test baru `backend/tests/test_best_move.py`

Tiru `test_move_analysis.py` (ada helper `_client` dan `_engine_available`).

- FEN ngawur → `422`.
- FEN posisi skakmat (tidak ada langkah legal) → `422`.
- Engine tidak ada (`MoveAnalyzer(engine_path="/nonexistent/stockfish")`) → `503`.
- Engine ada (skipif, sama seperti test analisis) FEN awal → `200`; `move_uci`
  panjang 4–5 dan legal untuk posisi itu.

## Definition of done

- `uv run pytest` hijau (semua test lama + `test_best_move.py`).
- Helper `curl` di README/AGENT backend ditambah untuk `/api/best-move`
  (opsional tapi disarankan, biar konsisten).
- Tidak menyentuh alur `/api/classify` (beku) dan tidak mengubah
  `/api/analyze-move`.

## Non-goals v1 (jangan dikerjakan)

- Parameter level/depth per-request.
- Pilih warna bot.
- Opening book / engine kedua.
- Perbaikan race `_ensure_engine` di luar lock (bug lama; `shortcut:` sudah
  diketahui — perbaiki hanya kalau konkurensi nyata jadi masalah).
