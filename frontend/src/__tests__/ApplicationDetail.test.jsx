import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ApplicationDetail from '../components/ApplicationDetail'
import { applicationAPI } from '../services/api'

// Mock API module
vi.mock('../services/api', () => ({
  applicationAPI: {
    getApplication: vi.fn(),
    getAuditLogs: vi.fn(),
    updateApplication: vi.fn(),
  },
}))

describe('ApplicationDetail', () => {
  const mockApplication = {
    id: 'app-123-abc-def',
    country: 'ES',
    full_name: 'Juan García López',
    identity_document: '12345678Z',
    requested_amount: 15000,
    monthly_income: 3500,
    status: 'APPROVED',
    risk_score: 25.5,
    created_at: '2024-01-15T10:30:00Z',
    updated_at: '2024-01-15T10:35:00Z',
    banking_data: {
      provider_name: 'Mock Banking Provider',
      credit_score: 750,
      total_debt: 5000,
      monthly_obligations: 800,
      has_defaults: false,
    },
    validation_errors: ['High debt-to-income ratio'],
  }

  const mockAuditLogs = [
    {
      id: 'audit-1',
      application_id: 'app-123-abc-def',
      old_status: 'PENDING',
      new_status: 'VALIDATING',
      changed_by: 'system',
      created_at: '2024-01-15T10:31:00Z',
      change_reason: null,
    },
    {
      id: 'audit-2',
      application_id: 'app-123-abc-def',
      old_status: 'VALIDATING',
      new_status: 'APPROVED',
      changed_by: 'admin',
      created_at: '2024-01-15T10:35:00Z',
      change_reason: 'Manual approval',
    },
  ]

  const mockOnClose = vi.fn()
  const mockOnUpdate = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    applicationAPI.getApplication.mockResolvedValue(mockApplication)
    applicationAPI.getAuditLogs.mockResolvedValue(mockAuditLogs)

    // Mock window.confirm and window.alert
    global.confirm = vi.fn(() => true)
    global.alert = vi.fn()
  })

  it('renders loading state initially', () => {
    render(
      <ApplicationDetail
        applicationId="app-123"
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    )

    expect(screen.getByText('Loading application details...')).toBeInTheDocument()
  })

  it('loads and displays application details', async () => {
    render(
      <ApplicationDetail
        applicationId="app-123"
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    )

    await waitFor(() => {
      expect(applicationAPI.getApplication).toHaveBeenCalledWith('app-123')
      expect(applicationAPI.getAuditLogs).toHaveBeenCalledWith('app-123')
    })

    expect(await screen.findByText('Juan García López')).toBeInTheDocument()
    expect(screen.getByText('12345678Z')).toBeInTheDocument()
    expect(screen.getByText('app-123-abc-def')).toBeInTheDocument()
    expect(screen.getByText('ES')).toBeInTheDocument()
  })

  it('displays banking information when available', async () => {
    render(
      <ApplicationDetail
        applicationId="app-123"
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    )

    await screen.findByText('Juan García López')

    expect(screen.getByText('Banking Information')).toBeInTheDocument()
    expect(screen.getByText('Mock Banking Provider')).toBeInTheDocument()
    expect(screen.getByText('750')).toBeInTheDocument()
    expect(screen.getByText('NO')).toBeInTheDocument()
  })

  it('displays assessment notes when validation errors exist', async () => {
    render(
      <ApplicationDetail
        applicationId="app-123"
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    )

    await screen.findByText('Juan García López')

    expect(screen.getByText('Assessment Notes')).toBeInTheDocument()
    expect(screen.getByText('High debt-to-income ratio')).toBeInTheDocument()
  })

  it('displays audit trail', async () => {
    render(
      <ApplicationDetail
        applicationId="app-123"
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    )

    await screen.findByText('Juan García López')

    expect(screen.getByText('Audit Trail')).toBeInTheDocument()
    expect(screen.getByText('system')).toBeInTheDocument()
    expect(screen.getByText('admin')).toBeInTheDocument()
    expect(screen.getByText('Manual approval')).toBeInTheDocument()
  })

  it('shows error state when API fails', async () => {
    applicationAPI.getApplication.mockRejectedValue(new Error('API Error'))
    applicationAPI.getAuditLogs.mockRejectedValue(new Error('API Error'))

    render(
      <ApplicationDetail
        applicationId="app-123"
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    )

    expect(await screen.findByText('Error loading application details')).toBeInTheDocument()
  })

  it('closes modal when overlay is clicked', async () => {
    const user = userEvent.setup({ delay: null })
    render(
      <ApplicationDetail
        applicationId="app-123"
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    )

    await screen.findByText('Juan García López')

    const overlay = screen.getByText('Juan García López').closest('.modal-overlay')
    await user.click(overlay)

    expect(mockOnClose).toHaveBeenCalledTimes(1)
  })

  it('closes modal when close button is clicked', async () => {
    const user = userEvent.setup({ delay: null })
    render(
      <ApplicationDetail
        applicationId="app-123"
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    )

    await screen.findByText('Juan García López')

    const closeButtons = screen.getAllByRole('button', { name: /Close/i })
    await user.click(closeButtons[0])

    expect(mockOnClose).toHaveBeenCalled()
  })

  it('does not close modal when content is clicked', async () => {
    const user = userEvent.setup({ delay: null })
    render(
      <ApplicationDetail
        applicationId="app-123"
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    )

    await screen.findByText('Juan García López')

    const content = screen.getByText('Juan García López').closest('.modal-content')
    await user.click(content)

    expect(mockOnClose).not.toHaveBeenCalled()
  })

  it('updates status when Update Status button is clicked', async () => {
    const user = userEvent.setup({ delay: null })
    applicationAPI.updateApplication.mockResolvedValue({ success: true })

    render(
      <ApplicationDetail
        applicationId="app-123"
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    )

    await screen.findByText('Juan García López')

    // Change status dropdown
    const statusSelect = screen.getByDisplayValue('APPROVED')
    await user.selectOptions(statusSelect, 'REJECTED')

    // Click update button
    const updateButton = screen.getByRole('button', { name: /Update Status/i })
    await user.click(updateButton)

    // Confirm dialog
    expect(global.confirm).toHaveBeenCalledWith(
      'Are you sure you want to change status to REJECTED?'
    )

    await waitFor(() => {
      expect(applicationAPI.updateApplication).toHaveBeenCalledWith('app-123', {
        status: 'REJECTED',
      })
    })

    expect(mockOnUpdate).toHaveBeenCalled()
    expect(global.alert).toHaveBeenCalledWith('Status updated successfully!')
  })

  it('does not update status if user cancels confirmation', async () => {
    const user = userEvent.setup({ delay: null })
    global.confirm.mockReturnValue(false)

    render(
      <ApplicationDetail
        applicationId="app-123"
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    )

    await screen.findByText('Juan García López')

    const statusSelect = screen.getByDisplayValue('APPROVED')
    await user.selectOptions(statusSelect, 'REJECTED')

    const updateButton = screen.getByRole('button', { name: /Update Status/i })
    await user.click(updateButton)

    expect(applicationAPI.updateApplication).not.toHaveBeenCalled()
  })

  it('shows alert if status is unchanged', async () => {
    const user = userEvent.setup({ delay: null })

    render(
      <ApplicationDetail
        applicationId="app-123"
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    )

    await screen.findByText('Juan García López')

    // Status is already APPROVED, try to update to APPROVED again
    const updateButton = screen.getByRole('button', { name: /Update Status/i })
    await user.click(updateButton)

    expect(global.alert).toHaveBeenCalledWith('Status is the same, no update needed')
    expect(applicationAPI.updateApplication).not.toHaveBeenCalled()
  })

  it('disables update button when status is unchanged', async () => {
    render(
      <ApplicationDetail
        applicationId="app-123"
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    )

    await screen.findByText('Juan García López')

    const updateButton = screen.getByRole('button', { name: /Update Status/i })
    expect(updateButton).toBeDisabled()
  })

  it('shows error when status update fails', async () => {
    const user = userEvent.setup({ delay: null })
    applicationAPI.updateApplication.mockRejectedValue({
      response: { data: { detail: 'Invalid status transition' } },
    })

    render(
      <ApplicationDetail
        applicationId="app-123"
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    )

    await screen.findByText('Juan García López')

    const statusSelect = screen.getByDisplayValue('APPROVED')
    await user.selectOptions(statusSelect, 'PENDING')

    const updateButton = screen.getByRole('button', { name: /Update Status/i })
    await user.click(updateButton)

    await waitFor(() => {
      expect(global.alert).toHaveBeenCalledWith(
        'Error updating status: Invalid status transition'
      )
    })
  })

  it('formats currency correctly', async () => {
    render(
      <ApplicationDetail
        applicationId="app-123"
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    )

    await screen.findByText('Juan García López')

    expect(screen.getByText('$15,000.00')).toBeInTheDocument()
    expect(screen.getByText('$3,500.00')).toBeInTheDocument()
    expect(screen.getByText('$5,000.00')).toBeInTheDocument()
    expect(screen.getByText('$800.00')).toBeInTheDocument()
  })

  it('displays risk score with color coding', async () => {
    render(
      <ApplicationDetail
        applicationId="app-123"
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    )

    await screen.findByText('Juan García López')

    const riskScore = screen.getByText(/25.5 \/ 100/i)
    expect(riskScore).toHaveStyle({ color: '#0f5132' }) // Low risk = green
  })

  it('shows dash for missing risk score', async () => {
    applicationAPI.getApplication.mockResolvedValue({
      ...mockApplication,
      risk_score: null,
    })

    render(
      <ApplicationDetail
        applicationId="app-123"
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    )

    await screen.findByText('Juan García López')

    // Find the risk score field
    const riskScoreLabel = screen.getByText('Risk Score:')
    const riskScoreValue = riskScoreLabel.nextElementSibling
    expect(riskScoreValue.textContent).toBe('-')
  })

  it('does not show banking section when data is empty', async () => {
    applicationAPI.getApplication.mockResolvedValue({
      ...mockApplication,
      banking_data: {},
    })

    render(
      <ApplicationDetail
        applicationId="app-123"
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    )

    await screen.findByText('Juan García López')

    expect(screen.queryByText('Banking Information')).not.toBeInTheDocument()
  })

  it('does not show assessment notes when no validation errors', async () => {
    applicationAPI.getApplication.mockResolvedValue({
      ...mockApplication,
      validation_errors: [],
    })

    render(
      <ApplicationDetail
        applicationId="app-123"
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    )

    await screen.findByText('Juan García López')

    expect(screen.queryByText('Assessment Notes')).not.toBeInTheDocument()
  })

  it('does not show audit trail when no logs', async () => {
    applicationAPI.getAuditLogs.mockResolvedValue([])

    render(
      <ApplicationDetail
        applicationId="app-123"
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    )

    await screen.findByText('Juan García López')

    expect(screen.queryByText('Audit Trail')).not.toBeInTheDocument()
  })

  it('reloads details after successful status update', async () => {
    const user = userEvent.setup({ delay: null })
    applicationAPI.updateApplication.mockResolvedValue({ success: true })

    render(
      <ApplicationDetail
        applicationId="app-123"
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    )

    await screen.findByText('Juan García López')

    applicationAPI.getApplication.mockClear()
    applicationAPI.getAuditLogs.mockClear()

    const statusSelect = screen.getByDisplayValue('APPROVED')
    await user.selectOptions(statusSelect, 'UNDER_REVIEW')

    const updateButton = screen.getByRole('button', { name: /Update Status/i })
    await user.click(updateButton)

    await waitFor(() => {
      expect(applicationAPI.getApplication).toHaveBeenCalledTimes(1)
      expect(applicationAPI.getAuditLogs).toHaveBeenCalledTimes(1)
    })
  })

  it('shows has_defaults as YES with red color', async () => {
    applicationAPI.getApplication.mockResolvedValue({
      ...mockApplication,
      banking_data: {
        ...mockApplication.banking_data,
        has_defaults: true,
      },
    })

    render(
      <ApplicationDetail
        applicationId="app-123"
        onClose={mockOnClose}
        onUpdate={mockOnUpdate}
      />
    )

    await screen.findByText('Juan García López')

    const yesText = screen.getByText('YES')
    expect(yesText).toHaveStyle({ color: '#842029' })
  })
})
