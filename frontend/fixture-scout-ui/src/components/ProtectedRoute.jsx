// src/components/ProtectedRoute.jsx
import React from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Box, CircularProgress } from '@mui/material';

const ProtectedRoute = () => {
    const { isAuthenticated, loadingAuth } = useAuth();
    const location = useLocation();

    if (loadingAuth) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
                <CircularProgress />
            </Box>
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