import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { askMentor, setMentorSessionScope, clearInFlightAsk } from '../mentorService'

function deferred() {
  let resolve, reject
  const promise = new Promise((res, rej) => { resolve = res; reject = rej })
  return { promise, resolve, reject }
}

describe('mentorService in-flight dedup scoping', () => {
  beforeEach(() => {
    clearInFlightAsk()
    setMentorSessionScope(0)
    vi.stubGlobal('fetch', vi.fn())
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    clearInFlightAsk()
  })

  it('dedups identical prompts within same session', async () => {
    const d = deferred()
    vi.mocked(fetch).mockReturnValue(d.promise)
    setMentorSessionScope('s1')
    const p1 = askMentor('hello', {})
    const p2 = askMentor('hello', {})
    expect(fetch).toHaveBeenCalledTimes(1)
    d.resolve(new Response(JSON.stringify({ ok: true }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    await Promise.all([p1, p2])
  })

  it('does not share across different sessions', async () => {
    const d1 = deferred()
    const d2 = deferred()
    vi.mocked(fetch)
      .mockReturnValueOnce(d1.promise)
      .mockReturnValueOnce(d2.promise)
    setMentorSessionScope('a')
    const pA = askMentor('hello', {})
    setMentorSessionScope('b')
    const pB = askMentor('hello', {})
    expect(fetch).toHaveBeenCalledTimes(2)
    d1.resolve(new Response(JSON.stringify({ a: 1 }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    d2.resolve(new Response(JSON.stringify({ b: 2 }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    const rA = await pA
    const rB = await pB
    expect(rA).toEqual({ a: 1 })
    expect(rB).toEqual({ b: 2 })
  })

  it('scope passed via option overrides', async () => {
    const d1 = deferred()
    const d2 = deferred()
    vi.mocked(fetch)
      .mockReturnValueOnce(d1.promise)
      .mockReturnValueOnce(d2.promise)
    const pA = askMentor('hi', { sessionScope: 'x' })
    const pB = askMentor('hi', { sessionScope: 'y' })
    expect(fetch).toHaveBeenCalledTimes(2)
    d1.resolve(new Response(JSON.stringify({ x: 1 }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    d2.resolve(new Response(JSON.stringify({ y: 2 }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    await Promise.all([pA, pB])
  })
})