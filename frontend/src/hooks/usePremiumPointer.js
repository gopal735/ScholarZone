import { useEffect } from 'react'

/* ═══════════════════════════════════════════════════════════════════
   Premium pointer behaviour — the port of the reference's listeners

   The reference runs one document-level `pointermove` listener and
   derives three things from it: the cursor glow's position, each
   card's gloss band and spotlight, and each card's 3D tilt. Magnetic
   buttons get their own small offset on the same event. This hook is
   that listener, installed once, with the reference's exact maths:

     tilt:  perspective(900px) rotateX((.5 - y) * 7deg)
                                 rotateY((x - .5) * 7deg) translateY(-4px)
     gloss: --gp = x * 100%            (115deg band, leads the cursor)
     spot: --mx/--my = pointer pixels inside the card
     magnet: translate = (dx * .2px) (dy * .3px)

   Three guards keep it honest:

   * Reduced motion. The tilt, the magnet and the glow's tracking all
     stop; the static material stays, because a card that stops tilting
     must still look like a card.

   * Fine pointers only. On touch there is no hover, so a card would
     freeze mid-tilt after a tap. The matchMedia check mirrors what
     ScholarshipCard already does, and the card's own CSS drops the
     gloss and spotlight layers for coarse input.

   * A single listener for the whole document, not one per card. A
     grid of twelve cards with twelve listeners re-measures rects on
     every move event; one listener with the closest() lookup the
     reference uses measures only the card under the cursor.
   ═══════════════════════════════════════════════════════════════════ */

const FINE_POINTER = '(hover: hover) and (pointer: fine)'
const CARD_SELECTOR = '.p-card'
const BUTTON_SELECTOR = '.p-btn'

export function usePremiumPointer() {
  useEffect(() => {
    if (typeof window === 'undefined') return

    const finePointer = window.matchMedia(FINE_POINTER).matches
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (!finePointer) return

    const glow = document.querySelector('.p-glow')

    /* The card the pointer is currently over. When the pointer moves
       from a card to anything else, the previous card's inline
       transform has to be cleared — the reference keeps this in a
       closure variable rather than re-querying, because the card may
       have been removed from the DOM by a re-render in between. */
    let lastCard = null
    let lastButton = null

    const resetCard = (card) => {
      if (!card) return
      card.style.transform = ''
    }

    /* The reference accumulates the tilt onto the element rather than
       composing it with a CSS variable, so a hover lift in the
       stylesheet would be wiped by the inline transform. The lift is
       therefore inside the transform string here — translateY(-4px) —
       exactly as the reference does it. */
    const handleMove = (event) => {
      if (glow) {
        glow.style.transform = `translate(${event.clientX}px, ${event.clientY}px)`
      }

      const card = event.target?.closest?.(CARD_SELECTOR) ?? null
      if (card && card !== lastCard) {
        resetCard(lastCard)
        lastCard = card
      }

      if (card) {
        const rect = card.getBoundingClientRect()
        if (rect.width > 0 && rect.height > 0) {
          const x = (event.clientX - rect.left) / rect.width
          const y = (event.clientY - rect.top) / rect.height

          card.style.setProperty('--mx', `${event.clientX - rect.left}px`)
          card.style.setProperty('--my', `${event.clientY - rect.top}px`)
          card.style.setProperty('--gp', `${x * 100}%`)

          if (!reducedMotion) {
            card.style.transform =
              `perspective(900px) rotateX(${(0.5 - y) * 7}deg) ` +
              `rotateY(${(x - 0.5) * 7}deg) translateY(-4px)`
          }
        }
      } else if (lastCard) {
        resetCard(lastCard)
        lastCard = null
      }

      /* The magnetic offset: the button leans toward the cursor by a
         fifth of the horizontal distance and a third of the vertical.
         Tracked separately from the card so leaving one never clears
         the other. */
      const button = event.target?.closest?.(BUTTON_SELECTOR) ?? null
      if (button && button !== lastButton) {
        if (lastButton) lastButton.style.translate = ''
        lastButton = button
      }

      if (button && !reducedMotion) {
        const rect = button.getBoundingClientRect()
        if (rect.width > 0 && rect.height > 0) {
          button.style.translate =
            `${(event.clientX - rect.left - rect.width / 2) * 0.2}px ` +
            `${(event.clientY - rect.top - rect.height / 2) * 0.3}px`
        }
      } else if (lastButton && !button) {
        lastButton.style.translate = ''
        lastButton = null
      }
    }

    /* Leaving the document clears both, so nothing is frozen
       mid-transform when the pointer comes back. */
    const handleLeave = () => {
      resetCard(lastCard)
      lastCard = null
      if (lastButton) {
        lastButton.style.translate = ''
        lastButton = null
      }
    }

    document.addEventListener('pointermove', handleMove, { passive: true })
    document.addEventListener('pointerleave', handleLeave, { passive: true })

    return () => {
      document.removeEventListener('pointermove', handleMove)
      document.removeEventListener('pointerleave', handleLeave)
      resetCard(lastCard)
    }
  }, [])
}

export default usePremiumPointer
