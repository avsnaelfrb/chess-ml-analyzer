import type { Board, Castling, Color, Kind, Square } from '../../types/chess'
import { squareName } from './notation'

const PIECE_LETTERS: Record<Kind, string> = {
  king: 'k',
  queen: 'q',
  rook: 'r',
  bishop: 'b',
  knight: 'n',
  pawn: 'p',
}

export type FenState = {
  board: Board
  turn: Color
  castling: Castling
  enPassant: Square | null
  /** Jumlah langkah (ply) yang sudah dimainkan, untuk field fullmove number. */
  ply: number
}

function piecePlacement(board: Board): string {
  const ranks: string[] = []
  for (let r = 0; r < 8; r++) {
    let rank = ''
    let empty = 0
    for (let c = 0; c < 8; c++) {
      const piece = board[r][c]
      if (!piece) {
        empty++
        continue
      }
      if (empty) {
        rank += empty
        empty = 0
      }
      const letter = PIECE_LETTERS[piece.kind]
      rank += piece.color === 'white' ? letter.toUpperCase() : letter
    }
    if (empty) rank += empty
    ranks.push(rank)
  }
  return ranks.join('/')
}

function castlingField(castling: Castling): string {
  const field =
    (castling.whiteKing ? 'K' : '') +
    (castling.whiteQueen ? 'Q' : '') +
    (castling.blackKing ? 'k' : '') +
    (castling.blackQueen ? 'q' : '')
  return field || '-'
}

/**
 * Bangun FEN dari state papan.
 *
 * Catatan: `halfmove_clock` belum dilacak oleh game sehingga selalu `0`
 * (cukup untuk klasifikasi fase; lihat PLANNING.md bagian 7).
 */
export function toFen(state: FenState): string {
  const placement = piecePlacement(state.board)
  const active = state.turn === 'white' ? 'w' : 'b'
  const castling = castlingField(state.castling)
  const enPassant = state.enPassant ? squareName(state.enPassant) : '-'
  const halfmove = 0
  const fullmove = Math.floor(state.ply / 2) + 1
  return `${placement} ${active} ${castling} ${enPassant} ${halfmove} ${fullmove}`
}

/** FEN posisi awal standar, dipakai untuk validasi/testing. */
export const INITIAL_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
