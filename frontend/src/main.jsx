import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'
import { LanguageProvider } from './context/LanguageContext'

ReactDOM.createRoot(document.getElementById('root')).render(
  // Temporarily disable StrictMode to prevent double mounting in development
  // which causes duplicate WebSocket listener registration
  // <React.StrictMode>
    <LanguageProvider>
      <App />
    </LanguageProvider>
  // </React.StrictMode>,
)
