# Backend Agent Notes

## Ringkasan proyek

Backend ini adalah API + model **klasifikasi fase permainan catur** langsung dari
satu string FEN. Kontraknya mengikuti `PLANNING.md` di root repo.

- Bahasa: Python 3.14 (lihat `.python-version`)
- Framework API: FastAPI + uvicorn
- Model: scikit-learn `RandomForestClassifier` di dalam `Pipeline`
- Package manager: `uv` (`pyproject.toml` + `uv.lock`)
- Target kelas: `opening` | `middlegame` | `endgame`
- Input model: **FEN saja**
- Dataset: `datasets/moves.csv` (Kaggle, tahap eksperimen, gitignored)

## Struktur saat ini

```text
backend/
├── AGENT.md                # Catatan konteks dan aturan kerja agent
├── README.md               # Panduan pakai singkat
├── main.py                 # Entrypoint ASGI: `from app.server import app`
├── pyproject.toml          # Dependency + konfigurasi pytest
├── uv.lock                 # Lockfile dependency
├── .python-version         # 3.14
├── .gitignore              # Abaikan .venv, datasets/, model artifact, cache
├── app/
│   ├── __init__.py
│   ├── config.py           # Path & setting (env CHESS_*)
│   ├── schemas.py          # Kontrak request/response (pydantic)
│   ├── classifier.py       # PhaseClassifier: muat model.joblib + predict
│   ├── routes.py           # Endpoint /api/health, /api/classify
│   ├── server.py           # App factory + CORS
│   └── ml/
│       ├── __init__.py
│       ├── labeling.py     # Definisi label fase + normalisasi
│       ├── features.py     # FEN -> fitur (satu-satunya sumber fitur)
│       ├── dataset.py      # Loader CSV streaming + sampling
│       └── train.py        # Script training + evaluasi + simpan model
├── models/
│   └── .gitkeep            # model.joblib & metrics.json (gitignored)
├── datasets/
│   └── moves.csv           # Dataset mentah (gitignored)
└── tests/
    ├── __init__.py
    ├── test_api.py             # Test endpoint API (5 test)
    ├── test_features.py        # Test ekstraksi fitur FEN (7 test)
    └── test_model_behavior.py  # Karakterisasi model di posisi skakmat (5 test)
```

## Kontrak API (FROZEN mengikuti PLANNING.md)

Base URL dev: `http://localhost:8000`.

| Endpoint | Sukses | Error |
|---|---|---|
| `GET /api/health` | `200 {"status":"ok"}` | — |
| `POST /api/classify` | `200` (lihat bawah) | `422` FEN invalid / body salah, `503` model belum ada |

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

## Alur prediksi (FEN -> label)

```text
POST /api/classify {fen}
  -> routes.classify (cek model siap -> 503 kalau belum)
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

## Fitur FEN

Didefinisikan di `app/ml/features.py` (`FEATURE_NAMES`), antara lain:
material & jumlah bidak per warna, jumlah tiap jenis bidak (pion–raja), total
material/bidak, jumlah major & minor, giliran (`side_to_move_white`), `ply`,
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
uv run python -m app.ml.train
uv run python -m app.ml.train --sample 0           # seluruh dataset
uv run python -m app.ml.train --sample 500000 --trees 300

# jalankan API
uv run uvicorn main:app --reload

# test
uv run pytest
```

## Hasil training terakhir

Model default (sampel 200k baris, 200 pohon, seed 42):

- Split: train 160.153 baris / 38.417 game, test 39.842 baris / 9.605 game.
- Akurasi test: **~0.9999**; log_loss ~0.0023; baseline mayoritas ~0.537.
- Akurasi dedup FEN: ~0.9999.
- Fitur paling penting: `fullmove_number`, `ply`, `material_total`,
  `material_black`, `piece_count_total`.
- Artifact: `models/model.joblib` dan `models/metrics.json` (keduanya gitignored).

Catatan penting: akurasi yang sangat tinggi ini **bukan** ukuran "kecerdasan"
model, melainkan indikasi bahwa definisi `phase` pada dataset sangat
deterministik (dominan oleh nomor langkah + material). Ini konsisten dengan
pembahasan desain dan perlu dijelaskan bila melaporkan metrik.

## Status milestone

| M | Target | Status |
|---|---|---|
| M0 | FEN generator + endpoint echo | Selesai (digantikan endpoint classify nyata) |
| M1 | Feature + labeling + train + model | Selesai |
| M2 | Integrasi `AnalysisPanel` + proxy + CORS | Selesai (frontend sudah terpasang) |
| M3 | Test + evaluasi model | Test API + fitur + perilaku model hijau; metrik dilaporkan |

## Catatan / utang teknis

- `models/` hanya berisi `.gitkeep`; model harus dilatih ulang (`uv run python -m app.ml.train`).
- `datasets/` dan artifact model **tidak** di-commit karena ukurannya besar.
- `halfmove_clock` dari frontend bisa selalu `0` (lihat PLANNING.md); fitur ini
  ada tapi tidak boleh diandalkan.
- `fastapi.testclient` memunculkan `StarletteDeprecationWarning` soal `httpx`;
  belum berdampak, pantau saat upgrade.
- Test `test_features.py` sudah mencakup fitur; loader `dataset.py` belum punya
  test khusus.
- **Temuan: label `phase` vs skakmat.** Model mengklasifikasi fase berdasarkan
  nomor langkah/material; skakmat bisa terjadi di fase mana pun, sehingga
  posisi skakmat tetap dapat berlabel `middlegame` (per definisi dataset).
  `tests/test_model_behavior.py` mengunci perilaku ini. Keputusan "game over"
  adalah produk/UX, belum ditentukan.
- **Batasan OOD model.** Posisi material rendah dengan `fullmove_number` kecil
  (tidak ada di dataset) diekstrapolasi ke default `middlegame`. Fitur yang
  lebih tahan OOD adalah kandidat revisi di masa depan.

## Aturan kerja agent

- Gunakan `uv` untuk semua operasi dependency; jangan pakai `pip` langsung.
- Jaga struktur modular: endpoint di `routes.py`, model di `classifier.py`,
  fitur/label/data/training di `app/ml/`.
- Jangan duplikasi logika ekstraksi fitur di luar `app/ml/features.py`.
- Jangan commit `datasets/`, `models/*.joblib`, atau `models/metrics.json`.
- Setelah perubahan kode, jalankan `uv run pytest`.
- Perubahan kontrak API harus diselaraskan dengan `PLANNING.md` di root repo.
