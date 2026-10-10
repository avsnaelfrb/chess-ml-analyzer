# PLANNING — Chess Classification Model

Dokumen ini menyelaraskan scope antara **frontend** dan **backend**. 

## 1. Tujuan project

Sesuai nama repo, fokus utama adalah **model klasifikasi**, bukan game engine
catur. Game di frontend hanyalah sarana untuk menghasilkan **input posisi**.

Flow MVP:

```
[Papan di frontend] ──FEN──▶ POST /api/classify ──▶ [Backend + model] ──▶ {label, confidence} ──▶ ditampilkan
```

## 2. Keputusan scope

- **Target klasifikasi:** fase permainan (game phase).
- **Label:** `opening` | `middlegame` | `endgame` (huruf kecil, enum).
- **Input model:** **FEN saja** (satu string). Frontend hanya mengirim FEN.
- **Dataset:** disiapkan user, diubah menjadi dataset **FEN** (sumber rencana:
  Kaggle). Definisi label fase ditentukan user (belum final).
- **Pembagian kerja:** frontend (dokumen ini) menyiapkan pembuatan + pengiriman
  FEN serta menampilkan hasil; backend (agent lain) menyiapkan API + model.

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
- `Content-Type: application/json`.

## 4. Tanggung jawab frontend

Perubahan yang direncanakan:

| File | Fungsi |
|---|---|
| `src/lib/chess/fen.ts` | Bangun FEN dari state papan |
| `src/api/classify.ts` | Client `fetch` ke `POST /api/classify` |
| `src/components/AnalysisPanel.vue` | Tombol "Analisis posisi" + tampilkan label & confidence |
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

## 5. Tanggung jawab backend (agent lain)

Struktur usulan:

```
backend/
├── main.py              # FastAPI app + CORS + endpoint
├── schemas.py           # ClassifyRequest / ClassifyResponse
├── classifier.py        # load model.joblib + predict
├── ml/
│   ├── dataset.py       # load dataset FEN
│   ├── labeling.py      # definisi label fase (milik user)
│   ├── features.py      # FEN → vektor fitur
│   └── train.py         # train + evaluasi + simpan model
├── data/                # raw & processed (gitignored)
├── models/              # model.joblib (gitignored)
└── tests/test_api.py
```

- Framework: FastAPI + uvicorn + pydantic.
- Model: scikit-learn (`RandomForestClassifier`, `random_state=42`).
- Artifact: `models/model.joblib`, dimuat saat startup.
- CORS: izinkan origin dev frontend (`http://localhost:5173`) bila tidak lewat
  proxy; proxy Vite juga disiapkan agar tetap aman.
- Dependency: `fastapi`, `uvicorn[standard]`, `pydantic`, `scikit-learn`,
  `python-chess`, `pytest`.
- Catatan Python: `.python-version` saat ini `3.14`; verifikasi dukungan wheel
  scikit-learn, turunkan ke 3.12/3.13 bila perlu.

## 6. Milestone

| M | Target | Bukti selesai |
|---|---|---|
| M0 | FEN generator + endpoint echo | Frontend kirim FEN, backend balas FEN sama |
| M1 | Feature + labeling + train + model | `/api/classify` balas salah satu dari 3 label |
| M2 | Integrasi `AnalysisPanel` + proxy + CORS | Klik tombol → label muncul |
| M3 | Test + evaluasi model (akurasi, confusion matrix) | Test hijau, metrik dilaporkan |

## 7. Non-goals (MVP)

- Autentikasi / user accounts.
- Penyimpanan riwayat analisis.
- Proses async / queue.
- Klasifikasi per langkah (butuh >1 FEN).
- Training dari dalam server API.

## 8. Definisi "selesai" sisi frontend

- `fen.ts` menghasilkan FEN valid; FEN awal lolos test.
- Tombol mengirim `{ fen }` ke `/api/classify` via proxy tanpa error CORS.
- Menampilkan label + confidence, plus state loading dan error.
- Bisa diuji dengan backend mock/stub.

## 9. Risiko

- **Data & label belum final** → `labeling.py` adalah bagian yang menunggu user.
- **Sirkularitas label** bila memakai heuristik sendiri; dicatat sebagai utang
  teknis sampai label nyata tersedia.
- **`halfmove_clock` tidak dikirim akurat** (selalu 0). Tidak masalah untuk fase,
  tapi backend tidak boleh bergantung padanya.
- **Python 3.14 vs scikit-learn** (lihat bagian 5).
