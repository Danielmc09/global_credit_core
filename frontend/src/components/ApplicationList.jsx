import { useState, useEffect, useRef, useCallback } from 'react';
import { toast } from 'react-toastify';
import { applicationAPI } from '../services/api';
import websocketService from '../services/websocket';
import ApplicationDetail from './ApplicationDetail';
import { WS_MESSAGE_TYPES } from '../utils/constants';
import { useTranslation } from '../hooks/useTranslation';
import { translateStatus } from '../utils/statusTranslator';

function ApplicationList({ refreshTrigger }) {
  const { t } = useTranslation();
  const [applications, setApplications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState({
    country: '',
    status: '',
  });
  const [highlightedIds, setHighlightedIds] = useState(new Set());
  const highlightTimeoutRef = useRef({});
  const [selectedApplicationId, setSelectedApplicationId] = useState(null);
  const [wsRefreshCounter, setWsRefreshCounter] = useState(0);
  const wsListenerRegistered = useRef(false);
  const messageCountRef = useRef(0);
  const [pagination, setPagination] = useState({
    page: 1,
    pageSize: 20,
    total: 0,
  });

  const loadApplications = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const data = await applicationAPI.getApplications({
        ...filters,
        page: pagination.page,
        page_size: pagination.pageSize,
      });

      setApplications(data.applications || []);
      setPagination((prev) => ({
        ...prev,
        total: data.total || 0,
        page: data.page || prev.page,
        pageSize: data.page_size || prev.pageSize,
      }));
    } catch (err) {
      setError(t('list.error'));
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [filters, pagination.page, pagination.pageSize]);

  useEffect(() => {
    loadApplications();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadApplications, refreshTrigger, wsRefreshCounter]);

  useEffect(() => {
    // Prevent duplicate listener registration (React Strict Mode causes double mount)
    if (wsListenerRegistered.current) {
      return;
    }

    wsListenerRegistered.current = true;

    // Ensure WebSocket is connected
    if (!websocketService.isConnected()) {
      websocketService.connect();
    }

    // Listen for WebSocket updates
    const handleMessage = (message) => {
      messageCountRef.current++;

      if (message.type === WS_MESSAGE_TYPES.APPLICATION_UPDATE) {
        const { id, status, risk_score, updated_at } = message.data;

        // Normalize IDs for comparison (both should be strings)
        const normalizedId = String(id).trim();

        // Show notification with color based on status
        const translatedStatus = translateStatus(status, t);
        const toastMessage = `${t('messages.applicationUpdated')} ${translatedStatus}`;
        const toastOptions = {
          autoClose: 3000,
        };

        switch (status) {
          case 'APPROVED':
            toast.success(toastMessage, toastOptions);
            break;
          case 'REJECTED':
            toast.error(toastMessage, toastOptions);
            break;
          case 'PENDING':
            toast.warning(toastMessage, toastOptions);
            break;
          case 'VALIDATING':
            toast.info(toastMessage, toastOptions);
            break;
          case 'UNDER_REVIEW':
            toast.info(toastMessage, toastOptions);
            break;
          default:
            toast.info(toastMessage, toastOptions);
        }

        // Update application in the list if it exists, otherwise trigger reload
        setApplications((prev) => {
          const existingAppIndex = prev.findIndex((app) => String(app.id).trim() === normalizedId);

          if (existingAppIndex !== -1) {
            // Application EXISTS - update it
            const currentApp = prev[existingAppIndex];

            // Convert risk_score to number (WebSocket sends it as string)
            const parsedRiskScore = risk_score !== null && risk_score !== undefined
              ? parseFloat(risk_score)
              : currentApp.risk_score;

            // Create completely new application object to ensure React detects the change
            const updatedApp = {
              ...currentApp,
              status: status,
              risk_score: parsedRiskScore,
              updated_at: updated_at || currentApp.updated_at,
              _updated: Date.now() // Force change detection
            };

            // Create new array with updated application
            const updated = [
              ...prev.slice(0, existingAppIndex),
              updatedApp,
              ...prev.slice(existingAppIndex + 1)
            ];

            return updated;
          } else {
            // Application DOESN'T EXIST - need to reload entire list
            // Trigger reload by incrementing counter
            setTimeout(() => {
              setWsRefreshCounter(c => c + 1);
            }, 0);

            return prev; // Don't modify array
          }
        });

        // Highlight the updated row
        setHighlightedIds((prev) => new Set(prev).add(id));

        // Remove highlight after 2 seconds
        if (highlightTimeoutRef.current[id]) {
          clearTimeout(highlightTimeoutRef.current[id]);
        }

        highlightTimeoutRef.current[id] = setTimeout(() => {
          setHighlightedIds((prev) => {
            const newSet = new Set(prev);
            newSet.delete(id);
            return newSet;
          });
          delete highlightTimeoutRef.current[id];
        }, 2000);
      }
    };

    websocketService.addListener(handleMessage);

    return () => {
      websocketService.removeListener(handleMessage);
      wsListenerRegistered.current = false; // Reset flag on cleanup
      // Clear all timeouts
      Object.values(highlightTimeoutRef.current).forEach(clearTimeout);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Run only once on mount - uses state setters which never change

  const handleFilterChange = (e) => {
    const { name, value } = e.target;
    setFilters((prev) => ({
      ...prev,
      [name]: value,
    }));
    // Reset to page 1 when filters change
    setPagination((prev) => ({
      ...prev,
      page: 1,
    }));
  };

  const handlePageChange = (newPage) => {
    setPagination((prev) => ({
      ...prev,
      page: newPage,
    }));
  };

  const handlePageSizeChange = (e) => {
    const newSize = parseInt(e.target.value, 10);
    setPagination((prev) => ({
      ...prev,
      pageSize: newSize,
      page: 1, // Reset to first page when changing page size
    }));
  };

  const totalPages = Math.ceil(pagination.total / pagination.pageSize);
  const startRecord = pagination.total === 0 ? 0 : (pagination.page - 1) * pagination.pageSize + 1;
  const endRecord = Math.min(pagination.page * pagination.pageSize, pagination.total);

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

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
    }).format(amount);
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleString();
  };

  return (
    <div className="card">
      <h2>{t('list.title')}</h2>

      {/* Filters */}
      <div className="filters">
        <select name="country" value={filters.country} onChange={handleFilterChange}>
          <option value="">{t('list.allCountries')}</option>
          <option value="ES">España</option>
          <option value="MX">México</option>
          <option value="BR">Brasil</option>
          <option value="CO">Colombia</option>
          <option value="PT">Portugal</option>
          <option value="IT">Italia</option>
        </select>

        <select name="status" value={filters.status} onChange={handleFilterChange}>
          <option value="">{t('list.allStatuses')}</option>
          <option value="PENDING">{t('list.statuses.pending')}</option>
          <option value="VALIDATING">{t('list.statuses.validating')}</option>
          <option value="APPROVED">{t('list.statuses.approved')}</option>
          <option value="REJECTED">{t('list.statuses.rejected')}</option>
          <option value="UNDER_REVIEW">{t('list.statuses.underReview')}</option>
        </select>

        <button onClick={loadApplications} className="btn btn-primary">
          {t('list.refresh')}
        </button>
      </div>

      {/* Loading State */}
      {loading && <div className="loading">{t('list.loading')}</div>}

      {/* Error State */}
      {error && <div className="error">{error}</div>}

      {/* Applications Table */}
      {!loading && !error && (
        <div className="table-container">
          {applications.length === 0 ? (
            <p style={{ textAlign: 'center', padding: '40px', color: '#888' }}>
              {t('list.noApplications')}
            </p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>{t('list.id')}</th>
                  <th>{t('list.country')}</th>
                  <th>{t('list.name')}</th>
                  <th>{t('list.document')}</th>
                  <th>{t('list.amount')}</th>
                  <th>{t('list.status')}</th>
                  <th>{t('list.riskScore')}</th>
                  <th>{t('list.created')}</th>
                  <th>{t('list.actions')}</th>
                </tr>
              </thead>
              <tbody>
                {applications.map((app) => (
                  <tr
                    key={app.id}
                    className={highlightedIds.has(app.id) ? 'highlight' : ''}
                  >
                    <td style={{ fontSize: '0.85rem', color: '#666' }}>
                      {app.id.slice(0, 8)}...
                    </td>
                    <td>
                      <strong>{app.country}</strong>
                    </td>
                    <td>{app.full_name}</td>
                    <td style={{ fontFamily: 'monospace', fontSize: '0.9rem' }}>
                      {app.identity_document}
                    </td>
                    <td>{formatCurrency(app.requested_amount)}</td>
                    <td>
                      <span className={getStatusBadgeClass(app.status)}>
                        {translateStatus(app.status, t)}
                      </span>
                    </td>
                    <td>
                      {app.risk_score ? (
                        <span
                          style={{
                            color:
                              app.risk_score < 30
                                ? '#0f5132'
                                : app.risk_score < 50
                                  ? '#856404'
                                  : '#842029',
                            fontWeight: 600,
                          }}
                        >
                          {parseFloat(app.risk_score).toFixed(1)}
                        </span>
                      ) : (
                        '-'
                      )}
                    </td>
                    <td style={{ fontSize: '0.85rem' }}>
                      {formatDate(app.created_at)}
                    </td>
                    <td>
                      <button
                        onClick={() => setSelectedApplicationId(app.id)}
                        className="btn-action"
                        title={t('list.viewDetails')}
                      >
                        {t('list.view')}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {!loading && !error && applications.length > 0 && (
        <div className="pagination-container">
          <div className="pagination-info">
            {t('list.showing')} {startRecord}-{endRecord} {t('list.of')} {pagination.total} {pagination.total === 1 ? t('list.application') : t('list.applications')}
          </div>

          <div className="pagination-controls">
            <div className="page-size-selector">
              <label htmlFor="pageSize">{t('list.recordsPerPage')}</label>
              <select
                id="pageSize"
                value={pagination.pageSize}
                onChange={handlePageSizeChange}
              >
                <option value="20">20</option>
                <option value="50">50</option>
                <option value="100">100</option>
              </select>
            </div>

            <div className="pagination-buttons">
              <button
                onClick={() => handlePageChange(1)}
                disabled={pagination.page === 1}
                className="btn-pagination"
                title={t('list.first')}
              >
                {t('list.first')}
              </button>
              <button
                onClick={() => handlePageChange(pagination.page - 1)}
                disabled={pagination.page === 1}
                className="btn-pagination"
                title={t('list.previous')}
              >
                {t('list.previous')}
              </button>

              <span className="page-indicator">
                {t('list.page')} {pagination.page} {t('list.of')} {totalPages}
              </span>

              <button
                onClick={() => handlePageChange(pagination.page + 1)}
                disabled={pagination.page >= totalPages}
                className="btn-pagination"
                title={t('list.next')}
              >
                {t('list.next')}
              </button>
              <button
                onClick={() => handlePageChange(totalPages)}
                disabled={pagination.page >= totalPages}
                className="btn-pagination"
                title={t('list.last')}
              >
                {t('list.last')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Application Detail Modal */}
      {selectedApplicationId && (
        <ApplicationDetail
          applicationId={selectedApplicationId}
          onClose={() => setSelectedApplicationId(null)}
          onUpdate={loadApplications}
        />
      )}
    </div>
  );
}

export default ApplicationList;
