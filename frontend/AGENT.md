# Frontend Agent Notes

## Ringkasan proyek

Frontend ini adalah web game catur sederhana untuk dua pemain lokal yang menjadi
**sumber input FEN** untuk model klasifikasi fase permainan (lihat `PLANNING.md`).

- Framework: Vue 3
- Bahasa: TypeScript
- Build tool: Vite
- Package manager: Deno 2 (`deno.lock` menjadi lockfile utama)
- Mode permainan: dua pemain lokal pada satu perangkat
- Fitur permainan: gerakan legal, giliran, skak, skakmat, remis, rokade, en passant, promosi pion, undo, reset, dan riwayat langkah
- Integrasi backend: kirim FEN ke `POST /api/classify` dan tampilkan label fase + confidence
- Gaya visual: modern minimalis, tema gelap dengan aksen hijau limau

## Struktur saat ini

```text
frontend/
├── AGENT.md                 # Catatan konteks dan aturan kerja agent
├── deno.json                # Konfigurasi task Deno (dev, build, preview)
├── deno.lock                # Lockfile dependency yang dikelola Deno
├── package.json              # Metadata dependency dan script proyek
├── vite.config.ts            # Konfigurasi Vite + plugin Vue + proxy /api
├── tsconfig.json             # Konfigurasi TypeScript utama
├── tsconfig.app.json         # Konfigurasi TypeScript aplikasi
├── tsconfig.node.json        # Konfigurasi TypeScript untuk konfigurasi Node/Vite
├── index.html                # Entry HTML Vite
├── public/
│   ├── favicon.svg
│   └── icons.svg
└── src/
    ├── main.ts               # Bootstrap Vue dan import stylesheet global
    ├── App.vue               # Shell layout; merangkai komponen dan composable
    ├── style.css             # Tema, layout, papan, panel analisis, responsivitas, dan modal promosi
    ├── api/
    │   └── classify.ts       # Client fetch ke POST /api/classify + tipe respons
    ├── types/
    │   └── chess.ts          # Tipe domain: Color, Piece, Move, Castling, Snapshot
    ├── lib/chess/
    │   ├── constants.ts      # Daftar file papan dan karakter ikon bidak
    │   ├── board.ts          # Pembuatan, kloning, dan castling awal
    │   ├── notation.ts       # Nama kotak, nama warna, dan notasi langkah
    │   ├── fen.ts            # Bangun FEN dari state papan + INITIAL_FEN
    │   └── engine.ts         # Aturan catur murni: pseudoMoves, applyMove, skak, langkah legal
    ├── composables/
    │   └── useChess.ts       # State reaktif permainan + aksi + computed fen
    └── components/
        ├── ChessBoard.vue    # Grid papan, bidak, sorotan, dan label
        ├── PlayerCard.vue    # Kartu pemain dan indikator giliran
        ├── StatusPanel.vue   # Status permainan (skak/skakmat/remis)
        ├── AnalysisPanel.vue # Tombol analisis fase + hasil dari API klasifikasi
        ├── MoveHistory.vue   # Riwayat langkah
        ├── GameControls.vue  # Tombol undo dan reset
        └── PromotionModal.vue # Modal pemilihan bidak promosi
```

`dist/` dan `node_modules/` dapat muncul setelah dependency atau build dijalankan; keduanya merupakan output/generated files, bukan sumber utama aplikasi.

## Aturan kerja dependency

- Gunakan Deno sebagai package manager untuk dependency frontend.
- Jangan memakai `npm install`, `npm ci`, atau mengganti lockfile dengan `package-lock.json`.
- Pertahankan `deno.lock` tetap sinkron setelah perubahan dependency.
- Dependency saat ini memakai package npm melalui kompatibilitas `npm:` Deno: Vue, Vite, TypeScript, `vue-tsc`, dan plugin Vue.

## Perintah umum

Install dependency:

```bash
deno install
```

Development server:

```bash
deno task dev
```

Build produksi dan type-check:

```bash
deno task build
```

Pratinjau hasil build:

```bash
deno task preview
```

Task di atas didefinisikan di `deno.json` dan memetakan script yang sama di `package.json` (`npm run dev`, `npm run build`, `npm run preview`). `vite` dijalankan langsung sebagai task Deno, sedangkan `vue-tsc` dijalankan lewat `node` karena patch SFC-nya tidak kompatibel dengan runtime Deno.

## Integrasi API klasifikasi

- Kontrak beku ada di `PLANNING.md` bagian 3: `POST /api/classify` menerima `{ "fen": "..." }` dan mengembalikan `{ label, confidence, probabilities, model_version }`; error berbentuk `{ "detail": "..." }` (FEN invalid `422`, model belum ada `503`).
- Base URL default memakai path relatif `/api`; saat dev, `vite.config.ts` mem-proxy `/api` ke `http://localhost:8000` sehingga tidak perlu CORS.
- Bila ingin menembak backend tanpa proxy, set environment `VITE_API_BASE` (mis. `http://localhost:8000`).
- FEN dibangun di `src/lib/chess/fen.ts` dan diekspos sebagai `fen` computed dari `useChess`; `halfmove_clock` selalu `0` dan `fullmove_number = floor(ply / 2) + 1`.
- `AnalysisPanel.vue` menerima prop `fen`, memanggil `classifyFen`, dan menangani state idle / loading / sukses / error. Hasil direset ketika posisi berubah.

## Perubahan backend yang perlu diketahui

Per Oktober 2026, struktur internal backend dirapikan **(tanpa mengubah kontrak
API)**. Frontend **tidak perlu penyesuaian apa pun** karena endpoint, bentuk
respons, CORS, dan proxy Vite tetap sama.

- Sisi HTTP backend digabung ke `backend/app/api.py` (skema + classifier +
  endpoint + app factory).
- Sisi ML digabung ke `backend/app/ml.py` (label + fitur FEN + dataset + training).
- Entrypoint training kini `uv run python train.py` dari folder `backend/`
  (sebelumnya `python -m app.ml.train`).
- Model ditambah fitur pola struktur pion, tetapi **input/response API tidak
  berubah**: `{ "fen": "..." }` → `{ label, confidence, probabilities, model_version }`.
- Endpoint & error tetap: `GET /api/health`, `POST /api/classify`
  (`422` FEN invalid, `503` model belum ada).

Dampak ke frontend: **nihil**. Selama backend jalan
(`uv run uvicorn main:app --reload`), proxy `/api` tetap berfungsi seperti semula.

## Catatan implementasi

- State permainan dan aksi berada di `src/composables/useChess.ts`; `App.vue` hanya merangkai komponen. Aturan catur murni (tanpa Vue) berada di `src/lib/chess/engine.ts` sehingga bisa diuji terpisah.
- Pembuatan FEN murni berada di `src/lib/chess/fen.ts` (tanpa Vue) agar mudah diuji; `useChess` hanya menyambungkannya ke state reaktif.
- Bidak menggunakan karakter Unicode, sehingga tidak ada dependency icon tambahan.
- Font visual dimuat dari Google Fonts melalui `src/style.css`; bila aplikasi perlu sepenuhnya offline, sediakan font lokal atau fallback sistem.
- Perubahan UI sebaiknya tetap menjaga layout responsif untuk desktop dan layar kecil.
- Setelah perubahan pada logika permainan atau integrasi, jalankan `deno task build` untuk memvalidasi Vue template dan TypeScript.
