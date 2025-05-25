// src/contexts/AuthContext.jsx
import React, { createContext, useContext, useState, useEffect } from 'react';
import { onAuthStateChanged, signOut as firebaseSignOut } from 'firebase/auth';
import { auth } from '../firebaseConfig'; // Your Firebase auth instance

const AuthContext = createContext();

export function useAuth() {
    return useContext(AuthContext);
}

export function AuthProvider({ children }) {
    const [currentUser, setCurrentUser] = useState(null); // Stores Firebase user object
    const [firebaseIdToken, setFirebaseIdToken] = useState(null); // Stores Firebase ID Token
    const [loading, setLoading] = useState(true); // To handle initial auth state check

    // This function will be called by the LoginPage after successful backend confirmation
    const loginUser = (firebaseUser, idToken) => {
        setCurrentUser(firebaseUser);
        setFirebaseIdToken(idToken);
    };

    const logoutUser = async () => {
        try {
            await firebaseSignOut(auth);
            setCurrentUser(null);
            setFirebaseIdToken(null);
            // Optionally clear other app-specific state or redirect
        } catch (error) {
            console.error("Error signing out: ", error);
            // Handle logout error if needed
        }
    };

    useEffect(() => {
        // Listen for Firebase auth state changes
        const unsubscribe = onAuthStateChanged(auth, async (user) => {
            setCurrentUser(user); // Set Firebase user object
            if (user) {
                try {
                    const token = await user.getIdToken(true); // Force refresh token if needed
                    setFirebaseIdToken(token);
                } catch (error) {
                    console.error("Error getting ID token on auth state change:", error);
                    setFirebaseIdToken(null); // Clear token on error
                    setCurrentUser(null); // Log out user if token fetch fails
                }
            } else {
                setFirebaseIdToken(null);
            }
            setLoading(false); // Auth state check complete
        });

        // Cleanup subscription on unmount
        return unsubscribe;
    }, []);

    const value = {
        currentUser,      // The Firebase user object (null if not logged in)
        firebaseIdToken,  // The Firebase ID Token string
        loginUser,        // Function to call after backend confirmation of profile
        logoutUser,       // Function to log out
        isAuthenticated: !!currentUser && !!firebaseIdToken, // Simple check
        loadingAuth: loading, // To show loading state while checking auth
    };

    return (
        <AuthContext.Provider value={value}>
            {!loading && children}
            {/* Don't render children until initial auth check is done */}
        </AuthContext.Provider>
    );
}