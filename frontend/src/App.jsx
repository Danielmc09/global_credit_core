import { useState, useEffect } from 'react';
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import ApplicationForm from './components/ApplicationForm';
import ApplicationList from './components/ApplicationList';
import websocketService from './services/websocket';
import { WS_MESSAGE_TYPES, CONNECTION_STATUS } from './utils/constants';

function App() {
  const [wsStatus, setWsStatus] = useState(CONNECTION_STATUS.DISCONNECTED);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

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
        {wsStatus === CONNECTION_STATUS.CONNECTED ? '● Connected' : '○ Disconnected'}
      </div>

      {/* Header */}
      <div className="header">
        <div className="container">
          <h1>Global Credit Core</h1>
          <p>Multi-Country Credit Application System</p>
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
