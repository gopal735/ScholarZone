import { useRef, useState } from 'react'
import { useJourneyI18n } from '../i18n/useJourneyI18n.js'
import { useJourney } from '../hooks/useJourney.js'
import { readImportFile, planReplacement } from '../lib/journeyImportExport.js'
import { ImportConfirmDialog, ResetDialog } from './Dialogs.jsx'
import { BilingualText } from './ui/primitives.jsx'

/**
 * Export, import and reset controls.
 *
 * Export is a real `Blob` download built from the normalised document, so the
 * file carries the schema version and the provenance labels verbatim. Import
 * validates the whole file before anything is applied, asks for confirmation,
 * and reports the precise reason a file was refused — a student who imported a
 * file that was not an export should be told that, not shown a generic failure.
 */
export function DataTools() {
  const { t, both } = useJourneyI18n()
  const { state, exportJson, replaceDocument, reset } = useJourney()
  const fileRef = useRef(null)
  const [resetOpen, setResetOpen] = useState(false)
  const [importOpen, setImportOpen] = useState(false)
  const [pendingFile, setPendingFile] = useState(null)
  const [message, setMessage] = useState(null)
  const [error, setError] = useState(null)

  const onExport = () => {
    setError(null)
    setMessage(null)
    try {
      const json = exportJson()
      const blob = new Blob([json], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = 'scholarzone-bangladesh-journey.json'
      document.body.appendChild(anchor)
      anchor.click()
      document.body.removeChild(anchor)
      URL.revokeObjectURL(url)
      setMessage(t('export.ready'))
    } catch {
      setError(t('error.body'))
    }
  }

  const onPickFile = async (event) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    const result = await readImportFile(file)
    if (!result.ok) {
      setError(t(`import.error.${result.reason}`) ?? t('error.body'))
      return
    }
    setPendingFile({ name: file.name, document: result.document })
    setImportOpen(true)
  }

  const onConfirmImport = () => {
    setError(null)
    if (!pendingFile) return
    const plan = planReplacement(state, pendingFile.document)
    replaceDocument(plan.next)
    setPendingFile(null)
    setImportOpen(false)
    setMessage(t('import.success'))
  }

  const onConfirmReset = () => {
    setError(null)
    const result = reset()
    setResetOpen(false)
    if (result && result.ok === false) {
      setError(t('storage.resetFailed'))
      return
    }
    setMessage(t('reset.success'))
  }

  const exportHeading = both('export.title')

  return (
    <section className="jtools" aria-labelledby="jtools-heading">
      <h2 className="jtools__heading" id="jtools-heading">
        <span className="jbilingual__primary">{exportHeading.primary}</span>
        {exportHeading.secondary ? (
          <span className="jbilingual__secondary" lang="en">
            {exportHeading.secondary}
          </span>
        ) : null}
      </h2>
      <p className="jtools__body">{t('export.body')}</p>

      <div className="jtools__actions">
        <button type="button" className="jbtn jbtn--primary" onClick={onExport}>
          {t('common.export')}
        </button>
        <button type="button" className="jbtn jbtn--quiet" onClick={() => fileRef.current?.click()}>
          {t('common.import')}
        </button>
        <button type="button" className="jbtn jbtn--danger" onClick={() => setResetOpen(true)}>
          {t('common.reset')}
        </button>
        <input
          ref={fileRef}
          type="file"
          accept="application/json,.json"
          className="sz-sr-only"
          onChange={onPickFile}
          aria-label={t('common.import')}
        />
      </div>

      <div className="jtools__status" role="status">
        {message ? <p className="jtools__message">{message}</p> : null}
        {error ? <p className="jtools__error">{error}</p> : null}
      </div>

      <ResetDialog open={resetOpen} onConfirm={onConfirmReset} onCancel={() => setResetOpen(false)} />
      <ImportConfirmDialog
        open={importOpen}
        fileName={pendingFile?.name}
        onConfirm={onConfirmImport}
        onCancel={() => {
          setPendingFile(null)
          setImportOpen(false)
        }}
      />
    </section>
  )
}

export { BilingualText }
