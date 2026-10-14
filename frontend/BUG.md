# BUG.md — Frontend (mode "vs bot")

Laporan bug untuk **agent frontend**. Sumber kebenaran fitur = `BOT.md` di folder
ini. Setiap entri punya ID dan kolom **Status** untuk di-*rolling*.

Cara pakai:

- Status: `OPEN` → `IN_PROGRESS` → `FIXED` (atau `WONTFIX` bila sengaja tidak
  dikerjakan, tulis alasannya).
- Setelah memperbaiki, ubah Status dan isi baris **Bukti** (hash commit / hasil
  `deno task build`). **Jangan hapus entri.**
- Setelah semua `FIXED`, jalankan `deno task build` sampai lolos, lalu ikuti
  checklist verifikasi manual di `BOT.md` bagian "Verifikasi manual".

## Ringkasan

| ID | Judul | Severity | Status |
|---|---|---|---|
| FE-001 | Tombol "Permainan baru" tidak membatalkan request bot | Sedang | FIXED |
| FE-002 | Manusia terkunci setelah bot gagal (503) | Sedang | FIXED |
| FE-003 | Pesan error lama muncul lagi setelah toggle bot off→on | Rendah | FIXED |
| FE-004 | Peta huruf promosi terduplikasi (invers) | Rendah | FIXED |

---

## FE-001 — Tombol "Permainan baru" tidak membatalkan request bot

- **Lokasi:** `frontend/src/App.vue:96` (binding `@reset="reset"`) dan
  `frontend/src/composables/useBot.ts:10`
- **Severity:** Sedang
- **Status:** FIXED
- **Bukti:** `cancel()` ditambah di `useBot` (`869d91d`), `onReset()` memanggil
  `bot.cancel()` sebelum `reset()` + binding `@reset="onReset"` (`8f377e5`), uji
  regresi "membatalkan request yang telat…" (`fe34312`). `deno task test` 15/15
  lolos, `deno task build` lolos.

### Apa ini

`useBot` hanya membatalkan request saat komponen unmount atau saat `enabled`
jadi `false`. Tombol "Permainan baru" memanggil `reset()` langsung, tanpa
menyentuh request yang sedang terbang.

### Reproduksi

1. Toggle "vs bot", main langkah putih (mis. `1.e4`).
2. Saat indikator "Bot berpikir…" muncul, klik **"Permainan baru"**.
3. Tunggu 1–2 detik.

### Expected

Papan kembali ke posisi awal tanpa pesan apa pun. Respons bot yang batal tidak
dipakai.

### Actual

Papan memang tereset, tetapi respons bot yang telat memanggil `playUci` pada
posisi baru → tidak ada langkah yang cocok → muncul pesan palsu
"Engine memberi langkah yang tidak valid."

### Fix terkecil

Tambah fungsi `cancel()` di `useBot` lalu panggil sebelum `reset()`:

```ts
// useBot.ts
function cancel() {
  controller?.abort()
  controller = null
  thinking.value = false
  error.value = null
}
// return { enabled, thinking, error, cancel }
```

```ts
// App.vue
function onReset() {
  bot.cancel()
  reset()
}
// template: @reset="onReset"
```

`toggleBot` sudah aman karena set `enabled=false` memicu abort, tapi tetap
disarankan panggil `bot.cancel()` di sana juga agar `error` ikut bersih.

### Verifikasi

- Ulangi reproduksi → tidak ada pesan error, papan tetap posisi awal.
- `deno task build` lolos.

---

## FE-002 — Manusia terkunci setelah bot gagal (503)

- **Lokasi:** `frontend/src/App.vue:43-46` (fungsi `onSelect`)
- **Severity:** Sedang
- **Status:** FIXED
- **Bukti:** Guard `onSelect` ditambah `!bot.error.value` (`8f377e5`), sesuai fix
  terkecil yang disarankan. Setelah error, klik tidak lagi diblokir dan
  permainan bisa lanjut; saat engine pulih, bot otomatis mencoba lagi di giliran
  hitam berikutnya. `deno task build` lolos.

### Apa ini

`BOT.md` menulis: saat bot gagal, "Manusia tetap bisa main manual". Tetapi
`onSelect` memblokir semua klik selama `turn === 'black'`. Kalau engine tidak
tersedia, langkah putih sudah jalan, giliran tetap hitam, dan pemain tidak bisa
melangkah lagi.

### Reproduksi

1. Matikan backend (atau pakai biner Stockfish yang tidak ada → `503`).
2. Toggle "vs bot", main `1.e4`.
3. Muncul pesan error. Klik bidak putih mana pun.

### Expected

Pemain masih bisa melanjutkan permainan (paling tidak tidak "terkunci").

### Actual

Semua klik diabaikan. Satu-satunya jalan keluar: Undo, atau toggle ke 2 pemain
(yang mereset permainan).

### Fix terkecil

Jangan blokir saat bot sedang error:

```ts
function onSelect(square: Square) {
  if (bot.enabled.value && !bot.error.value && (turn.value === 'black' || bot.thinking.value)) return
  choose(square)
}
```

Atau alternatif: saat `error` muncul, set `bot.enabled.value = false`.

### Verifikasi

- Reproduksi → setelah error, klik bidak putih tetap bisa melangkah.
- Kasus normal (engine hidup) tetap tidak bisa melangkah saat giliran bot.
- `deno task build` lolos.

---

## FE-003 — Pesan error lama muncul lagi setelah toggle bot off→on

- **Lokasi:** `frontend/src/composables/useBot.ts:36-46` (blok `watch`)
- **Severity:** Rendah
- **Status:** FIXED
- **Bukti:** Blok watch `!enabled` kini memanggil `cancel()` yang mengosongkan
  `error` (`869d91d`); `toggleBot` juga memanggil `bot.cancel()` (`8f377e5`), uji
  "cancel() membersihkan error dan thinking" (`fe34312`). `deno task test` 15/15
  lolos, `deno task build` lolos.

### Apa ini

Saat `enabled` jadi `false`, watch tidak mengosongkan `error`. Pesan error lama
tetap tersimpan dan muncul lagi begitu bot dinyalakan lagi (sebelum ada request
baru).

### Reproduksi

1. Toggle "vs bot" tanpa engine → muncul pesan error.
2. Toggle ke "2 pemain", lalu toggle lagi ke "vs bot".

### Expected

Pesan error hilang saat bot dimatikan/dinyalakan; hanya muncul dari request yang
benar-benar gagal.

### Actual

Pesan error lama muncul lagi.

### Fix terkecil

Kosongkan `error` di blok watch saat `!enabled`, atau cukup pakai `cancel()` dari
FE-001 di `toggleBot` (sama-sama mengosongkan `error`).

### Verifikasi

- Reproduksi → pesan error tidak muncul lagi setelah toggle ulang.
- `deno task build` lolos.

---

## FE-004 — Peta huruf promosi terduplikasi (invers)

- **Lokasi:** `frontend/src/composables/useChess.ts` — `playUci` (peta `q/r/b/n → Kind`)
  dan `makeMove` (peta `Kind → q/r/b/n`)
- **Severity:** Rendah
- **Status:** FIXED
- **Bukti:** Dua peta digabung jadi helper `promotionLetter` /
  `kindFromPromotionLetter` di `notation.ts` (`ef5b101`) lalu dipakai di
  `playUci` dan `makeMove` (`d9c0c4e`). Uji underpromotion `b2b1n` tetap lolos
  (`deno task test` 15/15), `deno task build` lolos.

### Apa ini

Dua peta berlawanan untuk hal yang sama disimpan di tempat berbeda. Bukan bug
fungsional saat ini, tapi rawan: ubah satu, lupa yang lain.

### Fix terkecil

Satukan jadi satu helper kecil (mis. `promotionLetter(kind)` dan
`kindFromPromotionLetter(letter)` di `useChess.ts` atau `notation.ts`), lalu pakai
di kedua tempat. **Hanya** lakukan kalau tidak membuat diff membengkak; kalau
ragu, biarkan (`WONTFIX` + alasan) — ini bukan blocker rilis.

### Verifikasi

- Underpromotion bot (`b7b8n`) tetap jalan.
- `deno task build` lolos.
