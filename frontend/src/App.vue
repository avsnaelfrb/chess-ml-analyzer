<script setup lang="ts">
import { computed, ref } from 'vue'

type Color = 'white' | 'black'
type Kind = 'king' | 'queen' | 'rook' | 'bishop' | 'knight' | 'pawn'
type Piece = { color: Color; kind: Kind }
type Square = { r: number; c: number }
type Move = Square & { from: Square; promotion?: Kind; castle?: 'king' | 'queen'; enPassant?: boolean }
type Snapshot = { board: (Piece | null)[][]; turn: Color; castling: Castling; enPassant: Square | null; notation: string }
type Castling = { whiteKing: boolean; whiteQueen: boolean; blackKing: boolean; blackQueen: boolean }

const icons: Record<Color, Record<Kind, string>> = {
  white: { king: '♔', queen: '♕', rook: '♖', bishop: '♗', knight: '♘', pawn: '♙' },
  black: { king: '♚', queen: '♛', rook: '♜', bishop: '♝', knight: '♞', pawn: '♟' },
}
const files = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
const opposite = (color: Color): Color => (color === 'white' ? 'black' : 'white')
const cloneBoard = (board: (Piece | null)[][]) => board.map(row => row.map(piece => (piece ? { ...piece } : null)))
const initialCastling = (): Castling => ({ whiteKing: true, whiteQueen: true, blackKing: true, blackQueen: true })

function createBoard() {
  const board: (Piece | null)[][] = Array.from({ length: 8 }, () => Array(8).fill(null))
  const back: Kind[] = ['rook', 'knight', 'bishop', 'queen', 'king', 'bishop', 'knight', 'rook']
  for (let c = 0; c < 8; c++) {
    board[0][c] = { color: 'black', kind: back[c] }
    board[1][c] = { color: 'black', kind: 'pawn' }
    board[6][c] = { color: 'white', kind: 'pawn' }
    board[7][c] = { color: 'white', kind: back[c] }
  }
  return board
}

const board = ref(createBoard())
const turn = ref<Color>('white')
const selected = ref<Square | null>(null)
const castling = ref<Castling>(initialCastling())
const enPassant = ref<Square | null>(null)
const history = ref<Snapshot[]>([])
const moves = ref<string[]>([])
const promotion = ref<{ move: Move } | null>(null)

const colorName = (color: Color) => (color === 'white' ? 'Putih' : 'Hitam')
const inBounds = (r: number, c: number) => r >= 0 && r < 8 && c >= 0 && c < 8
const squareName = (s: Square) => `${files[s.c]}${8 - s.r}`

function pseudoMoves(state: (Piece | null)[][], from: Square, includeCastle = true): Move[] {
  const piece = state[from.r][from.c]
  if (!piece) return []
  const result: Move[] = []

  const add = (r: number, c: number, extra: Partial<Move> = {}) => {
    if (!inBounds(r, c)) return false
    const target = state[r][c]
    if (!target) {
      result.push({ from, r, c, ...extra })
    } else if (target.color !== piece.color && target.kind !== 'king') {
      result.push({ from, r, c, ...extra })
    }
    return !target
  }

  if (piece.kind === 'pawn') {
    const dir = piece.color === 'white' ? -1 : 1
    const start = piece.color === 'white' ? 6 : 1
    if (inBounds(from.r + dir, from.c) && !state[from.r + dir][from.c]) {
      result.push({ from, r: from.r + dir, c: from.c })
      if (from.r === start && !state[from.r + 2 * dir][from.c]) {
        result.push({ from, r: from.r + 2 * dir, c: from.c })
      }
    }
    for (const dc of [-1, 1]) {
      const r = from.r + dir
      const c = from.c + dc
      if (!inBounds(r, c)) continue
      if (state[r][c] && state[r][c]!.color !== piece.color && state[r][c]!.kind !== 'king') {
        result.push({ from, r, c })
      }
      if (enPassant.value && enPassant.value.r === r && enPassant.value.c === c) {
        result.push({ from, r, c, enPassant: true })
      }
    }
  } else if (piece.kind === 'knight') {
    for (const [dr, dc] of [
      [-2, -1],
      [-2, 1],
      [-1, -2],
      [-1, 2],
      [1, -2],
      [1, 2],
      [2, -1],
      [2, 1],
    ]) {
      add(from.r + dr, from.c + dc)
    }
  } else if (piece.kind === 'king') {
    for (let dr = -1; dr <= 1; dr++) {
      for (let dc = -1; dc <= 1; dc++) {
        if (dr || dc) add(from.r + dr, from.c + dc)
      }
    }
    if (includeCastle && !inCheck(state, piece.color)) {
      const row = piece.color === 'white' ? 7 : 0
      const kingSide = piece.color === 'white' ? castling.value.whiteKing : castling.value.blackKing
      const queenSide = piece.color === 'white' ? castling.value.whiteQueen : castling.value.blackQueen
      if (
        kingSide &&
        !state[row][5] &&
        !state[row][6] &&
        !inCheckAfter(state, piece.color, { from: { r: row, c: 4 }, r: row, c: 5 }) &&
        !inCheckAfter(state, piece.color, { from: { r: row, c: 4 }, r: row, c: 6 })
      ) {
        result.push({ from, r: row, c: 6, castle: 'king' })
      }
      if (
        queenSide &&
        !state[row][1] &&
        !state[row][2] &&
        !state[row][3] &&
        !inCheckAfter(state, piece.color, { from: { r: row, c: 4 }, r: row, c: 3 }) &&
        !inCheckAfter(state, piece.color, { from: { r: row, c: 4 }, r: row, c: 2 })
      ) {
        result.push({ from, r: row, c: 2, castle: 'queen' })
      }
    }
  } else {
    const dirs =
      piece.kind === 'bishop'
        ? [
            [-1, -1],
            [-1, 1],
            [1, -1],
            [1, 1],
          ]
        : piece.kind === 'rook'
          ? [
              [-1, 0],
              [1, 0],
              [0, -1],
              [0, 1],
            ]
          : [
              [-1, -1],
              [-1, 1],
              [1, -1],
              [1, 1],
              [-1, 0],
              [1, 0],
              [0, -1],
              [0, 1],
            ]
    for (const [dr, dc] of dirs) {
      let r = from.r + dr
      let c = from.c + dc
      while (add(r, c)) {
        r += dr
        c += dc
      }
    }
  }

  return result.map(move => ({
    ...move,
    promotion: piece.kind === 'pawn' && (move.r === 0 || move.r === 7) ? 'queen' : undefined,
  }))
}

function applyMove(state: (Piece | null)[][], move: Move) {
  const next = cloneBoard(state)
  const piece = next[move.from.r][move.from.c]!
  next[move.from.r][move.from.c] = null
  next[move.r][move.c] = { ...piece, kind: move.promotion || piece.kind }
  if (move.enPassant) {
    next[move.r + (piece.color === 'white' ? 1 : -1)][move.c] = null
  }
  if (move.castle) {
    const row = move.from.r
    const rookCol = move.castle === 'king' ? 7 : 0
    const rookTo = move.castle === 'king' ? 5 : 3
    next[row][rookTo] = next[row][rookCol]
    next[row][rookCol] = null
  }
  return next
}

function inCheck(state: (Piece | null)[][], color: Color) {
  let king: Square | null = null
  for (let r = 0; r < 8; r++) {
    for (let c = 0; c < 8; c++) {
      if (state[r][c]?.kind === 'king' && state[r][c]?.color === color) king = { r, c }
    }
  }
  if (!king) return true
  return state.some((row, r) =>
    row.some(
      (p, c) =>
        p?.color === opposite(color) &&
        pseudoMoves(state, { r, c }, false).some(m => m.r === king!.r && m.c === king!.c),
    ),
  )
}

function inCheckAfter(state: (Piece | null)[][], color: Color, move: Move) {
  return inCheck(applyMove(state, move), color)
}

function legalMoves(from: Square) {
  return pseudoMoves(board.value, from).filter(m => !inCheckAfter(board.value, turn.value, m))
}

function allLegal(color: Color) {
  const old = turn.value
  turn.value = color
  const result: Move[] = []
  for (let r = 0; r < 8; r++) {
    for (let c = 0; c < 8; c++) {
      if (board.value[r][c]?.color === color) result.push(...legalMoves({ r, c }))
    }
  }
  turn.value = old
  return result
}

const legalTargets = computed(() => (selected.value ? legalMoves(selected.value) : []))
const checked = computed(() => inCheck(board.value, turn.value))
const gameOver = computed(() => allLegal(turn.value).length === 0)
const status = computed(() =>
  gameOver.value
    ? checked.value
      ? `Skakmat — ${colorName(opposite(turn.value))} menang`
      : 'Remis — tidak ada langkah legal'
    : checked.value
      ? `Skak! Giliran ${colorName(turn.value)}`
      : `Giliran ${colorName(turn.value)}`,
)

function notation(move: Move, piece: Piece, captured: boolean) {
  if (move.castle) return move.castle === 'king' ? 'O-O' : 'O-O-O'
  const symbols: Record<Kind, string> = { king: 'K', queen: 'Q', rook: 'R', bishop: 'B', knight: 'N', pawn: '' }
  return `${symbols[piece.kind]}${captured ? 'x' : ''}${squareName(move)}${move.promotion ? '=Q' : ''}`
}

function choose(square: Square) {
  if (gameOver.value) return
  const current = board.value[square.r][square.c]
  const target = selected.value && legalTargets.value.find(m => m.r === square.r && m.c === square.c)
  if (target) {
    if (target.promotion) {
      promotion.value = { move: target }
      return
    }
    makeMove(target)
    return
  }
  selected.value = current?.color === turn.value ? square : null
}

function makeMove(move: Move, promotedKind?: Kind) {
  const piece = board.value[move.from.r][move.from.c]!
  const captured = Boolean(board.value[move.r][move.c]) || Boolean(move.enPassant)
  history.value.push({
    board: cloneBoard(board.value),
    turn: turn.value,
    castling: { ...castling.value },
    enPassant: enPassant.value ? { ...enPassant.value } : null,
    notation: notation({ ...move, promotion: promotedKind }, piece, captured),
  })
  board.value = applyMove(board.value, { ...move, promotion: promotedKind || move.promotion })
  if (piece.kind === 'king') {
    if (piece.color === 'white') {
      castling.value.whiteKing = false
      castling.value.whiteQueen = false
    } else {
      castling.value.blackKing = false
      castling.value.blackQueen = false
    }
  }
  if (piece.kind === 'rook') {
    if (move.from.r === 7 && move.from.c === 0) castling.value.whiteQueen = false
    if (move.from.r === 7 && move.from.c === 7) castling.value.whiteKing = false
    if (move.from.r === 0 && move.from.c === 0) castling.value.blackQueen = false
    if (move.from.r === 0 && move.from.c === 7) castling.value.blackKing = false
  }
  enPassant.value =
    piece.kind === 'pawn' && Math.abs(move.r - move.from.r) === 2
      ? { r: (move.r + move.from.r) / 2, c: move.from.c }
      : null
  moves.value.push(history.value.at(-1)!.notation)
  turn.value = opposite(turn.value)
  selected.value = null
  promotion.value = null
}

function undo() {
  const last = history.value.pop()
  if (!last) return
  board.value = last.board
  turn.value = last.turn
  castling.value = last.castling
  enPassant.value = last.enPassant
  moves.value.pop()
  selected.value = null
  promotion.value = null
}

function reset() {
  board.value = createBoard()
  turn.value = 'white'
  castling.value = initialCastling()
  enPassant.value = null
  history.value = []
  moves.value = []
  selected.value = null
  promotion.value = null
}
</script>

<template>
  <main class="app-shell">
    <header class="topbar">
      <div class="brand">
        <span class="brand-mark">♞</span>
        <div><strong>Checkmate</strong><small>LOCAL ARENA</small></div>
      </div>
      <div class="online"><i></i> 2 pemain lokal</div>
    </header>
    <section class="game-layout">
      <div class="board-column">
        <div class="player-card" :class="{ active: turn === 'black' && !gameOver }">
          <span class="avatar black-avatar">♟</span>
          <div><b>Hitam</b><small>Black player</small></div>
          <span v-if="turn === 'black' && !gameOver" class="turn-dot"></span>
        </div>
        <div class="board-wrap">
          <div class="board" role="grid">
            <template v-for="r in 8" :key="r">
              <button
                v-for="c in 8"
                :key="`${r}-${c}`"
                class="square"
                :class="[
                  {
                    light: (r + c) % 2 === 0,
                    dark: (r + c) % 2 !== 0,
                    selected: selected && selected.r === r - 1 && selected.c === c - 1,
                    target: legalTargets.some(m => m.r === r - 1 && m.c === c - 1),
                    check:
                      checked &&
                      board[r - 1][c - 1]?.kind === 'king' &&
                      board[r - 1][c - 1]?.color === turn,
                  },
                ]"
                @click="choose({ r: r - 1, c: c - 1 })"
              >
                <span v-if="c === 1" class="rank-label">{{ 9 - r }}</span>
                <span v-if="r === 8" class="file-label">{{ files[c - 1] }}</span>
                <span v-if="board[r - 1][c - 1]" class="piece" :class="board[r - 1][c - 1]!.color">{{
                  icons[board[r - 1][c - 1]!.color][board[r - 1][c - 1]!.kind]
                }}</span>
                <span
                  v-if="legalTargets.some(m => m.r === r - 1 && m.c === c - 1)"
                  class="move-dot"
                ></span>
              </button>
            </template>
          </div>
        </div>
        <div class="player-card bottom" :class="{ active: turn === 'white' && !gameOver }">
          <span class="avatar white-avatar">♙</span>
          <div><b>Putih</b><small>White player</small></div>
          <span v-if="turn === 'white' && !gameOver" class="turn-dot"></span>
        </div>
      </div>
      <aside class="side-panel">
        <div class="status-card">
          <span class="eyebrow">GAME STATUS</span>
          <h1>{{ status }}</h1>
          <p>{{ gameOver ? 'Permainan telah selesai.' : 'Pilih bidak untuk melihat langkah yang tersedia.' }}</p>
          <span class="status-pill" :class="{ warning: checked }"><i></i>{{ gameOver ? 'SELESAI' : checked ? 'DALAM SKAK' : 'PERMAINAN BERJALAN' }}</span>
        </div>
        <div class="history-card">
          <div class="section-head">
            <h2>Riwayat langkah</h2>
            <span>{{ moves.length }} langkah</span>
          </div>
          <div v-if="!moves.length" class="empty-history">Belum ada langkah dimainkan</div>
          <div v-else class="move-list">
            <div v-for="(_, index) in Math.ceil(moves.length / 2)" :key="index" class="move-row">
              <span>{{ index + 1 }}</span>
              <b>{{ moves[index * 2] || '—' }}</b>
              <b>{{ moves[index * 2 + 1] || '—' }}</b>
            </div>
          </div>
        </div>
        <div class="controls">
          <button class="secondary" :disabled="!history.length" @click="undo">↶ <span>Undo langkah</span></button>
          <button class="primary" @click="reset">↻ <span>Permainan baru</span></button>
        </div>
        <p class="tip"><span>✦</span> Klik bidak lalu pilih kotak yang disorot untuk bergerak.</p>
      </aside>
    </section>
    <footer>
      <span>CHECKMATE / LOCAL ARENA</span>
      <span>Permainan catur sederhana untuk dua pemain</span>
    </footer>
    <div v-if="promotion" class="modal-backdrop">
      <div class="promotion-modal">
        <span class="eyebrow">PROMOSI BIDAK</span>
        <h2>Pilih bidak Anda</h2>
        <div class="promotion-options">
          <button v-for="kind in ['queen', 'rook', 'bishop', 'knight'] as Kind[]" :key="kind" @click="makeMove(promotion!.move, kind)">{{ icons[turn][kind] }}</button>
        </div>
      </div>
    </div>
  </main>
</template>
