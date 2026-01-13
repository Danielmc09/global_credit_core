import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ApplicationList from '../components/ApplicationList'
import { applicationAPI } from '../services/api'
import websocketService from '../services/websocket'

// Mock modules
vi.mock('../services/api', () => ({
  applicationAPI: {
    getApplications: vi.fn(),
  },
}))

vi.mock('../services/websocket', () => ({
  default: {
    addListener: vi.fn(),
    removeListener: vi.fn(),
    isConnected: vi.fn(() => true),
    connect: vi.fn(),
  },
}))

vi.mock('../components/ApplicationDetail', () => ({
  default: ({ applicationId, onClose }) => (
    <div data-testid="application-detail-modal">
      <div>Modal for {applicationId}</div>
      <button onClick={onClose}>Close Modal</button>
    </div>
  ),
}))

describe('ApplicationList', () => {
  const mockApplications = [
    {
      id: 'app-123-abc',
      country: 'ES',
      full_name: 'Juan García López',
      identity_document: '12345678Z',
      requested_amount: 15000,
      status: 'APPROVED',
      risk_score: 25.5,
      created_at: '2024-01-15T10:30:00Z',
      updated_at: '2024-01-15T10:35:00Z',
    },
    {
      id: 'app-456-def',
      country: 'MX',
      full_name: 'María Hernández',
      identity_document: 'HERM850101MDFRRR01',
      requested_amount: 50000,
      status: 'PENDING',
      risk_score: null,
      created_at: '2024-01-15T11:00:00Z',
      updated_at: '2024-01-15T11:00:00Z',
    },
  ]

  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
    applicationAPI.getApplications.mockResolvedValue({
      total: 2,
      page: 1,
      page_size: 20,
      applications: mockApplications,
    })
  })

  afterEach(() => {
    vi.runOnlyPendingTimers()
    vi.useRealTimers()
  })

  it('renders loading state initially', () => {
    render(<ApplicationList />)
    expect(screen.getByText('Loading applications...')).toBeInTheDocument()
  })

  it('loads and displays applications', async () => {
    render(<ApplicationList />)

    await waitFor(() => {
      expect(applicationAPI.getApplications).toHaveBeenCalledWith({
        country: '',
        status: '',
        page: 1,
        page_size: 20,
      })
    })

    expect(await screen.findByText('Juan García López')).toBeInTheDocument()
    expect(screen.getByText('María Hernández')).toBeInTheDocument()
    expect(screen.getByText('12345678Z')).toBeInTheDocument()
    expect(screen.getByText('HERM850101MDFRRR01')).toBeInTheDocument()
  })

  it('displays empty state when no applications', async () => {
    applicationAPI.getApplications.mockResolvedValue({
      total: 0,
      page: 1,
      page_size: 20,
      applications: []
    })

    render(<ApplicationList />)

    expect(await screen.findByText('No applications found')).toBeInTheDocument()
  })

  it('displays error state when API fails', async () => {
    applicationAPI.getApplications.mockRejectedValue(new Error('API Error'))

    render(<ApplicationList />)

    expect(await screen.findByText('Error loading applications')).toBeInTheDocument()
  })

  it('filters applications by country', async () => {
    const user = userEvent.setup({ delay: null })
    render(<ApplicationList />)

    await screen.findByText('Juan García López')

    const countryFilter = screen.getByDisplayValue('All Countries')
    await user.selectOptions(countryFilter, 'ES')

    await waitFor(() => {
      expect(applicationAPI.getApplications).toHaveBeenCalledWith({
        country: 'ES',
        status: '',
        page: 1,
        page_size: 20,
      })
    })
  })

  it('filters applications by status', async () => {
    const user = userEvent.setup({ delay: null })
    render(<ApplicationList />)

    await screen.findByText('Juan García López')

    const statusFilter = screen.getByDisplayValue('All Statuses')
    await user.selectOptions(statusFilter, 'APPROVED')

    await waitFor(() => {
      expect(applicationAPI.getApplications).toHaveBeenCalledWith({
        country: '',
        status: 'APPROVED',
        page: 1,
        page_size: 20,
      })
    })
  })

  it('refreshes applications when refresh button is clicked', async () => {
    const user = userEvent.setup({ delay: null })
    render(<ApplicationList />)

    await screen.findByText('Juan García López')

    applicationAPI.getApplications.mockClear()

    const refreshButton = screen.getByRole('button', { name: /Refresh/i })
    await user.click(refreshButton)

    await waitFor(() => {
      expect(applicationAPI.getApplications).toHaveBeenCalledTimes(1)
    })
  })

  it('displays status badges with correct styling', async () => {
    render(<ApplicationList />)

    const approvedBadge = await screen.findByText('APPROVED')
    const pendingBadge = screen.getByText('PENDING')

    expect(approvedBadge).toHaveClass('badge', 'badge-approved')
    expect(pendingBadge).toHaveClass('badge', 'badge-pending')
  })

  it('formats currency correctly', async () => {
    render(<ApplicationList />)

    await screen.findByText('Juan García López')

    // Check for formatted currency (should be $15,000.00 and $50,000.00)
    expect(screen.getByText('$15,000.00')).toBeInTheDocument()
    expect(screen.getByText('$50,000.00')).toBeInTheDocument()
  })

  it('displays risk score with color coding', async () => {
    render(<ApplicationList />)

    await screen.findByText('Juan García López')

    const riskScore = screen.getByText('25.5')
    expect(riskScore).toHaveStyle({ color: '#0f5132' }) // Low risk = green
  })

  it('shows dash for missing risk score', async () => {
    render(<ApplicationList />)

    await screen.findByText('María Hernández')

    // Find the cell with the dash
    const cells = screen.getAllByRole('cell')
    const riskScoreCells = cells.filter((cell) => cell.textContent === '-')
    expect(riskScoreCells.length).toBeGreaterThan(0)
  })

  it('opens detail modal when View button is clicked', async () => {
    const user = userEvent.setup({ delay: null })
    render(<ApplicationList />)

    await screen.findByText('Juan García López')

    const viewButtons = screen.getAllByText(/👁️ View/i)
    await user.click(viewButtons[0])

    expect(screen.getByTestId('application-detail-modal')).toBeInTheDocument()
    expect(screen.getByText(/Modal for app-123-abc/i)).toBeInTheDocument()
  })

  it('closes detail modal when onClose is called', async () => {
    const user = userEvent.setup({ delay: null })
    render(<ApplicationList />)

    await screen.findByText('Juan García López')

    const viewButtons = screen.getAllByText(/👁️ View/i)
    await user.click(viewButtons[0])

    expect(screen.getByTestId('application-detail-modal')).toBeInTheDocument()

    const closeButton = screen.getByText('Close Modal')
    await user.click(closeButton)

    await waitFor(() => {
      expect(screen.queryByTestId('application-detail-modal')).not.toBeInTheDocument()
    })
  })

  it('registers WebSocket listener on mount', () => {
    render(<ApplicationList />)

    expect(websocketService.addListener).toHaveBeenCalledTimes(1)
    expect(websocketService.addListener).toHaveBeenCalledWith(expect.any(Function))
  })

  it('unregisters WebSocket listener on unmount', () => {
    const { unmount } = render(<ApplicationList />)

    unmount()

    expect(websocketService.removeListener).toHaveBeenCalledTimes(1)
    expect(websocketService.removeListener).toHaveBeenCalledWith(expect.any(Function))
  })

  it('updates application when WebSocket message is received', async () => {
    render(<ApplicationList />)

    await screen.findByText('Juan García López')

    // Get the WebSocket listener function
    const listener = websocketService.addListener.mock.calls[0][0]

    // Simulate WebSocket update
    listener({
      type: 'application_update',
      data: {
        id: 'app-123-abc',
        status: 'REJECTED',
        risk_score: 85.3,
        updated_at: '2024-01-15T12:00:00Z',
      },
    })

    // Wait for the update to be reflected
    await waitFor(() => {
      expect(screen.getByText('REJECTED')).toBeInTheDocument()
      expect(screen.getByText('85.3')).toBeInTheDocument()
    })
  })

  it('highlights updated application row temporarily', async () => {
    render(<ApplicationList />)

    await screen.findByText('Juan García López')

    const listener = websocketService.addListener.mock.calls[0][0]

    // Simulate WebSocket update
    listener({
      type: 'application_update',
      data: {
        id: 'app-123-abc',
        status: 'UNDER_REVIEW',
        risk_score: 45.0,
        updated_at: '2024-01-15T12:00:00Z',
      },
    })

    // Row should have highlight class
    await waitFor(() => {
      const rows = screen.getAllByRole('row')
      const highlightedRow = rows.find((row) => row.className.includes('highlight'))
      expect(highlightedRow).toBeDefined()
    })

    // After 2 seconds, highlight should be removed
    vi.advanceTimersByTime(2000)

    await waitFor(() => {
      const rows = screen.getAllByRole('row')
      const highlightedRow = rows.find((row) => row.className.includes('highlight'))
      expect(highlightedRow).toBeUndefined()
    })
  })

  it('displays pagination information', async () => {
    render(<ApplicationList />)

    await screen.findByText('Juan García López')

    expect(screen.getByText('Showing 1-2 of 2 application(s)')).toBeInTheDocument()
  })

  it('truncates application ID in display', async () => {
    render(<ApplicationList />)

    await screen.findByText('Juan García López')

    expect(screen.getByText('app-123-...')).toBeInTheDocument()
    expect(screen.getByText('app-456-...')).toBeInTheDocument()
  })

  it('reloads applications when refreshTrigger prop changes', async () => {
    const { rerender } = render(<ApplicationList refreshTrigger={1} />)

    await screen.findByText('Juan García López')

    applicationAPI.getApplications.mockClear()

    rerender(<ApplicationList refreshTrigger={2} />)

    await waitFor(() => {
      expect(applicationAPI.getApplications).toHaveBeenCalledTimes(1)
    })
  })

  it('handles multiple WebSocket updates correctly', async () => {
    render(<ApplicationList />)

    await screen.findByText('Juan García López')

    const listener = websocketService.addListener.mock.calls[0][0]

    // First update
    listener({
      type: 'application_update',
      data: {
        id: 'app-123-abc',
        status: 'VALIDATING',
        risk_score: null,
        updated_at: '2024-01-15T12:00:00Z',
      },
    })

    await waitFor(() => {
      expect(screen.getByText('VALIDATING')).toBeInTheDocument()
    })

    // Second update to different application
    listener({
      type: 'application_update',
      data: {
        id: 'app-456-def',
        status: 'APPROVED',
        risk_score: 30.2,
        updated_at: '2024-01-15T12:01:00Z',
      },
    })

    await waitFor(() => {
      expect(screen.getAllByText('APPROVED')).toHaveLength(1)
      expect(screen.getByText('30.2')).toBeInTheDocument()
    })
  })

  // Pagination tests
  describe('Pagination controls', () => {
    it('renders pagination controls when applications are loaded', async () => {
      render(<ApplicationList />)

      await screen.findByText('Juan García López')

      expect(screen.getByLabelText('Records per page:')).toBeInTheDocument()
      expect(screen.getByText(/Page 1 of 1/i)).toBeInTheDocument()
      expect(screen.getByTitle('First page')).toBeInTheDocument()
      expect(screen.getByTitle('Previous page')).toBeInTheDocument()
      expect(screen.getByTitle('Next page')).toBeInTheDocument()
      expect(screen.getByTitle('Last page')).toBeInTheDocument()
    })

    it('changes page when next button is clicked', async () => {
      const user = userEvent.setup({ delay: null })
      // Mock a response with more pages
      applicationAPI.getApplications.mockResolvedValue({
        total: 50,
        page: 1,
        page_size: 20,
        applications: mockApplications,
      })

      render(<ApplicationList />)

      await screen.findByText('Juan García López')

      const nextButton = screen.getByTitle('Next page')
      await user.click(nextButton)

      await waitFor(() => {
        expect(applicationAPI.getApplications).toHaveBeenCalledWith(
          expect.objectContaining({
            page: 2,
            page_size: 20,
          })
        )
      })
    })

    it('changes page when previous button is clicked', async () => {
      const user = userEvent.setup({ delay: null })
      // Start on page 2
      applicationAPI.getApplications.mockResolvedValue({
        total: 50,
        page: 2,
        page_size: 20,
        applications: mockApplications,
      })

      render(<ApplicationList />)

      await screen.findByText('Juan García López')

      const prevButton = screen.getByTitle('Previous page')
      await user.click(prevButton)

      await waitFor(() => {
        expect(applicationAPI.getApplications).toHaveBeenCalledWith(
          expect.objectContaining({
            page: 1,
            page_size: 20,
          })
        )
      })
    })

    it('changes page size when selector value changes', async () => {
      const user = userEvent.setup({ delay: null })
      render(<ApplicationList />)

      await screen.findByText('Juan García López')

      const pageSizeSelect = screen.getByLabelText('Records per page:')
      await user.selectOptions(pageSizeSelect, '50')

      await waitFor(() => {
        expect(applicationAPI.getApplications).toHaveBeenCalledWith(
          expect.objectContaining({
            page: 1, // Should reset to page 1
            page_size: 50,
          })
        )
      })
    })

    it('disables first and previous buttons on first page', async () => {
      render(<ApplicationList />)

      await screen.findByText('Juan García López')

      const firstButton = screen.getByTitle('First page')
      const prevButton = screen.getByTitle('Previous page')

      expect(firstButton).toBeDisabled()
      expect(prevButton).toBeDisabled()
    })

    it('disables next and last buttons on last page', async () => {
      applicationAPI.getApplications.mockResolvedValue({
        total: 2,
        page: 1,
        page_size: 20,
        applications: mockApplications,
      })

      render(<ApplicationList />)

      await screen.findByText('Juan García López')

      const nextButton = screen.getByTitle('Next page')
      const lastButton = screen.getByTitle('Last page')

      expect(nextButton).toBeDisabled()
      expect(lastButton).toBeDisabled()
    })

    it('resets to page 1 when filters change', async () => {
      const user = userEvent.setup({ delay: null })

      // Start on page 2
      applicationAPI.getApplications.mockResolvedValue({
        total: 100,
        page: 2,
        page_size: 20,
        applications: mockApplications,
      })

      render(<ApplicationList />)

      await screen.findByText('Juan García López')

      // Change filter
      const countryFilter = screen.getByDisplayValue('All Countries')
      await user.selectOptions(countryFilter, 'ES')

      await waitFor(() => {
        expect(applicationAPI.getApplications).toHaveBeenCalledWith(
          expect.objectContaining({
            page: 1, // Should reset to page 1
            country: 'ES',
          })
        )
      })
    })
  })
})
