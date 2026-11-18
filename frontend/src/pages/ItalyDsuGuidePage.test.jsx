import { render, screen, fireEvent, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi, afterEach } from 'vitest'
import ItalyDsuGuidePage from './ItalyDsuGuidePage'

const renderPage = (options = {}) => {
  const { initialTime } = options
  if (initialTime) {
    vi.setSystemTime(new Date(initialTime))
  }
  return render(
    <MemoryRouter>
      <ItalyDsuGuidePage />
    </MemoryRouter>,
  )
}

const getRegionTable = () => {
  const tables = screen.getAllByRole('table')
  return tables.find(t => t.classList.contains('italy-dsu-guide__region-table') || t.querySelector('.italy-dsu-guide__region-table'))
}
const getHeader = () => screen.getByRole('banner').closest('header')
const getMain = () => screen.getByRole('main')

describe('ItalyDsuGuidePage - date boundary and status calculation', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('derives statuses from Europe/Rome time, not hardcoded values', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-11-18T14:00:00Z'))

    renderPage()

    const header = getHeader()
    const statusBar = header.querySelector('.italy-dsu-guide__status-bar')
    const openBadge = statusBar.querySelector('.status-pill--open')
    expect(openBadge).toBeInTheDocument()

    const openCount = parseInt(openBadge.textContent.match(/\d+/)[0], 10)
    expect(openCount).toBeGreaterThan(0)
  })

  it('shows Valle d\'Aosta as open when deadline is 4 Dec 2026 and current time is before that', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-11-20T10:00:00Z'))

    renderPage()

    const table = getRegionTable()
    const vdaRow = table.querySelector('#valle-aosta')
    expect(vdaRow).toHaveClass('status-open')
    expect(within(vdaRow).getByText('OPEN')).toBeInTheDocument()
  })

  it('shows Trento as open when PhD deadline is 30 Nov 2026 and current time is before that', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-11-20T10:00:00Z'))

    renderPage()

    const table = getRegionTable()
    const trentoRow = table.querySelector('#trentino-trento')
    expect(trentoRow).toHaveClass('status-open')
    expect(within(trentoRow).getByText('OPEN')).toBeInTheDocument()
  })

  it('shows Bolzano as closed when deadline is 3 Nov 2026 and current time is after that', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-11-20T10:00:00Z'))

    renderPage()

    const table = getRegionTable()
    const bolzanoRow = table.querySelector('#trentino-bolzano')
    expect(bolzanoRow).toHaveClass('status-closed')
    expect(within(bolzanoRow).getByText('CLOSED')).toBeInTheDocument()
  })

  it('shows status bar with Europe/Rome timezone timestamp', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-11-18T14:00:00Z'))

    renderPage()

    const statusNote = screen.getByText(/As of .* \(Europe\/Rome\)/)
    expect(statusNote).toBeInTheDocument()
  })
})

describe('ItalyDsuGuidePage - search functionality', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-11-18T14:00:00Z'))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('shows matching region when searching by university', () => {
    renderPage()

    const searchInput = screen.getByPlaceholderText(/Search regions, agencies, universities/i)
    fireEvent.change(searchInput, { target: { value: 'Bologna' } })

    const sidebar = screen.getByRole('navigation', { name: /Guide sections/i })
    const items = sidebar.querySelectorAll('li')
    expect(items.length).toBe(1)
    const itemText = items[0].textContent
    expect(itemText).toContain('Emilia-Romagna')
  })

  it('shows matching region when searching by agency', () => {
    renderPage()

    const searchInput = screen.getByPlaceholderText(/Search regions, agencies, universities/i)
    fireEvent.change(searchInput, { target: { value: 'ER.GO' } })

    const sidebar = screen.getByRole('navigation', { name: /Guide sections/i })
    const items = sidebar.querySelectorAll('li')
    expect(items.length).toBe(1)
    const itemText = items[0].textContent
    expect(itemText).toContain('Emilia-Romagna')
  })

  it('shows matching region name in search results', () => {
    renderPage()

    const searchInput = screen.getByPlaceholderText(/Search regions, agencies, universities/i)
    fireEvent.change(searchInput, { target: { value: 'Lazio' } })

    const sidebar = screen.getByRole('navigation', { name: /Guide sections/i })
    const items = sidebar.querySelectorAll('li')
    expect(items.length).toBe(1)
    const itemText = items[0].textContent
    expect(itemText).toContain('Lazio')
  })

  it('filters unrelated rows from search results', () => {
    renderPage()

    const searchInput = screen.getByPlaceholderText(/Search regions, agencies, universities/i)
    fireEvent.change(searchInput, { target: { value: 'Trento' } })

    const sidebar = screen.getByRole('navigation', { name: /Guide sections/i })
    const items = sidebar.querySelectorAll('li')
    expect(items.length).toBe(1)
    const itemText = items[0].textContent
    expect(itemText).toContain('Trentino (Trento)')
    expect(itemText).not.toContain('Alto Adige')
    expect(itemText).not.toContain('Bolzano')
  })

  it('filters out closed regions when Open Only filter is selected', () => {
    renderPage()

    const filterSelect = screen.getByLabelText(/Filter by status/i)
    fireEvent.change(filterSelect, { target: { value: 'open' } })

    const sidebar = screen.getByRole('navigation', { name: /Guide sections/i })
    const items = sidebar.querySelectorAll('li')
    items.forEach(item => {
      expect(item.querySelector('.status-open')).toBeInTheDocument()
      expect(item.querySelector('.status-closed')).not.toBeInTheDocument()
    })
  })

  it('shows all regions when All Regions filter is selected', () => {
    renderPage()

    const filterSelect = screen.getByLabelText(/Filter by status/i)
    fireEvent.change(filterSelect, { target: { value: 'all' } })

    const sidebar = screen.getByRole('navigation', { name: /Guide sections/i })
    expect(sidebar.querySelectorAll('li').length).toBe(21)
  })

  it('shows only closed regions when Closed filter is selected', () => {
    renderPage()

    const filterSelect = screen.getByLabelText(/Filter by status/i)
    fireEvent.change(filterSelect, { target: { value: 'closed' } })

    const sidebar = screen.getByRole('navigation', { name: /Guide sections/i })
    const items = sidebar.querySelectorAll('li')
    items.forEach(item => {
      expect(item.querySelector('.status-closed')).toBeInTheDocument()
      expect(item.querySelector('.status-open')).not.toBeInTheDocument()
    })
  })

  it('search and filter work together', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-11-20T10:00:00Z'))

    renderPage()

    const filterSelect = screen.getByLabelText(/Filter by status/i)
    fireEvent.change(filterSelect, { target: { value: 'open' } })

    const searchInput = screen.getByPlaceholderText(/Search regions, agencies, universities/i)
    fireEvent.change(searchInput, { target: { value: 'Trento' } })

    const sidebar = screen.getByRole('navigation', { name: /Guide sections/i })
    const items = sidebar.querySelectorAll('li')
    expect(items.length).toBe(1)
    const itemText = items[0].textContent
    expect(itemText).toContain('Trentino (Trento)')
    expect(itemText).not.toContain('Alto Adige')
  })
})

describe('ItalyDsuGuidePage - accessibility and navigation', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-11-18T14:00:00Z'))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('does not use invalid role=listbox on normal list links', () => {
    renderPage()

    const regionList = document.querySelector('.italy-dsu-guide__region-list')
    expect(regionList).toBeInTheDocument()
    expect(regionList).not.toHaveAttribute('role', 'listbox')
  })

  it('uses native list navigation with role=list', () => {
    renderPage()

    const regionList = document.querySelector('.italy-dsu-guide__region-list')
    expect(regionList).toHaveAttribute('role', 'list')
    const listItems = regionList.querySelectorAll('[role="listitem"]')
    expect(listItems.length).toBe(21)

    listItems.forEach(item => {
      const link = item.querySelector('a')
      expect(link).toBeInTheDocument()
    })
  })

  it('region notes appear in relevant rows in sidebar', () => {
    renderPage()

    const sidebar = screen.getByRole('navigation', { name: /Guide sections/i })
    const trentoItem = sidebar.querySelector('a[href="#trentino-trento"]').closest('li')
    expect(trentoItem).toHaveTextContent(/Non-EU non-residents EXCLUDED/)

    const bolzanoItem = sidebar.querySelector('a[href="#trentino-bolzano"]').closest('li')
    expect(bolzanoItem).toHaveTextContent(/Separate provincial call/)

    const piemonteItem = sidebar.querySelector('a[href="#piemonte"]').closest('li')
    expect(piemonteItem).toHaveTextContent(/PhD\/Specialisation window open/)
  })

  it('region notes appear in relevant rows in main table', () => {
    renderPage()

    const table = getRegionTable()
    const trentoRow = table.querySelector('#trentino-trento')
    expect(trentoRow).toHaveTextContent(/Non-EU non-residents EXCLUDED/)

    const bolzanoRow = table.querySelector('#trentino-bolzano')
    expect(bolzanoRow).toHaveTextContent(/Separate provincial call/)

    const piemonteRow = table.querySelector('#piemonte')
    expect(piemonteRow).toHaveTextContent(/PhD\/Specialisation window open/)
  })

  it('search input has proper aria-label and aria-describedby', () => {
    renderPage()

    const searchInput = screen.getByPlaceholderText(/Search regions, agencies, universities/i)
    expect(searchInput).toHaveAttribute('aria-label', 'Search regions')
    expect(searchInput).toHaveAttribute('aria-describedby', 'search-hint')
  })

  it('filter select has proper aria-label', () => {
    renderPage()

    const filterSelect = screen.getByLabelText(/Filter by status/i)
    expect(filterSelect).toHaveAttribute('aria-label', 'Filter by status')
  })

  it('region buttons have proper aria-label with status', () => {
    renderPage()

    const valleAostaBtn = screen.getByRole('link', { name: /Valle d'Aosta — OPEN/ })
    expect(valleAostaBtn).toHaveAttribute('aria-label', "Valle d'Aosta — OPEN")
  })
})

describe('ItalyDsuGuidePage - regional eligibility separation', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-11-20T10:00:00Z'))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('keeps Trento Opera Universitaria restriction visible and separate from Bolzano', () => {
    renderPage()

    const table = getRegionTable()
    const trentoRow = table.querySelector('#trentino-trento')
    expect(trentoRow).toHaveTextContent(/Non-EU non-residents EXCLUDED from Opera Universitaria call/)

    const bolzanoRow = table.querySelector('#trentino-bolzano')
    expect(bolzanoRow).toHaveTextContent(/Separate provincial call; uses DURP and VSE/)
    expect(bolzanoRow.textContent).not.toContain('Non-EU non-residents EXCLUDED')
  })

  it('does not apply Trento restriction to Bolzano in warnings section', () => {
    renderPage()

    const warningsSection = getMain().querySelector('#warnings')
    expect(warningsSection).toHaveTextContent(/Trentino \(Trento\) excludes non-resident non-EU/)
    expect(warningsSection).toHaveTextContent(/Alto Adige \(Bolzano\) has a separate provincial call/)
  })

  it('has separate agencies for Trento and Bolzano', () => {
    renderPage()

    const table = getRegionTable()
    const trentoRow = table.querySelector('#trentino-trento')
    expect(trentoRow).toHaveTextContent('Opera Universitaria Trento')

    const bolzanoRow = table.querySelector('#trentino-bolzano')
    expect(bolzanoRow).toHaveTextContent('Province of Bolzano (separate call)')
  })

  it('has separate universities for Trento and Bolzano', () => {
    renderPage()

    const table = getRegionTable()
    const trentoRow = table.querySelector('#trentino-trento')
    expect(trentoRow).toHaveTextContent('Università di Trento')

    const bolzanoRow = table.querySelector('#trentino-bolzano')
    expect(bolzanoRow).toHaveTextContent('Free University of Bozen-Bolzano')
  })
})

describe('ItalyDsuGuidePage - visa guidance without editorial text', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-11-18T14:00:00Z'))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('does not contain hardcoded "only VDA is open" claim', () => {
    renderPage()

    const pageText = getMain().textContent
    expect(pageText).not.toMatch(/only VDA is open/i)
    expect(pageText).not.toMatch(/only Valle d'Aosta is open/i)
  })

  it('visa guidance does not claim DSU award meets minimum means', () => {
    renderPage()

    const visaSection = getMain().querySelector('#visa')
    const visaText = visaSection.textContent

    expect(visaText).not.toMatch(/meets the minimum/i)
    expect(visaText).not.toMatch(/award meets.*minimum/i)
    expect(visaText).toMatch(/may not meet this threshold alone/i)
    expect(visaText).toMatch(/Consult your consulate/i)
  })

  it('visa guidance does not imply eligibility guarantees award', () => {
    renderPage()

    const visaSection = getMain().querySelector('#visa')
    const visaText = visaSection.textContent

    expect(visaText).toMatch(/DSU eligibility does not guarantee a scholarship/i)
    expect(visaText).toMatch(/final award is not guaranteed/i)
    expect(visaText).toMatch(/eligible non-winners receive services only/i)
  })

  it('checklist section does not imply guaranteed award', () => {
    renderPage()

    const checklistSection = getMain().querySelector('#checklist')
    const checklistText = checklistSection.textContent

    expect(checklistText).not.toMatch(/guaranteed.*scholarship/i)
    expect(checklistText).not.toMatch(/will receive.*cash/i)
  })
})

describe('ItalyDsuGuidePage - counts, status badges, and rows agreement', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-11-20T10:00:00Z'))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('open count in status bar matches open rows in region table', () => {
    renderPage()

    const header = getHeader()
    const statusBar = header.querySelector('.italy-dsu-guide__status-bar')
    const openBadge = statusBar.querySelector('.status-pill--open')
    const openCount = parseInt(openBadge.textContent.match(/\d+/)[0], 10)

    const table = getRegionTable()
    const tableOpenBadges = table.querySelectorAll('.status-badge.status-open')
    expect(tableOpenBadges.length).toBe(openCount)
  })

  it('closed count in status bar matches closed rows in region table', () => {
    renderPage()

    const header = getHeader()
    const statusBar = header.querySelector('.italy-dsu-guide__status-bar')
    const closedBadge = statusBar.querySelector('.status-pill--closed')
    const closedCount = parseInt(closedBadge.textContent.match(/\d+/)[0], 10)

    const table = getRegionTable()
    const tableClosedBadges = table.querySelectorAll('.status-badge.status-closed')
    expect(tableClosedBadges.length).toBe(closedCount)
  })

  it('sidebar region count matches table row count for each status', () => {
    renderPage()

    const sidebar = screen.getByRole('navigation', { name: /Guide sections/i })
    const sidebarOpenItems = sidebar.querySelectorAll('.status-open')
    const table = getRegionTable()
    const tableOpenBadges = table.querySelectorAll('.status-badge.status-open')

    expect(sidebarOpenItems.length).toBe(tableOpenBadges.length)
  })

  it('expired calls do not appear in Open Only filter', () => {
    renderPage()

    const filterSelect = screen.getByLabelText(/Filter by status/i)
    fireEvent.change(filterSelect, { target: { value: 'open' } })

    const sidebar = screen.getByRole('navigation', { name: /Guide sections/i })
    const closedBadges = sidebar.querySelectorAll('.status-closed')
    expect(closedBadges.length).toBe(0)

    const openBadges = sidebar.querySelectorAll('.status-open')
    expect(openBadges.length).toBeGreaterThan(0)
  })
})