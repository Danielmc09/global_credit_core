import { useState, useEffect } from 'react';
import { toast } from 'react-toastify';
import { applicationAPI } from '../services/api';
import { useTranslation } from '../hooks/useTranslation';
import { formatValidationErrors, translateError } from '../utils/errorTranslator';

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
  const { t } = useTranslation();
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
        toast.error(t('messages.errorLoadingCountries'));
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

      toast.success(`${t('messages.applicationCreated')} ${response.id.slice(0, 8)}...`);

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
          // Multiple validation errors - format and translate them
          const formattedErrors = formatValidationErrors(errorData.detail, t);
          
          // Create a more readable error message
          const errorMessages = formattedErrors.map((error, index) => {
            // Combine field and message in a user-friendly way
            if (error.message.includes(error.field)) {
              return `${index + 1}. ${error.message}`;
            }
            return `${index + 1}. ${error.field}: ${error.message}`;
          });

          // Show formatted error with better styling
          const fullMessage = `${t('messages.validationErrors')}\n\n${errorMessages.join('\n')}`;
          
          toast.error(fullMessage, {
            autoClose: 12000,
            style: {
              whiteSpace: 'pre-line',
              fontSize: '14px',
              lineHeight: '1.6',
              maxWidth: '500px',
              wordWrap: 'break-word'
            }
          });
        } else {
          // Single error message - translate it
          const translatedError = translateError(errorData.detail, t);
          toast.error(translatedError, {
            autoClose: 10000,
            style: {
              whiteSpace: 'pre-line',
              fontSize: '14px',
              lineHeight: '1.5'
            }
          });
        }
      } else {
        // Network or other errors
        const errorMessage = err.message || t('messages.errorCreating');
        const translatedError = translateError(errorMessage, t);
        toast.error(translatedError, {
          autoClose: 5000
        });
      }
    } finally {
      setLoading(false);
    }
  };

  const config = COUNTRY_CONFIGS[formData.country] || COUNTRY_CONFIGS.ES;

  return (
    <div className="card">
      <h2>{t('form.title')}</h2>

      <form onSubmit={handleSubmit}>
        <div className="two-column">
          <div className="form-group">
            <label htmlFor="country">{t('form.country')} *</label>
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
            <label htmlFor="full_name">{t('form.fullName')} *</label>
            <input
              type="text"
              id="full_name"
              name="full_name"
              value={formData.full_name}
              onChange={handleChange}
              placeholder={t('form.fullNamePlaceholder')}
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
            <label htmlFor="requested_amount">{t('form.requestedAmount')} *</label>
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
            <label htmlFor="monthly_income">{t('form.monthlyIncome')} *</label>
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
          {loading ? t('form.creating') : t('form.createButton')}
        </button>
      </form>
    </div>
  );
}

export default ApplicationForm;
