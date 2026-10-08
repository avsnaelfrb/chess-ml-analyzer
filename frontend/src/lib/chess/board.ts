import type { Board, Castling, Kind, Piece } from '../../types/chess'

export function createBoard(): Board {
  const board: Board = Array.from({ length: 8 }, () => Array<Piece | null>(8).fill(null))
  const back: Kind[] = ['rook', 'knight', 'bishop', 'queen', 'king', 'bishop', 'knight', 'rook']
  for (let c = 0; c < 8; c++) {
    board[0][c] = { color: 'black', kind: back[c] }
    board[1][c] = { color: 'black', kind: 'pawn' }
    board[6][c] = { color: 'white', kind: 'pawn' }
    board[7][c] = { color: 'white', kind: back[c] }
  }
  return board
}

export function cloneBoard(board: Board): Board {
  return board.map(row => row.map(piece => (piece ? { ...piece } : null)))
}

export function initialCastling(): Castling {
  return { whiteKing: true, whiteQueen: true, blackKing: true, blackQueen: true }
}
