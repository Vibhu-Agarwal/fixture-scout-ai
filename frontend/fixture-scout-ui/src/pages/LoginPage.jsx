// src/pages/LoginPage.jsx
import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { signInWithPopup } from 'firebase/auth';
import { auth, googleProvider } from '../firebaseConfig'; // Your Firebase auth instance & provider
import { useAuth } from '../contexts/AuthContext'; // Your AuthContext
import axios from 'axios'; // For making API calls

import Button from '@mui/material/Button';
import Container from '@mui/material/Container';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import Alert from '@mui/material/Alert';
import GoogleIcon from '@mui/icons-material/Google'; // MUI Google Icon

const API_GATEWAY_BASE_URL = "API_GATEWAY_BASE_URL";
const ENSURE_PROFILE_ENDPOINT = `${API_GATEWAY_BASE_URL}/auth/firebase/ensure-profile`;

function LoginPage() {
    const navigate = useNavigate();
    const location = useLocation();
    const { loginUser, isAuthenticated, loadingAuth } = useAuth(); // Get loginUser, isAuthenticated, loadingAuth from context
    const [error, setError] = useState('');
    const [isProcessing, setIsProcessing] = useState(false);

    const from = location.state?.from?.pathname || "/preferences"; // Where to redirect after login

    // If already authenticated and not loading, redirect away from login page
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
            // This gives you a Google Access Token. You can use it to access Google APIs.
            // const credential = GoogleAuthProvider.credentialFromResult(result);
            // const token = credential.accessToken;
            // The user object has the Firebase user information.
            const firebaseUser = result.user;

            if (firebaseUser) {
                const firebaseIdToken = await firebaseUser.getIdToken(true); // Get Firebase ID Token (force refresh)

                // Now call your backend to ensure the profile exists and get app-specific user data
                // This step also implicitly "registers" the user with your application backend
                try {
                    const backendResponse = await axios.post(ENSURE_PROFILE_ENDPOINT, {
                        firebase_id_token: firebaseIdToken,
                    });

                    if (backendResponse.status === 200 && backendResponse.data) {
                        // Successfully ensured profile on backend.
                        // The backendResponse.data should be your UserResponse model.
                        // You can use this data if needed, or just rely on the Firebase user object.
                        // The AuthContext's onAuthStateChanged will also pick up the Firebase user.
                        // loginUser(firebaseUser, firebaseIdToken); // Call context's login to update token, if needed separately
                        // onAuthStateChanged in AuthContext should handle setting currentUser and firebaseIdToken

                        logger.info("Backend profile ensured/retrieved:", backendResponse.data);
                        navigate(from, { replace: true }); // Redirect after successful backend sync
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
                    // Optionally sign out from Firebase if backend sync fails critically
                    // await firebaseSignOut(auth); 
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
            // More specific error handling based on googleAuthError.code can be added
            setError(displayError);
        } finally {
            setIsProcessing(false);
        }
    };

    if (loadingAuth) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '80vh' }}>
                <CircularProgress />
            </Box>
        );
    }

    // If already authenticated (e.g., navigating back to /login), don't show login form
    if (isAuthenticated) {
        return null; // Or a message, but useEffect should redirect
    }

    return (
        <Container component="main" maxWidth="xs">
            <Box
                sx={{
                    marginTop: 8,
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                }}
            >
                <Typography component="h1" variant="h5" gutterBottom>
                    Sign In
                </Typography>
                <Typography component="p" variant="subtitle1" align="center" sx={{ mb: 2 }}>
                    Access your Fixture Scout AI reminders and preferences.
                </Typography>
                {error && (
                    <Alert severity="error" sx={{ width: '100%', mb: 2 }}>
                        {error}
                    </Alert>
                )}
                <Button
                    type="button"
                    fullWidth
                    variant="contained"
                    sx={{ mt: 3, mb: 2, py: 1.5 }}
                    onClick={handleGoogleSignIn}
                    disabled={isProcessing}
                    startIcon={isProcessing ? <CircularProgress size={20} color="inherit" /> : <GoogleIcon />}
                >
                    {isProcessing ? "Signing In..." : "Sign In with Google"}
                </Button>
            </Box>
        </Container>
    );
}

export default LoginPage;