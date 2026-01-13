import { useState, useEffect } from 'react';
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import ApplicationForm from './components/ApplicationForm';
import ApplicationList from './components/ApplicationList';
import websocketService from './services/websocket';
import { WS_MESSAGE_TYPES, CONNECTION_STATUS } from './utils/constants';
import { useLanguage } from './context/LanguageContext';
import { useTranslation } from './hooks/useTranslation';

function App() {
  const [wsStatus, setWsStatus] = useState(CONNECTION_STATUS.DISCONNECTED);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const { language, changeLanguage } = useLanguage();
  const { t } = useTranslation();

  useEffect(() => {
    // Connect to WebSocket
    websocketService.connect();

    // Listen for connection status only
    // ApplicationList handles APPLICATION_UPDATE messages directly for real-time updates
    const handleMessage = (message) => {
      if (message.type === WS_MESSAGE_TYPES.CONNECTION) {
        setWsStatus(message.status);
      }
      // Note: APPLICATION_UPDATE is handled by ApplicationList component
      // to avoid conflicts with real-time updates
    };

    websocketService.addListener(handleMessage);

    // Cleanup
    return () => {
      websocketService.removeListener(handleMessage);
    };
  }, []);

  const handleApplicationCreated = () => {
    // Trigger refresh of application list
    setRefreshTrigger((prev) => prev + 1);
  };

  return (
    <div>
      <ToastContainer
        position="bottom-left"
        autoClose={3000}
        hideProgressBar={false}
        newestOnTop={true}
        closeOnClick
        rtl={false}
        pauseOnFocusLoss
        draggable
        pauseOnHover
        theme="light"
      />

      {/* Connection Status */}
      <div
        className={`connection-status ${
          wsStatus === CONNECTION_STATUS.CONNECTED ? 'status-connected' : 'status-disconnected'
        }`}
      >
        {wsStatus === CONNECTION_STATUS.CONNECTED ? t('app.connected') : t('app.disconnected')}
      </div>

      {/* Header */}
      <div className="header">
        <div className="container" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h1>{t('app.title')}</h1>
            <p>{t('app.subtitle')}</p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <label htmlFor="language-select" style={{ color: '#fff', fontSize: '0.9rem' }}>
              Idioma:
            </label>
            <select
              id="language-select"
              value={language}
              onChange={(e) => changeLanguage(e.target.value)}
              style={{
                padding: '8px 12px',
                borderRadius: '4px',
                border: '1px solid #ddd',
                fontSize: '0.9rem',
                cursor: 'pointer',
                backgroundColor: '#fff'
              }}
            >
              <option value="en">English</option>
              <option value="es">Español</option>
            </select>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="container">
        {/* Application Form */}
        <ApplicationForm onApplicationCreated={handleApplicationCreated} />

        {/* Application List */}
        <ApplicationList refreshTrigger={refreshTrigger} />
      </div>
    </div>
  );
}

export default App;
