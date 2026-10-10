# Backend — Chess Classification API

API klasifikasi **fase permainan catur** (`opening` / `middlegame` / `endgame`)
langsung dari satu string FEN. Kontraknya mengikuti `PLANNING.md` di root repo.

## Struktur project

```
backend/
├── main.py                 # entrypoint ASGI (uvicorn main:app)
├── app/
│   ├── config.py           # path & setting (env CHESS_*)
│   ├── schemas.py          # kontrak request/response (pydantic)
│   ├── classifier.py       # muat model + predict
│   ├── routes.py           # endpoint /api/health, /api/classify
│   ├── server.py           # app factory + CORS
│   └── ml/
│       ├── labeling.py     # definisi label fase
│       ├── features.py     # FEN -> fitur (dipakai training & serving)
│       ├── dataset.py      # loader CSV streaming
│       └── train.py        # script training
├── models/                 # artifact model.joblib + metrics.json (gitignored)
├── datasets/               # dataset mentah (gitignored)
└── tests/test_api.py
```

## Menjalankan

```bash
# dari folder backend/
uv sync                       # pasang dependency

# latih model (default: sampel 200k baris)
uv run python -m app.ml.train
uv run python -m app.ml.train --sample 0        # seluruh dataset
uv run python -m app.ml.train --sample 500000 --trees 300

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

- **Ekstraksi fitur tunggal.** `app/ml/features.py` dipakai training maupun
  serving lewat `FenFeatureExtractor` yang tertanam di dalam pipeline sklearn.
  Jadi `model.joblib` tidak mungkin "beda fitur" dengan saat training.
- **Split by `game_id`.** Training memakai `GroupShuffleSplit` agar baris dari
  satu game tidak terpecah ke train dan test (mencegah data leakage).
- **Evaluasi dedup.** Metrik tambahan dihitung pada FEN unik karena posisi
  opening yang sama banyak terulang antar-game.
- **Dataset.** Label diambil apa adanya dari kolom `phase`; tidak ada heuristik
  label buatan sendiri (lihat `app/ml/labeling.py`).

## Test

```bash
uv run pytest
```
