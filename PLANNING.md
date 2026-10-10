# PLANNING — Chess Classification Model

Dokumen ini adalah **sumber kebenaran bersama** untuk seluruh repo (frontend +
backend + model). Tujuannya menyelaraskan scope, kontrak, dan status antar
bagian. Setiap agent/anggota tim membaca ini lebih dulu sebelum bekerja.

> **Status terakhir diperbarui:** Oktober 2026.
> Ringkasan cepat: **kontrak API final, backend siap, dan integrasi klasifikasi
> frontend sudah selesai**. Game catur di frontend kini mengirim FEN posisi
> terkini ke backend dan menampilkan label fase + confidence.

## 1. Tujuan project

Sesuai nama repo, fokus utama adalah **model klasifikasi**, bukan game engine
catur. Game di frontend hanyalah sarana untuk menghasilkan **input posisi**.

Flow MVP:

```
[Papan di frontend] ──FEN──▶ POST /api/classify ──▶ [Backend + model] ──▶ {label, confidence} ──▶ ditampilkan
```

## 2. Keputusan scope (final)

- **Target klasifikasi:** fase permainan (game phase).
- **Label:** `opening` | `middlegame` | `endgame` (huruf kecil, enum).
- **Input model:** **FEN saja** (satu string). Frontend hanya mengirim FEN.
- **Sumber label:** kolom `phase` pada dataset, dipakai apa adanya. Tidak ada
  heuristik label buatan sendiri (menghindari sirkularitas).
- **Pembagian kerja:** frontend menyiapkan pembuatan + pengiriman FEN serta
  menampilkan hasil; backend menyiapkan API + model.

## 3. Kontrak API (FROZEN untuk MVP)

Base URL dev backend: `http://localhost:8000`.

### `GET /api/health`

Response `200`:

```json
{ "status": "ok" }
```

### `POST /api/classify`

Request (JSON):

```json
{ "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1" }
```

Response `200`:

```json
{
  "label": "middlegame",
  "confidence": 0.94,
  "probabilities": {
    "opening": 0.02,
    "middlegame": 0.94,
    "endgame": 0.04
  },
  "model_version": "0.1.0"
}
```

Aturan:

- `label` selalu salah satu dari `opening` | `middlegame` | `endgame`.
- `confidence` float `0.0`–`1.0`.
- `probabilities` memuat ketiga kelas dan totalnya ~1.0.
- FEN tidak valid → `400`/`422` dengan bentuk `{ "detail": "..." }`.
- Model belum tersedia di server → `503` dengan `{ "detail": "..." }`
  (server tetap hidup).
- `Content-Type: application/json`.
- CORS mengizinkan origin dev frontend (`http://localhost:5173`,
  `http://127.0.0.1:5173`). Proxy Vite tetap disiapkan agar aman.

## 4. Status terkini

| Area | Status | Catatan |
|---|---|---|
| Game catur frontend | ✅ Selesai | Vue 3 + TS + Vite, pemain lokal, aturan langkah lengkap |
| Integrasi klasifikasi frontend | ✅ Selesai | `src/api/classify.ts`, `AnalysisPanel`, proxy `/api` |
| Endpoint backend (`/api/health`, `/api/classify`) | ✅ Selesai | FastAPI, kontrak sesuai bagian 3 |
| Model klasifikasi | ✅ Baseline siap | `model.joblib` terlatih dari dataset |
| Dataset | ✅ Tersedia | `datasets/moves.csv`, sudah berlabel `phase` |
| Test backend | 🟡 Sebagian | 5 test API hijau; test fitur/dataset belum |
| Dokumentasi | 🟡 Berjalan | `backend/AGENT.md`, `frontend/AGENT.md` |

**Implikasi:** integrasi frontend (bagian 7) sudah terpasang dan teruji
end-to-end (health, classify, dan error `422` lewat proxy Vite). Sisa pekerjaan
berada di sisi backend/ML (test fitur/dataset, laporan metrik) dan dataset.

## 5. Dataset

Dataset eksperimen ada di `backend/datasets/moves.csv` (tidak di-commit, ukuran
besar). Fakta utama:

- ~3,18 juta baris, ~49.669 game unik.
- Kolom kunci untuk training: `game_id`, `ply`, `fen_before`, `phase`.
- Kolom lain tersedia (evaluasi, `cp_loss`, `move_quality`, clock, dll.) tetapi
  belum dipakai.
- Distribusi label: `middlegame` ~54%, `opening` ~30%, `endgame` ~15%.
- Setiap baris adalah posisi **sebelum** langkah (`fen_before`).

Catatan lintas tim: dataset ini bersifat **bahan latihan**, bukan skema data
produk. Game di frontend tidak perlu menyamai kolom dataset.

## 6. Pendekatan model

- Model: scikit-learn `RandomForestClassifier` (`random_state=42`) di dalam
  `Pipeline` yang juga memuat ekstraksi fitur dari FEN.
- Fitur: turunan FEN (material & jumlah bidak, jumlah tiap jenis bidak, giliran,
  `ply`/`fullmove_number`, hak rokade, en passant).
- **Anti-leakage:** evaluasi memakai split per `game_id` (baris satu game tidak
  terpecah ke train & test), plus metrik tambahan pada FEN unik.
- Artifact: `backend/models/model.joblib` (gitignored), dimuat saat server start.

Hasil baseline (sampel 200k baris): akurasi test ~0.9999 vs baseline mayoritas
~0.537. Akurasi setinggi ini menandakan definisi `phase` pada dataset sangat
deterministik (dominan nomor langkah + material) — **bukan** ukuran kecerdasan
model. Perlu dijelaskan apa adanya saat melaporkan metrik.

## 7. Tanggung jawab frontend

Implementasi (sudah selesai):

| File | Fungsi |
|---|---|
| `src/lib/chess/fen.ts` | Bangun FEN dari state papan |
| `src/api/classify.ts` | Client `fetch` ke `POST /api/classify` |
| `src/components/AnalysisPanel.vue` | Tombol "Analisis posisi" + tampilkan label & confidence |
| `src/composables/useChess.ts` | Expose `fen` computed dari state permainan |
| `src/style.css` | Gaya panel analisis |
| `vite.config.ts` | Proxy dev `/api` → `http://localhost:8000` |
| `src/App.vue` | Pasang `AnalysisPanel` |

Catatan teknis FEN dari state `useChess`:

- Field FEN standar (6): `piece_placement active_color castling en_passant halfmove_clock fullmove_number`.
- `active_color` dari `turn`.
- `castling` dari `castling` (KQkq, kosong bila tidak ada).
- `en_passant` dari `enPassant` (notasi `e3`), `-` bila tidak ada.
- `halfmove_clock` **belum dilacak** → kirim `0` (cukup untuk klasifikasi fase).
- `fullmove_number` = `floor(ply / 2) + 1`, dengan `ply = moves.length`.
- FEN awal **wajib** sama persis dengan:
  `rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1`.

Perilaku UI:

- Tombol memakai FEN posisi saat ini.
- State: idle / loading / sukses (label + confidence) / error.
- Tidak ada autentikasi, tidak ada penyimpanan.

Catatan: base URL default relatif (`/api`, memakai proxy Vite saat dev). Set
`VITE_API_BASE` bila ingin menembak backend langsung tanpa proxy.

## 8. Tanggung jawab backend

Struktur aktual (detail ada di `backend/AGENT.md`):

```
backend/
├── main.py                 # entrypoint ASGI (uvicorn main:app)
├── app/
│   ├── config.py           # path & setting (env CHESS_*)
│   ├── schemas.py          # kontrak request/response
│   ├── classifier.py       # muat model + predict
│   ├── routes.py           # endpoint API
│   ├── server.py           # app factory + CORS
│   └── ml/                 # labeling, features, dataset, train
├── models/                 # model.joblib + metrics.json (gitignored)
├── datasets/               # dataset mentah (gitignored)
└── tests/
```

- Framework: FastAPI + uvicorn + pydantic.
- Dependency: `fastapi`, `uvicorn`, `pydantic`, `scikit-learn`, `python-chess`,
  `pandas`, `pytest`. Manajemen paket: `uv`.
- Catatan Python: `.python-version` = 3.14; scikit-learn 1.9.1 sudah terbukti
  jalan di lingkungan ini.

## 9. Milestone

| M | Target | Bukti selesai | Status |
|---|---|---|---|
| M0 | FEN generator + endpoint echo | Frontend kirim FEN, backend balas FEN sama | ✅ (digantikan classify nyata) |
| M1 | Feature + labeling + train + model | `/api/classify` balas salah satu dari 3 label | ✅ |
| M2 | Integrasi `AnalysisPanel` + proxy + CORS | Klik tombol → label muncul | ✅ |
| M3 | Test + evaluasi model | Test hijau, metrik dilaporkan | 🟡 test API hijau, metrik ada |

## 10. Non-goals (MVP)

- Autentikasi / user accounts.
- Penyimpanan riwayat analisis.
- Proses async / queue.
- Klasifikasi per langkah (butuh >1 FEN).
- Training dari dalam server API.

## 11. Risiko & catatan

- **Duplikasi FEN antar-game** (mis. FEN awal berulang di banyak game) membuat
  metrik cenderung optimistis; sudah dimitigasi dengan evaluasi dedup FEN.
- **`halfmove_clock` tidak dikirim akurat** (selalu 0). Tidak masalah untuk fase,
  tapi backend tidak boleh bergantung padanya.
- **Interpretasi metrik:** akurasi tinggi berasal dari label yang deterministik;
  jangan diklaim sebagai bukti model "cerdas".
- **Kontrak API beku:** perubahan bentuk request/response harus disepakati
  bersama dan diperbarui di dokumen ini.

## 12. Cara menjalankan (dev)

Backend (model sudah tersedia):

```bash
cd backend
uv sync
uv run uvicorn main:app --reload        # http://localhost:8000
uv run python -m app.ml.train           # latih ulang bila perlu
uv run pytest
```

Frontend:

```bash
cd frontend
deno install
deno task dev                           # http://localhost:5173
```

Setelah integrasi selesai, alur uji: buka papan di frontend → klik "Analisis
posisi" → label + confidence muncul.
