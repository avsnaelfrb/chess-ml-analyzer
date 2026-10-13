# PLANNING — Chess Classification Model

Dokumen ini adalah **sumber kebenaran bersama** untuk seluruh repo (frontend +
backend + model). Tujuannya menyelaraskan scope, kontrak, dan status antar
bagian. Setiap agent/anggota tim membaca ini lebih dulu sebelum bekerja.

> **Status terakhir diperbarui:** Oktober 2026.
> Ringkasan cepat: kontrak `/api/classify` (klasifikasi **fase**) sudah **beku**
> dan terintegrasi di frontend — jangan diubah. Arah baru: menambah **tugas
> kedua**, yaitu **analisis langkah** (kualitas langkah), sebagai **endpoint &
> model terpisah**. Ini menuntut frontend mulai mengirim **`fen_before` +
> langkah (UCI)**, bukan hanya satu FEN.
>
> Legenda status: 🔒 **Beku** (jangan diubah tanpa kesepakatan) · ✅ **Selesai** ·
> 🔜 **Rencana** (belum dikerjakan, kontrak masih dapat berubah).

## 1. Tujuan project

Fokus utama repo adalah **model klasifikasi**, bukan game engine catur. Game di
frontend hanyalah sarana menghasilkan **input** bagi model.

Dua tugas yang disepakati:

1. **Fase permainan** (sudah jalan, beku) — input **FEN** → `opening` /
   `middlegame` / `endgame`.
2. **Analisis langkah** (rencana) — input **`fen_before` + langkah** → kualitas
   langkah (blunder/mistake/…). Endpoint **baru**, tidak menggantikan yang lama.

Flow saat ini (fase):

```
[Papan frontend] ──FEN──▶ POST /api/classify ──▶ [Backend + model] ──▶ {label, confidence} ──▶ ditampilkan
```

Flow yang direncanakan (analisis langkah):

```
[Papan frontend] ──{fen_before, move_uci}──▶ POST /api/analyze-move ──▶ [Backend + model] ──▶ {quality, ...} ──▶ ditampilkan
```

## 2. Prinsip desain (baca dulu sebelum menambah label)

- **FEN = posisi (state), bukan langkah (action).** FEN memuat semua bidak +
  metadata (giliran, rokade, en passant, nomor langkah), tetapi **tidak** memuat
  langkah yang baru dimainkan. Dua FEN identik tidak bicara apa pun soal
  "langkah tadi bagus/jelek".
- **Kualitas langkah butuh transisi**, yaitu *posisi sebelum* + *langkah*. Karena
  itu tugas ini butuh `fen_before` + `move_uci`, bukan satu FEN.
- **Jangan melatih model untuk label yang bisa dihitung aturan sederhana**
  (`is_capture`, `is_check`, `piece_type`, `side_to_move`, `promotion_piece`).
  Itu bisa dibaca langsung; model tidak menambah nilai.
- **Label yang berguna bagi pemain biasanya timpang** (mis. blunder sangat
  langka). Keseimbangan kelas harus dicek sebelum melatih.

## 3. Kontrak API — FASE 🔒 BEKU

Base URL dev backend: `http://localhost:8000`. **Bagian ini jangan diubah**
selama tidak ada kesepakatan baru; frontend sudah bergantung padanya.

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
  "probabilities": { "opening": 0.02, "middlegame": 0.94, "endgame": 0.04 },
  "model_version": "0.1.0"
}
```

Aturan:

- `label` selalu salah satu dari `opening` | `middlegame` | `endgame`.
- `confidence` float `0.0`–`1.0`; `probabilities` memuat ketiga kelas, total ~1.0.
- FEN tidak valid → `422` dengan `{ "detail": "..." }`.
- Model belum tersedia → `503` dengan `{ "detail": "..." }` (server tetap hidup).
- `Content-Type: application/json`.
- CORS mengizinkan origin dev frontend (`http://localhost:5173`,
  `http://127.0.0.1:5173`). Proxy Vite tetap dipakai saat dev.

## 4. Kontrak API — ANALISIS LANGKAH 🔜 RENCANA

**Belum diimplementasikan.** Bentuk di bawah adalah usulan agar frontend bisa
mulai menyiapkan pengiriman. Nama endpoint & bentuk respons **dapat berubah**
sebelum disepakati final.

### `POST /api/analyze-move` (usulan nama)

Request (JSON):

```json
{
  "fen_before": "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
  "move_uci": "d2d4"
}
```

- `fen_before`: posisi **sebelum** langkah dimainkan (6 field FEN standar).
- `move_uci`: langkah dalam notasi UCI — petak asal + petak tujuan, huruf kecil
  semua; tambahkan huruf promosi bila perlu (`e7e8q`, `a2a1n`).

Response `200` (usulan, masih dapat berubah):

```json
{
  "quality": "Inaccuracy",
  "cp_loss": 120,
  "probabilities": { "Good": 0.31, "Inaccuracy": 0.52, "Mistake": 0.12, "Blunder": 0.05 },
  "model_version": "0.2.0"
}
```

Aturan yang direncanakan (meniru gaya `/api/classify`):

- `quality` salah satu `Good` | `Inaccuracy` | `Mistake` | `Blunder`.
- `cp_loss` = kerugian centipawn (integer); `null` bila langkah = engine best.
- `fen_before` atau `move_uci` tidak valid → `422` `{ "detail": "..." }`.
- Model belum tersedia → `503` `{ "detail": "..." }`.

> Catatan keputusan yang belum diambil: apakah output utama berupa
> **klasifikasi** (4 kelas di atas) atau **regresi** `cp_loss`, atau keduanya.
> `quality` dapat diturunkan dari ambang `cp_loss` bila dipilih regresi.

## 5. Status terkini

| Area | Status | Catatan |
|---|---|---|
| Game catur frontend | ✅ Selesai | Vue 3 + TS + Vite, pemain lokal, aturan langkah lengkap |
| Integrasi fase frontend | ✅ Selesai | `src/api/classify.ts`, `AnalysisPanel`, proxy `/api` |
| Endpoint fase (`/api/health`, `/api/classify`) | 🔒 Beku | FastAPI, sesuai bagian 3 |
| Struktur backend | ✅ Dirapikan | 2 modul inti `app/api.py` + `app/ml.py`; entrypoint `train.py` |
| Model fase | ✅ Latih ulang | +8 fitur pola struktur pion; akurasi test ~0.9999 |
| Dataset | ✅ Tersedia | `moves.csv` (3,18 jt baris) + `puzzles.csv` (1.176 baris) |
| Test backend | ✅ Hijau | 25 test (API 5, fitur 7, pola pion 8, perilaku model 5) |
| Katalog label (dua dataset) | ✅ Terdokumentasi | Bagian 7 |
| Endpoint + model analisis langkah | 🔜 Rencana | Butuh input `fen_before` + `move_uci` (bagian 4 & 9) |

**Implikasi untuk frontend:** integrasi fase tidak berubah. Yang perlu disiapkan
adalah **mengirim `fen_before` + langkah (UCI)** agar endpoint analisis langkah
bisa dibangun (bagian 9). Belum ada yang rusak bila belum dikerjakan.

## 6. Dataset

Semua di `backend/datasets/` (gitignored, ukuran besar).

### `moves.csv` — data utama (posisi + langkah per baris)

- ~3,18 juta baris, ~49.669 game unik.
- Kolom kunci: `game_id`, `ply`, `fen_before`, `phase`.
- Kolom langkah/evaluasi (belum dipakai latihan): `move_san`, `move_uci`,
  `piece_type`, `is_capture`, `is_check`, `is_castle`, `is_promotion`,
  `promotion_piece`, `best_move_san`, `best_move_uci`, `eval_white_before`,
  `eval_white_after`, `cp_loss`, `move_quality`, clock.
- Setiap baris adalah posisi **sebelum** langkah (`fen_before`).
- **Penting:** `move_quality` dan `cp_loss` hanya terisi untuk **langkah pemain
  target** (`is_target_move = True`; proporsinya ~50% baris). `cp_loss` NaN
  berarti "langkah = engine best", **bukan data hilang**.
- `move_quality` (di baris target) sangat timpang: ~99,4% `Good`.
- **Tidak ada** kolom hasil game/terminasi/pembukaan di `moves.csv`.

### `puzzles.csv` — puzzle taktis

- 1.176 baris, 67 kolom.
- Tema 7 kelas: `capture` (567), `check` (258), `tactical-check` (146),
  `endgame-technique` (80), `mate` (59), `promotion` (37), `improvement` (29).
- Kolom lain: `difficulty_score`/`difficulty_bucket`, `is_forcing`,
  `engine_best_eval_cp`, `engine_best_mate`, `opening_eco`/`opening_name`,
  `target_result`, dll.
- Ciri: tema adalah sifat **taktis (langkah)**, jadi fitur FEN statis yang ada
  sekarang tidak cukup — perlu fitur dinamis. Uji awal klasifikasi tema
  ~0.495 ≈ baseline.

## 7. Katalog label yang mungkin (hasil analisis dua dataset)

Saringan: label harus **berguna bagi pemain** *dan* **tidak bisa dihitung aturan
sederhana** *dan* **cukup seimbang**.

### Dari `moves.csv`

| Label | Kolom sumber | Jenis | Seimbang? | Butuh langkah? | Nilai |
|---|---|---|---|---|---|
| Fase (sekarang) | `phase` | klasifikasi 3 | ya | tidak | rendah (deterministik) |
| Kualitas langkah | `move_quality` | klasifikasi 4 | ❌ ~99,4% Good | **ya** | tinggi tapi timpang |
| Kerugian centipawn | `cp_loss` | regresi | 50% = best move | **ya** | tinggi |
| Evaluasi posisi ("siapa unggul") | `eval_white_before` | regresi / bucket | kontinu | tidak | tinggi, FEN-only |
| Sifat taktis langkah | `is_capture/is_check/...` | multi-label | timpang | ya | ❌ bisa dihitung aturan |
| Bidak yang jalan | `piece_type` | klasifikasi 6 | ya | ya | ❌ bisa dihitung aturan |

### Dari `puzzles.csv`

| Label | Kolom sumber | Jenis | Seimbang? | Butuh langkah? | Nilai |
|---|---|---|---|---|---|
| Tema taktis | `final_theme` | klasifikasi 7 | timpang | tidak | tinggi; butuh fitur dinamis |
| Kesulitan | `difficulty_bucket` / `difficulty_score` | klasifikasi 4 / regresi | lumayan | tidak | sedang (sinyal lemah, R²~0,24) |
| Langkah memaksa? | `is_forcing` | biner | 88/12 | tidak | sedang (n kecil) |
| Hasil akhir pemain | `target_result` | klasifikasi 3 | 70/24/6 | tidak | rendah (outcome ≠ posisi) |
| Pembukaan | `opening_eco` / `opening_name` | klasifikasi 158/411 | parah | tidak | rendah (data sedikit, posisi telat) |

**Prioritas yang disepakati:** tugas kedua = **analisis langkah** (kualitas
langkah / `cp_loss`) karena paling berguna bagi pemain dan didukung data
terbesar. Kandidat berikutnya (tema taktis) dicatat sebagai rencana lanjutan.

## 8. Pendekatan model (tugas fase — yang sudah jalan)

- Model: scikit-learn `RandomForestClassifier` (`random_state=42`) di dalam
  `Pipeline` yang juga memuat ekstraksi fitur dari FEN.
- Fitur: turunan FEN — material & jumlah bidak, jumlah tiap jenis bidak, pola
  **struktur pion** (dobel/terisolasi/passed/pulau) per warna, giliran,
  `ply`/`fullmove_number`, hak rokade, en passant.
- **Anti-leakage:** split per `game_id`, plus metrik tambahan pada FEN unik.
- Artifact: `backend/models/model.joblib` (gitignored), dimuat saat server start.
- Baseline (sampel 200k): akurasi test ~0.9999 vs baseline mayoritas ~0.537.
  Akurasi tinggi karena label `phase` memang deterministik (nomor langkah +
  material) — **bukan** ukuran kecerdasan model.

Catatan: mengganti fitur (buang `ply`) atau algoritma (RF/HGB/LogReg) **tidak**
mengubah label posisi OOD (mis. K+Q mate di `fullmove 1` tetap `middlegame`).
Akar masalahnya definisi label, bukan fitur/model.

## 9. Tanggung jawab frontend

### 9a. Fase (selesai — jangan diubah)

| File | Fungsi |
|---|---|
| `src/lib/chess/fen.ts` | Bangun FEN dari state papan |
| `src/api/classify.ts` | Client `fetch` ke `POST /api/classify` |
| `src/components/AnalysisPanel.vue` | Tombol "Analisis posisi" + tampilkan label & confidence |
| `src/composables/useChess.ts` | Expose `fen` computed dari state permainan |
| `vite.config.ts` | Proxy dev `/api` → `http://localhost:8000` |
| `src/App.vue` | Pasang `AnalysisPanel` |

Catatan FEN dari state `useChess`: 6 field standar; `halfmove_clock` selalu `0`
(belum dilacak); `fullmove_number = floor(ply / 2) + 1`, `ply = moves.length`;
FEN awal wajib `rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1`.
Base URL default relatif (`/api`); override dengan `VITE_API_BASE`.

### 9b. Analisis langkah 🔜 RENCANA (yang perlu disiapkan frontend)

Tujuan: saat sebuah langkah dimainkan, frontend dapat mengirim **posisi sebelum
langkah** + **langkah itu** ke endpoint baru (bagian 4). Data ini **sudah ada** di
state frontend; hanya belum dikirim.

Yang dibutuhkan:

1. **`fen_before`** — FEN **sebelum** langkah. Di `useChess.makeMove`, baca
   `fen.value` **sebelum** `applyMove` (saat itu papan masih posisi lama).
   Snapshot posisi lama memang sudah disimpan di `history`.
2. **`move_uci`** — bangun dari objek `move` (`from`, `r/c` tujuan, `promotion`):
   `${squareName(move.from)}${squareName({r: move.r, c: move.c})}` +
   huruf promosi bila ada. Huruf UCI: `queen→q`, `rook→r`, `bishop→b`,
   `knight→n` — **jangan** pakai `promotion[0]` (knight → `k`, salah). Contoh
   `d2d4`, `e7e8q`, `b7b8n`. `squareName()` sudah ada di
   `src/lib/chess/notation.ts`.
3. Simpan sebagai "langkah terakhir", mis. `{ fenBefore, moveUci }`, lalu
   sediakan aksi (tombol "Analisis langkah") yang memanggil endpoint baru.

Penting:

- **Jangan kirim `fen` (sesudah langkah)** untuk tugas ini; yang dibutuhkan
  `fen_before`. `fen` yang ada sekarang = posisi **sesudah** langkah.
- **Jangan mengubah alur `/api/classify`** yang sudah jalan.
- Endpoint analisis langkah belum ada; frontend boleh menyiapkan pengiriman
  lebih dulu tanpa menunggu backend.

## 10. Tanggung jawab backend

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

- Framework: FastAPI + uvicorn + pydantic. Manajemen paket: `uv`.
- Struktur sengaja **ringkas (2 modul inti):** `app/api.py` = skema → classifier
  → endpoint → app factory; `app/ml.py` = label → fitur → dataset → training.
- Rencana analisis langkah akan menambah endpoint & (kemungkinan) artifact model
  baru. Bila ditambahkan, tetap pisahkan dari alur fase yang beku.

## 11. Milestone

| M | Target | Bukti selesai | Status |
|---|---|---|---|
| M0 | FEN generator + endpoint echo | Frontend kirim FEN, backend balas FEN sama | ✅ (digantikan classify nyata) |
| M1 | Feature + labeling + train + model fase | `/api/classify` balas salah satu dari 3 label | ✅ |
| M2 | Integrasi `AnalysisPanel` + proxy + CORS | Klik tombol → label muncul | ✅ |
| M3 | Test + evaluasi model | 25 test hijau; metrik ada | ✅ |
| M4 | Rapikan struktur backend | 2 modul inti (`app/api.py` + `app/ml.py`) | ✅ |
| M5 | Fitur pola struktur pion | 8 fitur + 8 test | ✅ |
| M6 | Katalog label dari dua dataset | Bagian 7 dokumen ini | ✅ |
| M7 | Endpoint + model analisis langkah | `{fen_before, move_uci}` → kualitas langkah | 🔜 rencana |
| M8 | Model tema taktis (`puzzles.csv`) | Klasifikasi tema dengan fitur dinamis | 🔜 rencana |

## 12. Non-goals (MVP)

- Autentikasi / user accounts.
- Penyimpanan riwayat analisis.
- Proses async / queue.
- Analisis seluruh permainan sekaligus (batch).
- Training dari dalam server API.
- Memprediksi langkah terbaik (policy) — hanya **menilai** langkah yang sudah dimainkan.

## 13. Risiko & catatan

- **State vs action.** Jangan menganggap FEN cukup untuk menilai langkah; lihat
  bagian 2. `fen_before` + `move_uci` wajib.
- **Ketimpangan kelas.** `move_quality` ~99,4% `Good`; jangan melatih kelas apa
  adanya tanpa penanganan (penyeimbangan/ambang). `promotion`, `is_forcing`
  kecil juga.
- **Data puzzle kecil** (1.176 baris); jangan berharap model besar.
- **Duplikasi FEN antar-game** membuat metrik optimistis; tetap pakai evaluasi
  dedup FEN.
- **`halfmove_clock` selalu `0`**; jangan jadikan fitur yang diandalkan.
- **Kontrak fase beku:** perubahan `/api/classify` harus disepakati dan
  diperbarui di dokumen ini dulu.
- **Endpoint analisis langkah masih rencana:** bentuk request/response dapat
  berubah sebelum final (bagian 4).

## 14. Cara menjalankan (dev)

Backend:

```bash
cd backend
uv sync
uv run uvicorn main:app --reload        # http://localhost:8000
uv run python train.py                   # latih ulang bila perlu
uv run pytest
```

Frontend:

```bash
cd frontend
deno install && deno task dev            # http://localhost:5173
# alternatif npm:
# npm install && npm run dev
```

Uji alur fase: buka papan di frontend → klik "Analisis posisi" → label +
confidence muncul.
