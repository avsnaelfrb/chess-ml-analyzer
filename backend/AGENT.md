# Backend Agent Notes

## Ringkasan proyek

Backend ini adalah API untuk dua tugas: **klasifikasi fase** permainan catur dari
satu string FEN, dan **analisis kualitas langkah** dari `fen_before` + langkah UCI
(memakai engine Stockfish). Keduanya mengikuti `PLANNING.md` di root repo.

- Bahasa: Python 3.14 (lihat `.python-version`)
- Framework API: FastAPI + uvicorn
- Model fase: scikit-learn `RandomForestClassifier` di dalam `Pipeline`
- Analisis langkah: engine UCI **Stockfish** (bukan model ML), biner di `bin/`
- Package manager: `uv` (`pyproject.toml` + `uv.lock`)
- Target kelas: `opening` | `middlegame` | `endgame`
- Input model: **FEN saja**
- Dataset: `datasets/moves.csv` (Kaggle, tahap eksperimen, gitignored).
  `datasets/puzzles.csv` (1176 puzzle taktis) tersedia sebagai bahan eksplorasi
  berikutnya.

## Struktur saat ini

```text
backend/
├── AGENT.md                # Catatan konteks dan aturan kerja agent
├── README.md               # Panduan pakai singkat
├── main.py                 # Entrypoint ASGI: `from app.api import app`
├── train.py                # Entrypoint training: `from app.ml import main`
├── pyproject.toml          # Dependency + konfigurasi pytest
├── uv.lock                 # Lockfile dependency
├── .python-version         # 3.14
├── .gitignore              # Abaikan .venv, datasets/, model artifact, cache
├── app/
│   ├── __init__.py
│   ├── config.py           # Path & setting (env CHESS_*)
│   ├── api.py              # Skema + classifier fase + MoveAnalyzer (engine) + endpoint + app factory
│   └── ml.py               # Label + fitur FEN + loader dataset + training (satu modul)
├── bin/
│   └── stockfish           # Biner engine UCI (gitignored, unduh sendiri)
├── models/
│   └── .gitkeep            # model.joblib & metrics.json (gitignored)
├── datasets/
│   └── moves.csv           # Dataset mentah (gitignored)
└── tests/
    ├── __init__.py
    ├── test_api.py             # Test endpoint API + batas input (12 test)
    ├── test_features.py        # Test ekstraksi fitur FEN (7 test)
    ├── test_pawn_structure.py  # Test pola struktur pion (8 test)
    ├── test_move_analysis.py   # Test endpoint analisis langkah / ambang (7 test)
    ├── test_best_move.py       # Test endpoint best-move (7 test)
    ├── test_engine_lifecycle.py # Race spawn & proses yatim, engine stub (3 test)
    ├── test_model_behavior.py  # Karakterisasi model di posisi skakmat (4 test)
    └── test_training.py        # Smoke test training + pengawas metrik (3 test)
```

Total: **51 test**.

Catatan struktur: demi mudah dipahami tanpa lompat file, sisi HTTP terkumpul di
`app/api.py` (skema → classifier → endpoint → app factory) dan sisi ML di
`app/ml.py` (label → fitur → dataset → training).

## Kontrak API (FROZEN mengikuti PLANNING.md)

Base URL dev: `http://localhost:8000`.

| Endpoint | Sukses | Error |
|---|---|---|
| `GET /api/health` | `200 {"status":"ok"}` | — |
| `POST /api/classify` | `200` (lihat bawah) | `422` FEN invalid / body salah, `503` model belum ada |
| `POST /api/analyze-move` | `200` (lihat bawah) | `422` FEN/posisi/langkah tidak valid, `503` engine belum ada |
| `POST /api/best-move` | `200 {"move_uci","model_version"}` | `422` FEN/posisi/tidak ada langkah legal, `503` engine belum ada |

Respons `/api/classify`:

```json
{
  "label": "opening",
  "confidence": 1.0,
  "probabilities": { "opening": 1.0, "middlegame": 0.0, "endgame": 0.0 },
  "model_version": "0.1.0"
}
```

- `label` selalu salah satu dari 3 kelas.
- `confidence` = probabilitas kelas terpilih, rentang `0.0`–`1.0`.
- `probabilities` selalu memuat ketiga kelas (kelas yang hilang diisi `0.0`).
- CORS mengizinkan `http://localhost:5173` & `http://127.0.0.1:5173`
  (bisa diubah lewat env `CHESS_CORS_ORIGINS`).

## Analisis langkah (endpoint kedua, engine Stockfish)

`POST /api/analyze-move` menilai kualitas satu langkah.

```json
// Request
{ "fen_before": "...", "move_uci": "d2d4" }
// Respons 200
{ "quality": "Good", "cp_loss": 8.0,
  "probabilities": { "Good": 1.0, "Inaccuracy": 0.0, "Mistake": 0.0, "Blunder": 0.0 },
  "model_version": "Stockfish 19" }
```

- Alur: `MoveAnalyzer.analyze(fen_before, move_uci)` memvalidasi FEN + legalitas
  langkah, lalu membandingkan skor engine (depth `CHESS_ENGINE_DEPTH`, default 12)
  sebelum vs sesudah langkah — keduanya dari sudut pandang pemain yang melangkah.
  Selisih = `cp_loss`; ambang `50/100/200` memetakannya ke
  `Good/Inaccuracy/Mistake/Blunder` (sama dengan definisi `move_quality` dataset).
- `probabilities` **deterministik satu-panas** (dari engine, bukan classifier).
- Posisi ilegal (mis. pihak yang tidak jalan sedang diskak) ditolak `422`
  **sebelum** ke engine — engine UCI menolak posisi seperti itu dan bisa mati.
- Biner default `bin/stockfish`; ubah lewat env `CHESS_STOCKFISH_PATH`. Engine
  dijalankan **malas** (saat analisis pertama) dan dimatikan saat shutdown.
  Tanpa biner → `503` (server tetap hidup).

## Langkah bot (endpoint ketiga, engine Stockfish)

`POST /api/best-move` mengembalikan langkah terbaik untuk posisi giliran.

```json
// Request
{ "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1" }
// Respons 200
{ "move_uci": "e7e5", "model_version": "Stockfish 19" }
```

- Alur: `MoveAnalyzer.best_move(fen)` memvalidasi FEN + legalitas posisi, lalu
  `engine.play(...)` pada depth `CHESS_ENGINE_DEPTH` (default 12) dan mengembalikan
  `move.uci()`.
- `model_version` sama dengan yang dipakai `/api/analyze-move`.
- Skakmat / remis **karena tidak ada langkah legal** (`not any(board.legal_moves)`;
  `LegalMoveGenerator` tidak punya `.any()`) → `422`; engine tidak ada → `503`.
  Material tidak cukup tetap punya langkah legal, jadi **tidak** ditolak.
- Level bot = `CHESS_ENGINE_DEPTH`; belum ada parameter level per-request.

## Alur prediksi (FEN -> label)

```text
POST /api/classify {fen}
  -> api.classify (cek model siap -> 503 kalau belum)
  -> PhaseClassifier.predict(fen)
  -> model.predict_proba([fen])   # model = Pipeline
       -> FenFeatureExtractor.transform  # FEN -> vektor fitur
       -> RandomForestClassifier.predict_proba
  -> pilih label dengan probabilitas tertinggi
  -> ClassifyResponse {label, confidence, probabilities, model_version}
```

## Dataset

`datasets/moves.csv` — **498 MB**, **3.184.116 baris**, **49.669 game unik**,
`ply` maksimum 299.

- Kolom yang dipakai training: `game_id`, `ply`, `fen_before`, `phase`.
- Kolom lain tersedia (eval, `cp_loss`, `move_quality`, clock, dll.) tapi belum dipakai.
- Distribusi label: `middlegame` ~54%, `opening` ~30%, `endgame` ~15%.
- Label diambil **apa adanya** dari kolom `phase`; tidak ada heuristik label
  buatan sendiri (menghindari sirkularitas).
- `datasets/puzzles.csv` (gitignored) — 1176 puzzle taktis berlabel tema
  (7 kelas: `capture`/`check`/`mate`/`promotion`/dll.) + `difficulty_score`.
  **Belum dipakai produksi**; kandidat eksplorasi. Sifatnya taktis (butuh fitur
  dinamis), uji awal klasifikasi tema ~0.495 ≈ baseline.

## Fitur FEN

Didefinisikan di `app/ml.py` (`FEATURE_NAMES`), antara lain:
material & jumlah bidak per warna, jumlah tiap jenis bidak (pion–raja), total
material/bidak, jumlah major & minor, pola struktur pion per warna (pion dobel,
terisolasi, passed, pulau pion), giliran (`side_to_move_white`), `ply`,
`fullmove_number`, `halfmove_clock`, hak rokade, dan en passant.

## Keputusan desain penting

- **Fitur terpusat.** `FenFeatureExtractor` ditanam sebagai langkah pertama
  `Pipeline`, dan pipeline itulah yang disimpan ke `model.joblib`. Training dan
  serving otomatis memakai ekstraksi fitur yang sama — tidak mungkin drift.
- **Split by `game_id`.** Training memakai `GroupShuffleSplit` supaya baris dari
  satu game tidak terpecah ke train dan test (mencegah data leakage).
- **Evaluasi dedup FEN.** Metrik tambahan dihitung pada FEN unik karena posisi
  opening yang sama banyak terulang antar-game.
- **Graceful tanpa model.** Bila `models/model.joblib` tidak ada, server tetap
  hidup dan `/api/classify` mengembalikan `503`, bukan crash. Ini memudahkan
  integrasi frontend sebelum model siap.
- **Injeksi classifier.** `create_app(classifier=...)` memudahkan test memakai
  model tiruan tanpa menyentuh artifact asli.

## Perintah umum

```bash
# dari folder backend/
uv sync                         # pasang/segarkan dependency

# training (default: sampel 200k baris)
uv run python train.py
uv run python train.py --sample 0           # seluruh dataset
uv run python train.py --sample 500000 --trees 300

# jalankan API
uv run uvicorn main:app --reload

# test
uv run pytest
```

## Hasil training terakhir

Model default (sampel 200k baris, 200 pohon, seed 42) — **tanpa fitur waktu**:

- Split: train 160.153 baris / 38.417 game, test 39.842 baris / 9.605 game.
- Akurasi test: **~0.944**; log_loss ~0.164; baseline mayoritas ~0.537.
- Akurasi dedup FEN (buang test yang juga ada di train, lalu dedup):
  **~0.937** (n = 35.575, dari 35.653 baris unseen).
- Fitur paling penting: `material_total`, `castling_rights`, `material_white`,
  `piece_count_total`, `material_black`.
- Artifact: `models/model.joblib` dan `models/metrics.json` (keduanya gitignored).

Kenapa angkanya jauh lebih rendah dari sebelumnya (~0.9999)? Karena `ply`,
`fullmove_number` dan `halfmove_clock` **dibuang** (BE-005). Ketiga kolom
itulah yang aturan pelabelan `phase` pakai, jadi selama fitur itu ada model
hanya memulihkan aturan — angka 0.9999 tidak pernah mengukur kualitas model.

Catatan penting: `phase` pada dataset memang sangat deterministik dari
material + nomor langkah. Bagian nomor langkah tidak boleh dipakai, jadi
sisanya ada di material — konsisten dengan pembahasan desain dan perlu
dijelaskan bila melaporkan metrik.

## Status milestone

| M | Target | Status |
|---|---|---|
| M0 | FEN generator + endpoint echo | Selesai (digantikan endpoint classify nyata) |
| M1 | Feature + labeling + train + model | Selesai |
| M2 | Integrasi `AnalysisPanel` + proxy + CORS | Selesai (frontend sudah terpasang) |
| M3 | Test + evaluasi model | 51 test hijau (API/batas input, fitur, pola pion, perilaku model, analisis langkah, best-move, siklus engine, training); metrik dilaporkan |
| M4 | Rapikan struktur backend | Selesai: 2 modul inti (`app/api.py` + `app/ml.py`), entrypoint `train.py` |
| M5 | Fitur pola struktur pion | Selesai: 8 fitur + `tests/test_pawn_structure.py` |
| M6 | Analisis langkah (engine Stockfish) | Selesai: `/api/analyze-move` + `tests/test_move_analysis.py` |
| M7 | Model `puzzles.csv` / pengenalan pola taktis | Rencana (belum dikerjakan) |

## Catatan / utang teknis

- `models/` hanya berisi `.gitkeep`; model harus dilatih ulang (`uv run python train.py`).
- `datasets/` dan artifact model **tidak** di-commit karena ukurannya besar.
- `halfmove_clock` dari frontend bisa selalu `0` (lihat PLANNING.md). Kolom itu
  sudah **tidak** dipakai sebagai fitur (label leakage, BE-005), jadi ketidak-
  akuratannya tidak berdampak — tapi jangan dipakai sebagai bahan latih ulang
  tanpa memperbaiki sisi frontend.
- `fastapi.testclient` memunculkan `StarletteDeprecationWarning` soal `httpx`;
  belum berdampak, pantau saat upgrade.
- Test `test_features.py` sudah mencakup fitur; `tests/test_pawn_structure.py`
  mencakup pola pion. Loader dataset (streaming/sampling) di `app/ml.py` belum
  punya test khusus.
- `app/experiment.py` (utility non-produksi) untuk membandingkan set fitur &
  algoritma: `uv run python -m app.experiment`. Hasilnya: membuang fitur
  giliran / mengganti algoritma tidak mengubah label posisi OOD — akar masalah
  di definisi label.
- **Temuan: label `phase` vs skakmat.** Model mengklasifikasi fase berdasarkan
  nomor langkah/material; skakmat bisa terjadi di fase mana pun, sehingga
  posisi skakmat tetap dapat berlabel `middlegame` (per definisi dataset).
  `tests/test_model_behavior.py` mengunci perilaku ini. Keputusan "game over"
  adalah produk/UX, belum ditentukan.
- **Batasan OOD model.** Posisi dengan material rendah dan nomor langkah kecil
  (tidak ada di dataset) diekstrapolasi ke default `middlegame`. Fitur yang
  lebih tahan OOD adalah kandidat revisi di masa depan.

## Aturan kerja agent

- Gunakan `uv` untuk semua operasi dependency; jangan pakai `pip` langsung.
- Jaga struktur ringkas: endpoint + classifier di `app/api.py`, fitur/label/
  data/training di `app/ml.py`.
- Jangan duplikasi logika ekstraksi fitur di luar `app/ml.py`.
- Jangan commit `datasets/`, `models/*.joblib`, `models/metrics.json`, atau `bin/`
  (biner engine).
- Setelah perubahan kode, jalankan `uv run pytest`.
- Perubahan kontrak API harus diselaraskan dengan `PLANNING.md` di root repo.
