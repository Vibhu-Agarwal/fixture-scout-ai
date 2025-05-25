// src/App.jsx
import React, { useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, Outlet, Link as RouterLink, useNavigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import {
  ThemeProvider,
  createTheme,
  CssBaseline,
  CircularProgress,
  Box,
  Container,
  AppBar,
  Toolbar,
  Typography,
  Button,
  IconButton,
  Menu,
  MenuItem,
  Tooltip,
  Divider
  // Stack // We might not need Stack if we manage flex items directly in Toolbar
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import AccountCircle from '@mui/icons-material/AccountCircle';

// Import your page components
import LoginPage from './pages/LoginPage';
import PreferencesPage from './pages/PreferencesPage';
import RemindersPage from './pages/RemindersPage';
import ProtectedRoute from './components/ProtectedRoute';

const NotFoundPage = () => <Typography variant="h4" sx={{ p: 2 }}>404 - Page Not Found</Typography>;

const theme = createTheme({ /* ... your theme ... */ });

function MainLayout() {
  const { isAuthenticated, logoutUser, currentUser } = useAuth();
  const navigate = useNavigate();

  const [anchorElNav, setAnchorElNav] = useState(null);
  const [anchorElUser, setAnchorElUser] = useState(null);

  const handleOpenNavMenu = (event) => setAnchorElNav(event.currentTarget);
  const handleCloseNavMenu = () => setAnchorElNav(null);
  const handleOpenUserMenu = (event) => setAnchorElUser(event.currentTarget);
  const handleCloseUserMenu = () => setAnchorElUser(null);

  const handleNavAndClose = (path) => {
    navigate(path);
    handleCloseNavMenu();
    handleCloseUserMenu();
  };

  const handleLogoutAndClose = () => {
    logoutUser();
    handleCloseUserMenu();
    navigate('/login');
  };

  const navLinks = [
    { label: 'Preferences', path: '/preferences' },
    { label: 'Reminders', path: '/reminders' },
  ];

  return (
    <>
      <AppBar position="static">
        <Container maxWidth="xl">
          <Toolbar disableGutters>

            {/* Hamburger Menu for Mobile (isAuthenticated) - Placed on the Left */}
            {isAuthenticated && (
              <Box sx={{ display: { xs: 'flex', md: 'none' }, mr: 1 }}> {/* Added mr for spacing */}
                <IconButton
                  size="large"
                  aria-label="navigation menu"
                  onClick={handleOpenNavMenu}
                  color="inherit"
                >
                  <MenuIcon />
                </IconButton>
                <Menu
                  id="menu-appbar-nav"
                  anchorEl={anchorElNav}
                  anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
                  keepMounted
                  transformOrigin={{ vertical: 'top', horizontal: 'left' }}
                  open={Boolean(anchorElNav)}
                  onClose={handleCloseNavMenu}
                >
                  {navLinks.map((link) => (
                    <MenuItem key={link.label} onClick={() => handleNavAndClose(link.path)}>
                      <Typography textAlign="center">{link.label}</Typography>
                    </MenuItem>
                  ))}
                </Menu>
              </Box>
            )}

            {/* App Title/Logo */}
            <Typography
              variant="h6"
              noWrap
              component={RouterLink}
              to="/"
              sx={{
                mr: 2, // Margin right for spacing
                // Display logic:
                // - On xs (mobile): display if NOT authenticated OR if authenticated but NO hamburger (which isn't our case here with hamburger)
                // - On md (desktop): always display
                // Better logic: make it grow and center itself if it's the main element.
                display: 'flex', // Always display as flex item
                fontFamily: 'monospace',
                fontWeight: 700,
                letterSpacing: '.1rem',
                color: 'inherit',
                textDecoration: 'none',
                // This will make it take available space and allow centering if other elements are fixed width
                flexGrow: 1,
                // Center the title text itself if it's the only growing element
                // This works well when hamburger and user icon are on either side
                justifyContent: { xs: 'center', md: 'flex-start' }, // Center on mobile, start on desktop
                // If hamburger isn't there (e.g. not authenticated), it will naturally center better.
                // Let's refine the centering with a wrapper Box for the title if needed.
              }}
            >
              FixtureScout
            </Typography>

            {/* Desktop Navigation Links (isAuthenticated) - Placed after title on desktop */}
            {isAuthenticated && (
              <Box sx={{ display: { xs: 'none', md: 'flex' }, ml: 'auto' }}> {/* Push to right after title */}
                {navLinks.map((link) => (
                  <Button
                    key={link.label}
                    onClick={() => handleNavAndClose(link.path)}
                    sx={{ my: 2, color: 'white', display: 'block', mx: 1 }}
                  >
                    {link.label}
                  </Button>
                ))}
              </Box>
            )}

            {/* Spacer: This will push User Area to the far right on desktop if nav links are present */}
            {/* On mobile, if only title and user area, title with flexGrow:1 will center it against user area */}
            {/* This might not be needed if title has flexGrow:1 and desktop nav is also present */}
            {/* Let's remove this specific spacer and rely on flexGrow of title and placement of User Area */}
            {/* <Box sx={{ flexGrow: 1 }} /> */}


            {/* User Area (Login/Logout, User Name) - Placed on the Right */}
            <Box sx={{ flexGrow: 0, ml: isAuthenticated ? 2 : 0 }}> {/* Add margin-left if authenticated to space from nav/title */}
              {isAuthenticated && currentUser ? (
                <>
                  <Tooltip title="User Menu">
                    <IconButton onClick={handleOpenUserMenu} sx={{ p: 0 }}>
                      <AccountCircle sx={{ color: 'white', fontSize: '2rem' }} />
                    </IconButton>
                  </Tooltip>
                  <Menu
                    sx={{ mt: '45px' }}
                    id="menu-appbar-user"
                    anchorEl={anchorElUser}
                    anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
                    keepMounted
                    transformOrigin={{ vertical: 'top', horizontal: 'right' }}
                    open={Boolean(anchorElUser)}
                    onClose={handleCloseUserMenu}
                  >
                    <MenuItem disabled sx={{ justifyContent: 'center' }}>
                      <Typography textAlign="center">
                        {currentUser.displayName || currentUser.email.split('@')[0]}
                      </Typography>
                    </MenuItem>
                    <Divider />
                    <MenuItem onClick={handleLogoutAndClose} sx={{ justifyContent: 'center' }}>
                      <Typography textAlign="center">Logout</Typography>
                    </MenuItem>
                  </Menu>
                </>
              ) : (
                <Button color="inherit" component={RouterLink} to="/login">Login</Button>
              )}
            </Box>
          </Toolbar>
        </Container>
      </AppBar>
      <Container maxWidth="lg" sx={{ mt: 2, mb: 2 }}>
        <Outlet />
      </Container>
    </>
  );
}

// App function with Routes remains the same
function App() {
  // ... (same as before) ...
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