import { useCallback, useState } from 'react'

import {
  archiveScholarship,
  createScholarship,
  deleteScholarship,
  EDITABLE_FIELDS,
  emptyDraft,
  fetchScholarshipAudit,
  fetchScholarshipList,
  updateScholarship,
} from '../services/adminScholarshipService'

/**
 * The scholarship administration surface: create, edit, archive, and the
 * deliberate permanent delete.
 *
 * The delete flow is the part to look at. It is not a button that fires
 * when clicked: the operator types the exact string "DELETE <id>" and a
 * reason, and the page refuses to submit until both are present. When the
 * server refuses because something depends on the record (a student's
 * saved list, an application, a verification trail), the blocking
 * dependencies are shown rather than a generic error - the record is not
 * removable, and the operator is told what to resolve first.
 */
function AdminScholarshipManager() {
  const [adminSecret, setAdminSecret] = useState('')
  const [filters, setFilters] = useState({ q: '', status: '' })
  const [rows, setRows] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const [draft, setDraft] = useState(emptyDraft)
  const [editingId, setEditingId] = useState(null)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [deleteConfirm, setDeleteConfirm] = useState('')
  const [deleteReason, setDeleteReason] = useState('')
  const [blockedBy, setBlockedBy] = useState([])
  const [auditFor, setAuditFor] = useState(null)
  const [audit, setAudit] = useState([])

  const load = useCallback(() => {
    if (!adminSecret) return
    setLoading(true)
    setError('')
    fetchScholarshipList(adminSecret, filters)
      .then((payload) => {
        setRows(payload.items || [])
        setTotal(payload.total || 0)
      })
      .catch((fetchError) => setError(fetchError.message))
      .finally(() => setLoading(false))
  }, [adminSecret, filters])

  // No effect auto-loads the list: the requests only start when the
  // operator submits the secret, presses search, or finishes a mutation.
  // An effect that fired on mount would fetch before there is anything to
  // authenticate with, and a cascading load is the wrong shape for a page
  // whose whole input is a deliberate navigation.

  if (!adminSecret) {
    return (
      <section className="admin-section">
        <h3>Scholarship administration</h3>
        <p className="muted">
          Enter the administrator secret to list, create, edit, archive and permanently delete
          scholarship records. The secret is held in this tab only and never stored.
        </p>
        <label>
          Administrator secret
          <input
            type="password"
            autoComplete="off"
            value={adminSecret}
            onChange={(event) => setAdminSecret(event.target.value)}
          />
        </label>
        <div className="admin-form-actions">
          <button
            className="glass-btn glass-btn--active"
            type="button"
            disabled={!adminSecret}
            onClick={load}
          >
            Load records
          </button>
        </div>
      </section>
    )
  }

  const startEdit = (row) => {
    setEditingId(row.id)
    const next = emptyDraft()
    for (const key of Object.keys(next)) next[key] = row[key] ?? ''
    setDraft(next)
    setNotice('')
  }

  const submitDraft = (event) => {
    event.preventDefault()
    if (!adminSecret) return
    const fields = {}
    for (const [key, value] of Object.entries(draft)) {
      if (value === '') continue
      fields[key] = value === 'true' ? true : value === 'false' ? false : value
    }
    const reason = editingId ? 'edited through the admin manager' : 'created through the admin manager'
    const action = editingId
      ? updateScholarship(adminSecret, editingId, { fields, reason })
      : createScholarship(adminSecret, { ...fields, reason })
    action
      .then(() => {
        setNotice(editingId ? `Updated record ${editingId}.` : 'Record created.')
        setEditingId(null)
        setDraft(emptyDraft())
        load()
      })
      .catch((submitError) => setError(submitError.message))
  }

  const archive = (row) => {
    const reason = window.prompt(`Archive reason for record ${row.id}?`, 'discontinued')
    if (!reason) return
    archiveScholarship(adminSecret, row.id, reason)
      .then(() => {
        setNotice(`Archived record ${row.id}.`)
        load()
      })
      .catch((archiveError) => setError(archiveError.message))
  }

  const runDelete = () => {
    if (!deleteTarget) return
    deleteScholarship(adminSecret, deleteTarget.id, deleteConfirm, deleteReason)
      .then((result) => {
        setNotice(`Permanently deleted record ${result.deleted}.`)
        setDeleteTarget(null)
        setDeleteConfirm('')
        setDeleteReason('')
        setBlockedBy([])
        load()
      })
      .catch((deleteError) => {
        if (deleteError.blocked_by) {
          setBlockedBy(deleteError.blocked_by)
        } else {
          setBlockedBy([])
        }
        setError(deleteError.message)
      })
  }

  const showAudit = (row) => {
    if (auditFor === row.id) {
      setAuditFor(null)
      return
    }
    fetchScholarshipAudit(adminSecret, row.id)
      .then((payload) => {
        setAudit(payload.items || [])
        setAuditFor(row.id)
      })
      .catch((auditError) => setError(auditError.message))
  }

  return (
    <section className="admin-section">
      <div className="admin-toolbar">
        <input
          type="search"
          placeholder="Search title, country or source"
          value={filters.q}
          onChange={(event) => setFilters({ ...filters, q: event.target.value })}
        />
        <select
          value={filters.status}
          onChange={(event) => setFilters({ ...filters, status: event.target.value })}
        >
          <option value="">Any status</option>
          <option value="open">Open</option>
          <option value="upcoming">Upcoming</option>
          <option value="closed">Closed</option>
        </select>
        <button className="glass-btn glass-btn--ghost glass-btn--sm" type="button" onClick={load}>
          Search
        </button>
        <span className="muted">{total} record(s)</span>
      </div>

      {error && <p className="form-error" role="alert">{error}</p>}
      {notice && <p className="form-success" role="status">{notice}</p>}

      <table className="admin-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Title</th>
            <th>Country</th>
            <th>Status</th>
            <th>Deadline</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td>{row.id}</td>
              <td>{row.title}</td>
              <td>{row.country}</td>
              <td>{row.status}</td>
              <td>{row.deadline_date || '—'}</td>
              <td className="admin-actions">
                <button className="glass-btn glass-btn--ghost glass-btn--sm" onClick={() => startEdit(row)}>
                  Edit
                </button>
                <button className="glass-btn glass-btn--ghost glass-btn--sm" onClick={() => showAudit(row)}>
                  Audit
                </button>
                <button className="glass-btn glass-btn--ghost glass-btn--sm" onClick={() => archive(row)}>
                  Archive
                </button>
                <button
                  className="glass-btn glass-btn--ghost glass-btn--sm"
                  onClick={() => {
                    setDeleteTarget(row)
                    setDeleteConfirm('')
                    setDeleteReason('')
                    setBlockedBy([])
                  }}
                >
                  Delete
                </button>
              </td>
            </tr>
          ))}
          {!loading && rows.length === 0 && (
            <tr>
              <td colSpan={6} className="muted">No records match.</td>
            </tr>
          )}
        </tbody>
      </table>

      <form className="admin-form" onSubmit={submitDraft}>
        <h3>{editingId ? `Edit record ${editingId}` : 'Create a record'}</h3>
        <div className="admin-form-grid">
          {EDITABLE_FIELDS.map((field) => (
            <label key={field.key} className={field.required ? 'required' : ''}>
              {field.label}
              <input
                value={draft[field.key] ?? ''}
                onChange={(event) => setDraft({ ...draft, [field.key]: event.target.value })}
                required={field.required}
              />
            </label>
          ))}
        </div>
        <div className="admin-form-actions">
          <button className="glass-btn glass-btn--active" type="submit">
            {editingId ? 'Save changes' : 'Create record'}
          </button>
          {editingId && (
            <button className="glass-btn glass-btn--ghost" type="button" onClick={() => setEditingId(null)}>
              Cancel
            </button>
          )}
        </div>
      </form>

      {auditFor && (
        <div className="admin-audit">
          <h3>Change trail for record {auditFor}</h3>
          {audit.length === 0 && <p className="muted">Nothing recorded yet.</p>}
          <ul>
            {audit.map((entry) => (
              <li key={entry.id}>
                <strong>{entry.action}</strong> by {entry.operator} at {entry.recorded_at}
                {entry.reason ? ` — ${entry.reason}` : ''}
                {Array.isArray(entry.changed_fields) && entry.changed_fields.length > 0
                  ? ` [${entry.changed_fields.join(', ')}]`
                  : ''}
              </li>
            ))}
          </ul>
        </div>
      )}

      {deleteTarget && (
        <div className="admin-danger" role="dialog" aria-modal="true">
          <h3>Permanently delete record {deleteTarget.id}</h3>
          <p>
            <strong>{deleteTarget.title}</strong> ({deleteTarget.country})
          </p>
          <p className="muted">
            This cannot be undone from the admin surface, and it is refused if anything depends on
            the record. The change trail keeps the row&rsquo;s full contents either way.
          </p>
          {blockedBy.length > 0 && (
            <p className="form-error" role="alert">
              Refused: the following depend on this record and must survive it: {blockedBy.join(', ')}
            </p>
          )}
          <label>
            Type exactly <code>DELETE {deleteTarget.id}</code>
            <input value={deleteConfirm} onChange={(event) => setDeleteConfirm(event.target.value)} />
          </label>
          <label>
            Reason (recorded with the deletion)
            <input value={deleteReason} onChange={(event) => setDeleteReason(event.target.value)} />
          </label>
          <div className="admin-form-actions">
            <button
              className="glass-btn glass-btn--review"
              type="button"
              disabled={deleteConfirm !== `DELETE ${deleteTarget.id}` || deleteReason.trim() === ''}
              onClick={runDelete}
            >
              Delete permanently
            </button>
            <button className="glass-btn glass-btn--ghost" type="button" onClick={() => setDeleteTarget(null)}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </section>
  )
}

export default AdminScholarshipManager
