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
  Divider,
  useMediaQuery,
  Fade,
  Slide
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import AccountCircle from '@mui/icons-material/AccountCircle';
import SportsSoccerIcon from '@mui/icons-material/SportsSoccer';

// Import your page components
import LoginPage from './pages/LoginPage';
import PreferencesPage from './pages/PreferencesPage';
import RemindersPage from './pages/RemindersPage';
import ProtectedRoute from './components/ProtectedRoute';

const NotFoundPage = () => (
  <Box sx={{
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '60vh',
    textAlign: 'center'
  }}>
    <Typography variant="h2" sx={{ mb: 2, fontWeight: 'bold', background: 'linear-gradient(45deg, #FF6B6B, #4ECDC4)', backgroundClip: 'text', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
      404
    </Typography>
    <Typography variant="h5" sx={{ mb: 1, color: 'text.primary' }}>
      Page Not Found
    </Typography>
    <Typography variant="body1" color="text.secondary">
      The page you're looking for doesn't exist.
    </Typography>
  </Box>
);

// Create a modern dark theme
const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#4ECDC4',
      light: '#7FDDD7',
      dark: '#2A9D8F',
      contrastText: '#1A1A1A',
    },
    secondary: {
      main: '#FF6B6B',
      light: '#FF8E8E',
      dark: '#E55A5A',
      contrastText: '#FFFFFF',
    },
    background: {
      default: '#0A0A0A',
      paper: '#1A1A1A',
      elevated: '#2A2A2A',
    },
    surface: {
      main: '#1A1A1A',
      light: '#2A2A2A',
      dark: '#0A0A0A',
    },
    text: {
      primary: '#FFFFFF',
      secondary: '#B0B0B0',
      disabled: '#666666',
    },
    divider: 'rgba(255, 255, 255, 0.12)',
    action: {
      hover: 'rgba(255, 255, 255, 0.08)',
      selected: 'rgba(78, 205, 196, 0.16)',
      disabled: 'rgba(255, 255, 255, 0.3)',
    },
  },
  typography: {
    fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
    h1: {
      fontWeight: 700,
      fontSize: '2.5rem',
      '@media (min-width:600px)': {
        fontSize: '3rem',
      },
    },
    h2: {
      fontWeight: 600,
      fontSize: '2rem',
      '@media (min-width:600px)': {
        fontSize: '2.5rem',
      },
    },
    h3: {
      fontWeight: 600,
      fontSize: '1.75rem',
    },
    h4: {
      fontWeight: 600,
      fontSize: '1.5rem',
    },
    h5: {
      fontWeight: 600,
      fontSize: '1.25rem',
    },
    h6: {
      fontWeight: 600,
      fontSize: '1.125rem',
    },
    body1: {
      fontSize: '1rem',
      lineHeight: 1.6,
    },
    body2: {
      fontSize: '0.875rem',
      lineHeight: 1.5,
    },
    button: {
      fontWeight: 600,
      textTransform: 'none',
    },
  },
  shape: {
    borderRadius: 12,
  },
  components: {
    MuiAppBar: {
      styleOverrides: {
        root: {
          background: 'linear-gradient(135deg, #1A1A1A 0%, #2A2A2A 100%)',
          backdropFilter: 'blur(10px)',
          borderBottom: '1px solid rgba(255, 255, 255, 0.12)',
          boxShadow: '0 4px 20px rgba(0, 0, 0, 0.3)',
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
          background: 'linear-gradient(135deg, #1A1A1A 0%, #2A2A2A 100%)',
          border: '1px solid rgba(255, 255, 255, 0.12)',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          padding: '10px 24px',
          fontWeight: 600,
          textTransform: 'none',
          transition: 'all 0.2s ease-in-out',
          '&:hover': {
            transform: 'translateY(-1px)',
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.3)',
          },
        },
        contained: {
          background: 'linear-gradient(135deg, #4ECDC4 0%, #2A9D8F 100%)',
          '&:hover': {
            background: 'linear-gradient(135deg, #5EDDD4 0%, #3AAD9F 100%)',
          },
        },
        outlined: {
          borderColor: 'rgba(255, 255, 255, 0.3)',
          '&:hover': {
            borderColor: '#4ECDC4',
            backgroundColor: 'rgba(78, 205, 196, 0.08)',
          },
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            borderRadius: 8,
            '&:hover .MuiOutlinedInput-notchedOutline': {
              borderColor: 'rgba(255, 255, 255, 0.5)',
            },
            '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
              borderColor: '#4ECDC4',
            },
          },
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          background: 'linear-gradient(135deg, #1A1A1A 0%, #2A2A2A 100%)',
          border: '1px solid rgba(255, 255, 255, 0.12)',
          borderRadius: 12,
        },
      },
    },
    MuiListItem: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          marginBottom: 4,
          '&:hover': {
            backgroundColor: 'rgba(255, 255, 255, 0.04)',
          },
        },
      },
    },
  },
});

function MainLayout() {
  const { isAuthenticated, logoutUser, currentUser } = useAuth();
  const navigate = useNavigate();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

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
    { label: 'Preferences', path: '/preferences', icon: '⚙️' },
    { label: 'Reminders', path: '/reminders', icon: '🔔' },
  ];

  return (
    <Box sx={{ minHeight: '100vh', background: 'linear-gradient(135deg, #0A0A0A 0%, #1A1A1A 100%)' }}>
      <AppBar position="static" elevation={0}>
        <Container maxWidth="xl">
          <Toolbar disableGutters sx={{ minHeight: { xs: 64, md: 70 } }}>
            {/* Mobile Menu */}
            {isAuthenticated && (
              <Box sx={{ display: { xs: 'flex', md: 'none' }, mr: 2 }}>
                <IconButton
                  size="large"
                  aria-label="navigation menu"
                  onClick={handleOpenNavMenu}
                  sx={{
                    color: 'white',
                    '&:hover': {
                      backgroundColor: 'rgba(255, 255, 255, 0.1)',
                    },
                  }}
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
                  TransitionComponent={Slide}
                  PaperProps={{
                    sx: {
                      background: 'linear-gradient(135deg, #2A2A2A 0%, #1A1A1A 100%)',
                      border: '1px solid rgba(255, 255, 255, 0.12)',
                      borderRadius: 2,
                      mt: 1,
                    },
                  }}
                >
                  {navLinks.map((link) => (
                    <MenuItem
                      key={link.label}
                      onClick={() => handleNavAndClose(link.path)}
                      sx={{
                        minWidth: 150,
                        '&:hover': {
                          backgroundColor: 'rgba(78, 205, 196, 0.1)',
                        },
                      }}
                    >
                      <Typography textAlign="center" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <span>{link.icon}</span>
                        {link.label}
                      </Typography>
                    </MenuItem>
                  ))}
                </Menu>
              </Box>
            )}

            {/* Logo/Brand */}
            <Box sx={{
              display: 'flex',
              alignItems: 'center',
              flexGrow: 1,
              justifyContent: { xs: 'center', md: 'flex-start' }
            }}>
              <Box
                component={RouterLink}
                to="/"
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  textDecoration: 'none',
                  color: 'inherit',
                  '&:hover': {
                    textDecoration: 'none',
                  },
                }}
              >
                <SportsSoccerIcon sx={{
                  fontSize: { xs: 28, md: 32 },
                  mr: 1,
                  color: '#4ECDC4',
                }} />
                <Typography
                  variant="h6"
                  sx={{
                    fontWeight: 700,
                    background: 'linear-gradient(45deg, #4ECDC4, #FF6B6B)',
                    backgroundClip: 'text',
                    WebkitBackgroundClip: 'text',
                    WebkitTextFillColor: 'transparent',
                    fontSize: { xs: '1.25rem', md: '1.5rem' },
                  }}
                >
                  FixtureScout
                </Typography>
              </Box>
            </Box>

            {/* Desktop Navigation */}
            {isAuthenticated && (
              <Box sx={{ display: { xs: 'none', md: 'flex' }, gap: 1 }}>
                {navLinks.map((link) => (
                  <Button
                    key={link.label}
                    onClick={() => handleNavAndClose(link.path)}
                    sx={{
                      color: 'white',
                      px: 3,
                      py: 1,
                      borderRadius: 2,
                      '&:hover': {
                        backgroundColor: 'rgba(255, 255, 255, 0.1)',
                        transform: 'translateY(-1px)',
                      },
                    }}
                  >
                    <span style={{ marginRight: '8px' }}>{link.icon}</span>
                    {link.label}
                  </Button>
                ))}
              </Box>
            )}

            {/* User Area */}
            <Box sx={{ ml: 2 }}>
              {isAuthenticated && currentUser ? (
                <>
                  <Tooltip title="User Menu">
                    <IconButton
                      onClick={handleOpenUserMenu}
                      sx={{
                        color: 'white',
                        '&:hover': {
                          backgroundColor: 'rgba(255, 255, 255, 0.1)',
                        },
                      }}
                    >
                      <AccountCircle sx={{ fontSize: '2rem' }} />
                    </IconButton>
                  </Tooltip>
                  <Menu
                    sx={{ mt: 1 }}
                    id="menu-appbar-user"
                    anchorEl={anchorElUser}
                    anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
                    keepMounted
                    transformOrigin={{ vertical: 'top', horizontal: 'right' }}
                    open={Boolean(anchorElUser)}
                    onClose={handleCloseUserMenu}
                    TransitionComponent={Fade}
                    PaperProps={{
                      sx: {
                        background: 'linear-gradient(135deg, #2A2A2A 0%, #1A1A1A 100%)',
                        border: '1px solid rgba(255, 255, 255, 0.12)',
                        borderRadius: 2,
                        minWidth: 180,
                      },
                    }}
                  >
                    <MenuItem disabled sx={{ justifyContent: 'center', opacity: 0.7 }}>
                      <Typography variant="body2" textAlign="center">
                        {currentUser.displayName || currentUser.email.split('@')[0]}
                      </Typography>
                    </MenuItem>
                    <Divider sx={{ my: 1 }} />
                    <MenuItem
                      onClick={handleLogoutAndClose}
                      sx={{
                        justifyContent: 'center',
                        '&:hover': {
                          backgroundColor: 'rgba(255, 107, 107, 0.1)',
                        },
                      }}
                    >
                      <Typography textAlign="center" color="error.main">
                        Logout
                      </Typography>
                    </MenuItem>
                  </Menu>
                </>
              ) : (
                <Button
                  component={RouterLink}
                  to="/login"
                  variant="contained"
                  sx={{
                    background: 'linear-gradient(135deg, #4ECDC4 0%, #2A9D8F 100%)',
                    color: 'white',
                    px: 3,
                    py: 1,
                    '&:hover': {
                      background: 'linear-gradient(135deg, #5EDDD4 0%, #3AAD9F 100%)',
                      transform: 'translateY(-1px)',
                    },
                  }}
                >
                  Login
                </Button>
              )}
            </Box>
          </Toolbar>
        </Container>
      </AppBar>

      <Container
        maxWidth="lg"
        sx={{
          mt: { xs: 2, md: 4 },
          mb: { xs: 2, md: 4 },
          px: { xs: 2, md: 3 },
          minHeight: 'calc(100vh - 120px)',
        }}
      >
        <Fade in timeout={300}>
          <Box>
            <Outlet />
          </Box>
        </Fade>
      </Container>
    </Box>
  );
}

// App function with Routes remains the same
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