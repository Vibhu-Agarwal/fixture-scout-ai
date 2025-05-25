// src/services/api.js
import axios from 'axios';

const API_GATEWAY_BASE_URL = "API_GATEWAY_BASE_URL";

const apiClient = axios.create({
    baseURL: API_GATEWAY_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

// Function to get the current Firebase ID token
// This needs access to your AuthContext or a way to get the token.
// For simplicity, we'll assume the token is passed to functions that need it,
// OR we can use an interceptor that fetches it from a global state/context if available outside React components.
// A common pattern is to have AuthContext provide the token.

// Interceptor to add the Firebase ID Token to requests
// This requires that the AuthContext and its token are accessible globally or passed around.
// A cleaner way for components is to get the token from useAuth() and pass it to specific API functions.
// However, an interceptor is convenient if set up carefully.

// Let's make API functions that accept the token as an argument first,
// as it's cleaner to manage within React components using useAuth().

// --- User Management Service API Calls ---

// This endpoint is called by LoginPage and doesn't need the app's auth token in header,
// as it sends the firebase_id_token in the body.
export const ensureUserProfile = async (firebaseIdToken) => {
    try {
        const response = await apiClient.post('/auth/firebase/ensure-profile', {
            firebase_id_token: firebaseIdToken,
        });
        return response.data; // Should be UserResponse
    } catch (error) {
        console.error("Error ensuring user profile:", error.response?.data || error.message);
        throw error.response?.data || new Error("Failed to ensure user profile.");
    }
};

export const getUserPreferences = async (firebaseIdToken) => {
    try {
        const response = await apiClient.get('/preferences', {
            headers: { Authorization: `Bearer ${firebaseIdToken}` },
        });
        return response.data; // Should be UserPreferenceResponse
    } catch (error) {
        console.error("Error fetching user preferences:", error.response?.data || error.message);
        throw error.response?.data || new Error("Failed to fetch user preferences.");
    }
};

export const setUserPreferences = async (firebaseIdToken, preferencesData) => {
    // preferencesData should be: { raw_user_prompt: "...", prompt_for_scout: "..." }
    try {
        const response = await apiClient.put('/preferences', preferencesData, {
            headers: { Authorization: `Bearer ${firebaseIdToken}` },
        });
        return response.data; // Should be UserPreferenceResponse
    } catch (error) {
        console.error("Error setting user preferences:", error.response?.data || error.message);
        throw error.response?.data || new Error("Failed to set user preferences.");
    }
};

export const getUserReminders = async (firebaseIdToken) => {
    try {
        const response = await apiClient.get('/reminders', {
            headers: { Authorization: `Bearer ${firebaseIdToken}` },
        });
        return response.data; // Should be UserRemindersListResponse
    } catch (error) {
        console.error("Error fetching user reminders:", error.response?.data || error.message);
        throw error.response?.data || new Error("Failed to fetch user reminders.");
    }
};

export const submitReminderFeedback = async (firebaseIdToken, reminderId, feedbackPayload) => {
    // feedbackPayload should be: { feedback_reason_text: "..." }
    try {
        const response = await apiClient.post(`/reminders/${reminderId}/feedback`, feedbackPayload, {
            headers: { Authorization: `Bearer ${firebaseIdToken}` },
        });
        return response.data; // Should be UserFeedbackDoc
    } catch (error) {
        console.error(`Error submitting feedback for reminder ${reminderId}:`, error.response?.data || error.message);
        throw error.response?.data || new Error("Failed to submit feedback.");
    }
};

// --- Prompt Optimization Service API Calls ---
export const optimizePrompt = async (firebaseIdToken, rawPrompt) => {
    // The gateway endpoint /prompts/optimize expects a body like:
    // { "raw_user_prompt": "..." }
    // The user_id comes from the token, so no need to send it in the body from UI.
    try {
        const response = await apiClient.post('/prompts/optimize', { raw_user_prompt: rawPrompt }, {
            headers: { Authorization: `Bearer ${firebaseIdToken}` },
        });
        return response.data; // Should be PromptOptimizeResponse
    } catch (error) {
        console.error("Error optimizing prompt:", error.response?.data || error.message);
        throw error.response?.data || new Error("Failed to optimize prompt.");
    }
};


// Alternative: Using an Axios interceptor to automatically add the token
// This requires a way to access the token globally or from a store.
// If using AuthContext, this global access can be tricky without prop drilling or a more complex setup.
// For now, passing the token to each API function is more explicit and works well with useAuth().

/*
// Example of an interceptor IF you had a global token store:
// (This is NOT directly usable with the current AuthContext without modification)

let globalFirebaseIdToken = null; 
// This would need to be updated by AuthContext, which is not ideal for separation.

export const setGlobalAuthToken = (token) => {
  globalFirebaseIdToken = token;
};

apiClient.interceptors.request.use(
  (config) => {
    if (globalFirebaseIdToken && !config.url.includes('/auth/firebase/ensure-profile')) { // Don't add to the auth call itself
      config.headers['Authorization'] = `Bearer ${globalFirebaseIdToken}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);
*/


export default apiClient; // Export the configured instance if needed elsewhere, or just named exports.