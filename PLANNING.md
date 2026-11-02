# PLANNING — Chess Classification Model

Dokumen ini adalah **sumber kebenaran bersama** untuk seluruh repo (frontend +
backend + model). Tujuannya menyelaraskan scope, kontrak, dan status antar
bagian. Setiap agent/anggota tim membaca ini lebih dulu sebelum bekerja.

> **Status terakhir diperbarui:** November 2026.
> Ringkasan cepat: kontrak `/api/classify` (klasifikasi **fase**) sudah **beku**
> dan terintegrasi di frontend — jangan diubah. Tugas kedua, **analisis langkah**
> (`POST /api/analyze-move`, input `fen_before` + langkah UCI), **sudah jalan**:
> backend memakai engine UCI **Stockfish** untuk menghitung centipawn loss lalu
> memetakannya ke `Good/Inaccuracy/Mistake/Blunder`. Frontend sudah mengirim
> `fen_before` + `move_uci` dan menampilkan hasilnya.
>
> Tugas ketiga, **pola serangan hitam** (`POST /api/classify-tactic`, input FEN
> giliran putih), **sudah jalan end-to-end**: backend model ML multi-label +
> panel frontend yang hanya aktif saat giliran putih. Kontrak di bagian 4b,
> UI di bagian 9c.
>
> Legenda status: 🔒 **Beku** (jangan diubah tanpa kesepakatan) · ✅ **Selesai** ·
> 🔜 **Rencana** (belum dikerjakan).

## 1. Tujuan project

Fokus utama repo adalah **model klasifikasi**, bukan game engine catur. Game di
frontend hanyalah sarana menghasilkan **input** bagi model.

Tugas yang disepakati:

1. **Fase permainan** (sudah jalan, beku) — input **FEN** → `opening` /
   `middlegame` / `endgame`.
2. **Analisis langkah** (sudah jalan) — input **`fen_before` + langkah (UCI)** →
   kualitas langkah (Good/Inaccuracy/Mistake/Blunder) lewat engine Stockfish.
   Endpoint **baru**, tidak menggantikan yang lama.
3. **Pola serangan hitam** (sudah jalan) — input **FEN
   giliran putih** → daftar motif taktik hitam (multi-label) beserta
   probabilitasnya. Endpoint **baru** `/api/classify-tactic`, tidak
   menggantikan `/api/classify`.

Flow saat ini (fase):

```
[Papan frontend] ──FEN──▶ POST /api/classify ──▶ [Backend + model] ──▶ {label, confidence} ──▶ ditampilkan
```

Flow analisis langkah (sudah jalan):

```
[Papan frontend] ──{fen_before, move_uci}──▶ POST /api/analyze-move ──▶ [Backend + model] ──▶ {quality, ...} ──▶ ditampilkan
```

Flow pola serangan hitam (sudah jalan):

```
[Papan frontend, giliran putih] ──FEN──▶ POST /api/classify-tactic ──▶ [Backend + model multi-label] ──▶ {labels[]} ──▶ ditampilkan
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
- **Pola serangan hitam adalah multi-label.** Satu posisi bisa punya `fork` +
  `sacrifice` + `mate` sekaligus; jangan dipaksa jadi satu kelas.
- **Input model taktis = FEN giliran putih.** Di mode vs bot, user putih dan bot
  hitam. Dataset Lichess dipilih dari FEN `w` (solver = hitam) supaya input
  training sama dengan yang dikirim frontend. Jangan mengubah FEN (mis.
  menerapkan langkah lawan) sebelum memanggil endpoint.
- **Model taktis memprediksi potensi, bukan kepastian.** FEN hanya posisi;
  motif baru muncul setelah langkah berikutnya. Karena itu hasilnya berupa
  probabilitas per motif, bukan satu vonis.

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

## 4b. Kontrak API — POLA SERANGAN HITAM ✅ sudah jalan (backend + frontend)

Model ML **multi-label** terpisah dari model fase. Endpoint tidak menggantikan
`/api/classify`.

### `POST /api/classify-tactic`

Request (JSON) — sama seperti `/api/classify`:

```json
{ "fen": "6k1/5p1p/4p3/4q3/3nN3/2Q3P1/PP3P1P/6K1 w - - 2 37" }
```

- Kirim FEN **posisi saat ini, giliran putih** (`w` di field kedua). Itu input
  yang dipakai saat training.
- Jangan menerapkan langkah apa pun dulu; jangan mengirim FEN setelah langkah.

Response `200`:

```json
{
  "labels": [
    { "label": "fork", "probability": 0.61 },
    { "label": "hangingPiece", "probability": 0.55 },
    { "label": "discoveredAttack", "probability": 0.48 }
  ],
  "model_version": "0.1.0"
}
```

Aturan:

- `labels` berisi **semua 23 motif**, diurutkan dari probabilitas tertinggi.
  Frontend boleh mengambil top-N atau memfilter sendiri.
- `probability` tiap motif **independen**, `0.0`–`1.0`; **tidak** dijumlahkan
  menjadi 1 (ini multi-label, bukan softmax).
- Nama motif yang mungkin muncul:
  `advancedPawn`, `attackingF2F7`, `attraction`, `backRankMate`,
  `capturingDefender`, `clearance`, `deflection`, `discoveredAttack`,
  `discoveredCheck`, `doubleCheck`, `exposedKing`, `fork`, `hangingPiece`,
  `interference`, `kingsideAttack`, `mate`, `pin`, `promotion`, `queensideAttack`,
  `sacrifice`, `skewer`, `trappedPiece`, `xRayAttack`.
- FEN tidak valid / angka langkah ekstrem → `422` `{ "detail": "..." }`.
- Artifact model taktis belum ada / korup / versi fitur beda → `503`
  `{ "detail": "..." }`. Endpoint fase tetap hidup.
- `model_version` diambil dari artifact, bukan konstanta env.
- Model hanya dilatih pada FEN giliran putih. FEN giliran hitam tetap diterima
  (tidak `422`), tetapi hasilnya di luar distribusi training — frontend
  sebaiknya hanya memanggil saat `turn === 'white'`.

**Kualitas model saat ini (jujur, jangan ditampilkan sebagai kebenaran):**

Baseline 200k baris (160k train / 40k test, split per `GameId`) **tanpa**
`class_weight="balanced"`: macro-AP **0,274**, macro-F1@0,5 **0,153**,
micro-F1 **0,384**, subset accuracy **0,194**. Motif yang relatif jalan:
`mate` (AP 0,741), `backRankMate` (0,638), `advancedPawn` (0,624),
`kingsideAttack` (0,537), `queensideAttack` (0,518). Motif langka masih lemah,
mis. `interference` (0,010), `clearance` (0,038), `capturingDefender` (0,046),
`xRayAttack` (0,055).

Macro-F1 turun dibanding versi `balanced` karena ambang tetap 0,5 tidak cocok
untuk kelas timpang; gunakan **AP** untuk membandingkan kualitas ranking.
Probabilitas masih membawa prior dataset (`mate` ~44% dari data), jadi **jangan
tampilkan top-1 sebagai kesimpulan**. Tampilkan beberapa label dengan bar
probabilitas, beri label "eksperimental", dan terapkan ambang tampilan.

## 5. Status terkini

| Area | Status | Catatan |
|---|---|---|
| Game catur frontend | ✅ Selesai | Vue 3 + TS + Vite, pemain lokal, aturan langkah lengkap |
| Integrasi fase frontend | ✅ Selesai | `src/api/classify.ts`, `AnalysisPanel`, proxy `/api` |
| Endpoint fase (`/api/health`, `/api/classify`) | 🔒 Beku | FastAPI, sesuai bagian 3 |
| Struktur backend | ✅ Dirapikan | `app/api.py` + `app/ml.py` + modul taktis terpisah; entrypoint `train.py`, `train_black_attack.py` |
| Model fase | ✅ Latih ulang | Tanpa fitur waktu (BE-005); akurasi test ~0.944, baseline ~0.537 |
| Dataset | ✅ Tersedia | `moves.csv` (3,18 jt baris) + `puzzles.csv` (1.176 baris) |
| Test backend | ✅ Hijau | 78 test (API+batas input 12, fitur fase 7, pola pion 8, perilaku model 4, analisis langkah 7, best-move 7, siklus engine 3, training fase 3, filter taktis 10, fitur taktis 10, training taktis 3, API taktis 4) |
| Katalog label (tiga dataset) | ✅ Terdokumentasi | Bagian 7 |
| Analisis langkah (`/api/analyze-move`) | ✅ Selesai (engine) | Stockfish; kontrak di bagian 4 |
| Langkah bot (`/api/best-move`) | ✅ Selesai (engine) | Mode vs bot; kontrak di bagian 4 |
| Dataset taktis Lichess | ✅ Terpasang | `Lichess/chess-puzzles` via HuggingFace `datasets`; detail bagian 6c |
| Model pola serangan hitam | ✅ Baseline | Multi-label, 23 motif, 46 fitur, macro-AP 0,274; metrik bagian 4b/8b |
| Endpoint taktis (`/api/classify-tactic`) | ✅ Selesai (backend) | Kontrak di bagian 4b |
| Integrasi frontend pola serangan hitam | ✅ Selesai | Panel di `AnalysisPanel`, hanya giliran putih; bagian 9c |

**Implikasi untuk frontend:** integrasi fase tidak berubah. Frontend sudah
mengirim **`fen_before` + `move_uci`** dan menampilkan hasil analisis langkah
(bagian 9b) — end-to-end sudah jalan. Pola serangan hitam sudah dipanggil dari
panel analisis saat giliran putih (bagian 9c).

## 6. Dataset

Dataset lokal ada di `backend/datasets/` (gitignored, ukuran besar). Dataset
taktis Lichess diunduh ke cache HuggingFace, bukan ke folder ini.

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

### `Lichess/chess-puzzles` — dataset taktis (HuggingFace) ✅

Dimuat lewat `datasets.load_dataset("Lichess/chess-puzzles")`, **bukan** disimpan
di repo. Cache HF ~1,1 GB; total 6.157.341 baris.

- Kolom kunci: `FEN`, `Moves`, `Themes`, `GameId`, `Popularity`, `Rating`,
  `NbPlays`.
- **`FEN` = satu ply sebelum posisi puzzle.** `Moves[0]` adalah langkah lawan
  (blunder) yang memulai taktik. Karena itu **jangan** menerapkan `Moves[0]`;
  FEN mentah itulah yang dikirim frontend.
- Filter yang dipakai training:
  - `FEN.split()[1] == "w"` → solver (yang memainkan taktik) adalah **hitam**.
    Ini yang membuat motifnya "serangan hitam" dan inputnya cocok dengan FEN
    giliran putih dari frontend.
  - `Popularity >= 50` → buang puzzle yang jarang dimainkan.
  - Sampling `--sample N` untuk eksperimen cepat (default 200k).
- Split **per `GameId`** (bukan per baris) supaya posisi dari game yang sama
  tidak muncul di train dan test sekaligus.
- Detail loader: `backend/app/tactical.py`.

## 7. Katalog label yang mungkin (hasil analisis tiga dataset)

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
terbesar. Rencana lanjutan tema taktis kemudian dikerjakan dengan dataset
Lichess (bagian 7c/8b), bukan `puzzles.csv` yang terlalu kecil.

### Dari `Lichess/chess-puzzles` — motif serangan hitam (23 label)

Sumber: kolom `Themes` (dipisah spasi). Hanya tema **serangan/taktik** yang
diambil; tema generik dibuang (fase, panjang puzzle, keunggulan, sumber,
`defensiveMove`, `quietMove`, `zugzwang`). Satu posisi bisa punya beberapa
motif → **multi-label**, jangan dipaksa satu kelas.

| Label | Arti singkat |
|---|---|
| `fork` | satu bidak menyerang dua target sekaligus |
| `pin` | bidak putih terpaku ke bidak/raja di belakangnya |
| `skewer` | bidak depan dipaksa bergerak, membuka bidak belakang |
| `discoveredAttack` | membuka serangan bidak lain dengan menggerakkan bidak |
| `xRayAttack` | serangan menembus bidak sendiri |
| `deflection` | memaksa pembela meninggalkan tugasnya |
| `attraction` | menarik bidak putih ke petak yang merugikan |
| `clearance` | mengosongkan petak/garis untuk bidak lain |
| `interference` | menyumbat garis pertahanan putih |
| `sacrifice` | mengorbankan material untuk motif |
| `discoveredCheck` | skak yang terbuka karena bidak lain bergerak |
| `doubleCheck` | skak ganda |
| `kingsideAttack` | serangan ke sayap raja |
| `queensideAttack` | serangan ke sayap ratu |
| `attackingF2F7` | menyerang petak lemah f2/f7 |
| `backRankMate` | skak mat baris belakang |
| `exposedKing` | raja putih terbuka |
| `hangingPiece` | bidak putih tak terjaga |
| `trappedPiece` | bidak putih terkurung |
| `capturingDefender` | menangkap pembela lalu menyerang |
| `advancedPawn` | pion maju berbahaya |
| `promotion` | promosi pion |
| `mate` | skak mat |

Daftar final + urutan ada di `ATTACK_CLASSES` (`backend/app/tactical.py`) dan
ikut disimpan di artifact. Endpoint mengembalikan **semua 23** label.

## 8. Pendekatan model

### 8a. Fase — yang sudah jalan

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

### 8b. Pola serangan hitam — baseline ✅

Semua fitur diukur dari **sudut pandang hitam**, karena motif yang dipelajari
adalah motif hitam pada posisi giliran putih.

- **Fitur (46, dinamis dari FEN)** di `backend/app/tactical_features.py`:
  material, posisi raja putih (file/rank/castled, shield pion, file terbuka,
  bidak berat hitam di dekat raja), tekanan hitam (jumlah/nilai bidak putih
  yang diserang, hanging, fork targets, defender yang bisa ditangkap), pin
  putih, geometri skewer/discovered/discovered-check, pion hitam
  maju/passed/promosi, celah baris belakang, dan proksi mobilitas hitam
  (simulasi giliran hitam: jumlah langkah, skak, tangkapan, nilai tangkapan).
  Papan asli tidak diubah; hanya salinan untuk hitung mobilitas.
- **Model:** `Pipeline` = `TacticalFeatureExtractor` → `StandardScaler` →
  `OneVsRestClassifier(LogisticRegression(solver="liblinear"))`. Multi-label
  One-vs-Rest: tiap motif punya probabilitas sendiri (tidak di-softmax).
  Sengaja **tanpa** `class_weight="balanced"`: bobot seimbang membuat motif
  langka sangat overconfident pada posisi di luar training (posisi awal bisa
  memberi `trappedPiece` ~0,96).
- **Split & evaluasi:** split per `GameId`; metrik **per-kelas average
  precision (AP)** + macro/micro-F1. Accuracy tidak dipakai karena `mate`
  ~44% sementara `interference`/`xRayAttack` ~0,5%.
- **Artifact:** `backend/models/black_attack.joblib` berisi
  `{pipeline, classes, feature_names, model_version}` (gitignored). Metrik
  per kelas: `backend/models/black_attack_metrics.json` (gitignored).
- **Baseline (200k baris, 160k train / 40k test):** macro-AP **0,274**,
  macro-F1@0,5 **0,153**, micro-F1 **0,384**, subset accuracy **0,194**.

Motif dengan AP terbaik (test 40k):

| Motif | Support | AP |
|---|---:|---:|
| `mate` | 17.721 | 0,741 |
| `backRankMate` | 2.185 | 0,638 |
| `advancedPawn` | 3.500 | 0,624 |
| `kingsideAttack` | 4.783 | 0,537 |
| `queensideAttack` | 989 | 0,518 |
| `promotion` | 1.376 | 0,458 |
| `attackingF2F7` | 268 | 0,420 |

Motif dengan AP terburuk (support kecil):

| Motif | Support | AP |
|---|---:|---:|
| `interference` | 207 | 0,010 |
| `clearance` | 758 | 0,038 |
| `capturingDefender` | 421 | 0,046 |
| `xRayAttack` | 200 | 0,055 |
| `doubleCheck` | 258 | 0,081 |
| `deflection` | 2.355 | 0,106 |

Batasan yang harus diingat:

- Probabilitas **belum terkalibrasi**. Tanpa `class_weight`, nilainya jauh
  lebih masuk akal (posisi awal: `mate` ~0,60, label lain < 0,26), tetapi
  masih membawa prior dataset karena training hanya berisi posisi puzzle
  (`mate` ~44%). Jangan jadikan top-1 sebagai keputusan.
- Macro-F1@0,5 rendah untuk motif langka. Itu efek ambang, bukan ranking;
  AP tetap naik dibanding versi `balanced`. Ambang per motif belum dituning.
- Model memprediksi **potensi** dari posisi statis, bukan memastikan langkah
  berikutnya. Motif nyata baru muncul setelah hitam melangkah.
- Artefak tidak di-commit. Clone baru harus menjalankan training dulu, kalau
  tidak endpoint membalas `503`.

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

### 9c. Pola serangan hitam ✅ (backend + frontend selesai)

Target: tombol/panel "Pola serangan hitam" yang memanggil
`POST /api/classify-tactic` (kontrak bagian 4b) dan menampilkan beberapa motif
teratas dengan bar probabilitas.

Yang perlu ditambahkan:

1. **Client** di `src/api/classify.ts`, mengikuti pola `classifyFen` /
   `analyzeMove` (termasuk `AbortSignal` dan `ClassifyError`):

   ```ts
   export type TacticLabel = { label: string; probability: number }
   export type ClassifyTacticResponse = {
     labels: TacticLabel[]
     model_version: string
   }

   export async function classifyTactic(
     fen: string,
     signal?: AbortSignal,
   ): Promise<ClassifyTacticResponse> {
     // POST `${API_BASE}/api/classify-tactic` body { fen }
   }
   ```

   Tidak perlu ubah `vite.config.ts`; proxy `/api` sudah ada.

2. **Panggil hanya saat `turn === 'white'`.** FEN yang dikirim adalah FEN
   **posisi saat ini** (`fen` computed yang sudah dipakai `classifyFen`), bukan
   `fen_before`. Jangan menerapkan langkah apa pun lebih dulu. Bila
   `turn === 'black'`, sembunyikan tombol (atau tampilkan "analisis hanya untuk
   giliran putih").
3. **UI** di `src/components/AnalysisPanel.vue`, mengikuti blok fase:
   loading state, disable tombol saat request jalan, `current.abort()` sebelum
   request baru, dan tangani error (`422` FEN invalid, `503` model belum
   dilatih, status `0` jaringan).
4. **Tampilan hasil:** filter `probability >= 0.5` (atau ambang yang
   disepakati), lalu ambil top-N (mis. 5) dan urutkan dari yang terbesar. Bila
   tidak ada yang lolos, tampilkan "tidak ada motif dominan" — jangan paksa
   menampilkan 5 label. Karena probabilitas masih membawa prior dataset:
   - jangan tampilkan top-1 sebagai "kesimpulan";
   - beri label "eksperimental" / "perkiraan";
   - jangan menjumlahkan probabilitas menjadi 100% (tiap motif independen).

Nama motif yang mungkin muncul ada di bagian 4b/7c. Tidak perlu memetakan ke
Bahasa Indonesia; boleh tambahkan label tampilan di frontend bila mau.

## 10. Tanggung jawab backend

Struktur aktual (detail ada di `backend/AGENT.md`):

```
backend/
├── main.py                 # entrypoint ASGI (uvicorn main:app)
├── train.py                # entrypoint training model fase
├── train_black_attack.py   # entrypoint training model taktis
├── prepare_black_attack.py # cek/siapkan dataset taktis
├── app/
│   ├── config.py           # path & setting (env CHESS_*)
│   ├── api.py              # skema + classifier + endpoint + app factory
│   ├── ml.py               # label + fitur FEN + dataset + training fase
│   ├── tactical.py         # dataset Lichess, label motif, split per GameId
│   ├── tactical_features.py# 46 fitur taktis dari FEN
│   └── tactical_training.py# pipeline + evaluasi multi-label
├── models/                 # *.joblib + *metrics.json (gitignored)
├── datasets/               # dataset mentah (gitignored)
└── tests/
```

- Framework: FastAPI + uvicorn + pydantic. Manajemen paket: `uv`.
- Struktur sengaja **ringkas:** `app/api.py` = skema → classifier → endpoint →
  app factory; `app/ml.py` = label → fitur → dataset → training fase.
- Analisis langkah & langkah bot sudah ditambahkan tanpa menyentuh alur fase
  yang beku: `app/api.py` menampung `MoveAnalyzer` (engine Stockfish) terpisah
  dari `PhaseClassifier` (model ML).
- Model taktis **terpisah total** dari fase: modul `app/tactical*.py`, artifact
  sendiri, `TacticalClassifier` sendiri, endpoint `/api/classify-tactic`.
  `/api/classify` dan `app/ml.py` tidak disentuh.
- `datasets>=5.1.0` ada di `pyproject.toml`; dataset taktis diunduh ke cache HF
  saat training pertama, bukan disimpan di repo.

## 11. Milestone

| M | Target | Bukti selesai | Status |
|---|---|---|---|
| M0 | FEN generator + endpoint echo | Frontend kirim FEN, backend balas FEN sama | ✅ (digantikan classify nyata) |
| M1 | Feature + labeling + train + model fase | `/api/classify` balas salah satu dari 3 label | ✅ |
| M2 | Integrasi `AnalysisPanel` + proxy + CORS | Klik tombol → label muncul | ✅ |
| M3 | Test + evaluasi model | test hijau; metrik ada | ✅ |
| M4 | Rapikan struktur backend | modul inti terpisah per tugas (`api`, `ml`, `tactical*`) | ✅ |
| M5 | Fitur pola struktur pion | 8 fitur + 8 test | ✅ |
| M6 | Katalog label dari dataset | Bagian 7 dokumen ini | ✅ |
| M7 | Endpoint analisis langkah (engine Stockfish) | `{fen_before, move_uci}` → kualitas langkah | ✅ |
| M8 | Model tema taktis (`puzzles.csv`) | Klasifikasi tema dengan fitur dinamis | ✅ digantikan M9 (data `puzzles.csv` terlalu kecil) |
| M9 | Model pola serangan hitam (Lichess) | 23 motif multi-label, endpoint `/api/classify-tactic`, macro-AP 0,274 | ✅ backend |
| M10 | UI pola serangan hitam | Panel memanggil `/api/classify-tactic` saat giliran putih | ✅ frontend |

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
- **Data puzzle kecil** (1.176 baris); jangan berharap model besar. Karena itu
  model taktis memakai `Lichess/chess-puzzles`, bukan `puzzles.csv`.
- **Model taktis hanya melihat FEN, bukan langkah.** Ia memperkirakan *potensi*
  motif hitam; jangan mengklaim langkah pasti. FEN giliran hitam tetap diterima
  tetapi di luar distribusi training.
- **Probabilitas taktis belum terkalibrasi.** Versi tanpa `class_weight`
  sudah jauh lebih masuk akal, tetapi masih membawa prior dataset (`mate` ~44%)
  dan ambang 0,5 belum dituning per motif. Tampilkan sebagai perkiraan
  eksperimental; jangan pakai top-1 sebagai vonis dan jangan dijumlahkan
  menjadi 100%.
- **Motif langka sulit dipelajari** (`interference`, `clearance`,
  `capturingDefender`, `xRayAttack` AP < 0,06). Bila ditampilkan, beri ambang
  tinggi atau sembunyikan.
- **Artifact taktis gitignored.** Clone baru harus
  `uv run python train_black_attack.py` sebelum endpoint berguna; tanpa itu
  `/api/classify-tactic` membalas `503` (endpoint fase tetap hidup).
- **Dataset taktis diunduh saat training pertama** (~1,1 GB cache HF). Butuh
  koneksi; `HF_TOKEN` opsional untuk rate limit lebih tinggi.
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
uv run python train.py                   # latih ulang model fase
uv run python train_black_attack.py --sample 200000   # model taktis (cepat)
uv run python train_black_attack.py --sample 0        # model taktis, semua data
uv run pytest
```

`train_black_attack.py` mengunduh `Lichess/chess-puzzles` ke cache HF pada
run pertama. Hasil: `models/black_attack.joblib` +
`models/black_attack_metrics.json` (keduanya gitignored). Env terkait:
`CHESS_BLACK_ATTACK_MODEL`, `CHESS_BLACK_ATTACK_METRICS`,
`CHESS_BLACK_ATTACK_MODEL_VERSION`.

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

Uji alur taktis: pastikan giliran putih → klik "Pola
serangan hitam" → beberapa motif + persen muncul. Kembalikan ke giliran hitam →
tombol tidak tersedia. Jika backend tanpa artifact, harus muncul pesan error
`503` yang ramah, bukan crash.
