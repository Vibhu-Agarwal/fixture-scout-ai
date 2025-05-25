// src/utils/errorUtils.js

/**
 * Safely extracts a displayable error message from various error structures.
 * Prioritizes err.detail, then err.message, then provides a default.
 * If detail or message is an object/array, it stringifies it.
 * @param {any} error The error object.
 * @param {string} defaultMessage The default message if no specific message can be extracted.
 * @returns {string} A string representation of the error.
 */
export const getDisplayErrorMessage = (error, defaultMessage = "An unexpected error occurred.") => {
    if (!error) {
        return defaultMessage;
    }

    // Try to get specific detail from backend (FastAPI HTTPException often has it here)
    if (error.detail) {
        if (typeof error.detail === 'string') {
            return error.detail;
        }
        // If detail is an object or array (e.g., Pydantic validation errors), stringify it
        try {
            return JSON.stringify(error.detail);
        } catch (e) {
            // Fallback if stringify fails for some reason
            return "Detailed error information could not be displayed.";
        }
    }

    // Try to get message property
    if (error.message && typeof error.message === 'string') {
        return error.message;
    }

    // If error itself is a string
    if (typeof error === 'string') {
        return error;
    }

    // Fallback to default message
    return defaultMessage;
};