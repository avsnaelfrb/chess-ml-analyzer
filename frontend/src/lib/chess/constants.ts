import type { Color, Kind } from '../../types/chess'

export const files: string[] = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']

export const icons: Record<Color, Record<Kind, string>> = {
  white: { king: '♔', queen: '♕', rook: '♖', bishop: '♗', knight: '♘', pawn: '♙' },
  black: { king: '♚', queen: '♛', rook: '♜', bishop: '♝', knight: '♞', pawn: '♟' },
}
