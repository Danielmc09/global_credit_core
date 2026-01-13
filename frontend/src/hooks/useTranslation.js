import { useLanguage } from '../context/LanguageContext';
import enTranslations from '../translations/en.json';
import esTranslations from '../translations/es.json';

const translations = {
  en: enTranslations,
  es: esTranslations,
};

export const useTranslation = () => {
  const { language } = useLanguage();

  const t = (key, params = {}) => {
    const keys = key.split('.');
    let value = translations[language];

    for (const k of keys) {
      if (value && typeof value === 'object') {
        value = value[k];
      } else {
        return key; // Return key if translation not found
      }
    }

    let result = value || key;

    // Replace parameters in the translation string
    if (typeof result === 'string' && Object.keys(params).length > 0) {
      Object.entries(params).forEach(([paramKey, paramValue]) => {
        result = result.replace(new RegExp(`{{${paramKey}}}`, 'g'), paramValue);
      });
    }

    return result;
  };

  return { t, language };
};
