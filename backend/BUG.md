# BUG.md — Backend (mode "vs bot")

Laporan bug untuk **agent backend**. Sumber kebenaran fitur = `BOT.md` di folder
ini. Setiap entri punya ID dan kolom **Status** untuk di-*rolling*.

Cara pakai:

- Status: `OPEN` → `IN_PROGRESS` → `FIXED` (atau `WONTFIX` bila sengaja tidak
  dikerjakan, tulis alasannya).
- Setelah memperbaiki, ubah Status dan isi baris **Bukti** (hash commit / output
  test). **Jangan hapus entri** — biar jadi jejak.
- Setelah semua `FIXED`, jalankan `uv run pytest` sampai hijau.

## Ringkasan

| ID | Judul | Severity | Status |
|---|---|---|---|
| BE-001 | `is_game_over()` menolak posisi yang masih punya langkah legal | Sedang | FIXED |
| BE-002 | Tidak ada batas panjang input; body penuh di-buffer, di-log, dan dipantulkan | Tinggi | FIXED |
| BE-003 | FEN valid bisa mematikan Stockfish → 503 + respawn berulang | Tinggi | FIXED |
| BE-004 | `model.joblib` korup/skema beda → crash saat import (bukan 503) | Tinggi | FIXED |
| BE-005 | Label leakage: `phase` diturunkan dari fitur yang dipakai model | Tinggi | FIXED |
| BE-006 | Race spawn melepas proses Stockfish (cold start konkuren) | Sedang | FIXED |
| BE-007 | `OverflowError` dari FEN absurd di `/api/classify` → 500, bukan 422 | Sedang | FIXED |
| BE-008 | Engine crash dibuang tanpa `quit()`/`close()` (proses yatim) | Sedang | FIXED |
| BE-009 | Metrik & test ML lemah; `model_version` tidak dari artifact | Sedang | FIXED |
| BE-010 | Dokumen backend/PLANNING basi (best-move absen, hitungan test salah, BOT.md terhapus) | Sedang | FIXED |
| BE-011 | Sisa temuan backend (rendah) | Rendah | FIXED (2 sub-item WONTFIX) |

---

## BE-001 — `is_game_over()` terlalu luas

- **Lokasi:** `backend/app/api.py:288` (method `MoveAnalyzer.best_move`)
- **Severity:** Sedang
- **Status:** FIXED
- **Bukti:** commit `12c9158` (+ test `2da9328`). `uv run pytest` → 37 lulus.
  Repro `{"fen":"8/8/8/4k3/8/4K3/8/8 b - - 0 1"}` → `200
  {"move_uci":"e5d5","model_version":"Stockfish 19"}`. Catatan: saran `not
  board.legal_moves.any()` di atas **tidak jalan** di python-chess 1.11.2
  (`LegalMoveGenerator` tak punya `.any()`); dipakai `not any(board.legal_moves)`.

### Apa ini

`best_move` membalas `422` saat `board.is_game_over()`. Masalahnya
`is_game_over()` di python-chess bukan hanya "tidak ada langkah legal": ia juga
true untuk **material tidak cukup** (`is_insufficient_material`), **aturan 75
langkah**, dan **repetisi lima kali**. Posisi seperti itu tetap punya langkah
legal, dan engine tetap bisa memilih langkah.

### Reproduksi

```bash
curl -X POST http://localhost:8000/api/best-move \
  -H 'Content-Type: application/json' \
  -d '{"fen":"8/8/8/4k3/8/4K3/8/8 b - - 0 1"}'
```

FEN ini Raja vs Raja: `legal_moves = 5` tetapi `is_game_over() = True`.

### Expected

`200` dengan `move_uci` legal (engine melangkah). Ini juga yang diharapkan
frontend: `gameOver` di FE = "tidak ada langkah legal" (`allLegal(...).length === 0`),
jadi FE menganggap permainan **belum** selesai dan akan memanggil endpoint ini.

### Actual

`422` dengan detail `"tidak ada langkah legal"` — padahal ada 5 langkah legal.
Akibatnya bot gagal melangkah dan giliran mentok di hitam.

### Fix terkecil

Satu baris, di `backend/app/api.py:288`:

```python
# ganti:
if board.is_game_over():
# menjadi:
if not board.legal_moves.any():
```

### Catatan (penting)

Bukan salah agent: pseudo-code di `BOT.md` (dan catatan di `AGENT.md`/`README.md`)
memang menulis `is_game_over()`. Karena itu, saat memperbaiki **sekalian koreksi
spec/dokumentasi**:

- `BOT.md` bagian scope: ganti contoh `if board.is_game_over():` jadi
  `if not board.legal_moves.any():`, serta perbaiki kalimat
  "FEN dengan langkah legal tidak akan kena" (itu keliru).
- `AGENT.md` / `README.md`: ubah "skakmat / remis (tidak ada langkah legal) → 422"
  jadi hanya **skakmat / remis karena tidak ada langkah legal**.

### Test yang harus ditambah

Di `backend/tests/test_best_move.py`:

- FEN material tidak cukup (mis. `8/8/8/4k3/8/4K3/8/8 b - - 0 1`) dengan engine
  **ada** → `200` dan `move_uci` legal.
- Pastikan test skakmat lama (`MATE_FEN`) tetap `422` (langkah legal = 0).

### Di luar scope

Deteksi remis-material/50-langkah yang lebih benar di **frontend** (agar papan
mengumumkan remis) bukan tugas entri ini; kalau nanti dikerjakan, ubah FE dan BE
bersamaan.

---

## BE-002 — Tidak ada batas panjang input; body penuh di-buffer, di-log, dan dipantulkan

- **Lokasi:** `backend/app/api.py:55-61`, `:77-89`, `:106-112` (skema request),
  `:444`, `:446`, `:448`, `:456` (middleware)
- **Severity:** Tinggi
- **Status:** FIXED
- **Bukti:** commit `01847ea` + `6ae7ffc` + `f3d4817`, test `34518ec`.
  `max_length` FEN 200 / `move_uci` 5; badan > 64 KB → `413` sebelum diproses
  (`test_oversize_body_returns_413`); log dipotong 300 karakter dan `\n` di-
  netralkan (`_snippet`) — injeksi baris log tidak mungkin; middleware pass-
  through untuk non-`/api/*` jadi respons di luar API tidak dibuffer.
  **Batas yang diterima:** pydantic masih memantulkan `input` di `detail`, jadi
  ukuran 422 maksimal = ukuran request (terbatas 64 KB). Naikkan handler
  `RequestValidationError` hanya kalau itu mulai jadi masalah.
  Terukur live (uvicorn + repro asli): FEN 2 MB → **`413`, respons 43 byte**
  (sebelumnya `422` respons 2.097.225 byte); badan 100 KB → `413`; keduanya
  **tidak muncul di log sama sekali**; baris log request biasa kini satu baris
  pendek berisi FEN saja.

### Apa ini

Tidak ada `max_length` pada `fen`/`move_uci` dan tidak ada batas ukuran body.
Middleware `await request.body()` menampung seluruh body, lalu mem-buffer seluruh
respons (`:446`) dan mencatat body ke log (`:448`). `422 detail` juga memantulkan
FEN. Akibatnya: DoS memori, injeksi baris log (karakter `\n`), dan input pengguna
bocor ke log.

### Reproduksi

```bash
# FEN ~2 MB (python3, tanpa file)
python3 - <<'PY'
import json, urllib.request, urllib.error
fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1" + " " * 2_000_000
req = urllib.request.Request(
    "http://localhost:8000/api/best-move",
    data=json.dumps({"fen": fen}).encode(),
    headers={"Content-Type": "application/json"})
try:
    print("200", len(urllib.request.urlopen(req).read()))
except urllib.error.HTTPError as e:
    print(e.code, len(e.read()))   # -> 422 dengan body ~2 MB
PY
```

Terukur: request FEN ~2 MB → respons `422` sebesar **2.097.225 byte** dalam 0.06s;
baris log memuat body mentah; body dengan `\n` tercatat sebagai baris log palsu.

### Expected

Field terlalu panjang → `422` (atau `413`) dengan pesan singkat; log tidak
memuat body.

### Fix terkecil

Tambah `max_length` (FEN ≤ ~200, `move_uci` ≤ 5), batasi ukuran body, dan jangan
log/pantulkan input mentah (-potong atau ganti dengan panjangnya saja).

### Verifikasi

- Request melebihi batas → `422`/`413`, log tidak memuat body.
- `uv run pytest` lolos.

---

## BE-003 — FEN yang lolos validasi bisa mematikan Stockfish → 503 + respawn berulang

- **Lokasi:** `backend/app/api.py:283-300`, `_ensure_engine:235-246`
  (root: `backend/app/ml.py:222,232-234`)
- **Severity:** Tinggi
- **Status:** FIXED
- **Bukti:** commit `01847ea`, test `10c7f7c` + `8a87aa9`.
  `_parse_board()` menolak `fullmove_number`/`halfmove_clock` > 9999 sebelum
  engine disentuh. Terukur: `fullmove 99999` (33 karakter) → `422
  "fen: fullmove_number melebihi batas 9999"`, bukan `503`; FEN 308 digit →
  kena `max_length` dulu. Test memakai engine tak-ada, jadi `422` membuktikan
  validasi jalan sebelum spawn (bila lolos hasilnya `503`).
  Live di satu server yang sama: `99999` → `422` (53 byte), lalu FEN normal →
  `200 {"move_uci":"c7c5"}` — proses Stockfish tidak dibunuh.

### Apa ini

FEN dengan `fullmove_number`/`halfmove_clock` raksasa tetap `is_valid() = True`
tapi membuat Stockfish `exit(1)`. Endpoint memetakannya ke `503` dan membuang
engine; tiap request seperti itu membunuh lalu menghidupkan proses ~103 MB.
Digabung race spawn (BE-006) → churn resource.

### Reproduksi (terverifikasi)

```bash
python3 - <<'PY'
import json, urllib.request, urllib.error
fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 " + "9" * 308
for ep in ("best-move", "analyze-move"):
    body = {"fen": fen} if ep == "best-move" else {"fen_before": fen, "move_uci": "e2e4"}
    req = urllib.request.Request(
        f"http://localhost:8000/api/{ep}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    try:
        print(ep, "200", urllib.request.urlopen(req).read())
    except urllib.error.HTTPError as e:
        print(ep, e.code, e.read())   # -> 503 "engine process died unexpectedly (exit code: 1)"
PY
```

best-move dan analyze-move sama-sama `503 "engine process died unexpectedly
(exit code: 1)"`.

### Expected

Input dengan nomor langkah tak masuk akal → `422` (kesalahan input), engine tidak
dibunuh.

### Fix terkecil

Validasi/batasi `fullmove_number`/`halfmove_clock` (atau normalisasi FEN)
sebelum diserahkan ke engine; klasifikasikan error input sebagai `422`.

### Verifikasi

- FEN absurd → `422`, engine tetap hidup (request berikutnya `200`).
- `uv run pytest` lolos.

---

## BE-004 — `model.joblib` korup/skema beda → crash saat import (bukan 503)

- **Lokasi:** `backend/app/api.py:148-160` (`PhaseClassifier.from_path`), `:465`
  (`app = create_app()` di level modul)
- **Severity:** Tinggi
- **Status:** FIXED
- **Bukti:** commit `01847ea`, test `34518ec`.
  `joblib.load` dibungkus `try/except Exception` → `cls(None)` (log error, server
  tetap hidup), plus guard `hasattr(model, "predict_proba")` untuk artifact yang
  ter-load tapi bukan estimator. Ditambah **smoke predict** satu posisi awal saat
  load: menangkap artifact lama yang jumlah fiturnya beda dari kode (mis. akibat
  BE-005) — tanpa itu artifact tetap "ready" lalu tiap request gagal dan sklearn
  melempar `ValueError` yang terbaca sebagai **422 palsu**. Test: file sampah,
  `dict`, dan pipeline dengan jumlah fitur tak cocok → `ready is False`
  (`/api/classify` `503`).

### Apa ini

`from_path` hanya memeriksa `path.exists()`; `joblib.load` tidak dibungkus
try/except. Karena `app = create_app()` dijalankan saat import, artifact yang
corrupt/tak kompatibel membuat proses gagal start. Hanya kasus **file hilang**
yang jatuh anggun ke mode 503. Tidak ada validasi bahwa objek hasil load benar
(fitted `Pipeline` + `FenFeatureExtractor`).

### Expected

Artifact bermasalah → service tetap hidup dengan `/api/classify` `503` (atau
start gagal dengan pesan yang jelas), bukan stack trace saat import.

### Fix terkecil

Bungkus `joblib.load` dengan `try/except Exception` → kembalikan `cls(None)`;
validasi hasil (`predict_proba` ada, extractor sesuai).

### Verifikasi

- Rusak `model.joblib` → proses hidup, `/api/classify` `503`.
- `uv run pytest` lolos.

---

## BE-005 — Label leakage: `phase` diturunkan dari fitur yang dipakai model

- **Lokasi:** `backend/app/ml.py:102-114`, `:222-236`;
  `backend/models/metrics.json:58-99`
- **Severity:** Tinggi
- **Status:** FIXED
- **Bukti:** commit `01847ea` (fitur), `021753f` (experiment), test `52476a6`.
  **Retrain tanpa fitur waktu** (pilihan user): `ply`/`fullmove_number`/
  `halfmove_clock` dibuang dari `FEATURE_NAMES` + `extract_features`, lalu
  `uv run python train.py` (sampel 200k, 200 pohon, seed 42).
  Sebelum → sesudah: akurasi `0.99992` → **`0.9439`**, dedup `0.99992` →
  **`0.9373`** (n=35.575, dari 35.653 baris unseen), baseline `0.5370`.
  Top-5 fitur kini `material_total`, `castling_rights`, `material_white`,
  `piece_count_total`, `material_black` — tidak ada lagi fitur pelabelan.
  Test `test_time_features_absent_because_label_leakage` mengunci hal ini.
  Artifact gitignored, jadi angka ada di mesin lokal + `AGENT.md`/`README.md`/
  `PLANNING.md` yang menampilkan ~0.944.

### Apa ini

Fitur teratas model persis fitur yang dipakai aturan pelabelan fase:
`fullmove_number` (0.182), `ply` (0.151), `material_total` (0.118), dst. Akurasi
0.99992 karena model **memulihkan aturan pelabelan**, bukan belajar catur. Ini
juga melanggar prinsip proyek sendiri di `PLANNING.md:51` ("jangan melatih model
untuk label yang bisa dihitung aturan sederhana").

### Bukti

Importance `model.joblib` sama persis dengan `metrics.json`; `test_model_behavior.py`
mengunci perilaku berbasis `ply`/material; `backend/AGENT.md:213-216` mengakui
keterbatasan ini.

### Expected

Fitur posisi-saja (tanpa `ply`/`fullmove_number`/`halfmove_clock`), atau fase
dirilis sebagai aturan sehingga klaim akurasi tidak menyesatkan.

### Fix terkecil

Buang fitur waktu dari `FEATURE_NAMES`/`extract_features` dan latih ulang; atau
tandai `WONTFIX` + alasan bila memang keputusan produk untuk v1 (lalu jangan
pakai angka akurasi ini untuk klaim kualitas).

### Verifikasi

- Hitung ulang metrik tanpa fitur waktu; bandingkan akurasi.
- `uv run pytest` lolos.

---

## BE-006 — Race spawn melepas proses Stockfish (cold start konkuren)

- **Lokasi:** `backend/app/api.py:235-246` (`_ensure_engine`), dipanggil sebelum
  lock di `:264` dan `:291`
- **Severity:** Sedang
- **Status:** FIXED
- **Bukti:** commit `01847ea`, test `284d52d`.
  `_ensure_engine()` dipanggil **di dalam** `with self._lock` pada `analyze()`
  dan `best_move()`, dan `close()` juga ambil lock. Test stub spawn lambat 0.1s,
  8 thread `best_move` bersamaan → `len(spawns) == 1`.
  **Catatan:** `backend/BOT.md` bagian "Non-goals v1" menulis perbaikan ini
  ditunda sampai konkurensi nyata jadi masalah — entri BUG.md ini (severity
  Sedang, ada probe 7/8 bocor) yang mengalahkan, sesuai instruksi eksekusi.

### Apa ini

`_ensure_engine` tidak memakai lock dan dipanggil **sebelum** `with self._lock`.
Request pertama yang datang bersamaan masing-masing men-`popen_uci`; `self._engine`
hanya menyimpan satu, sisanya tidak pernah `quit()` → proses bocor.

### Bukti

Probe dengan stub `popen_uci` lambat (0.2s), 8 panggilan `_ensure_engine`
konkuren → 8 spawn, 8 engine tertahan, **7 bocor**.

### Fix terkecil

Pindahkan spawn ke dalam lock, atau cek ulang `if self._engine is None:` di dalam
lock sebelum `popen_uci`.

### Verifikasi

- 8 request konkuren pada cold start → hanya 1 proses Stockfish tersisa.
- `uv run pytest` lolos.

---

## BE-007 — `OverflowError` dari FEN absurd di `/api/classify` → 500, bukan 422

- **Lokasi:** handler `backend/app/api.py:333-343` (hanya menangkap `ValueError`
  dan `ModelNotLoadedError`); root `backend/app/ml.py:222,232-234`
- **Severity:** Sedang
- **Status:** FIXED
- **Bukti:** commit `01847ea`, test `34518ec`.
  Dua lapis: (1) akar masalahnya hilang — `float(fullmove/halfmove)` tidak ada
  lagi setelah fitur waktu dibuang (BE-005); (2) `/api/classify` kini memanggil
  `_parse_board()` sebelum predict → `fullmove 99999` maupun 308 digit dua-duanya
  `422`. Tidak ada lagi jalur `OverflowError` ke handler.

### Apa ini

`float(board.fullmove_number)` / `float(board.halfmove_clock)` overflow untuk
nilai 308+ digit. `chess.Board` menerimanya, `extract_features` melempar
`OverflowError`, dan handler tidak menangkapnya → `500`.

### Reproduksi

`POST /api/classify` dengan FEN di mana field terakhir berisi `9` sebanyak 308
digit → `500 Internal Server Error`.

### Expected

`422` (input tidak valid).

### Fix terkecil

Tangkap `(ValueError, OverflowError)` di handler, atau batasi field saat parse.

### Verifikasi

- FEN overflow → `422`.
- `uv run pytest` lolos.

---

## BE-008 — Engine crash dibuang tanpa `quit()`/`close()` (proses yatim)

- **Lokasi:** `backend/app/api.py:273-276`, `:296-299`
- **Severity:** Sedang
- **Status:** FIXED
- **Bukti:** commit `01847ea`, test `284d52d`.
  Helper `_discard_engine()` mengambil referensi, men-`quit()` (error ditelan),
  baru men-set `self._engine = None`; dipakai di cabang `EngineError`
  `analyze()`/`best_move()` dan di `close()`. Test stub `EngineError` →
  `quit_calls == 1`, `_engine is None`, dan request berikutnya spawn proses baru
  (bukan memakai yang mati).

### Apa ini

Saat `EngineError`, `self._engine = None` menghapus satu-satunya referensi tanpa
menutup transport. Bila proses masih hidup, ia menjadi yatim.

### Bukti

Dengan engine stub yang `analyse`-nya melempar: `quit()`/`close()` tidak pernah
dipanggil; `_engine` langsung di-`None`.

### Fix terkecil

`try: self._engine.quit() except Exception: pass` sebelum `self._engine = None`.

### Verifikasi

- Setelah error engine, tidak ada proses `stockfish` tersisa.
- `uv run pytest` lolos.

---

## BE-009 — Metrik & test ML lemah; `model_version` tidak dari artifact

- **Lokasi:** `backend/app/ml.py:439-445` (`dedup_accuracy`), `:460`;
  `backend/app/config.py:21`; `backend/tests/test_model_behavior.py:25-28`
- **Severity:** Sedang
- **Status:** FIXED
- **Bukti:** commit `01847ea` (ml.py), test `9f745c4`.
  - Dedup: baris test yang FEN-nya juga ada di **train** dibuang dulu
    (`unseen_test_size` = 35.653) → baru dedup (`dedup_test_size` = 35.575).
  - Versi: disematkan saat training sebagai `pipeline.model_version_`, dan
    `PhaseClassifier.from_path` membacanya (`getattr(model, "model_version_")`)
    — bukan lagi konstanta env. Test parity dengan `metrics.json`.
  - `tests/test_training.py`: smoke training (fit + `predict_proba` menormalkan
    + `evaluate()`) yang jalan **tanpa artifact**, plus pengawas metrik — test
    gagal bila `accuracy`/`dedup_accuracy` di bawah `baseline_majority`.
  **Sisa batasan:** test akurasi artifact terhadap data test asli belum ada
  (butuh dataset 498 MB di CI); ganti dengan paritas `metrics.json` + guard
  baseline dulu.

### Apa ini

- `dedup_accuracy` hanya membuang FEN duplikat **di dalam test set**; FEN yang
  sama masih ada di train (posisi opening berulang di 49.669 game) → metrik masih
  optimistis.
- Test model asli `skipif not MODEL_PATH.exists()`, sedangkan artifact
  gitignored → di CI semua test model asli **skip**. Tidak ada test akurasi atau
  parity dengan `metrics.json`.
- `model_version` adalah konstanta `CHESS_MODEL_VERSION` (default "0.1.0"), bukan
  dari artifact → versi yang dilayani bisa salah setelah retrain.

### Fix terkecil

Saat mengukur, buang baris test yang FEN-nya ada di train; tambah smoke-test
training kecil + test parity akurasi; simpan versi di artifact dan baca saat load.

### Verifikasi

- `dedup_accuracy` turun ke angka yang jujur.
- Test gagal bila akurasi artifact < baseline.
- `uv run pytest` lolos.

---

## BE-010 — Dokumen backend/PLANNING basi

- **Lokasi:** `PLANNING.md:153`, `:302-303`, `:312`, `:329`;
  `backend/AGENT.md:45-49`, `:225`; `backend/BOT.md` (terhapus)
- **Severity:** Sedang
- **Status:** FIXED
- **Bukti:** commit `d28c2cc`, `a31e184`, `36f8cd4`, `e16dc34`.
  - `PLANNING.md` bagian 4 kini memuat seksi **`POST /api/best-move`** lengkap
    dengan aturan 422 (hanya tanpa langkah legal) + batas input; baris status
    (`:151-156`) dan milestone M3 (`:312`) dihitung ulang → **51 test**.
  - `backend/AGENT.md` struktur test lengkap (7 file, jumlah per file, total 50)
    dan M3; `backend/README.md` daftar file test ikut.
  - **`BOT.md` dipulihkan, bukan dihapus** — setelah file kembali di working
    tree (identik dengan HEAD, tanpa perubahan ter-commit), referensi justru
    dipertahankan: `PLANNING.md:329` dan `BUG.md:3` tetap menunjuk `BOT.md`.
    Kontradiksi `board.legal_moves.any()` vs `not any(board.legal_moves)` sudah
    dikoreksi sejak commit `2177d95`, jadi isinya kini selaras dengan kode.

### Apa ini

- `PLANNING.md` (disebut "sumber kebenaran bersama") tidak mencatat
  `POST /api/best-move` sama sekali; dengan `BOT.md` terhapus, kontrak bot tidak
  ada di dokumen sumber mana pun kecuali `AGENT.md`/`README.md`.
- Hitungan test salah: tertulis **31** (breakdown `test_features` 7, `perilaku
  model` 5) dan **25** hijau; aktual **37** (`test_features` 8,
  `test_model_behavior` 4, dan `test_best_move` 6 tidak tercantum).
  `backend/AGENT.md:45-49` sama salahnya.
- `backend/BOT.md` dihapus di working tree (masih ada di HEAD) padahal dirujuk
  `backend/BUG.md:3,75,79` dan `PLANNING.md:329`; isinya juga kontradiksi
  (`board.legal_moves.any()` vs `not any(board.legal_moves)`).

### Fix terkecil

Tambah seksi kontrak `/api/best-move` di PLANNING.md; perbarui hitungan
(37) dan struktur test di `backend/AGENT.md`; putuskan `BOT.md` (pulihkan +
koreksi, atau selesaikan penghapusan dan alihkan referensi ke `AGENT.md`).

### Verifikasi

- Tidak ada angka test yang salah; tidak ada referensi ke file yang tidak ada.

---

## BE-011 — Sisa temuan backend (rendah)

- **Lokasi:** `backend/app/api.py:24,300,448,456,465`;
  `backend/app/config.py:27`; `backend/app/ml.py:236`;
  `backend/app/experiment.py:102`
- **Severity:** Rendah
- **Status:** FIXED (2 sub-item WONTFIX)
- **Bukti:** commit `01847ea`, `021753f`, `6ae7ffc`, test `34518ec` + `52476a6`.
  Per item:
  - `ENGINE_DEPTH` → `_int_env()`: env non-angka/`0`/negatif jatuh ke default 12,
    proses tidak crash saat import.
  - `result.move is None` → `ModelNotLoadedError` (`503`), bukan `AttributeError`.
  - Middleware: non-`/api/*` **pass-through** (tidak dibuffer, `background`
    tidak dibuang). `/api/*` masih dibuffer karena itu satu-satunya jalan untuk
    mencatat status+badan; dicatat sebagai `shortcut:` di `log_io`.
  - `import numpy as np` dihapus.
  - Log FEN → `_snippet()`: dipotong 300 karakter, `\r`/`\n` dinetralkan.
  - `has_en_passant` → `board.has_legal_en_passant()` (test
    `test_en_passant_only_when_capture_legal`). Aman karena ikut retrain BE-005.
  - `experiment.py:102` → `type=Path`; varian `no_ply`/`no_ply+derived`
    dihapus karena `PLY_FEATURES` sudah tidak ada (ikut fitur dibuang).
  - **WONTFIX — model dimuat saat import:** itu memang cara app memvalidasi
    artifact di awal; lazy-load hanya menunda kegagalan dan menambah state.
  - **WONTFIX — `datasets/puzzles.csv` belum dipakai:** bahan milestone M7 yang
    belum dikerjakan; menghapusnya justru membuang data yang direncanakan.

- `ENGINE_DEPTH` dari env di-parse tanpa validasi/batas → nilai non-angka crash
  saat import; `0`/negatif tak tertangani (`config.py:27`).
- `result.move` bisa `None` → `AttributeError` 500 (`api.py:300`).
- Middleware membangun ulang respons & membuang `background`, serta mem-buffer
  (mematikan streaming) (`api.py:456`).
- `import numpy as np` tak terpakai (`api.py:24`); model di-load saat import
  (`api.py:465`).
- FEN mentah dicatat di level INFO (`api.py:448`) → injeksi baris log.
- `has_en_passant` memakai `board.ep_square is not None` (`ml.py:236`), bukan
  `has_legal_en_passant()`.
- `backend/datasets/puzzles.csv` (1.176 baris) tidak dipakai kode mana pun.
- `backend/app/experiment.py:102` memakai `type=type(DATASET_PATH)` (aneh,
  sebaiknya `type=Path`).

### Verifikasi

- Perbaikan tidak mengubah perilaku normal; `uv run pytest` lolos.
