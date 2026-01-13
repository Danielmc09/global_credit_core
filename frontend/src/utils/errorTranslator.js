/**
 * Translates and formats backend error messages to be more user-friendly
 * @param {string} errorMessage - The error message from the backend
 * @param {function} t - The translation function from useTranslation hook
 * @returns {string} - Translated and formatted error message
 */
export const translateError = (errorMessage, t) => {
  if (!errorMessage || typeof errorMessage !== 'string') {
    return errorMessage || t('errors.unknown');
  }

  // Normalize the message: remove extra whitespace, normalize newlines
  let message = errorMessage
    .replace(/\r\n/g, ' ')
    .replace(/\n/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

  // Field name translations
  const fieldTranslations = {
    'monthly_income': t('form.monthlyIncome'),
    'requested_amount': t('form.requestedAmount'),
    'full_name': t('form.fullName'),
    'identity_document': t('form.identityDocument'),
    'country': t('form.country'),
    'body': t('errors.requestBody'),
  };

  // Common error patterns and their translations
  const errorPatterns = [
    // Complete minimum requirement error with income (handles multi-line messages)
    {
      pattern: /Value error,\s*Monthly income\s*!?\s*below minimum requirement for CountryCode\.(\w+):\s*\$?([\d,]+\.?\d*)\s*\.?\s*Your income:\s*\$?([\d,]+\.?\d*)/i,
      translate: (match, countryCode, requiredAmount, userAmount) => {
        const countryName = t(`countries.${countryCode}`) || countryCode;
        const formattedRequired = formatCurrency(requiredAmount);
        const formattedUser = formatCurrency(userAmount);
        return `${t('errors.monthlyIncomeError')}\n${t('errors.belowMinimumRequirement', { 
          country: countryName, 
          amount: formattedRequired 
        })}\n${t('errors.yourIncome', { amount: formattedUser })}`;
      }
    },
    // Minimum requirement errors (standalone)
    {
      pattern: /below minimum requirement for CountryCode\.(\w+):\s*\$?([\d,]+\.?\d*)/i,
      translate: (match, countryCode, amount) => {
        const countryName = t(`countries.${countryCode}`) || countryCode;
        const formattedAmount = formatCurrency(amount);
        return t('errors.belowMinimumRequirement', { 
          country: countryName, 
          amount: formattedAmount 
        });
      }
    },
    // Value error with income
    {
      pattern: /Value error,\s*Monthly income/i,
      translate: () => t('errors.monthlyIncomeError')
    },
    // Your income (standalone)
    {
      pattern: /Your income:\s*\$?([\d,]+\.?\d*)/i,
      translate: (match, amount) => {
        const formattedAmount = formatCurrency(amount);
        return t('errors.yourIncome', { amount: formattedAmount });
      }
    },
    // Document validation
    {
      pattern: /document validation failed/i,
      translate: () => t('errors.documentValidationFailed')
    },
    // Empty field errors
    {
      pattern: /cannot be empty/i,
      translate: () => t('errors.cannotBeEmpty')
    },
    // Full name validation - complete message (must come before generic pattern)
    {
      pattern: /full name should include at least first and last name/i,
      translate: () => {
        return t('errors.fullNameShouldIncludeFirstLast');
      }
    },
    {
      pattern: /full name should include at least (\d+) (?:name|names)/i,
      translate: (match, count) => {
        return t('errors.fullNameShouldInclude', { count });
      }
    },
    {
      pattern: /should include at least|debe incluir al menos/i,
      translate: () => t('errors.shouldIncludeAtLeast')
    },
    // Duplicate application
    {
      pattern: /already exists|duplicate/i,
      translate: () => t('errors.duplicateApplication')
    },
    // Country not supported
    {
      pattern: /not supported/i,
      translate: () => t('errors.countryNotSupported')
    },
    // Type errors
    {
      pattern: /value is not a valid/i,
      translate: () => t('errors.invalidValue')
    },
    {
      pattern: /field required/i,
      translate: () => t('errors.fieldRequired')
    },
  ];

  // Try to match patterns (check longer patterns first)
  // Sort patterns by length to match more specific patterns first
  const sortedPatterns = [...errorPatterns].sort((a, b) => {
    const aLength = a.pattern.toString().length;
    const bLength = b.pattern.toString().length;
    return bLength - aLength; // Longer patterns first
  });

  for (const { pattern, translate } of sortedPatterns) {
    const match = message.match(pattern);
    if (match) {
      return translate(match, ...match.slice(1));
    }
  }

  // If no pattern matches, try to improve the message format
  return improveErrorMessage(message, fieldTranslations, t);
};

/**
 * Improves error message format by translating field names and cleaning up
 */
const improveErrorMessage = (message, fieldTranslations, t) => {
  let improved = message;

  // Replace field names with translations
  Object.entries(fieldTranslations).forEach(([field, translation]) => {
    const regex = new RegExp(`\\b${field}\\b`, 'gi');
    improved = improved.replace(regex, translation);
  });

  // Clean up common patterns
  improved = improved
    .replace(/Value error,\s*/gi, '')
    .replace(/CountryCode\./gi, '')
    .replace(/\s+/g, ' ')
    .trim();

  // Capitalize first letter
  if (improved.length > 0) {
    improved = improved.charAt(0).toUpperCase() + improved.slice(1);
  }

  return improved || message;
};

/**
 * Formats currency amount
 */
const formatCurrency = (amount) => {
  const numAmount = parseFloat(amount.replace(/,/g, ''));
  if (isNaN(numAmount)) return amount;
  
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
  }).format(numAmount);
};

/**
 * Formats validation errors from Pydantic/FastAPI
 */
export const formatValidationErrors = (errors, t) => {
  if (!Array.isArray(errors)) {
    return [translateError(errors, t)];
  }

  return errors.map((error) => {
    const field = error.loc?.slice(-1)[0] || 'field';
    const message = error.msg || 'Validation error';
    
    // Translate field name
    const fieldTranslations = {
      'monthly_income': t('form.monthlyIncome'),
      'requested_amount': t('form.requestedAmount'),
      'full_name': t('form.fullName'),
      'identity_document': t('form.identityDocument'),
      'country': t('form.country'),
      'body': t('errors.requestBody'),
    };

    const translatedField = fieldTranslations[field] || field;
    const translatedMessage = translateError(message, t);

    // Check if message contains additional info (like income amounts)
    let fullMessage = translatedMessage;
    
    // Special handling for full_name validation - ensure complete message
    if (field === 'full_name') {
      if (message.includes('should include at least first and last name') || 
          message.includes('Full name should include at least first and last name')) {
        fullMessage = t('errors.fullNameShouldIncludeFirstLast');
      } else if (message.includes('should include at least')) {
        const match = message.match(/(\d+)/);
        if (match) {
          fullMessage = t('errors.fullNameShouldInclude', { count: match[1] });
        } else {
          // Fallback to generic message if pattern doesn't match
          fullMessage = t('errors.fullNameShouldIncludeFirstLast');
        }
      }
    }
    
    // Extract additional context from the original message
    if (message.includes('below minimum requirement')) {
      const match = message.match(/CountryCode\.(\w+):\s*\$?([\d,]+\.?\d*)/i);
      if (match) {
        const countryCode = match[1];
        const amount = match[2];
        const countryName = t(`countries.${countryCode}`) || countryCode;
        const formattedAmount = formatCurrency(amount);
        fullMessage = t('errors.belowMinimumRequirement', { 
          country: countryName, 
          amount: formattedAmount 
        });
      }
    }

    if (message.includes('Your income:')) {
      const match = message.match(/Your income:\s*\$?([\d,]+\.?\d*)/i);
      if (match) {
        const amount = match[1];
        const formattedAmount = formatCurrency(amount);
        fullMessage += ` ${t('errors.yourIncome', { amount: formattedAmount })}`;
      }
    }

    return {
      field: translatedField,
      message: fullMessage,
      original: message
    };
  });
};
