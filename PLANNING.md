# PLANNING — Chess Classification Model

Dokumen ini adalah **sumber kebenaran bersama** untuk seluruh repo (frontend +
backend + model). Tujuannya menyelaraskan scope, kontrak, dan status antar
bagian. Setiap agent/anggota tim membaca ini lebih dulu sebelum bekerja.

> **Status terakhir diperbarui:** Oktober 2026.
> Ringkasan cepat: **kontrak API final, backend siap, dan integrasi klasifikasi
> frontend sudah selesai**. Backend baru saja dirapikan menjadi 2 modul inti
> (`app/api.py` + `app/ml.py`), fitur pola struktur pion ditambahkan, dan seluruh
> **25 test hijau**. `datasets/puzzles.csv` (1176 puzzle taktis berlabel tema)
> tersedia sebagai bahan eksplorasi model berikutnya — belum dipakai.

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
| Struktur backend | ✅ Dirapikan | 2 modul inti `app/api.py` + `app/ml.py`; entrypoint `train.py` |
| Model klasifikasi | ✅ Latih ulang | +8 fitur pola struktur pion; akurasi test ~0.9999 |
| Dataset | ✅ Tersedia | `moves.csv` (3,18 jt baris, berlabel `phase`) + `puzzles.csv` (eksplorasi, belum dipakai) |
| Test backend | ✅ Hijau | 25 test: API (5), fitur (7), pola pion (8), perilaku model (5) |
| Dokumentasi | ✅ Selaras | `backend/AGENT.md`, `frontend/AGENT.md`, `PLANNING.md` |

**Implikasi:** integrasi frontend (bagian 7) sudah terpasang dan teruji
end-to-end (health, classify, dan error `422` lewat proxy Vite). Perombakan
struktur backend **tidak mengubah kontrak API**, sehingga frontend tidak perlu
penyesuaian. Sisa pekerjaan berada di sisi eksplorasi ML (mis. model berbasis
`puzzles.csv` / pengenalan pola taktis).

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

Selain itu tersedia `backend/datasets/puzzles.csv` (gitignored) — **1176 puzzle
taktis berlabel tema** (`capture`/`check`/`mate`/`promotion`/dll., 7 kelas) plus
`difficulty_score` dan `engine_best_eval_cp`. **Belum dipakai produksi**; ini
kandidat eksplorasi model berikutnya. Ciri pentingnya: tema puzzle adalah sifat
**taktis (gerakan)** sehingga fitur statis FEN yang ada sekarang tidak cukup —
perlu fitur dinamis (legal moves, serangan). Hasil uji awal: klasifikasi tema
~0.495 ≈ baseline, artinya perlu fitur baru, bukan sekadar ganti algoritma.

## 6. Pendekatan model

- Model: scikit-learn `RandomForestClassifier` (`random_state=42`) di dalam
  `Pipeline` yang juga memuat ekstraksi fitur dari FEN.
- Fitur: turunan FEN — material & jumlah bidak, jumlah tiap jenis bidak, pola
  **struktur pion** (pion dobel, terisolasi, passed, pulau pion) per warna,
  giliran, `ply`/`fullmove_number`, hak rokade, en passant.
- **Anti-leakage:** evaluasi memakai split per `game_id` (baris satu game tidak
  terpecah ke train & test), plus metrik tambahan pada FEN unik.
- Artifact: `backend/models/model.joblib` (gitignored), dimuat saat server start.

Hasil baseline (sampel 200k baris): akurasi test ~0.9999 vs baseline mayoritas
~0.537. Akurasi setinggi ini menandakan definisi `phase` pada dataset sangat
deterministik (dominan nomor langkah + material) — **bukan** ukuran kecerdasan
model. Perlu dijelaskan apa adanya saat melaporkan metrik.

Catatan eksplorasi (sudah diuji): mengganti fitur (buang `ply`) atau algoritma
(RF/HGB/LogReg) **tidak** mengubah label posisi OOD seperti K+Q mate di
`fullmove 1` — masalahnya ada di **definisi label** `phase` yang berbasis
nomor langkah, bukan di fitur/model. Mengubah perilaku itu berarti merelabel
dataset (keputusan produk), di luar kontrak saat ini.

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
├── train.py                # entrypoint training model
├── app/
│   ├── config.py           # path & setting (env CHESS_*)
│   ├── api.py              # skema + classifier + endpoint + app factory
│   └── ml.py               # label + fitur FEN + dataset + training
├── models/                 # model.joblib + metrics.json (gitignored)
├── datasets/               # dataset mentah (gitignored)
└── tests/
```

- Framework: FastAPI + uvicorn + pydantic.
- Dependency: `fastapi`, `uvicorn`, `pydantic`, `scikit-learn`, `python-chess`,
  `pandas`, `pytest`. Manajemen paket: `uv`.
- Catatan Python: `.python-version` = 3.14; scikit-learn 1.9.1 sudah terbukti
  jalan di lingkungan ini.
- Struktur sengaja **ringkas (2 modul inti)** agar alur mudah diikuti tanpa lompat
  file: `app/api.py` = skema → classifier → endpoint → app factory; `app/ml.py` =
  label → fitur → dataset → training. Entrypoint: `main.py` (server) & `train.py`.

## 9. Milestone

| M | Target | Bukti selesai | Status |
|---|---|---|---|
| M0 | FEN generator + endpoint echo | Frontend kirim FEN, backend balas FEN sama | ✅ (digantikan classify nyata) |
| M1 | Feature + labeling + train + model | `/api/classify` balas salah satu dari 3 label | ✅ |
| M2 | Integrasi `AnalysisPanel` + proxy + CORS | Klik tombol → label muncul | ✅ |
| M3 | Test + evaluasi model | Test hijau, metrik dilaporkan | ✅ 25 test hijau; metrik ada |
| M4 | Rapikan struktur backend | Sisi HTTP & ML jadi 2 modul inti | ✅ `app/api.py` + `app/ml.py` |
| M5 | Fitur pola struktur pion | Fitur dobel/terisolasi/passed/pulau + test | ✅ 8 test khusus |
| M6 | Model berbasis `puzzles.csv` / pengenalan pola taktis | Klasifikasi tema dengan fitur dinamis | 🔜 rencana (belum dikerjakan) |

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
- **Fitur/algoritma tak bisa mengalahkan label.** Posisi OOD (mis. K+Q mate di
  `fullmove 1`) tetap `middlegame` walau fitur `ply` dibuang atau algoritma
  diganti — akar masalahnya definisi `phase` berbasis nomor langkah (lihat bagian 6).
- **Kontrak API beku:** perubahan bentuk request/response harus disepakati
  bersama dan diperbarui di dokumen ini.

## 12. Cara menjalankan (dev)

Backend (model sudah tersedia):

```bash
cd backend
uv sync
uv run uvicorn main:app --reload        # http://localhost:8000
uv run python train.py                    # latih ulang bila perlu
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
