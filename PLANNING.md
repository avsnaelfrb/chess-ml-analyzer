# PLANNING — Chess Classification Model

Dokumen ini adalah **sumber kebenaran bersama** untuk seluruh repo (frontend +
backend + model). Tujuannya menyelaraskan scope, kontrak, dan status antar
bagian. Setiap agent/anggota tim membaca ini lebih dulu sebelum bekerja.

> **Status terakhir diperbarui:** Oktober 2026.
> Ringkasan cepat: kontrak `/api/classify` (klasifikasi **fase**) sudah **beku**
> dan terintegrasi di frontend — jangan diubah. Tugas kedua, **analisis langkah**
> (`POST /api/analyze-move`, input `fen_before` + langkah UCI), **sudah jalan**:
> backend memakai engine UCI **Stockfish** untuk menghitung centipawn loss lalu
> memetakannya ke `Good/Inaccuracy/Mistake/Blunder`. Frontend sudah mengirim
> `fen_before` + `move_uci` dan menampilkan hasilnya.
>
> Legenda status: 🔒 **Beku** (jangan diubah tanpa kesepakatan) · ✅ **Selesai** ·
> 🔜 **Rencana** (belum dikerjakan).

## 1. Tujuan project

Fokus utama repo adalah **model klasifikasi**, bukan game engine catur. Game di
frontend hanyalah sarana menghasilkan **input** bagi model.

Dua tugas yang disepakati:

1. **Fase permainan** (sudah jalan, beku) — input **FEN** → `opening` /
   `middlegame` / `endgame`.
2. **Analisis langkah** (sudah jalan) — input **`fen_before` + langkah (UCI)** →
   kualitas langkah (Good/Inaccuracy/Mistake/Blunder) lewat engine Stockfish.
   Endpoint **baru**, tidak menggantikan yang lama.

Flow saat ini (fase):

```
[Papan frontend] ──FEN──▶ POST /api/classify ──▶ [Backend + model] ──▶ {label, confidence} ──▶ ditampilkan
```

Flow analisis langkah (sudah jalan):

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

## 4. Kontrak API — ANALISIS LANGKAH ✅ SUDAH JALAN (engine)

Dihitung engine UCI **Stockfish** (bukan model ML). Engine menilai skor posisi
sebelum langkah (langkah terbaik) dan skor setelah langkah dimainkan — keduanya
dari sudut pandang pemain yang melangkah; selisihnya = `cp_loss`.

### `POST /api/analyze-move`

Request (JSON):

```json
{
  "fen_before": "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
  "move_uci": "d2d4"
}
```

- `fen_before`: posisi **sebelum** langkah (6 field FEN; harus posisi **legal**).
- `move_uci`: langkah dalam notasi UCI — huruf kecil semua; tambahkan huruf
  promosi bila perlu (`e7e8q`, `b7b8n`).

Response `200`:

```json
{
  "quality": "Inaccuracy",
  "cp_loss": 120.0,
  "probabilities": { "Good": 0.0, "Inaccuracy": 1.0, "Mistake": 0.0, "Blunder": 0.0 },
  "model_version": "Stockfish 19"
}
```

Aturan:

- `quality` salah satu `Good` | `Inaccuracy` | `Mistake` | `Blunder`, hasil ambang
  `cp_loss`: `<50` Good, `50–99` Inaccuracy, `100–199` Mistake, `≥200` Blunder
  (sama persis dengan definisi kolom `move_quality` di dataset).
- `cp_loss` = kerugian centipawn (`>= 0`), dihitung engine.
- `probabilities` bersifat **deterministik satu-panas** (engine memberi satu
  kelas pasti), bukan distribusi statistik.
- `model_version` = nama engine (mis. `"Stockfish 19"`).
- `fen_before` tidak valid / posisi ilegal / langkah ilegal → `422` `{ "detail": "..." }`.
- Engine belum tersedia (biner hilang) → `503` `{ "detail": "..." }`.

### `POST /api/best-move`

Langkah terbaik untuk mode **vs bot**. Pilihan bot = engine **Stockfish**,
bukan model ML (lihat non-goal bagian 12).

Request (JSON):

```json
{ "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1" }
```

Response `200`:

```json
{ "move_uci": "c7c5", "model_version": "Stockfish 19" }
```

Aturan:

- `fen` = posisi giliran yang harus melangkah (6 field FEN, posisi legal).
- `move_uci` selalu langkah **legal** pada `fen`; format UCI huruf kecil,
  promosi `q`/`r`/`b`/`n` bila perlu.
- `model_version` = nama engine, sama seperti `/api/analyze-move`.
- FEN tidak valid / posisi ilegal / **tidak ada langkah legal** → `422`
  `{ "detail": "..." }`. Yang ditolak hanya posisi tanpa langkah sama sekali
  (skakmat/remis mati); remis material tidak cukup, 75-langkah atau 5-fold
  **tetap** menghasilkan langkah.
- Engine belum tersedia (biner hilang) → `503` `{ "detail": "..." }`.

Batas input berlaku untuk semua endpoint: `fen` maks 200 karakter,
`move_uci` maks 5 karakter, badan request maks 64 KB (lebih → `413`).

## 5. Status terkini

| Area | Status | Catatan |
|---|---|---|
| Game catur frontend | ✅ Selesai | Vue 3 + TS + Vite, pemain lokal, aturan langkah lengkap |
| Integrasi fase frontend | ✅ Selesai | `src/api/classify.ts`, `AnalysisPanel`, proxy `/api` |
| Endpoint fase (`/api/health`, `/api/classify`) | 🔒 Beku | FastAPI, sesuai bagian 3 |
| Struktur backend | ✅ Dirapikan | 2 modul inti `app/api.py` + `app/ml.py`; entrypoint `train.py` |
| Model fase | ✅ Latih ulang | Tanpa fitur waktu (BE-005); akurasi test ~0.944, baseline ~0.537 |
| Dataset | ✅ Tersedia | `moves.csv` (3,18 jt baris) + `puzzles.csv` (1.176 baris) |
| Test backend | ✅ Hijau | 51 test (API+batas input 12, fitur 7, pola pion 8, perilaku model 4, analisis langkah 7, best-move 7, siklus engine 3, training 3) |
| Katalog label (dua dataset) | ✅ Terdokumentasi | Bagian 7 |
| Analisis langkah (`/api/analyze-move`) | ✅ Selesai (engine) | Stockfish; kontrak di bagian 4 |
| Langkah bot (`/api/best-move`) | ✅ Selesai (engine) | Mode vs bot; kontrak di bagian 4 |

**Implikasi untuk frontend:** integrasi fase tidak berubah. Frontend sudah
mengirim **`fen_before` + `move_uci`** dan menampilkan hasil analisis langkah
(bagian 9b) — end-to-end sudah jalan.

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
  hak rokade, en passant. Sengaja **tanpa** `ply` / `fullmove_number` /
  `halfmove_clock`: kolom itulah yang aturan pelabelan `phase` pakai, jadi
  memakainya = label leakage (lihat risiko bagian 13).
- **Anti-leakage:** split per `game_id`, plus metrik tambahan pada FEN unik yang
  tidak muncul di train.
- Artifact: `backend/models/model.joblib` (gitignored), dimuat saat server start.
- Baseline (sampel 200k): akurasi test **~0.944** vs baseline mayoritas ~0.537;
  dedup ~0.937. Angka turun dari ~0.9999 setelah fitur waktu dibuang — dan
  ~0.9999 itu memang bukan ukuran kecerdasan model.

Catatan: mengganti algoritma (RF/HGB/LogReg) **tidak** mengubah label posisi
OOD (mis. K+Q mate di `fullmove 1` tetap `middlegame`) — bahkan fitur waktu
sekalipun. Akar masalahnya definisi label, bukan fitur/model.

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

### 9b. Analisis langkah ✅ sudah diimplementasikan

Saat sebuah langkah dimainkan, frontend mengirim **posisi sebelum langkah** +
**langkah itu** ke `POST /api/analyze-move` (bagian 4).

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
- Analisis langkah & langkah bot sudah ditambahkan tanpa menyentuh alur fase
  yang beku: `app/api.py` menampung `MoveAnalyzer` (engine Stockfish) terpisah
  dari `PhaseClassifier` (model ML).

## 11. Milestone

| M | Target | Bukti selesai | Status |
|---|---|---|---|
| M0 | FEN generator + endpoint echo | Frontend kirim FEN, backend balas FEN sama | ✅ (digantikan classify nyata) |
| M1 | Feature + labeling + train + model fase | `/api/classify` balas salah satu dari 3 label | ✅ |
| M2 | Integrasi `AnalysisPanel` + proxy + CORS | Klik tombol → label muncul | ✅ |
| M3 | Test + evaluasi model | 51 test hijau; metrik ada | ✅ |
| M4 | Rapikan struktur backend | 2 modul inti (`app/api.py` + `app/ml.py`) | ✅ |
| M5 | Fitur pola struktur pion | 8 fitur + 8 test | ✅ |
| M6 | Katalog label dari dua dataset | Bagian 7 dokumen ini | ✅ |
| M7 | Endpoint analisis langkah (engine Stockfish) | `{fen_before, move_uci}` → kualitas langkah | ✅ |
| M8 | Model tema taktis (`puzzles.csv`) | Klasifikasi tema dengan fitur dinamis | 🔜 rencana |

## 12. Non-goals (MVP)

- Autentikasi / user accounts.
- Penyimpanan riwayat analisis.
- Proses async / queue.
- Analisis seluruh permainan sekaligus (batch).
- Training dari dalam server API.
- Memprediksi langkah terbaik (policy) **sebagai model ML** — model hanya
  **menilai** langkah yang sudah dimainkan. Pengecualian: mode **vs bot** memilih
  langkah lewat engine **Stockfish** (bukan model ML); kontraknya di
  `backend/BOT.md` + `frontend/BOT.md`, ringkasnya di bagian 4 dokumen ini.

## 13. Risiko & catatan

- **State vs action.** Jangan menganggap FEN cukup untuk menilai langkah; lihat
  bagian 2. `fen_before` + `move_uci` wajib.
- **`move_quality` timpang (99,35% Good)** dan hanya ambang dari `cp_loss` →
  kualitas langkah **tidak** dilatih sebagai model ML, melainkan dihitung engine
  (Stockfish). Jangan menggantinya dengan classifier — baseline "selalu Good"
  saja sudah 99,35%.
- **Analisis langkah butuh biner engine.** `backend/bin/stockfish` tidak
  di-commit; tanpa itu endpoint membalas `503`. Arahkan lewat
  `CHESS_STOCKFISH_PATH`.
- **Probabilitas analisis langkah deterministik** (satu-panas), bukan keyakinan
  statistik — jangan ditampilkan sebagai "confidence model".
- **Data puzzle kecil** (1.176 baris); jangan berharap model besar.
- **Duplikasi FEN antar-game** membuat metrik optimistis; tetap pakai evaluasi
  dedup FEN.
- **`halfmove_clock` selalu `0`**; jangan jadikan fitur yang diandalkan.
- **Kontrak fase beku:** perubahan `/api/classify` harus disepakati dan
  diperbarui di dokumen ini dulu.

## 14. Cara menjalankan (dev)

Backend:

```bash
cd backend
uv sync
uv run uvicorn main:app --reload        # http://localhost:8000
uv run python train.py                   # latih ulang bila perlu
uv run pytest
```

Engine analisis langkah: taruh biner Stockfish di `backend/bin/stockfish`
(atau set `CHESS_STOCKFISH_PATH` ke biner/sistem). Unduhan resmi:
`github.com/official-stockfish/Stockfish/releases/latest` →
`stockfish-linux-x86-64-universal.tar.gz`. Tanpa biner, `/api/analyze-move`
membalas `503` (bagian 4).

Frontend:

```bash
cd frontend
deno install && deno task dev            # http://localhost:5173
# alternatif npm:
# npm install && npm run dev
```

Uji alur fase: buka papan di frontend → klik "Analisis posisi" → label +
confidence muncul.
