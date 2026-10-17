# Backend — Chess Classification API

API untuk **klasifikasi fase** permainan catur (`opening` / `middlegame` /
`endgame`) dari satu string FEN, **analisis kualitas langkah**
(`Good`/`Inaccuracy`/`Mistake`/`Blunder`) dari `fen_before` + langkah UCI, dan
**langkah bot** (langkah terbaik engine). Analisis memakai engine Stockfish.
Kontraknya mengikuti `PLANNING.md` di root repo.

## Struktur project

```
backend/
├── main.py                 # entrypoint ASGI (uvicorn main:app)
├── train.py                # entrypoint training model
├── app/
│   ├── config.py           # path & setting (env CHESS_*)
│   ├── api.py              # skema + classifier fase + MoveAnalyzer (engine) + endpoint
│   └── ml.py               # label + fitur FEN + dataset + training
├── bin/                    # biner engine Stockfish (gitignored)
├── models/                 # artifact model.joblib + metrics.json (gitignored)
├── datasets/               # dataset mentah (gitignored)
└── tests/                  # test_api, test_features, test_pawn_structure, test_move_analysis, test_best_move, test_engine_lifecycle, test_model_behavior, test_training
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

Analisis langkah butuh biner engine. Unduh Stockfish resmi
(`github.com/official-stockfish/Stockfish/releases/latest`, mis.
`stockfish-linux-x86-64-universal.tar.gz`) dan taruh binernya di
`bin/stockfish`, atau set `CHESS_STOCKFISH_PATH`. Tanpa biner,
`/api/analyze-move` dan `/api/best-move` membalas `503` (server tetap hidup).

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

### Analisis langkah

```bash
curl -X POST http://localhost:8000/api/analyze-move \
  -H 'Content-Type: application/json' \
  -d '{"fen_before":"3r2k1/8/8/8/3Q4/8/5PP1/6K1 w - - 0 1","move_uci":"f2f3"}'
```

Respons (ratu digantung → blunder):

```json
{
  "quality": "Blunder",
  "cp_loss": 1340.0,
  "probabilities": { "Good": 0.0, "Inaccuracy": 0.0, "Mistake": 0.0, "Blunder": 1.0 },
  "model_version": "Stockfish 19"
}
```

### Langkah bot

```bash
curl -X POST http://localhost:8000/api/best-move \
  -H 'Content-Type: application/json' \
  -d '{"fen":"rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"}'
```

Respons:

```json
{ "move_uci": "e7e5", "model_version": "Stockfish 19" }
```

- `GET /api/health` → `{"status": "ok"}`
- FEN / posisi / langkah tidak valid → `422` dengan `{ "detail": "..." }`
- Skakmat / remis **karena tidak ada langkah legal** → `422`
- Model fase atau engine belum ada → `503`

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
- **Tanpa fitur waktu.** `ply` / `fullmove_number` / `halfmove_clock` tidak
  dipakai: kolom itulah yang aturan pelabelan `phase` pakai, jadi memakainya
  membuat model hanya memulihkan aturan (label leakage). Setelah dibuang,
  akurasi test ~0.944 — angka yang jujur, bukan ~0.9999.
- **Analisis langkah = engine, bukan ML.** Label `move_quality` di dataset
  timpang (99,35% Good) dan hanya ambang `cp_loss`, jadi kualitas dihitung
  Stockfish langsung — bukan dilatih.

## Test

```bash
uv run pytest
```
