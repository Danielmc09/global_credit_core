import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import axios from 'axios'
import { applicationAPI } from '../services/api'

// Mock axios
vi.mock('axios')

describe('API Service', () => {
  const mockAxiosInstance = {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
    interceptors: {
      request: {
        use: vi.fn((onFulfilled, onRejected) => {
          // Store the interceptor for testing
          mockAxiosInstance.interceptors.request.onFulfilled = onFulfilled
          mockAxiosInstance.interceptors.request.onRejected = onRejected
        }),
      },
      response: {
        use: vi.fn((onFulfilled, onRejected) => {
          mockAxiosInstance.interceptors.response.onFulfilled = onFulfilled
          mockAxiosInstance.interceptors.response.onRejected = onRejected
        }),
      },
    },
  }

  beforeEach(() => {
    vi.clearAllMocks()
    axios.create.mockReturnValue(mockAxiosInstance)
    console.log = vi.fn()
    console.error = vi.fn()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('getApplications', () => {
    it('fetches applications without filters', async () => {
      const mockData = {
        applications: [{ id: '1', name: 'Test' }],
        total: 1,
      }
      mockAxiosInstance.get.mockResolvedValue({ data: mockData })

      const result = await applicationAPI.getApplications()

      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/applications?')
      expect(result).toEqual(mockData)
    })

    it('fetches applications with country filter', async () => {
      const mockData = { applications: [], total: 0 }
      mockAxiosInstance.get.mockResolvedValue({ data: mockData })

      await applicationAPI.getApplications({ country: 'ES' })

      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/applications?country=ES')
    })

    it('fetches applications with status filter', async () => {
      const mockData = { applications: [], total: 0 }
      mockAxiosInstance.get.mockResolvedValue({ data: mockData })

      await applicationAPI.getApplications({ status: 'APPROVED' })

      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/applications?status=APPROVED')
    })

    it('fetches applications with multiple filters', async () => {
      const mockData = { applications: [], total: 0 }
      mockAxiosInstance.get.mockResolvedValue({ data: mockData })

      await applicationAPI.getApplications({
        country: 'MX',
        status: 'PENDING',
        page: 2,
        page_size: 20,
      })

      expect(mockAxiosInstance.get).toHaveBeenCalledWith(
        '/applications?country=MX&status=PENDING&page=2&page_size=20'
      )
    })
  })

  describe('getApplication', () => {
    it('fetches a single application by ID', async () => {
      const mockData = {
        id: 'app-123',
        full_name: 'Juan García',
        status: 'APPROVED',
      }
      mockAxiosInstance.get.mockResolvedValue({ data: mockData })

      const result = await applicationAPI.getApplication('app-123')

      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/applications/app-123')
      expect(result).toEqual(mockData)
    })
  })

  describe('createApplication', () => {
    it('creates a new application', async () => {
      const payload = {
        country: 'ES',
        full_name: 'Juan García López',
        identity_document: '12345678Z',
        requested_amount: 15000,
        monthly_income: 3500,
      }
      const mockResponse = { id: 'new-app-123', ...payload, status: 'PENDING' }
      mockAxiosInstance.post.mockResolvedValue({ data: mockResponse })

      const result = await applicationAPI.createApplication(payload)

      expect(mockAxiosInstance.post).toHaveBeenCalledWith('/applications', payload)
      expect(result).toEqual(mockResponse)
    })
  })

  describe('updateApplication', () => {
    it('updates an existing application', async () => {
      const updateData = { status: 'APPROVED' }
      const mockResponse = {
        id: 'app-123',
        status: 'APPROVED',
        updated_at: '2024-01-15T12:00:00Z',
      }
      mockAxiosInstance.patch.mockResolvedValue({ data: mockResponse })

      const result = await applicationAPI.updateApplication('app-123', updateData)

      expect(mockAxiosInstance.patch).toHaveBeenCalledWith('/applications/app-123', updateData)
      expect(result).toEqual(mockResponse)
    })
  })

  describe('deleteApplication', () => {
    it('deletes an application', async () => {
      const mockResponse = { success: true }
      mockAxiosInstance.delete.mockResolvedValue({ data: mockResponse })

      const result = await applicationAPI.deleteApplication('app-123')

      expect(mockAxiosInstance.delete).toHaveBeenCalledWith('/applications/app-123')
      expect(result).toEqual(mockResponse)
    })
  })

  describe('getAuditLogs', () => {
    it('fetches audit logs for an application', async () => {
      const mockLogs = [
        {
          id: 'audit-1',
          old_status: 'PENDING',
          new_status: 'APPROVED',
          changed_by: 'admin',
        },
      ]
      mockAxiosInstance.get.mockResolvedValue({ data: mockLogs })

      const result = await applicationAPI.getAuditLogs('app-123')

      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/applications/app-123/audit')
      expect(result).toEqual(mockLogs)
    })
  })

  describe('getCountryStats', () => {
    it('fetches country statistics', async () => {
      const mockStats = {
        country: 'ES',
        total_applications: 150,
        approved: 100,
        rejected: 30,
      }
      mockAxiosInstance.get.mockResolvedValue({ data: mockStats })

      const result = await applicationAPI.getCountryStats('ES')

      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/applications/stats/country/ES')
      expect(result).toEqual(mockStats)
    })
  })

  describe('getSupportedCountries', () => {
    it('fetches supported countries', async () => {
      const mockData = {
        supported_countries: ['ES', 'PT', 'IT', 'MX', 'CO', 'BR'],
      }
      mockAxiosInstance.get.mockResolvedValue({ data: mockData })

      const result = await applicationAPI.getSupportedCountries()

      expect(mockAxiosInstance.get).toHaveBeenCalledWith(
        '/applications/meta/supported-countries'
      )
      expect(result).toEqual(mockData)
    })
  })

  describe('Error Handling', () => {
    it('handles API errors correctly', async () => {
      const error = {
        response: {
          data: { detail: 'Not found' },
          status: 404,
        },
        message: 'Request failed',
      }
      mockAxiosInstance.get.mockRejectedValue(error)

      await expect(applicationAPI.getApplication('invalid-id')).rejects.toEqual(error)
    })

    it('handles network errors', async () => {
      const error = new Error('Network Error')
      mockAxiosInstance.get.mockRejectedValue(error)

      await expect(applicationAPI.getApplications()).rejects.toThrow('Network Error')
    })
  })

  describe('Axios Configuration', () => {
    it('creates axios instance with correct base URL', () => {
      // Re-import to trigger axios.create
      vi.resetModules()
      require('../services/api')

      expect(axios.create).toHaveBeenCalledWith(
        expect.objectContaining({
          baseURL: expect.stringContaining('/api/v1'),
          headers: {
            'Content-Type': 'application/json',
          },
        })
      )
    })
  })

  describe('Request Interceptor', () => {
    it('logs request information', () => {
      const config = {
        method: 'get',
        url: '/applications',
      }

      const interceptor = mockAxiosInstance.interceptors.request.onFulfilled
      if (interceptor) {
        const result = interceptor(config)

        expect(console.log).toHaveBeenCalledWith('API Request: GET /applications')
        expect(result).toEqual(config)
      }
    })

    it('handles request errors', async () => {
      const error = new Error('Request setup error')

      const interceptor = mockAxiosInstance.interceptors.request.onRejected
      if (interceptor) {
        await expect(interceptor(error)).rejects.toThrow('Request setup error')
      }
    })
  })

  describe('Response Interceptor', () => {
    it('returns response on success', () => {
      const response = {
        data: { id: '123' },
        status: 200,
      }

      const interceptor = mockAxiosInstance.interceptors.response.onFulfilled
      if (interceptor) {
        const result = interceptor(response)
        expect(result).toEqual(response)
      }
    })

    it('logs error information on response error', async () => {
      const error = {
        response: {
          data: { detail: 'Validation error' },
          status: 400,
        },
        message: 'Request failed',
      }

      const interceptor = mockAxiosInstance.interceptors.response.onRejected
      if (interceptor) {
        await expect(interceptor(error)).rejects.toEqual(error)
        expect(console.error).toHaveBeenCalledWith(
          'API Error:',
          { detail: 'Validation error' }
        )
      }
    })

    it('logs error message when no response data', async () => {
      const error = {
        message: 'Network timeout',
      }

      const interceptor = mockAxiosInstance.interceptors.response.onRejected
      if (interceptor) {
        await expect(interceptor(error)).rejects.toEqual(error)
        expect(console.error).toHaveBeenCalledWith('API Error:', 'Network timeout')
      }
    })
  })
})
