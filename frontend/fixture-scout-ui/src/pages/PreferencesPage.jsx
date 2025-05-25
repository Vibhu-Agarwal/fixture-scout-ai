// src/pages/PreferencesPage.jsx
import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { getUserPreferences, setUserPreferences, optimizePrompt } from '../services/api'; // Import your API functions
import { getDisplayErrorMessage } from '../utils/errorUtils';

import Container from '@mui/material/Container';
import Typography from '@mui/material/Typography';
import TextField from '@mui/material/TextField';
import Button from '@mui/material/Button';
import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import Alert from '@mui/material/Alert';
import Paper from '@mui/material/Paper';
import Grid from '@mui/material/Grid';
import Tooltip from '@mui/material/Tooltip';
import IconButton from '@mui/material/IconButton';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh'; // For optimize button
import SaveIcon from '@mui/icons-material/Save';

function PreferencesPage() {
    const { firebaseIdToken, currentUser } = useAuth();
    const [rawUserPrompt, setRawUserPrompt] = useState('');
    const [optimizedPromptFromAPI, setOptimizedPromptFromAPI] = useState(''); // Stores what API returns
    const [promptForScout, setPromptForScout] = useState(''); // What will actually be saved for the scout

    const [isLoading, setIsLoading] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [isOptimizing, setIsOptimizing] = useState(false);
    const [error, setError] = useState('');
    const [successMessage, setSuccessMessage] = useState('');

    // Fetch preferences when the component mounts or token changes
    const fetchPreferences = useCallback(async () => {
        if (!firebaseIdToken || !currentUser) return;
        setIsLoading(true);
        setError('');
        setSuccessMessage('');
        try {
            const prefs = await getUserPreferences(firebaseIdToken);
            setRawUserPrompt(prefs.raw_user_prompt || '');
            const currentScoutPrompt = prefs.optimized_llm_prompt || prefs.raw_user_prompt || '';
            setOptimizedPromptFromAPI(currentScoutPrompt); // Initialize with what's saved as optimized
            setPromptForScout(currentScoutPrompt); // This is what's active for scout
        } catch (err) {
            console.error("Failed to load preferences:", err);
            setError(getDisplayErrorMessage(err, "Failed to load preferences. Please try again."));
        } finally {
            setIsLoading(false);
        }
    }, [firebaseIdToken, currentUser]);

    useEffect(() => {
        fetchPreferences();
    }, [fetchPreferences]);

    const handleOptimizePrompt = async () => {
        if (!firebaseIdToken || !rawUserPrompt.trim()) {
            setError("Please enter your preferences before optimizing.");
            return;
        }
        setIsOptimizing(true);
        setError('');
        setSuccessMessage('');
        try {
            // The API for optimizePrompt expects: { raw_user_prompt: "..." }
            // The user_id is handled by the token/gateway.
            const response = await optimizePrompt(firebaseIdToken, rawUserPrompt);
            setOptimizedPromptFromAPI(response.optimized_user_prompt);
            // By default, set the promptForScout to the newly optimized one
            setPromptForScout(response.optimized_user_prompt);
            setSuccessMessage("Prompt optimized successfully! Review and save.");
        } catch (err) {
            console.error("Failed to optimize prompt:", err);
            setError(getDisplayErrorMessage(err, "Failed to optimize prompt. You can still use your manually entered prompt."));
            setOptimizedPromptFromAPI(''); // Clear if optimization fails
        } finally {
            setIsOptimizing(false);
        }
    };

    const handleSavePreferences = async () => {
        if (!firebaseIdToken) {
            setError("Authentication token not available. Please try logging in again.");
            return;
        }
        setIsSaving(true);
        setError('');
        setSuccessMessage('');

        // Determine which prompt to save for the scout:
        // If optimizedPromptFromAPI has content (meaning optimize was clicked and successful),
        // and promptForScout still matches it, use it.
        // Otherwise, if user edited rawUserPrompt after optimization and promptForScout
        // hasn't been explicitly set to something else (e.g. user clicks "use my raw prompt" button - not implemented here),
        // the logic in user_management_service will use raw_user_prompt if prompt_for_scout is empty.
        // For the UI, we send what's in `promptForScout` as `prompt_for_scout` to the backend.
        // And `rawUserPrompt` as `raw_user_prompt`.
        // The backend (`user_management_service`) then decides if `promptForScout` is empty, it uses `rawUserPrompt`.

        const payload = {
            raw_user_prompt: rawUserPrompt,
            prompt_for_scout: promptForScout // This field name matches UserPreferenceSubmitRequest
        };

        try {
            await setUserPreferences(firebaseIdToken, payload);
            setSuccessMessage("Preferences saved successfully!");
        } catch (err) {
            console.error("Failed to save preferences:", err);
            setError(getDisplayErrorMessage(err, "Failed to save preferences. Please try again."));
        } finally {
            setIsSaving(false);
        }
    };

    // Option for user to decide which prompt to use for the scout
    const handleUseRawPromptForScout = () => {
        setPromptForScout(rawUserPrompt);
        setSuccessMessage("Switched to use your manually entered prompt for the Scout. Remember to save.");
    };

    const handleUseOptimizedPromptForScout = () => {
        if (optimizedPromptFromAPI) {
            setPromptForScout(optimizedPromptFromAPI);
            setSuccessMessage("Switched to use the AI-optimized prompt for the Scout. Remember to save.");
        } else {
            setError("No optimized prompt available to use. Please optimize first or enter manually.");
        }
    };


    if (isLoading) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '200px' }}>
                <CircularProgress />
            </Box>
        );
    }

    return (
        <Container maxWidth="md">
            <Paper elevation={3} sx={{ p: 3, mt: 3 }}>
                <Typography variant="h5" component="h1" gutterBottom>
                    Your Match Preferences
                </Typography>
                {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
                {successMessage && <Alert severity="success" sx={{ mb: 2 }}>{successMessage}</Alert>}

                <Grid container spacing={3}>
                    <Grid item xs={12} md={6}>
                        <Typography variant="h6" gutterBottom>
                            Describe Your Interests
                        </Typography>
                        <TextField
                            label="Your Raw Preferences"
                            multiline
                            rows={8}
                            fullWidth
                            variant="outlined"
                            value={rawUserPrompt}
                            onChange={(e) => {
                                setRawUserPrompt(e.target.value);
                                // If user edits raw prompt, they might want to re-optimize or use raw.
                                // We can implicitly set promptForScout to raw if they edit after optimizing,
                                // or let them choose explicitly.
                                // For now, let's make it so editing raw prompt means promptForScout will become raw unless they re-optimize
                                // or explicitly choose the optimized one again.
                                if (optimizedPromptFromAPI && promptForScout === optimizedPromptFromAPI) {
                                    // If they were using optimized, but now edit raw, default to using new raw
                                    setPromptForScout(e.target.value);
                                } else if (!optimizedPromptFromAPI) {
                                    // If no optimization ever happened, raw is always the scout prompt
                                    setPromptForScout(e.target.value);
                                }
                            }}
                            placeholder="e.g., I want all Real Madrid games. Also, any important Champions League matches, especially knockout stages. Maybe some big derbies if they are interesting."
                            helperText="Describe the types of football matches you're interested in."
                        />
                        <Box sx={{ mt: 1, display: 'flex', justifyContent: 'flex-end' }}>
                            <Tooltip title="Let AI optimize your prompt for better results">
                                <span>
                                    <Button
                                        variant="contained"
                                        color="secondary"
                                        onClick={handleOptimizePrompt}
                                        disabled={isOptimizing || !rawUserPrompt.trim()}
                                        startIcon={isOptimizing ? <CircularProgress size={20} color="inherit" /> : <AutoFixHighIcon />}
                                    >
                                        {isOptimizing ? "Optimizing..." : "Optimize Prompt"}
                                    </Button>
                                </span>
                            </Tooltip>
                        </Box>
                    </Grid>

                    <Grid item xs={12} md={6}>
                        <Typography variant="h6" gutterBottom>
                            AI Optimized Prompt (For Fixture Scout)
                        </Typography>
                        <TextField
                            label="Optimized Prompt"
                            multiline
                            rows={8}
                            fullWidth
                            variant="outlined"
                            value={optimizedPromptFromAPI} // Display what the API returned
                            InputProps={{
                                readOnly: true, // Typically, user doesn't edit this directly
                            }}
                            helperText={optimizedPromptFromAPI ? "This is the AI-suggested prompt. You can choose to use this or your manually entered one." : "Click 'Optimize Prompt' to generate an AI-enhanced version."}
                            placeholder="AI will generate an optimized version here..."
                        />
                        <Box sx={{ mt: 1, display: 'flex', justifyContent: 'space-between' }}>
                            <Button
                                onClick={handleUseRawPromptForScout}
                                disabled={promptForScout === rawUserPrompt && rawUserPrompt !== ''}
                                size="small"
                            >
                                Use Manual Prompt
                            </Button>
                            <Button
                                onClick={handleUseOptimizedPromptForScout}
                                disabled={!optimizedPromptFromAPI || promptForScout === optimizedPromptFromAPI}
                                size="small"
                                color="secondary"
                            >
                                Use Optimized Prompt
                            </Button>
                        </Box>
                    </Grid>
                    <Grid item xs={12}>
                        <Typography variant="subtitle2" sx={{ mb: 1, fontStyle: 'italic' }}>
                            Currently selected for Scout: {promptForScout === rawUserPrompt && rawUserPrompt !== '' ? "Your Manual Prompt" : (promptForScout === optimizedPromptFromAPI && optimizedPromptFromAPI !== '' ? "AI Optimized Prompt" : "Using Manual (if filled) / Optimized (if available)")}
                        </Typography>
                        <Button
                            type="button"
                            fullWidth
                            variant="contained"
                            color="primary"
                            size="large"
                            onClick={handleSavePreferences}
                            disabled={isSaving || (!rawUserPrompt.trim() && !promptForScout.trim())} // Disable if nothing to save
                            startIcon={isSaving ? <CircularProgress size={24} color="inherit" /> : <SaveIcon />}
                        >
                            {isSaving ? "Saving..." : "Save Preferences"}
                        </Button>
                    </Grid>
                </Grid>
            </Paper>
        </Container>
    );
}

export default PreferencesPage;