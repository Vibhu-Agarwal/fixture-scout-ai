// src/App.jsx
import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { ThemeProvider, createTheme, CssBaseline, CircularProgress, Box, Container, AppBar, Toolbar, Typography, Button } from '@mui/material';
import ProtectedRoute from './components/ProtectedRoute'; // Assuming this exists

// Import your page components
import LoginPage from './pages/LoginPage';
import PreferencesPage from './pages/PreferencesPage';
import RemindersPage from './pages/RemindersPage';

const NotFoundPage = () => <Typography variant="h4" sx={{ p: 2, textAlign: 'center', mt: 4 }}>404 - Page Not Found</Typography>;

const theme = createTheme({ /* ... your theme ... */ });

function MainLayout() {
  const { isAuthenticated, logoutUser, currentUser } = useAuth();

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}> {/* Ensure layout takes full height */}
      <AppBar position="static">
        {/* Toolbar is usually fine, it's for internal spacing. AppBar itself should be full width. */}
        {/* If AppBar is not full width, something is wrong with its parent or CssBaseline isn't working as expected */}
        <Container maxWidth="xl"> {/* Or use false for completely fluid, or keep lg if that's desired max for content *within* appbar */}
          <Toolbar disableGutters> {/* disableGutters removes default padding if you want edge-to-edge Toolbar content */}
            <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
              Fixture Scout AI
            </Typography>
            {isAuthenticated && currentUser && (
              <Typography sx={{ mr: 2 }}>
                Hello, {currentUser.displayName || currentUser.email}
              </Typography>
            )}
            {isAuthenticated ? (
              <Button color="inherit" onClick={logoutUser}>Logout</Button>
            ) : (
              <Button color="inherit" component={RouterLink} to="/login">Login</Button>
              // Using RouterLink for navigation without full page reload
            )}
          </Toolbar>
        </Container>
      </AppBar>

      {/* Main content area */}
      {/* Using component="main" for semantic HTML and flexGrow to take available space */}
      <Container
        component="main"
        maxWidth="xl" // << TRY CHANGING THIS: 'xl', 'lg', 'md', or false for fluid
        // If you set it to 'false', it will try to be 100% width of viewport.
        // 'xl' is often a good compromise for wide screens.
        sx={{
          flexGrow: 1, // Makes the container take up available vertical space
          py: 3,      // Add some padding top and bottom
          display: 'flex', // Added to help center content if maxWidth is hit
          flexDirection: 'column' // Added to help center content
        }}
      >
        <Outlet /> {/* This is where the routed page component will be rendered */}
      </Container>

      {/* Optional Footer */}
      <Box component="footer" sx={{ bgcolor: 'background.paper', py: 2, mt: 'auto' }}>
        <Container maxWidth="lg">
          <Typography variant="body2" color="text.secondary" align="center">
            {'© '}
            Fixture Scout AI {new Date().getFullYear()}
            {'.'}
          </Typography>
        </Container>
      </Box>
    </Box>
  );
}

// Need to import RouterLink for proper navigation with react-router
import { Link as RouterLink } from 'react-router-dom';


function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <AuthProvider>
        <Router>
          <Routes>
            <Route element={<MainLayout />}>
              <Route path="/login" element={<LoginPage />} />
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