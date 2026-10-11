# Backend — Chess Classification API

API klasifikasi **fase permainan catur** (`opening` / `middlegame` / `endgame`)
langsung dari satu string FEN. Kontraknya mengikuti `PLANNING.md` di root repo.

## Struktur project

```
backend/
├── main.py                 # entrypoint ASGI (uvicorn main:app)
├── train.py                # entrypoint training model
├── app/
│   ├── config.py           # path & setting (env CHESS_*)
│   ├── api.py              # skema + classifier + endpoint + app factory
│   └── ml.py               # label + fitur FEN + dataset + training
├── models/                 # artifact model.joblib + metrics.json (gitignored)
├── datasets/               # dataset mentah (gitignored)
└── tests/                  # test_api, test_features, test_pawn_structure, test_model_behavior
```

## Menjalankan

```bash
# dari folder backend/
uv sync                       # pasang dependency

# latih model (default: sampel 200k baris)
uv run python train.py
uv run python train.py --sample 0        # seluruh dataset
uv run python train.py --sample 500000 --trees 300

# jalankan API (butuh model.joblib sudah ada)
uv run uvicorn main:app --reload
```

Bila `models/model.joblib` belum ada, server tetap hidup tetapi
`/api/classify` mengembalikan `503` (tidak crash) supaya frontend bisa
berintegrasi lebih dulu.

## Endpoint

```bash
curl -X POST http://localhost:8000/api/classify \
  -H 'Content-Type: application/json' \
  -d '{"fen":"rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"}'
```

Respons:

```json
{
  "label": "opening",
  "confidence": 1.0,
  "probabilities": { "opening": 1.0, "middlegame": 0.0, "endgame": 0.0 },
  "model_version": "0.1.0"
}
```

- `GET /api/health` → `{"status": "ok"}`
- FEN tidak valid → `422` dengan `{ "detail": "..." }`
- Model belum ada → `503`

## Catatan desain

- **Ekstraksi fitur tunggal.** `app/ml.py` dipakai training maupun
  serving lewat `FenFeatureExtractor` yang tertanam di dalam pipeline sklearn.
  Jadi `model.joblib` tidak mungkin "beda fitur" dengan saat training.
- **Split by `game_id`.** Training memakai `GroupShuffleSplit` agar baris dari
  satu game tidak terpecah ke train dan test (mencegah data leakage).
- **Evaluasi dedup.** Metrik tambahan dihitung pada FEN unik karena posisi
  opening yang sama banyak terulang antar-game.
- **Dataset.** Label diambil apa adanya dari kolom `phase`; tidak ada heuristik
  label buatan sendiri (lihat `app/ml.py`).

## Test

```bash
uv run pytest
```
