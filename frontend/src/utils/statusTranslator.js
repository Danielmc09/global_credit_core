/**
 * Translates application status values to the current language
 * @param {string} status - The status value (e.g., "APPROVED", "PENDING")
 * @param {function} t - The translation function from useTranslation hook
 * @returns {string} - Translated status
 */
export const translateStatus = (status, t) => {
  if (!status) return status;

  // Convert status to lowercase for lookup
  const statusKey = status.toLowerCase().replace(/_/g, '');
  
  // Map status values to translation keys
  const statusMap = {
    'pending': 'list.statuses.pending',
    'validating': 'list.statuses.validating',
    'approved': 'list.statuses.approved',
    'rejected': 'list.statuses.rejected',
    'underreview': 'list.statuses.underReview',
    'completed': 'list.statuses.completed',
    'cancelled': 'list.statuses.cancelled',
  };

  const translationKey = statusMap[statusKey];
  
  if (translationKey) {
    return t(translationKey);
  }

  // If no translation found, return original status
  return status;
};
