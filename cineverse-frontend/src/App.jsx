import { BrowserRouter } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { AuthProvider } from './context/AuthContext';
import { CustomerProvider } from './context/CustomerContext';
import AppRoutes from './routes/AppRoutes';

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <CustomerProvider>
          <AppRoutes />
          <Toaster
            position="top-right"
            toastOptions={{
              style: {
                background: '#161f38',
                color: '#fff',
                border: '1px solid rgba(255,255,255,0.1)',
              },
              success: { iconTheme: { primary: '#22c55e', secondary: '#161f38' } },
              error: { iconTheme: { primary: '#E50914', secondary: '#161f38' } },
            }}
          />
        </CustomerProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
