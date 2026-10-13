import { useEffect, useRef } from 'react'
import { useJourneyI18n } from '../i18n/useJourneyI18n.js'
import { BilingualText } from './ui/primitives.jsx'

/**
 * Confirmation dialog for the reset action.
 *
 * Behaviour worth pinning, because each is a place a dialog usually goes wrong:
 *
 * - Focus moves to the dialog on open and is restored to the invoking control on
 *   close, so a keyboard user is not dropped at the top of the document.
 * - Escape closes, and focus is trapped inside while open, so tabbing cannot
 *   wander behind the scrim.
 * - The scrim sits below the surface it dims, so a click on a control inside the
 *   dialog reaches the control rather than being swallowed by the overlay.
 * - The dialog states exactly which keys it removes, in both languages, because
 *   "reset" is the one action here that destroys work.
 */
export function ResetDialog({ open, onConfirm, onCancel }) {
  const { t, both, mode } = useJourneyI18n()
  const dialogRef = useRef(null)
  const confirmRef = useRef(null)
  const restoreFocusRef = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    restoreFocusRef.current = document.activeElement
    confirmRef.current?.focus()

    const onKeyDown = (event) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        onCancel()
        return
      }
      if (event.key !== 'Tab') return
      const focusable = dialogRef.current?.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      )
      if (!focusable || focusable.length === 0) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      if (restoreFocusRef.current && typeof restoreFocusRef.current.focus === 'function') {
        restoreFocusRef.current.focus()
      }
    }
  }, [open, onCancel])

  if (!open) return null

  const title = both('reset.title')
  const body = both('reset.body')

  return (
    <div className="jscrim" onMouseDown={(event) => { if (event.target === event.currentTarget) onCancel() }}>
      <div
        className="jdialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="jreset-title"
        aria-describedby="jreset-body"
        ref={dialogRef}
      >
        <h2 className="jdialog__title" id="jreset-title">
          <span className="jbilingual__primary">{title.primary}</span>
          {title.secondary ? (
            <span className="jbilingual__secondary" lang="en">
              {title.secondary}
            </span>
          ) : null}
        </h2>

        <div className="jdialog__body" id="jreset-body">
          <p>{body.primary}</p>
          {body.secondary ? (
            <p className="jdialog__en" lang="en">
              {body.secondary}
            </p>
          ) : null}
          <p className="jdialog__warning">{t('reset.warning')}</p>
          {mode === 'both' ? (
            <p className="jdialog__en">{t('reset.warning')}</p>
          ) : null}
        </div>

        <div className="jdialog__actions">
          <button type="button" className="jbtn jbtn--quiet" onClick={onCancel}>
            {t('reset.cancel')}
          </button>
          <button type="button" className="jbtn jbtn--danger" onClick={onConfirm} ref={confirmRef}>
            {t('reset.confirm')}
          </button>
        </div>
      </div>
    </div>
  )
}

/**
 * Import confirmation dialog.
 *
 * Separate from the reset dialog because it asks a different question: this one
 * replaces progress with a file the student chose, and it must be impossible to
 * trigger by accident while a file is being picked.
 */
export function ImportConfirmDialog({ open, fileName, onConfirm, onCancel }) {
  const { t, both } = useJourneyI18n()
  const dialogRef = useRef(null)
  const confirmRef = useRef(null)
  const restoreFocusRef = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    restoreFocusRef.current = document.activeElement
    confirmRef.current?.focus()

    const onKeyDown = (event) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        onCancel()
        return
      }
      if (event.key !== 'Tab') return
      const focusable = dialogRef.current?.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      )
      if (!focusable || focusable.length === 0) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      if (restoreFocusRef.current && typeof restoreFocusRef.current.focus === 'function') {
        restoreFocusRef.current.focus()
      }
    }
  }, [open, onCancel])

  if (!open) return null

  const title = both('import.title')
  const body = both('import.body')

  return (
    <div className="jscrim" onMouseDown={(event) => { if (event.target === event.currentTarget) onCancel() }}>
      <div
        className="jdialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="jimport-title"
        aria-describedby="jimport-body"
        ref={dialogRef}
      >
        <h2 className="jdialog__title" id="jimport-title">
          <span className="jbilingual__primary">{title.primary}</span>
          {title.secondary ? (
            <span className="jbilingual__secondary" lang="en">
              {title.secondary}
            </span>
          ) : null}
        </h2>

        <div className="jdialog__body" id="jimport-body">
          <p>{body.primary}</p>
          {body.secondary ? (
            <p className="jdialog__en" lang="en">
              {body.secondary}
            </p>
          ) : null}
          {fileName ? <p className="jdialog__file">{fileName}</p> : null}
        </div>

        <div className="jdialog__actions">
          <button type="button" className="jbtn jbtn--quiet" onClick={onCancel}>
            {t('import.cancel')}
          </button>
          <button type="button" className="jbtn jbtn--primary" onClick={onConfirm} ref={confirmRef}>
            {t('import.confirm')}
          </button>
        </div>
      </div>
    </div>
  )
}

export { BilingualText }
