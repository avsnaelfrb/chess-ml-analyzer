import { describe, expect, it } from 'vitest'
import { useChess } from '../src/composables/useChess'
import type { Board } from '../src/types/chess'

const emptyBoard = (): Board => Array.from({ length: 8 }, () => Array(8).fill(null)) as Board

/** Papan dengan raja putih e1, raja hitam e8, dan pion hitam di b2 (siap promosi). */
function promotionBoard() {
  const chess = useChess()
  chess.board.value = emptyBoard()
  chess.board.value[7][4] = { color: 'white', kind: 'king' }
  chess.board.value[0][4] = { color: 'black', kind: 'king' }
  chess.board.value[6][1] = { color: 'black', kind: 'pawn' }
  chess.turn.value = 'black'
  return chess
}

describe('useChess.playUci', () => {
  it('memainkan langkah legal dan memperbarui turn, history, dan lastMove', () => {
    const chess = useChess()

    expect(chess.playUci('e2e4')).toBe(true)
    expect(chess.turn.value).toBe('black')
    expect(chess.history.value).toHaveLength(1)
    expect(chess.moves.value).toEqual(['e4'])
    expect(chess.lastMoveInfo.value?.moveUci).toBe('e2e4')
  })

  it('mengabaikan langkah ilegal tanpa mengubah state', () => {
    const chess = useChess()

    expect(chess.playUci('e2e5')).toBe(false)
    expect(chess.turn.value).toBe('white')
    expect(chess.history.value).toHaveLength(0)
    expect(chess.board.value[6][4]).toMatchObject({ color: 'white', kind: 'pawn' })
  })

  it('menolak langkah milik warna yang bukan gilirannya', () => {
    const chess = useChess()

    expect(chess.playUci('e7e5')).toBe(false)
    expect(chess.turn.value).toBe('white')
    expect(chess.history.value).toHaveLength(0)
  })

  it('menerapkan underpromotion sesuai huruf kelima UCI', () => {
    const chess = promotionBoard()

    expect(chess.playUci('b2b1n')).toBe(true)
    expect(chess.board.value[7][1]).toMatchObject({ color: 'black', kind: 'knight' })
    expect(chess.lastMoveInfo.value?.moveUci).toBe('b2b1n')
  })

  it('menerapkan promosi queen default', () => {
    const chess = promotionBoard()

    expect(chess.playUci('b2b1q')).toBe(true)
    expect(chess.board.value[7][1]).toMatchObject({ color: 'black', kind: 'queen' })
  })
})

describe('useChess.lastHumanMove', () => {
  it('mencatat langkah manusia; langkah bot (playUci) tidak menimpanya', () => {
    const chess = useChess()

    chess.choose({ r: 6, c: 4 }) // e2
    chess.choose({ r: 4, c: 4 }) // e4 — langkah manusia
    expect(chess.lastHumanMove.value?.moveUci).toBe('e2e4')

    expect(chess.playUci('e7e5')).toBe(true) // balasan bot
    expect(chess.lastMoveInfo.value?.moveUci).toBe('e7e5')
    expect(chess.lastHumanMove.value?.moveUci).toBe('e2e4')
  })

  it('dikosongkan oleh undo dan reset', () => {
    const chess = useChess()
    chess.choose({ r: 6, c: 4 })
    chess.choose({ r: 4, c: 4 })

    chess.undo()
    expect(chess.lastHumanMove.value).toBeNull()

    chess.choose({ r: 6, c: 4 })
    chess.choose({ r: 4, c: 4 })
    chess.reset()
    expect(chess.lastHumanMove.value).toBeNull()
  })
})
