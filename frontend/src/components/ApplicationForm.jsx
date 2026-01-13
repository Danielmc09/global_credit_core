import { useState, useEffect } from 'react';
import { toast } from 'react-toastify';
import { applicationAPI } from '../services/api';

const COUNTRY_CONFIGS = {
  ES: {
    name: 'España',
    documentLabel: 'DNI',
    documentPlaceholder: '12345678Z',
    documentHelp: '8 dígitos seguidos de una letra',
  },
  MX: {
    name: 'México',
    documentLabel: 'CURP',
    documentPlaceholder: 'HERM850101MDFRRR01',
    documentHelp: '18 caracteres alfanuméricos',
  },
  BR: {
    name: 'Brasil',
    documentLabel: 'CPF',
    documentPlaceholder: '12345678909',
    documentHelp: '11 dígitos',
  },
  CO: {
    name: 'Colombia',
    documentLabel: 'Cédula',
    documentPlaceholder: '1234567890',
    documentHelp: '6-10 dígitos',
  },
  PT: {
    name: 'Portugal',
    documentLabel: 'NIF',
    documentPlaceholder: '123456789',
    documentHelp: '9 dígitos',
  },
  IT: {
    name: 'Italia',
    documentLabel: 'Codice Fiscale',
    documentPlaceholder: 'RSSMRA80A01H501U',
    documentHelp: '16 caracteres alfanuméricos',
  },
};

function ApplicationForm({ onApplicationCreated }) {
  const [formData, setFormData] = useState({
    country: 'ES',
    full_name: '',
    identity_document: '',
    requested_amount: '',
    monthly_income: '',
  });

  const [supportedCountries, setSupportedCountries] = useState(['ES', 'MX']);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // Fetch supported countries from API
    applicationAPI
      .getSupportedCountries()
      .then((data) => {
        if (data.supported_countries) {
          setSupportedCountries(data.supported_countries);
        }
      })
      .catch(() => {
        toast.error('Error loading supported countries');
      });
  }, []);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const submitData = {
        ...formData,
        requested_amount: parseFloat(formData.requested_amount),
        monthly_income: parseFloat(formData.monthly_income),
        country_specific_data: {},
      };

      const response = await applicationAPI.createApplication(submitData);

      toast.success(`Application created successfully! ID: ${response.id.slice(0, 8)}...`);

      // Reset form
      setFormData({
        country: formData.country,
        full_name: '',
        identity_document: '',
        requested_amount: '',
        monthly_income: '',
      });

      // Notify parent
      if (onApplicationCreated) {
        onApplicationCreated(response);
      }
    } catch (err) {
      // Handle validation errors from FastAPI/Pydantic
      const errorData = err.response?.data;
      
      if (errorData?.detail) {
        // Check if detail is an array (validation errors) or a string (single error)
        if (Array.isArray(errorData.detail)) {
          // Multiple validation errors
          const errorMessages = errorData.detail.map((error) => {
            const field = error.loc?.slice(-1)[0] || 'field';
            const message = error.msg || 'Validation error';
            return `${field}: ${message}`;
          });
          toast.error(`Validation errors:\n${errorMessages.join('\n')}`, {
            autoClose: 8000,
          });
        } else {
          // Single error message
          toast.error(errorData.detail);
        }
      } else {
        toast.error(err.message || 'Error creating application');
      }
    } finally {
      setLoading(false);
    }
  };

  const config = COUNTRY_CONFIGS[formData.country] || COUNTRY_CONFIGS.ES;

  return (
    <div className="card">
      <h2>Create Credit Application</h2>

      <form onSubmit={handleSubmit}>
        <div className="two-column">
          <div className="form-group">
            <label htmlFor="country">Country *</label>
            <select
              id="country"
              name="country"
              value={formData.country}
              onChange={handleChange}
              required
            >
              {supportedCountries.map((code) => (
                <option key={code} value={code}>
                  {COUNTRY_CONFIGS[code]?.name || code}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="full_name">Full Name *</label>
            <input
              type="text"
              id="full_name"
              name="full_name"
              value={formData.full_name}
              onChange={handleChange}
              placeholder="Juan García López"
              required
            />
          </div>
        </div>

        <div className="form-group">
          <label htmlFor="identity_document">
            {config.documentLabel} *
          </label>
          <input
            type="text"
            id="identity_document"
            name="identity_document"
            value={formData.identity_document}
            onChange={handleChange}
            placeholder={config.documentPlaceholder}
            required
          />
          <small style={{ color: '#888', fontSize: '0.9rem' }}>
            {config.documentHelp}
          </small>
        </div>

        <div className="two-column">
          <div className="form-group">
            <label htmlFor="requested_amount">Requested Amount *</label>
            <input
              type="number"
              id="requested_amount"
              name="requested_amount"
              value={formData.requested_amount}
              onChange={handleChange}
              placeholder="15000"
              min="0"
              step="0.01"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="monthly_income">Monthly Income *</label>
            <input
              type="number"
              id="monthly_income"
              name="monthly_income"
              value={formData.monthly_income}
              onChange={handleChange}
              placeholder="3500"
              min="0"
              step="0.01"
              required
            />
          </div>
        </div>

        <button type="submit" className="btn btn-primary" disabled={loading}>
          {loading ? 'Creating...' : 'Create Application'}
        </button>
      </form>
    </div>
  );
}

export default ApplicationForm;
