import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ApplicationForm from '../components/ApplicationForm'
import { applicationAPI } from '../services/api'

// Mock API module
vi.mock('../services/api', () => ({
  applicationAPI: {
    getSupportedCountries: vi.fn(),
    createApplication: vi.fn(),
  },
}))

describe('ApplicationForm', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Default mock for supported countries
    applicationAPI.getSupportedCountries.mockResolvedValue({
      supported_countries: ['ES', 'MX'],
    })
  })

  it('renders the form with all fields', async () => {
    render(<ApplicationForm />)

    expect(screen.getByText('Create Credit Application')).toBeInTheDocument()
    expect(screen.getByLabelText(/Country/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/Full Name/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/DNI/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/Requested Amount/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/Monthly Income/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Create Application/i })).toBeInTheDocument()
  })

  it('fetches supported countries on mount', async () => {
    render(<ApplicationForm />)

    await waitFor(() => {
      expect(applicationAPI.getSupportedCountries).toHaveBeenCalledTimes(1)
    })
  })

  it('changes document label when country changes', async () => {
    const user = userEvent.setup()
    render(<ApplicationForm />)

    // Initially should show DNI for Spain
    expect(screen.getByLabelText(/DNI/i)).toBeInTheDocument()
    expect(screen.getByPlaceholderText('12345678Z')).toBeInTheDocument()

    // Change to Mexico
    const countrySelect = screen.getByLabelText(/Country/i)
    await user.selectOptions(countrySelect, 'MX')

    // Should now show CURP for Mexico
    expect(screen.getByLabelText(/CURP/i)).toBeInTheDocument()
    expect(screen.getByPlaceholderText('HERM850101MDFRRR01')).toBeInTheDocument()
  })

  it('updates form data when user types', async () => {
    const user = userEvent.setup()
    render(<ApplicationForm />)

    const nameInput = screen.getByLabelText(/Full Name/i)
    const documentInput = screen.getByLabelText(/DNI/i)
    const amountInput = screen.getByLabelText(/Requested Amount/i)
    const incomeInput = screen.getByLabelText(/Monthly Income/i)

    await user.type(nameInput, 'Juan García López')
    await user.type(documentInput, '12345678Z')
    await user.type(amountInput, '15000')
    await user.type(incomeInput, '3500')

    expect(nameInput).toHaveValue('Juan García López')
    expect(documentInput).toHaveValue('12345678Z')
    expect(amountInput).toHaveValue(15000)
    expect(incomeInput).toHaveValue(3500)
  })

  it('submits form successfully and shows success message', async () => {
    const user = userEvent.setup()
    const mockResponse = {
      id: 'abc123def456',
      country: 'ES',
      full_name: 'Juan García López',
      status: 'PENDING',
    }
    applicationAPI.createApplication.mockResolvedValue(mockResponse)

    const onApplicationCreated = vi.fn()
    render(<ApplicationForm onApplicationCreated={onApplicationCreated} />)

    // Fill form
    await user.type(screen.getByLabelText(/Full Name/i), 'Juan García López')
    await user.type(screen.getByLabelText(/DNI/i), '12345678Z')
    await user.type(screen.getByLabelText(/Requested Amount/i), '15000')
    await user.type(screen.getByLabelText(/Monthly Income/i), '3500')

    // Submit
    const submitButton = screen.getByRole('button', { name: /Create Application/i })
    await user.click(submitButton)

    // Verify API was called
    await waitFor(() => {
      expect(applicationAPI.createApplication).toHaveBeenCalledWith({
        country: 'ES',
        full_name: 'Juan García López',
        identity_document: '12345678Z',
        requested_amount: 15000,
        monthly_income: 3500,
        country_specific_data: {},
      })
    })

    // Verify success message
    expect(await screen.findByText(/Application created successfully!/i)).toBeInTheDocument()
    expect(screen.getByText(/abc123de/i)).toBeInTheDocument()

    // Verify callback was called
    expect(onApplicationCreated).toHaveBeenCalledWith(mockResponse)

    // Verify form was reset (except country)
    expect(screen.getByLabelText(/Full Name/i)).toHaveValue('')
    expect(screen.getByLabelText(/DNI/i)).toHaveValue('')
  })

  it('shows error message when API call fails', async () => {
    const user = userEvent.setup()
    const errorMessage = 'Invalid DNI format'
    applicationAPI.createApplication.mockRejectedValue({
      response: {
        data: {
          detail: errorMessage,
        },
      },
    })

    render(<ApplicationForm />)

    // Fill and submit form
    await user.type(screen.getByLabelText(/Full Name/i), 'Juan García López')
    await user.type(screen.getByLabelText(/DNI/i), 'INVALID')
    await user.type(screen.getByLabelText(/Requested Amount/i), '15000')
    await user.type(screen.getByLabelText(/Monthly Income/i), '3500')

    const submitButton = screen.getByRole('button', { name: /Create Application/i })
    await user.click(submitButton)

    // Verify error message appears
    expect(await screen.findByText(errorMessage)).toBeInTheDocument()
  })

  it('shows generic error message when API error has no detail', async () => {
    const user = userEvent.setup()
    applicationAPI.createApplication.mockRejectedValue(new Error('Network error'))

    render(<ApplicationForm />)

    // Fill and submit form
    await user.type(screen.getByLabelText(/Full Name/i), 'Juan García López')
    await user.type(screen.getByLabelText(/DNI/i), '12345678Z')
    await user.type(screen.getByLabelText(/Requested Amount/i), '15000')
    await user.type(screen.getByLabelText(/Monthly Income/i), '3500')

    await user.click(screen.getByRole('button', { name: /Create Application/i }))

    expect(await screen.findByText(/Error creating application/i)).toBeInTheDocument()
  })

  it('disables submit button while loading', async () => {
    const user = userEvent.setup()
    applicationAPI.createApplication.mockImplementation(
      () => new Promise((resolve) => setTimeout(resolve, 100))
    )

    render(<ApplicationForm />)

    // Fill form
    await user.type(screen.getByLabelText(/Full Name/i), 'Juan García López')
    await user.type(screen.getByLabelText(/DNI/i), '12345678Z')
    await user.type(screen.getByLabelText(/Requested Amount/i), '15000')
    await user.type(screen.getByLabelText(/Monthly Income/i), '3500')

    const submitButton = screen.getByRole('button', { name: /Create Application/i })
    await user.click(submitButton)

    // Button should be disabled and show loading text
    expect(submitButton).toBeDisabled()
    expect(screen.getByText('Creating...')).toBeInTheDocument()
  })

  it('clears error message when user starts typing', async () => {
    const user = userEvent.setup()
    applicationAPI.createApplication.mockRejectedValue({
      response: { data: { detail: 'Some error' } },
    })

    render(<ApplicationForm />)

    // Trigger error
    await user.type(screen.getByLabelText(/Full Name/i), 'Juan García López')
    await user.type(screen.getByLabelText(/DNI/i), '12345678Z')
    await user.type(screen.getByLabelText(/Requested Amount/i), '15000')
    await user.type(screen.getByLabelText(/Monthly Income/i), '3500')
    await user.click(screen.getByRole('button', { name: /Create Application/i }))

    // Error should appear
    expect(await screen.findByText(/Some error/i)).toBeInTheDocument()

    // Type in a field
    await user.type(screen.getByLabelText(/Full Name/i), ' Extra')

    // Error should be cleared
    await waitFor(() => {
      expect(screen.queryByText(/Some error/i)).not.toBeInTheDocument()
    })
  })

  it('validates required fields', () => {
    render(<ApplicationForm />)

    const nameInput = screen.getByLabelText(/Full Name/i)
    const documentInput = screen.getByLabelText(/DNI/i)
    const amountInput = screen.getByLabelText(/Requested Amount/i)
    const incomeInput = screen.getByLabelText(/Monthly Income/i)

    expect(nameInput).toBeRequired()
    expect(documentInput).toBeRequired()
    expect(amountInput).toBeRequired()
    expect(incomeInput).toBeRequired()
  })

  it('handles Mexico-specific fields correctly', async () => {
    const user = userEvent.setup()
    const mockResponse = { id: 'mxapp123', country: 'MX', status: 'PENDING' }
    applicationAPI.createApplication.mockResolvedValue(mockResponse)

    render(<ApplicationForm />)

    // Change to Mexico
    await user.selectOptions(screen.getByLabelText(/Country/i), 'MX')

    // Fill form with Mexico data
    await user.type(screen.getByLabelText(/Full Name/i), 'María Hernández')
    await user.type(screen.getByLabelText(/CURP/i), 'HERM850101MDFRRR01')
    await user.type(screen.getByLabelText(/Requested Amount/i), '50000')
    await user.type(screen.getByLabelText(/Monthly Income/i), '15000')

    await user.click(screen.getByRole('button', { name: /Create Application/i }))

    await waitFor(() => {
      expect(applicationAPI.createApplication).toHaveBeenCalledWith({
        country: 'MX',
        full_name: 'María Hernández',
        identity_document: 'HERM850101MDFRRR01',
        requested_amount: 50000,
        monthly_income: 15000,
        country_specific_data: {},
      })
    })
  })
})
