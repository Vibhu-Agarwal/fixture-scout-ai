// src/pages/LoginPage.jsx
import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { signInWithPopup } from 'firebase/auth';
import { auth, googleProvider } from '../firebaseConfig';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';

import Button from '@mui/material/Button';
import Container from '@mui/material/Container';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import Alert from '@mui/material/Alert';
import Paper from '@mui/material/Paper';
import GoogleIcon from '@mui/icons-material/Google';
import SportsSoccerIcon from '@mui/icons-material/SportsSoccer';
import Fade from '@mui/material/Fade';
import useMediaQuery from '@mui/material/useMediaQuery';
import { useTheme } from '@mui/material/styles';

const API_GATEWAY_BASE_URL = "API_GATEWAY_BASE_URL";
const ENSURE_PROFILE_ENDPOINT = `${API_GATEWAY_BASE_URL}/auth/firebase/ensure-profile`;

function LoginPage() {
    const navigate = useNavigate();
    const location = useLocation();
    const { loginUser, isAuthenticated, loadingAuth } = useAuth();
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

    const [error, setError] = useState('');
    const [isProcessing, setIsProcessing] = useState(false);

    const from = location.state?.from?.pathname || "/preferences";

    useEffect(() => {
        if (!loadingAuth && isAuthenticated) {
            navigate(from, { replace: true });
        }
    }, [isAuthenticated, loadingAuth, navigate, from]);

    const handleGoogleSignIn = async () => {
        setError('');
        setIsProcessing(true);
        try {
            const result = await signInWithPopup(auth, googleProvider);
            const firebaseUser = result.user;

            if (firebaseUser) {
                const firebaseIdToken = await firebaseUser.getIdToken(true);

                try {
                    const backendResponse = await axios.post(ENSURE_PROFILE_ENDPOINT, {
                        firebase_id_token: firebaseIdToken,
                    });

                    if (backendResponse.status === 200 && backendResponse.data) {
                        console.info("Backend profile ensured/retrieved:", backendResponse.data);
                        navigate(from, { replace: true });
                    } else {
                        throw new Error(backendResponse.data.detail || "Failed to ensure profile on backend.");
                    }
                } catch (backendError) {
                    console.error("Backend ensure-profile error:", backendError);
                    let errorMessage = "Login failed after Google Sign-In. Could not sync with application backend.";
                    if (backendError.response && backendError.response.data && backendError.response.data.detail) {
                        errorMessage = backendError.response.data.detail;
                    } else if (backendError.message) {
                        errorMessage = backendError.message;
                    }
                    setError(errorMessage);
                }
            } else {
                throw new Error("No user information received from Google Sign-In.");
            }
        } catch (googleAuthError) {
            console.error("Google Sign-In Error:", googleAuthError);
            let displayError = "Google Sign-In failed. Please try again.";
            if (googleAuthError.code === 'auth/popup-closed-by-user') {
                displayError = "Sign-in popup closed before completion.";
            } else if (googleAuthError.code === 'auth/cancelled-popup-request') {
                displayError = "Multiple sign-in attempts. Please try again.";
            }
            setError(displayError);
        } finally {
            setIsProcessing(false);
        }
    };

    if (loadingAuth) {
        return (
            <Box sx={{
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                minHeight: '80vh',
                flexDirection: 'column',
                gap: 2
            }}>
                <CircularProgress size={60} thickness={4} />
                <Typography variant="body1" color="text.secondary">
                    Loading...
                </Typography>
            </Box>
        );
    }

    if (isAuthenticated) {
        return null;
    }

    return (
        <Container component="main" maxWidth="sm">
            <Fade in timeout={500}>
                <Box
                    sx={{
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        minHeight: '80vh',
                        py: 4,
                    }}
                >
                    <Paper
                        elevation={8}
                        sx={{
                            p: { xs: 3, md: 5 },
                            width: '100%',
                            maxWidth: 450,
                            background: 'linear-gradient(135deg, #1A1A1A 0%, #2A2A2A 100%)',
                            border: '1px solid rgba(255, 255, 255, 0.12)',
                            borderRadius: 3,
                            position: 'relative',
                            overflow: 'hidden',
                            '&::before': {
                                content: '""',
                                position: 'absolute',
                                top: 0,
                                left: 0,
                                right: 0,
                                height: '4px',
                                background: 'linear-gradient(90deg, #4ECDC4, #FF6B6B, #4ECDC4)',
                                backgroundSize: '200% 100%',
                                animation: 'gradientShift 3s ease-in-out infinite',
                            },
                        }}
                    >
                        {/* Logo and Title */}
                        <Box sx={{ textAlign: 'center', mb: 4 }}>
                            <Box sx={{
                                display: 'flex',
                                justifyContent: 'center',
                                alignItems: 'center',
                                mb: 2,
                                gap: 1
                            }}>
                                <SportsSoccerIcon sx={{
                                    fontSize: { xs: 40, md: 48 },
                                    color: '#4ECDC4',
                                    filter: 'drop-shadow(0 0 8px rgba(78, 205, 196, 0.3))'
                                }} />
                                <Typography
                                    variant={isMobile ? "h4" : "h3"}
                                    component="h1"
                                    sx={{
                                        fontWeight: 700,
                                        background: 'linear-gradient(45deg, #4ECDC4, #FF6B6B)',
                                        backgroundClip: 'text',
                                        WebkitBackgroundClip: 'text',
                                        WebkitTextFillColor: 'transparent',
                                        textAlign: 'center',
                                    }}
                                >
                                    FixtureScout
                                </Typography>
                            </Box>
                            <Typography
                                variant="h5"
                                component="h2"
                                gutterBottom
                                sx={{
                                    fontWeight: 600,
                                    color: 'text.primary',
                                    mb: 1
                                }}
                            >
                                Welcome Back
                            </Typography>
                            <Typography
                                variant="body1"
                                color="text.secondary"
                                sx={{
                                    lineHeight: 1.6,
                                    maxWidth: 300,
                                    mx: 'auto'
                                }}
                            >
                                Sign in to access your personalized football match reminders and preferences.
                            </Typography>
                        </Box>

                        {/* Error Alert */}
                        {error && (
                            <Alert
                                severity="error"
                                sx={{
                                    mb: 3,
                                    borderRadius: 2,
                                    '& .MuiAlert-icon': {
                                        color: '#FF6B6B'
                                    }
                                }}
                            >
                                {error}
                            </Alert>
                        )}

                        {/* Sign In Button */}
                        <Button
                            type="button"
                            fullWidth
                            variant="contained"
                            size="large"
                            onClick={handleGoogleSignIn}
                            disabled={isProcessing}
                            startIcon={
                                isProcessing ? (
                                    <CircularProgress size={20} color="inherit" />
                                ) : (
                                    <GoogleIcon sx={{ fontSize: 24 }} />
                                )
                            }
                            sx={{
                                py: 2,
                                px: 3,
                                fontSize: '1.1rem',
                                fontWeight: 600,
                                borderRadius: 2,
                                background: isProcessing
                                    ? 'linear-gradient(135deg, #666, #888)'
                                    : 'linear-gradient(135deg, #4ECDC4 0%, #2A9D8F 100%)',
                                color: 'white',
                                textTransform: 'none',
                                boxShadow: '0 4px 20px rgba(78, 205, 196, 0.3)',
                                transition: 'all 0.3s ease-in-out',
                                '&:hover': {
                                    background: isProcessing
                                        ? 'linear-gradient(135deg, #666, #888)'
                                        : 'linear-gradient(135deg, #5EDDD4 0%, #3AAD9F 100%)',
                                    transform: 'translateY(-2px)',
                                    boxShadow: '0 8px 30px rgba(78, 205, 196, 0.4)',
                                },
                                '&:disabled': {
                                    transform: 'none',
                                    boxShadow: 'none',
                                },
                            }}
                        >
                            {isProcessing ? "Signing In..." : "Continue with Google"}
                        </Button>

                        {/* Footer Text */}
                        <Box sx={{ textAlign: 'center', mt: 4 }}>
                            <Typography
                                variant="body2"
                                color="text.secondary"
                                sx={{
                                    opacity: 0.8,
                                    fontSize: '0.875rem'
                                }}
                            >
                                By signing in, you agree to our terms of service and privacy policy.
                            </Typography>
                        </Box>
                    </Paper>
                </Box>
            </Fade>

            <style>
                {`
                    @keyframes gradientShift {
                        0%, 100% { background-position: 0% 50%; }
                        50% { background-position: 100% 50%; }
                    }
                `}
            </style>
        </Container>
    );
}

export default LoginPage;