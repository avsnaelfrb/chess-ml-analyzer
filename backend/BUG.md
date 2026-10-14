# BUG.md — Backend (mode "vs bot")

Laporan bug untuk **agent backend**. Sumber kebenaran fitur = `BOT.md` di folder
ini. Setiap entri punya ID dan kolom **Status** untuk di-*rolling*.

Cara pakai:

- Status: `OPEN` → `IN_PROGRESS` → `FIXED` (atau `WONTFIX` bila sengaja tidak
  dikerjakan, tulis alasannya).
- Setelah memperbaiki, ubah Status dan isi baris **Bukti** (hash commit / output
  test). **Jangan hapus entri** — biar jadi jejak.
- Setelah semua `FIXED`, jalankan `uv run pytest` sampai hijau.

## Ringkasan

| ID | Judul | Severity | Status |
|---|---|---|---|
| BE-001 | `is_game_over()` menolak posisi yang masih punya langkah legal | Sedang | FIXED |

---

## BE-001 — `is_game_over()` terlalu luas

- **Lokasi:** `backend/app/api.py:288` (method `MoveAnalyzer.best_move`)
- **Severity:** Sedang
- **Status:** FIXED
- **Bukti:** commit `12c9158` (+ test `2da9328`). `uv run pytest` → 37 lulus.
  Repro `{"fen":"8/8/8/4k3/8/4K3/8/8 b - - 0 1"}` → `200
  {"move_uci":"e5d5","model_version":"Stockfish 19"}`. Catatan: saran `not
  board.legal_moves.any()` di atas **tidak jalan** di python-chess 1.11.2
  (`LegalMoveGenerator` tak punya `.any()`); dipakai `not any(board.legal_moves)`.

### Apa ini

`best_move` membalas `422` saat `board.is_game_over()`. Masalahnya
`is_game_over()` di python-chess bukan hanya "tidak ada langkah legal": ia juga
true untuk **material tidak cukup** (`is_insufficient_material`), **aturan 75
langkah**, dan **repetisi lima kali**. Posisi seperti itu tetap punya langkah
legal, dan engine tetap bisa memilih langkah.

### Reproduksi

```bash
curl -X POST http://localhost:8000/api/best-move \
  -H 'Content-Type: application/json' \
  -d '{"fen":"8/8/8/4k3/8/4K3/8/8 b - - 0 1"}'
```

FEN ini Raja vs Raja: `legal_moves = 5` tetapi `is_game_over() = True`.

### Expected

`200` dengan `move_uci` legal (engine melangkah). Ini juga yang diharapkan
frontend: `gameOver` di FE = "tidak ada langkah legal" (`allLegal(...).length === 0`),
jadi FE menganggap permainan **belum** selesai dan akan memanggil endpoint ini.

### Actual

`422` dengan detail `"tidak ada langkah legal"` — padahal ada 5 langkah legal.
Akibatnya bot gagal melangkah dan giliran mentok di hitam.

### Fix terkecil

Satu baris, di `backend/app/api.py:288`:

```python
# ganti:
if board.is_game_over():
# menjadi:
if not board.legal_moves.any():
```

### Catatan (penting)

Bukan salah agent: pseudo-code di `BOT.md` (dan catatan di `AGENT.md`/`README.md`)
memang menulis `is_game_over()`. Karena itu, saat memperbaiki **sekalian koreksi
spec/dokumentasi**:

- `BOT.md` bagian scope: ganti contoh `if board.is_game_over():` jadi
  `if not board.legal_moves.any():`, serta perbaiki kalimat
  "FEN dengan langkah legal tidak akan kena" (itu keliru).
- `AGENT.md` / `README.md`: ubah "skakmat / remis (tidak ada langkah legal) → 422"
  jadi hanya **skakmat / remis karena tidak ada langkah legal**.

### Test yang harus ditambah

Di `backend/tests/test_best_move.py`:

- FEN material tidak cukup (mis. `8/8/8/4k3/8/4K3/8/8 b - - 0 1`) dengan engine
  **ada** → `200` dan `move_uci` legal.
- Pastikan test skakmat lama (`MATE_FEN`) tetap `422` (langkah legal = 0).

### Di luar scope

Deteksi remis-material/50-langkah yang lebih benar di **frontend** (agar papan
mengumumkan remis) bukan tugas entri ini; kalau nanti dikerjakan, ubah FE dan BE
bersamaan.
