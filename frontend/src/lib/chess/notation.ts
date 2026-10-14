import type { Color, Kind, Move, Piece, Square } from '../../types/chess'
import { files } from './constants'

export const colorName = (color: Color) => (color === 'white' ? 'Putih' : 'Hitam')

export const squareName = (s: Square) => `${files[s.c]}${8 - s.r}`

export const promotionLetter = (kind: Kind): string =>
  kind === 'queen' ? 'q' : kind === 'rook' ? 'r' : kind === 'bishop' ? 'b' : kind === 'knight' ? 'n' : ''

export const kindFromPromotionLetter = (letter: string): Kind | undefined =>
  letter === 'q'
    ? 'queen'
    : letter === 'r'
      ? 'rook'
      : letter === 'b'
        ? 'bishop'
        : letter === 'n'
          ? 'knight'
          : undefined

export function moveNotation(move: Move, piece: Piece, captured: boolean): string {
  if (move.castle) return move.castle === 'king' ? 'O-O' : 'O-O-O'
  const symbols: Record<Kind, string> = {
    king: 'K',
    queen: 'Q',
    rook: 'R',
    bishop: 'B',
    knight: 'N',
    pawn: '',
  }
  return `${symbols[piece.kind]}${captured ? 'x' : ''}${squareName(move)}${move.promotion ? '=Q' : ''}`
}
