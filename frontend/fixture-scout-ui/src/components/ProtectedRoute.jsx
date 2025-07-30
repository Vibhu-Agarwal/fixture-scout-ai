// src/components/ProtectedRoute.jsx
import React from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Box, CircularProgress, Typography } from '@mui/material';
import Fade from '@mui/material/Fade';

const ProtectedRoute = () => {
    const { isAuthenticated, loadingAuth } = useAuth();
    const location = useLocation();

    if (loadingAuth) {
        return (
            <Fade in timeout={300}>
                <Box sx={{
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    minHeight: '100vh',
                    flexDirection: 'column',
                    gap: 2,
                    background: 'linear-gradient(135deg, #0A0A0A 0%, #1A1A1A 100%)'
                }}>
                    <CircularProgress
                        size={60}
                        thickness={4}
                        sx={{
                            color: '#4ECDC4',
                        }}
                    />
                    <Typography variant="body1" color="text.secondary">
                        Loading...
                    </Typography>
                </Box>
            </Fade>
        );
    }

    if (!isAuthenticated) {
        // Redirect them to the /login page, but save the current location they were
        // trying to go to so we can send them along after they login.
        return <Navigate to="/login" state={{ from: location }} replace />;
    }

    return <Outlet />; // Render the child route component
};

export default ProtectedRoute;