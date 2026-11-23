import { useCallback, useEffect, useRef, useState } from 'react'
import {
  StudyPlanUnauthenticatedError,
  StudyPlanConflictError,
  fetchPlans,
  createPlan,
  deletePlan,
  addTask,
  updateTask,
  deleteTask,
} from '../services/studyPlannerService'
import './StudyPlannerPage.css'

const PAGE_STATUS = Object.freeze({ LOADING: 'loading', READY: 'ready', ERROR: 'error', UNAUTH: 'unauth' })

export default function StudyPlannerPage() {
  const [status, setStatus] = useState(PAGE_STATUS.LOADING)
  const [plans, setPlans] = useState([])
  const [error, setError] = useState(null)
  const [newTitle, setNewTitle] = useState('')
  const [newTask, setNewTask] = useState({})
  const [pending, setPending] = useState({ plans: false, tasks: {} })
  const requestIdRef = useRef(0)

  const load = useCallback(async () => {
    const thisRequest = ++requestIdRef.current
    setStatus(PAGE_STATUS.LOADING)
    try {
      const data = await fetchPlans()
      if (thisRequest !== requestIdRef.current) return
      setPlans(data)
      setError(null)
      setStatus(PAGE_STATUS.READY)
    } catch (caught) {
      if (thisRequest !== requestIdRef.current) return
      if (caught instanceof StudyPlanUnauthenticatedError) {
        setStatus(PAGE_STATUS.UNAUTH)
        return
      }
      setError(caught)
      setStatus(PAGE_STATUS.ERROR)
    }
  }, [])

  useEffect(() => {
    const id = setTimeout(() => { void load() }, 0)
    return () => clearTimeout(id)
  }, [load])

  const handleCreatePlan = async (e) => {
    e.preventDefault()
    if (!newTitle.trim() || pending.plans) return
    setPending((p) => ({ ...p, plans: true }))
    try {
      await createPlan({ title: newTitle.trim() })
      setNewTitle('')
      await load()
    } catch (caught) { setError(caught) }
    finally { setPending((p) => ({ ...p, plans: false })) }
  }

  const handleDeletePlan = async (id) => {
    if (pending.plans) return
    setPending((p) => ({ ...p, plans: true }))
    try { await deletePlan(id); await load() } catch (caught) { setError(caught) }
    finally { setPending((p) => ({ ...p, plans: false })) }
  }

  const handleAddTask = async (planId) => {
    const title = (newTask[planId] || '').trim()
    if (!title || pending.tasks[planId]) return
    setPending((p) => ({ ...p, tasks: { ...p.tasks, [planId]: true } }))
    try {
      await addTask(planId, { title })
      setNewTask((s) => ({ ...s, [planId]: '' }))
      await load()
    } catch (caught) { setError(caught) }
    finally { setPending((p) => ({ ...p, tasks: { ...p.tasks, [planId]: false } })) }
  }

  const handleToggleTask = async (task) => {
    try {
      await updateTask(task.id, { status: task.status === 'completed' ? 'reopened' : 'completed', version: task.version })
      await load()
    } catch (caught) {
      if (caught instanceof StudyPlanConflictError) {
        await load()
        setError(caught)
        return
      }
      setError(caught)
    }
  }

  const handleDeleteTask = async (id) => {
    try { await deleteTask(id); await load() } catch (caught) { setError(caught) }
  }

  if (status === PAGE_STATUS.LOADING) return <div className="sp-page"><p>Loading…</p></div>
  if (status === PAGE_STATUS.UNAUTH) return <div className="sp-page"><p>Please sign in to use the study planner.</p></div>
  if (status === PAGE_STATUS.ERROR) return <div className="sp-page"><p>Error: {String(error)}</p><button onClick={load}>Retry</button></div>

  return (
    <div className="sp-page">
      <h1>Study Planner</h1>
      <form onSubmit={handleCreatePlan} className="sp-create">
        <input aria-label="New plan title" value={newTitle} onChange={(e) => setNewTitle(e.target.value)} placeholder="New plan title" />
        <button type="submit">Create plan</button>
      </form>
      {error && <p className="sp-error">{String(error)}</p>}
      {plans.length === 0 && <p>No plans yet.</p>}
      {plans.map((plan) => (
        <div key={plan.id} className="sp-plan">
          <div className="sp-plan-header">
            <h2>{plan.title}</h2>
            <button onClick={() => handleDeletePlan(plan.id)}>Delete</button>
          </div>
          <ul>
            {(plan.tasks || []).map((t) => (
              <li key={t.id} className={t.status === 'completed' ? 'done' : ''}>
                <label>
                  <input type="checkbox" checked={t.status === 'completed'} onChange={() => handleToggleTask(t)} />
                  {t.title}
                </label>
                <button onClick={() => handleDeleteTask(t.id)}>×</button>
              </li>
            ))}
          </ul>
          <div className="sp-add-task">
            <input
              aria-label={`New task for ${plan.title}`}
              value={newTask[plan.id] || ''}
              onChange={(e) => setNewTask((s) => ({ ...s, [plan.id]: e.target.value }))}
              placeholder="New task"
            />
            <button onClick={() => handleAddTask(plan.id)}>Add task</button>
          </div>
        </div>
      ))}
    </div>
  )
}
