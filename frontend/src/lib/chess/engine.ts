import type { Board, Castling, Color, Move, Square } from '../../types/chess'
import { cloneBoard } from './board'

/** Posisi statis yang dibutuhkan mesin untuk membangkitkan dan memvalidasi langkah. */
export type Position = {
  board: Board
  castling: Castling
  enPassant: Square | null
}

type PseudoMoveOptions = {
  includeCastle?: boolean
  allowKingCapture?: boolean
}

export const opposite = (color: Color): Color => (color === 'white' ? 'black' : 'white')

const inBounds = (r: number, c: number) => r >= 0 && r < 8 && c >= 0 && c < 8

/**
 * Membangkitkan langkah pseudo-legal. `allowKingCapture` dipakai khusus untuk
 * deteksi skak: saat true, raja lawan boleh menjadi target sehingga ancaman
 * terhadap raja ikut terdeteksi.
 */
export function pseudoMoves(
  position: Position,
  from: Square,
  { includeCastle = true, allowKingCapture = false }: PseudoMoveOptions = {},
): Move[] {
  const { board: state } = position
  const piece = state[from.r][from.c]
  if (!piece) return []
  const result: Move[] = []

  const add = (r: number, c: number, extra: Partial<Move> = {}) => {
    if (!inBounds(r, c)) return false
    const target = state[r][c]
    if (!target) {
      result.push({ from, r, c, ...extra })
    } else if (target.color !== piece.color && (allowKingCapture || target.kind !== 'king')) {
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
      if (
        state[r][c] &&
        state[r][c]!.color !== piece.color &&
        (allowKingCapture || state[r][c]!.kind !== 'king')
      ) {
        result.push({ from, r, c })
      }
      if (position.enPassant && position.enPassant.r === r && position.enPassant.c === c) {
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
    if (includeCastle && !inCheck(position, piece.color)) {
      const row = piece.color === 'white' ? 7 : 0
      const kingSide = piece.color === 'white' ? position.castling.whiteKing : position.castling.blackKing
      const queenSide = piece.color === 'white' ? position.castling.whiteQueen : position.castling.blackQueen
      if (
        kingSide &&
        !state[row][5] &&
        !state[row][6] &&
        !inCheckAfter(position, piece.color, { from: { r: row, c: 4 }, r: row, c: 5 }) &&
        !inCheckAfter(position, piece.color, { from: { r: row, c: 4 }, r: row, c: 6 })
      ) {
        result.push({ from, r: row, c: 6, castle: 'king' })
      }
      if (
        queenSide &&
        !state[row][1] &&
        !state[row][2] &&
        !state[row][3] &&
        !inCheckAfter(position, piece.color, { from: { r: row, c: 4 }, r: row, c: 3 }) &&
        !inCheckAfter(position, piece.color, { from: { r: row, c: 4 }, r: row, c: 2 })
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

export function applyMove(board: Board, move: Move): Board {
  const next = cloneBoard(board)
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

export function inCheck(position: Position, color: Color): boolean {
  let king: Square | null = null
  const { board: state } = position
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
        pseudoMoves(position, { r, c }, { includeCastle: false, allowKingCapture: true }).some(
          m => m.r === king!.r && m.c === king!.c,
        ),
    ),
  )
}

export function inCheckAfter(position: Position, color: Color, move: Move): boolean {
  return inCheck({ ...position, board: applyMove(position.board, move) }, color)
}

export function legalMoves(position: Position, from: Square, turn: Color): Move[] {
  return pseudoMoves(position, from).filter(m => !inCheckAfter(position, turn, m))
}

export function allLegal(position: Position, color: Color): Move[] {
  const result: Move[] = []
  for (let r = 0; r < 8; r++) {
    for (let c = 0; c < 8; c++) {
      if (position.board[r][c]?.color === color) {
        result.push(...legalMoves(position, { r, c }, color))
      }
    }
  }
  return result
}
