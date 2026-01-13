import { useState, useEffect } from 'react';
import { toast } from 'react-toastify';
import { applicationAPI } from '../services/api';
import { useTranslation } from '../hooks/useTranslation';
import { translateError } from '../utils/errorTranslator';
import { translateStatus } from '../utils/statusTranslator';

// Final states that cannot be changed
const FINAL_STATES = ['APPROVED', 'REJECTED', 'CANCELLED', 'COMPLETED'];

function ApplicationDetail({ applicationId, onClose, onUpdate }) {
  const { t, language } = useTranslation();
  const [application, setApplication] = useState(null);
  const [auditLogs, setAuditLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [updating, setUpdating] = useState(false);
  const [newStatus, setNewStatus] = useState('');
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);

  useEffect(() => {
    loadApplicationDetails();
  }, [applicationId]);

  const loadApplicationDetails = async () => {
    try {
      setLoading(true);
      setError(null);

      // Load application and audit logs in parallel
      const [appData, auditData] = await Promise.all([
        applicationAPI.getApplication(applicationId),
        applicationAPI.getAuditLogs(applicationId),
      ]);

      setApplication(appData);
      setAuditLogs(auditData.audit_logs || auditData);
      setNewStatus(appData.status);
    } catch (err) {
      setError(t('detail.errorLoadingDetails'));
      toast.error(t('messages.errorLoadingDetails'));
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateStatusClick = () => {
    // Check if in final state
    if (FINAL_STATES.includes(application.status)) {
      toast.error(t('messages.cannotChangeFinal'));
      return;
    }

    if (newStatus === application.status) {
      toast.warning(t('messages.statusSame'));
      return;
    }

    // Show confirmation dialog
    setShowConfirmDialog(true);
  };

  const handleConfirmUpdate = async () => {
    setShowConfirmDialog(false);

    try {
      setUpdating(true);
      await applicationAPI.updateApplication(applicationId, {
        status: newStatus,
      });

      // Reload application details and audit logs to show the new entry
      await loadApplicationDetails();

      // Notify parent first
      if (onUpdate) {
        onUpdate();
      }

      // Show success message
      toast.success(t('messages.statusUpdated'));
      
      // Close modal after successful update
      onClose();
    } catch (err) {
      const errorMsg = err.response?.data?.detail || err.message;
      const translatedError = translateError(errorMsg, t);
      toast.error(`${t('messages.errorUpdatingStatus')} ${translatedError}`, {
        autoClose: 8000,
        style: {
          fontSize: '14px',
          lineHeight: '1.5'
        }
      });
    } finally {
      setUpdating(false);
    }
  };

  const handleCancelUpdate = () => {
    setShowConfirmDialog(false);
  };

  const formatCurrency = (amount) => {
    const locale = language === 'es' ? 'es-ES' : 'en-US';
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
    }).format(amount);
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Invalid Date';
    try {
      const date = new Date(dateString);
      if (isNaN(date.getTime())) return 'Invalid Date';
      const locale = language === 'es' ? 'es-ES' : 'en-US';
      return date.toLocaleString(locale);
    } catch (e) {
      return 'Invalid Date';
    }
  };

  const getStatusBadgeClass = (status) => {
    const statusMap = {
      PENDING: 'badge-pending',
      VALIDATING: 'badge-validating',
      APPROVED: 'badge-approved',
      REJECTED: 'badge-rejected',
      UNDER_REVIEW: 'badge-review',
    };
    return `badge ${statusMap[status] || 'badge-pending'}`;
  };

  if (loading) {
    return (
      <div className="modal-overlay" onClick={onClose}>
        <div className="modal-content" onClick={(e) => e.stopPropagation()}>
          <div className="loading">{t('detail.loading')}</div>
        </div>
      </div>
    );
  }

  if (error || !application) {
    return (
      <div className="modal-overlay" onClick={onClose}>
        <div className="modal-content" onClick={(e) => e.stopPropagation()}>
          <div className="error">{error || t('detail.notFound')}</div>
          <button onClick={onClose} className="btn btn-primary">
            {t('detail.close')}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content large" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{t('detail.title')}</h2>
          <button className="close-btn" onClick={onClose} aria-label={t('detail.close')}>
            ×
          </button>
        </div>

        <div className="modal-body">
          {/* Basic Information */}
          <section className="detail-section">
            <h3>{t('detail.basicInfo')}</h3>
            <div className="detail-grid">
              <div className="detail-item">
                <label>{t('detail.labels.id')}</label>
                <span style={{ fontFamily: 'monospace', fontSize: '0.9rem' }}>
                  {application.id}
                </span>
              </div>
              <div className="detail-item">
                <label>{t('detail.labels.country')}</label>
                <span>
                  <strong>{application.country}</strong>
                </span>
              </div>
              <div className="detail-item">
                <label>{t('detail.labels.fullName')}</label>
                <span>{application.full_name}</span>
              </div>
              <div className="detail-item">
                <label>{t('detail.labels.identityDocument')}</label>
                <span style={{ fontFamily: 'monospace' }}>
                  {application.identity_document}
                </span>
              </div>
              <div className="detail-item">
                <label>{t('detail.labels.requestedAmount')}</label>
                <span>{formatCurrency(application.requested_amount)}</span>
              </div>
              <div className="detail-item">
                <label>{t('detail.labels.monthlyIncome')}</label>
                <span>{formatCurrency(application.monthly_income)}</span>
              </div>
              <div className="detail-item">
                <label>{t('detail.labels.status')}</label>
                <span className={getStatusBadgeClass(application.status)}>
                  {translateStatus(application.status, t)}
                </span>
              </div>
              <div className="detail-item">
                <label>{t('detail.labels.riskScore')}</label>
                <span>
                  {application.risk_score ? (
                    <span
                      style={{
                        color:
                          application.risk_score < 30
                            ? '#0f5132'
                            : application.risk_score < 50
                            ? '#856404'
                            : '#842029',
                        fontWeight: 600,
                      }}
                    >
                      {parseFloat(application.risk_score).toFixed(1)} / 100
                    </span>
                  ) : (
                    '-'
                  )}
                </span>
              </div>
              <div className="detail-item">
                <label>{t('detail.labels.riskCondition')}</label>
                <span>
                  {application.country_specific_data?.risk_level ? (
                    <span
                      style={{
                        color:
                          application.country_specific_data.risk_level === 'LOW'
                            ? '#0f5132'
                            : application.country_specific_data.risk_level === 'MEDIUM'
                            ? '#856404'
                            : application.country_specific_data.risk_level === 'HIGH'
                            ? '#ff9800'
                            : '#842029',
                        fontWeight: 600,
                        textTransform: 'uppercase',
                      }}
                    >
                      {application.country_specific_data.risk_level}
                    </span>
                  ) : (
                    '-'
                  )}
                </span>
              </div>
              <div className="detail-item">
                <label>{t('detail.labels.created')}</label>
                <span>{formatDate(application.created_at)}</span>
              </div>
              <div className="detail-item">
                <label>{t('detail.labels.updated')}</label>
                <span>{formatDate(application.updated_at)}</span>
              </div>
            </div>
          </section>

          {/* Banking Data */}
          {application.banking_data &&
            Object.keys(application.banking_data).length > 0 && (
              <section className="detail-section">
                <h3>{t('detail.bankingInfo')}</h3>
                <div className="detail-grid">
                  {application.banking_data.provider_name && (
                    <div className="detail-item">
                      <label>{t('detail.labels.provider')}</label>
                      <span>{application.banking_data.provider_name}</span>
                    </div>
                  )}
                  {application.banking_data.credit_score && (
                    <div className="detail-item">
                      <label>{t('detail.labels.creditScore')}</label>
                      <span>{application.banking_data.credit_score}</span>
                    </div>
                  )}
                  {application.banking_data.total_debt && (
                    <div className="detail-item">
                      <label>{t('detail.labels.totalDebt')}</label>
                      <span>{formatCurrency(application.banking_data.total_debt)}</span>
                    </div>
                  )}
                  {application.banking_data.monthly_obligations && (
                    <div className="detail-item">
                      <label>{t('detail.labels.monthlyObligations')}</label>
                      <span>
                        {formatCurrency(application.banking_data.monthly_obligations)}
                      </span>
                    </div>
                  )}
                  {application.banking_data.has_defaults !== undefined && (
                    <div className="detail-item">
                      <label>{t('detail.labels.hasDefaults')}</label>
                      <span
                        style={{
                          color: application.banking_data.has_defaults
                            ? '#842029'
                            : '#0f5132',
                          fontWeight: 600,
                        }}
                      >
                        {application.banking_data.has_defaults ? t('detail.yes') : t('detail.no')}
                      </span>
                    </div>
                  )}
                </div>
              </section>
            )}

          {/* Validation Errors/Reasons */}
          {application.validation_errors &&
            application.validation_errors.length > 0 && (
              <section className="detail-section">
                <h3>{t('detail.assessmentNotes')}</h3>
                <ul>
                  {application.validation_errors.map((error, index) => (
                    <li key={index}>
                      {error}
                    </li>
                  ))}
                </ul>
              </section>
            )}

          {/* Update Status */}
          <section className="detail-section">
            <h3>{t('detail.updateStatus')}</h3>
            {FINAL_STATES.includes(application.status) ? (
              <div style={{ padding: '16px 20px', background: '#fafafa', borderRadius: '8px', color: '#666', border: '1px solid #e5e5e5', fontSize: '0.9rem' }}>
                <strong>{t('detail.statusCannotChange')}</strong> {t('detail.statusCannotChangeFinal')} <strong>{translateStatus(application.status, t)}</strong>
              </div>
            ) : (
              <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                <select
                  value={newStatus}
                  onChange={(e) => setNewStatus(e.target.value)}
                  className="form-group select"
                  style={{ flex: 1, padding: '12px 16px', fontSize: '0.9rem', border: '1px solid #d1d1d1', borderRadius: '8px' }}
                >
                  <option value="PENDING">{translateStatus('PENDING', t)}</option>
                  <option value="VALIDATING">{translateStatus('VALIDATING', t)}</option>
                  <option value="APPROVED">{translateStatus('APPROVED', t)}</option>
                  <option value="REJECTED">{translateStatus('REJECTED', t)}</option>
                  <option value="UNDER_REVIEW">{translateStatus('UNDER_REVIEW', t)}</option>
                  <option value="COMPLETED">{translateStatus('COMPLETED', t)}</option>
                  <option value="CANCELLED">{translateStatus('CANCELLED', t)}</option>
                </select>
                <button
                  onClick={handleUpdateStatusClick}
                  className="btn btn-primary"
                  disabled={updating || newStatus === application.status}
                >
                  {updating ? t('detail.updating') : t('detail.updateButton')}
                </button>
              </div>
            )}
          </section>

          {/* Audit Logs - Shows the business flow (status changes) */}
          {auditLogs.length > 0 && (
            <section className="detail-section">
              <h3>{t('detail.flow')}</h3>
              <div className="audit-logs">
                {auditLogs.map((log) => (
                  <div key={log.id} className="audit-log-item">
                    <div className="audit-log-header">
                      <span className="audit-log-date">
                        {formatDate(log.created_at)}
                      </span>
                      <span className="audit-log-user">{log.changed_by}</span>
                    </div>
                    <div className="audit-log-change">
                      <span className={getStatusBadgeClass(log.old_status)}>
                        {log.old_status ? translateStatus(log.old_status, t) : t('detail.initial')}
                      </span>
                      <span style={{ margin: '0 12px', color: '#999' }}>→</span>
                      <span className={getStatusBadgeClass(log.new_status)}>
                        {translateStatus(log.new_status, t)}
                      </span>
                    </div>
                    {log.change_reason && (
                      <div className="audit-log-reason">{log.change_reason}</div>
                    )}
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>

        <div className="modal-footer">
          <button onClick={onClose} className="btn btn-primary">
            {t('detail.close')}
          </button>
        </div>
      </div>

      {/* Confirmation Dialog */}
      {showConfirmDialog && (
        <div className="modal-overlay" onClick={handleCancelUpdate}>
          <div className="confirm-dialog" onClick={(e) => e.stopPropagation()}>
            <h3>{t('detail.confirmTitle')}</h3>
            <p>
              {t('detail.confirmMessage')}{' '}
              <strong>{translateStatus(application.status, t)}</strong> {t('detail.confirmTo')} <strong>{translateStatus(newStatus, t)}</strong>?
            </p>
            <div className="confirm-dialog-actions">
              <button onClick={handleCancelUpdate} className="btn btn-secondary">
                {t('detail.cancel')}
              </button>
              <button onClick={handleConfirmUpdate} className="btn btn-primary">
                {t('detail.confirm')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default ApplicationDetail;
