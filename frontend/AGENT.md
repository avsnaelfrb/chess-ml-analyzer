# Frontend Agent Notes

## Ringkasan proyek

Frontend ini adalah web game catur sederhana untuk dua pemain lokal.

- Framework: Vue 3
- Bahasa: TypeScript
- Build tool: Vite
- Package manager: Deno 2 (`deno.lock` menjadi lockfile utama)
- Mode permainan: dua pemain lokal pada satu perangkat
- Fitur permainan: gerakan legal, giliran, skak, skakmat, remis, rokade, en passant, promosi pion, undo, reset, dan riwayat langkah
- Gaya visual: modern minimalis, tema gelap dengan aksen hijau limau

## Struktur saat ini

```text
frontend/
├── AGENT.md                 # Catatan konteks dan aturan kerja agent
├── deno.json                # Konfigurasi task Deno (dev, build, preview)
├── deno.lock                # Lockfile dependency yang dikelola Deno
├── package.json              # Metadata dependency dan script proyek
├── vite.config.ts            # Konfigurasi Vite + plugin Vue
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
    ├── style.css             # Tema, layout, papan, responsivitas, dan modal promosi
    ├── types/
    │   └── chess.ts          # Tipe domain: Color, Piece, Move, Castling, Snapshot
    ├── lib/chess/
    │   ├── constants.ts      # Daftar file papan dan karakter ikon bidak
    │   ├── board.ts          # Pembuatan, kloning, dan castling awal
    │   ├── notation.ts       # Nama kotak, nama warna, dan notasi langkah
    │   └── engine.ts         # Aturan catur murni: pseudoMoves, applyMove, skak, langkah legal
    ├── composables/
    │   └── useChess.ts       # State reaktif permainan + aksi (choose, makeMove, undo, reset)
    └── components/
        ├── ChessBoard.vue    # Grid papan, bidak, sorotan, dan label
        ├── PlayerCard.vue    # Kartu pemain dan indikator giliran
        ├── StatusPanel.vue   # Status permainan (skak/skakmat/remis)
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

## Catatan implementasi

- State permainan dan aksi berada di `src/composables/useChess.ts`; `App.vue` hanya merangkai komponen. Aturan catur murni (tanpa Vue) berada di `src/lib/chess/engine.ts` sehingga bisa diuji terpisah. Belum ada backend atau penyimpanan permainan.
- Bidak menggunakan karakter Unicode, sehingga tidak ada dependency icon tambahan.
- Font visual dimuat dari Google Fonts melalui `src/style.css`; bila aplikasi perlu sepenuhnya offline, sediakan font lokal atau fallback sistem.
- Perubahan UI sebaiknya tetap menjaga layout responsif untuk desktop dan layar kecil.
- Setelah perubahan pada logika permainan, jalankan `npm run build` untuk memvalidasi Vue template dan TypeScript.
