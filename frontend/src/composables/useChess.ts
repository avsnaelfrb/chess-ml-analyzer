import { computed, ref } from 'vue'
import { cloneBoard, createBoard, initialCastling } from '../lib/chess/board'
import { allLegal, applyMove, inCheck, legalMoves, opposite, type Position } from '../lib/chess/engine'
import { colorName, moveNotation } from '../lib/chess/notation'
import type { Castling, Color, Kind, Move, Snapshot, Square } from '../types/chess'

export function useChess() {
  const board = ref(createBoard())
  const turn = ref<Color>('white')
  const selected = ref<Square | null>(null)
  const castling = ref<Castling>(initialCastling())
  const enPassant = ref<Square | null>(null)
  const history = ref<Snapshot[]>([])
  const moves = ref<string[]>([])
  const promotion = ref<{ move: Move } | null>(null)

  const currentPosition = (): Position => ({
    board: board.value,
    castling: castling.value,
    enPassant: enPassant.value,
  })

  const legalTargets = computed(() =>
    selected.value ? legalMoves(currentPosition(), selected.value, turn.value) : [],
  )
  const checked = computed(() => inCheck(currentPosition(), turn.value))
  const gameOver = computed(() => allLegal(currentPosition(), turn.value).length === 0)
  const status = computed(() =>
    gameOver.value
      ? checked.value
        ? `Skakmat — ${colorName(opposite(turn.value))} menang`
        : 'Remis — tidak ada langkah legal'
      : checked.value
        ? `Skak! Giliran ${colorName(turn.value)}`
        : `Giliran ${colorName(turn.value)}`,
  )

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
      notation: moveNotation({ ...move, promotion: promotedKind }, piece, captured),
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

  return {
    board,
    turn,
    selected,
    legalTargets,
    checked,
    gameOver,
    status,
    history,
    moves,
    promotion,
    choose,
    makeMove,
    undo,
    reset,
  }
}
