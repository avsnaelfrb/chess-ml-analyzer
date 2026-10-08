export type Color = 'white' | 'black'

export type Kind = 'king' | 'queen' | 'rook' | 'bishop' | 'knight' | 'pawn'

export type Piece = { color: Color; kind: Kind }

export type Square = { r: number; c: number }

export type Move = Square & {
  from: Square
  promotion?: Kind
  castle?: 'king' | 'queen'
  enPassant?: boolean
}

export type Board = (Piece | null)[][]

export type Castling = {
  whiteKing: boolean
  whiteQueen: boolean
  blackKing: boolean
  blackQueen: boolean
}

export type Snapshot = {
  board: Board
  turn: Color
  castling: Castling
  enPassant: Square | null
  notation: string
}
