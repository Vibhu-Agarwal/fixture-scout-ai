// src/App.jsx
import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { ThemeProvider, createTheme, CssBaseline, CircularProgress, Box, Container, AppBar, Toolbar, Typography, Button } from '@mui/material'; // Added MUI components
import LoginPage from './pages/LoginPage';
import ProtectedRoute from './components/ProtectedRoute';
import PreferencesPage from './pages/PreferencesPage';
import RemindersPage from './pages/RemindersPage';

// Placeholder Pages (Create these files in src/pages/)
const NotFoundPage = () => <Typography variant="h4" sx={{ p: 2 }}>404 - Page Not Found</Typography>;


// MUI Basic Theme (optional, you can customize this)
const theme = createTheme({
  palette: {
    mode: 'light', // or 'dark'
    primary: {
      main: '#1976d2', // Example primary color
    },
    secondary: {
      main: '#dc004e', // Example secondary color
    },
  },
});

// ProtectedRoute component

// Main App Layout with Basic Nav
function MainLayout() {
  const { isAuthenticated, logoutUser, currentUser } = useAuth();

  return (
    <>
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            Fixture Scout AI
          </Typography>
          {isAuthenticated && currentUser && (
            <Typography sx={{ mr: 2 }}>Hello, {currentUser.displayName || currentUser.email}</Typography>
          )}
          {isAuthenticated ? (
            <Button color="inherit" onClick={logoutUser}>Logout</Button>
          ) : (
            <Button color="inherit" href="/login">Login</Button>
            // Or Link component from react-router-dom if not full page reload
          )}
        </Toolbar>
      </AppBar>
      <Container maxWidth="lg" sx={{ mt: 2, mb: 2 }}>
        <Outlet /> {/* This is where the routed page component will be rendered */}
      </Container>
    </>
  );
}


function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <AuthProvider>
        <Router>
          <Routes>
            <Route element={<MainLayout />}>
              <Route path="/login" element={<LoginPage />} />

              {/* Protected Routes now use the ProtectedRoute component */}
              <Route element={<ProtectedRoute />}>
                <Route path="/preferences" element={<PreferencesPage />} />
                <Route path="/reminders" element={<RemindersPage />} />
                <Route path="/" element={<Navigate to="/preferences" replace />} />
              </Route>

              <Route path="*" element={<NotFoundPage />} />
            </Route>
          </Routes>
        </Router>
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;