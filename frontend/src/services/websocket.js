import { WS_URL, WS_ACTIONS, WS_MESSAGE_TYPES, CONNECTION_STATUS } from '../utils/constants';

class WebSocketService {
  constructor() {
    this.ws = null;
    this.listeners = new Set();
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 3000;
    this.isConnecting = false;
    this.pingInterval = null;
    this.pingIntervalMs = 20000; // Send ping every 20 seconds
  }

  connect() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      return;
    }

    if (this.isConnecting) {
      return;
    }

    this.isConnecting = true;

    try {
      this.ws = new WebSocket(WS_URL);

      this.ws.onopen = () => {
        this.isConnecting = false;
        this.reconnectAttempts = 0;
        this.startPingInterval();
        this.notifyListeners({ type: WS_MESSAGE_TYPES.CONNECTION, status: CONNECTION_STATUS.CONNECTED });
      };

      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          this.notifyListeners(message);
        } catch (error) {
          // Error parsing message - ignore
        }
      };

      this.ws.onerror = () => {
        this.isConnecting = false;
        this.notifyListeners({ type: WS_MESSAGE_TYPES.CONNECTION, status: CONNECTION_STATUS.ERROR });
        this.attemptReconnect();
      };

      this.ws.onclose = () => {
        this.isConnecting = false;
        this.ws = null;
        this.stopPingInterval();
        this.notifyListeners({ type: WS_MESSAGE_TYPES.CONNECTION, status: CONNECTION_STATUS.DISCONNECTED });
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
          this.attemptReconnect();
        }
      };
    } catch (error) {
      this.isConnecting = false;
    }
  }

  attemptReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      setTimeout(() => {
        this.connect();
      }, this.reconnectDelay);
    }
  }

  disconnect() {
    if (this.ws) {
      this.reconnectAttempts = this.maxReconnectAttempts; // Prevent auto-reconnect
      this.stopPingInterval();
      this.ws.close();
      this.ws = null;
    }
  }

  startPingInterval() {
    this.stopPingInterval();

    this.pingInterval = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.send({ action: WS_ACTIONS.PING });
      }
    }, this.pingIntervalMs);
  }

  stopPingInterval() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  send(message) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }

  subscribe(applicationId) {
    this.send({
      action: WS_ACTIONS.SUBSCRIBE,
      application_id: applicationId,
    });
  }

  addListener(callback) {
    this.listeners.add(callback);
  }

  removeListener(callback) {
    this.listeners.delete(callback);
  }

  notifyListeners(message) {
    this.listeners.forEach((callback) => {
      try {
        callback(message);
      } catch (error) {
        // Error in listener - ignore
      }
    });
  }

  isConnected() {
    return this.ws && this.ws.readyState === WebSocket.OPEN;
  }
}

// Singleton instance
const websocketService = new WebSocketService();

export default websocketService;
