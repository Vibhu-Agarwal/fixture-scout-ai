// src/pages/PreferencesPage.jsx
import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { getUserPreferences, setUserPreferences, optimizePrompt } from '../services/api';
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
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import SaveIcon from '@mui/icons-material/Save';
import Fade from '@mui/material/Fade';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import useMediaQuery from '@mui/material/useMediaQuery';
import { useTheme } from '@mui/material/styles';
import LightbulbIcon from '@mui/icons-material/Lightbulb';
import EditIcon from '@mui/icons-material/Edit';

function PreferencesPage() {
    const { firebaseIdToken, currentUser } = useAuth();
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('md'));

    const [rawUserPrompt, setRawUserPrompt] = useState('');
    const [optimizedPromptFromAPI, setOptimizedPromptFromAPI] = useState('');
    const [promptForScout, setPromptForScout] = useState('');

    const [isLoading, setIsLoading] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [isOptimizing, setIsOptimizing] = useState(false);
    const [error, setError] = useState('');
    const [successMessage, setSuccessMessage] = useState('');

    const fetchPreferences = useCallback(async () => {
        if (!firebaseIdToken || !currentUser) return;
        setIsLoading(true);
        setError('');
        setSuccessMessage('');
        try {
            const prefs = await getUserPreferences(firebaseIdToken);
            setRawUserPrompt(prefs.raw_user_prompt || '');
            const currentScoutPrompt = prefs.optimized_llm_prompt || prefs.raw_user_prompt || '';
            setOptimizedPromptFromAPI(currentScoutPrompt);
            setPromptForScout(currentScoutPrompt);
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
            const response = await optimizePrompt(firebaseIdToken, rawUserPrompt);
            setOptimizedPromptFromAPI(response.optimized_user_prompt);
            setPromptForScout(response.optimized_user_prompt);
            setSuccessMessage("Prompt optimized successfully! Review and save.");
        } catch (err) {
            console.error("Failed to optimize prompt:", err);
            setError(getDisplayErrorMessage(err, "Failed to optimize prompt. You can still use your manually entered prompt."));
            setOptimizedPromptFromAPI('');
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

        const payload = {
            raw_user_prompt: rawUserPrompt,
            prompt_for_scout: promptForScout
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
            <Box sx={{
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                minHeight: '60vh',
                flexDirection: 'column',
                gap: 2
            }}>
                <CircularProgress size={60} thickness={4} />
                <Typography variant="body1" color="text.secondary">
                    Loading your preferences...
                </Typography>
            </Box>
        );
    }

    return (
        <Fade in timeout={300}>
            <Container maxWidth="lg">
                {/* Header */}
                <Box sx={{ mb: 4, textAlign: 'center' }}>
                    <Typography
                        variant="h3"
                        component="h1"
                        gutterBottom
                        sx={{
                            fontWeight: 700,
                            background: 'linear-gradient(45deg, #4ECDC4, #FF6B6B)',
                            backgroundClip: 'text',
                            WebkitBackgroundClip: 'text',
                            WebkitTextFillColor: 'transparent',
                            mb: 2
                        }}
                    >
                        Match Preferences
                    </Typography>
                    <Typography
                        variant="h6"
                        color="text.secondary"
                        sx={{
                            maxWidth: 600,
                            mx: 'auto',
                            lineHeight: 1.6
                        }}
                    >
                        Tell us about your football interests and let AI optimize your preferences for better match recommendations.
                    </Typography>
                </Box>

                {/* Alerts */}
                {error && (
                    <Alert
                        severity="error"
                        sx={{
                            mb: 3,
                            borderRadius: 2,
                            '& .MuiAlert-icon': { color: '#FF6B6B' }
                        }}
                    >
                        {error}
                    </Alert>
                )}
                {successMessage && (
                    <Alert
                        severity="success"
                        sx={{
                            mb: 3,
                            borderRadius: 2,
                            '& .MuiAlert-icon': { color: '#4ECDC4' }
                        }}
                    >
                        {successMessage}
                    </Alert>
                )}

                <Grid container spacing={3}>
                    {/* Raw Preferences Card */}
                    <Grid item xs={12} lg={6}>
                        <Card
                            elevation={4}
                            sx={{
                                height: '100%',
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
                                    height: '3px',
                                    background: 'linear-gradient(90deg, #4ECDC4, #2A9D8F)',
                                },
                            }}
                        >
                            <CardContent sx={{ p: 3 }}>
                                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                                    <EditIcon sx={{ color: '#4ECDC4', mr: 1, fontSize: 24 }} />
                                    <Typography variant="h5" component="h2" sx={{ fontWeight: 600 }}>
                                        Your Preferences
                                    </Typography>
                                </Box>

                                <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                                    Describe the types of football matches you're interested in. Be as specific as possible!
                                </Typography>

                                <TextField
                                    label="Your Match Preferences"
                                    multiline
                                    rows={8}
                                    fullWidth
                                    variant="outlined"
                                    value={rawUserPrompt}
                                    onChange={(e) => {
                                        setRawUserPrompt(e.target.value);
                                        if (optimizedPromptFromAPI && promptForScout === optimizedPromptFromAPI) {
                                            setPromptForScout(e.target.value);
                                        } else if (!optimizedPromptFromAPI) {
                                            setPromptForScout(e.target.value);
                                        }
                                    }}
                                    placeholder="e.g., I'm a Madridista, so CL is obvious. London derbies. Culers only against our city neighbors in red and white. Some top notch big-hype CL matches, regardless of stage. International wise, Die Mannschaft is love. Also CR7 is my favorite player."
                                    sx={{
                                        '& .MuiOutlinedInput-root': {
                                            borderRadius: 2,
                                            '&:hover .MuiOutlinedInput-notchedOutline': {
                                                borderColor: 'rgba(78, 205, 196, 0.5)',
                                            },
                                            '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
                                                borderColor: '#4ECDC4',
                                            },
                                        },
                                    }}
                                />

                                <Box sx={{ mt: 2, display: 'flex', justifyContent: 'flex-end' }}>
                                    <Tooltip title="Let AI optimize your prompt for better results">
                                        <span>
                                            <Button
                                                variant="contained"
                                                onClick={handleOptimizePrompt}
                                                disabled={isOptimizing || !rawUserPrompt.trim()}
                                                startIcon={
                                                    isOptimizing ? (
                                                        <CircularProgress size={20} color="inherit" />
                                                    ) : (
                                                        <AutoFixHighIcon />
                                                    )
                                                }
                                                sx={{
                                                    background: 'linear-gradient(135deg, #FF6B6B, #E55A5A)',
                                                    '&:hover': {
                                                        background: 'linear-gradient(135deg, #FF8E8E, #FF6B6B)',
                                                    },
                                                    '&:disabled': {
                                                        background: 'linear-gradient(135deg, #666, #888)',
                                                    },
                                                }}
                                            >
                                                {isOptimizing ? "Optimizing..." : "Optimize with AI"}
                                            </Button>
                                        </span>
                                    </Tooltip>
                                </Box>
                            </CardContent>
                        </Card>
                    </Grid>

                    {/* Optimized Prompt Card */}
                    <Grid item xs={12} lg={6}>
                        <Card
                            elevation={4}
                            sx={{
                                height: '100%',
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
                                    height: '3px',
                                    background: 'linear-gradient(90deg, #FF6B6B, #E55A5A)',
                                },
                            }}
                        >
                            <CardContent sx={{ p: 3 }}>
                                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                                    <LightbulbIcon sx={{ color: '#FF6B6B', mr: 1, fontSize: 24 }} />
                                    <Typography variant="h5" component="h2" sx={{ fontWeight: 600 }}>
                                        AI Optimized
                                    </Typography>
                                </Box>

                                <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                                    {optimizedPromptFromAPI
                                        ? "AI-enhanced version of your preferences for better match detection."
                                        : "Click 'Optimize with AI' to generate an enhanced version of your preferences."
                                    }
                                </Typography>

                                <TextField
                                    label="Optimized Preferences"
                                    multiline
                                    rows={8}
                                    fullWidth
                                    variant="outlined"
                                    value={optimizedPromptFromAPI}
                                    InputProps={{
                                        readOnly: true,
                                    }}
                                    sx={{
                                        '& .MuiOutlinedInput-root': {
                                            borderRadius: 2,
                                            backgroundColor: 'rgba(255, 255, 255, 0.02)',
                                        },
                                    }}
                                    placeholder="AI will generate an optimized version here..."
                                />

                                {optimizedPromptFromAPI && (
                                    <Box sx={{ mt: 2, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                                        <Button
                                            onClick={handleUseRawPromptForScout}
                                            disabled={promptForScout === rawUserPrompt && rawUserPrompt !== ''}
                                            size="small"
                                            variant="outlined"
                                            sx={{
                                                borderColor: 'rgba(78, 205, 196, 0.3)',
                                                color: '#4ECDC4',
                                                '&:hover': {
                                                    borderColor: '#4ECDC4',
                                                    backgroundColor: 'rgba(78, 205, 196, 0.08)',
                                                },
                                            }}
                                        >
                                            Use Manual
                                        </Button>
                                        <Button
                                            onClick={handleUseOptimizedPromptForScout}
                                            disabled={!optimizedPromptFromAPI || promptForScout === optimizedPromptFromAPI}
                                            size="small"
                                            variant="outlined"
                                            sx={{
                                                borderColor: 'rgba(255, 107, 107, 0.3)',
                                                color: '#FF6B6B',
                                                '&:hover': {
                                                    borderColor: '#FF6B6B',
                                                    backgroundColor: 'rgba(255, 107, 107, 0.08)',
                                                },
                                            }}
                                        >
                                            Use Optimized
                                        </Button>
                                    </Box>
                                )}
                            </CardContent>
                        </Card>
                    </Grid>

                    {/* Current Selection & Save */}
                    <Grid item xs={12}>
                        <Card
                            elevation={2}
                            sx={{
                                background: 'linear-gradient(135deg, #1A1A1A 0%, #2A2A2A 100%)',
                                border: '1px solid rgba(255, 255, 255, 0.12)',
                                borderRadius: 3,
                                p: 3,
                            }}
                        >
                            <Typography variant="subtitle1" sx={{ mb: 2, fontWeight: 600, color: 'text.primary' }}>
                                Currently Selected for Scout:
                                <Box component="span" sx={{
                                    ml: 1,
                                    color: promptForScout === rawUserPrompt && rawUserPrompt !== ''
                                        ? '#4ECDC4'
                                        : promptForScout === optimizedPromptFromAPI && optimizedPromptFromAPI !== ''
                                            ? '#FF6B6B'
                                            : 'text.secondary',
                                    fontWeight: 500
                                }}>
                                    {promptForScout === rawUserPrompt && rawUserPrompt !== ''
                                        ? "Your Manual Preferences"
                                        : promptForScout === optimizedPromptFromAPI && optimizedPromptFromAPI !== ''
                                            ? "AI Optimized Preferences"
                                            : "Using Manual (if filled) / Optimized (if available)"
                                    }
                                </Box>
                            </Typography>

                            <Button
                                type="button"
                                fullWidth
                                variant="contained"
                                size="large"
                                onClick={handleSavePreferences}
                                disabled={isSaving || (!rawUserPrompt.trim() && !promptForScout.trim())}
                                startIcon={isSaving ? <CircularProgress size={24} color="inherit" /> : <SaveIcon />}
                                sx={{
                                    py: 2,
                                    fontSize: '1.1rem',
                                    fontWeight: 600,
                                    background: 'linear-gradient(135deg, #4ECDC4 0%, #2A9D8F 100%)',
                                    '&:hover': {
                                        background: 'linear-gradient(135deg, #5EDDD4 0%, #3AAD9F 100%)',
                                        transform: 'translateY(-1px)',
                                    },
                                    '&:disabled': {
                                        background: 'linear-gradient(135deg, #666, #888)',
                                        transform: 'none',
                                    },
                                }}
                            >
                                {isSaving ? "Saving Preferences..." : "Save Preferences"}
                            </Button>
                        </Card>
                    </Grid>
                </Grid>
            </Container>
        </Fade>
    );
}

export default PreferencesPage;