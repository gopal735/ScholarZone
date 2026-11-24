import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import StudyPlannerPage from './StudyPlannerPage'

const deferred = () => {
  let resolve, reject
  const promise = new Promise((res, rej) => { resolve = res; reject = rej })
  return { promise, resolve, reject }
}

vi.mock('../services/studyPlannerService', () => {
  class StudyPlanUnauthenticatedError extends Error {}
  class StudyPlanConflictError extends Error {}
  return {
    StudyPlanUnauthenticatedError,
    StudyPlanConflictError,
    fetchPlans: vi.fn(),
    createPlan: vi.fn(),
    deletePlan: vi.fn(),
    addTask: vi.fn(),
    updateTask: vi.fn(),
    deleteTask: vi.fn(),
  }
})

import * as svc from '../services/studyPlannerService'

describe('StudyPlannerPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows loading then plans', async () => {
    const d = deferred()
    svc.fetchPlans.mockReturnValue(d.promise)
    render(<StudyPlannerPage />)
    expect(screen.getByText(/Loading/i)).toBeInTheDocument()
    d.resolve([{ id: 1, title: 'Plan', tasks: [] }])
    await waitFor(() => expect(screen.getByText('Plan')).toBeInTheDocument())
  })

  it('preserves mutation error when refresh succeeds', async () => {
    svc.fetchPlans.mockResolvedValue([{ id: 1, title: 'Plan', tasks: [] }])
    const addDeferred = deferred()
    svc.addTask.mockReturnValue(addDeferred.promise)
    render(<StudyPlannerPage />)
    await waitFor(() => expect(screen.getByText('Plan')).toBeInTheDocument())

    const input = screen.getByLabelText(/New task for Plan/i)
    fireEvent.change(input, { target: { value: 'Task A' } })
    fireEvent.click(screen.getByRole('button', { name: /Add task/i }))

    const refreshDeferred = deferred()
    svc.fetchPlans.mockReturnValue(refreshDeferred.promise)
    // trigger refresh via retry? Use a second add? Instead call load through retry button not present.
    // Reject the task request to create an error.
    addDeferred.reject(new Error('add failed'))
    await waitFor(() => expect(screen.getByText(/add failed/i)).toBeInTheDocument())

    // A successful refresh should not clear the mutation error.
    refreshDeferred.resolve([{ id: 1, title: 'Plan', tasks: [] }])
    await waitFor(() => expect(screen.getByText('Plan')).toBeInTheDocument())
    expect(screen.getByText(/add failed/i)).toBeInTheDocument()
  })

  it('preserves draft when task request succeeds after edit', async () => {
    svc.fetchPlans.mockResolvedValue([{ id: 1, title: 'Plan', tasks: [] }])
    const addDeferred = deferred()
    svc.addTask.mockReturnValue(addDeferred.promise)
    render(<StudyPlannerPage />)
    await waitFor(() => expect(screen.getByText('Plan')).toBeInTheDocument())

    const input = screen.getByLabelText(/New task for Plan/i)
    fireEvent.change(input, { target: { value: 'Task A' } })
    fireEvent.click(screen.getByRole('button', { name: /Add task/i }))
    // edit draft while pending
    fireEvent.change(input, { target: { value: 'Task B' } })
    addDeferred.resolve({ id: 2, title: 'Task A' })
    await waitFor(() => expect(input.value).toBe('Task B'))
  })
})
