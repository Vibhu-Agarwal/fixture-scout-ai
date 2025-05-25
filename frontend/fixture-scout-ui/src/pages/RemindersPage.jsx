// src/pages/RemindersPage.jsx
import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { getUserReminders, submitReminderFeedback } from '../services/api'; // Import your API functions

import Container from '@mui/material/Container';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import Alert from '@mui/material/Alert';
import Paper from '@mui/material/Paper';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemText from '@mui/material/ListItemText';
import ListItemSecondaryAction from '@mui/material/ListItemSecondaryAction';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import Divider from '@mui/material/Divider';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogTitle from '@mui/material/DialogTitle';
import TextField from '@mui/material/TextField';
import Button from '@mui/material/Button';

import ThumbDownOffAltIcon from '@mui/icons-material/ThumbDownOffAlt'; // Icon for "Not Interested"
import EventIcon from '@mui/icons-material/Event';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import SportsSoccerIcon from '@mui/icons-material/SportsSoccer';
import CampaignIcon from '@mui/icons-material/Campaign'; // For reminder mode
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import HourglassEmptyIcon from '@mui/icons-material/HourglassEmpty';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';


function ReminderStatusIcon({ status }) {
    // Simple status to icon mapping
    if (status === "sent" || status === "delivered_mock" || status === "sent_mock_email" || status === "sent_mock_phone_call") {
        return <Tooltip title={`Status: ${status}`}><CheckCircleOutlineIcon color="success" /></Tooltip>;
    } else if (status === "pending" || status === "queued_for_notification" || status === "triggered") {
        return <Tooltip title={`Status: ${status}`}><HourglassEmptyIcon color="action" /></Tooltip>;
    } else if (status && status.startsWith("failed")) {
        return <Tooltip title={`Status: ${status}`}><ErrorOutlineIcon color="error" /></Tooltip>;
    }
    return <Tooltip title={`Status: ${status || 'Unknown'}`}><HelpOutlineIcon color="disabled" /></Tooltip>;
}


function RemindersPage() {
    const { firebaseIdToken, currentUser } = useAuth();
    const [reminders, setReminders] = useState([]);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState('');
    const [successMessage, setSuccessMessage] = useState(''); // For feedback submission

    // Feedback Dialog State
    const [openFeedbackDialog, setOpenFeedbackDialog] = useState(false);
    const [currentReminderForFeedback, setCurrentReminderForFeedback] = useState(null);
    const [feedbackReason, setFeedbackReason] = useState('');
    const [isSubmittingFeedback, setIsSubmittingFeedback] = useState(false);

    const fetchReminders = useCallback(async () => {
        if (!firebaseIdToken || !currentUser) return;
        setIsLoading(true);
        setError('');
        try {
            const response = await getUserReminders(firebaseIdToken);
            // The API returns UserRemindersListResponse which has a 'reminders' array
            setReminders(response.reminders || []);
        } catch (err) {
            console.error("Failed to load reminders:", err);
            setError(getDisplayErrorMessage(err, "Failed to load reminders. Please try again."));
            setReminders([]); // Clear reminders on error
        } finally {
            setIsLoading(false);
        }
    }, [firebaseIdToken, currentUser]);

    useEffect(() => {
        fetchReminders();
    }, [fetchReminders]);

    const handleOpenFeedbackDialog = (reminder) => {
        setCurrentReminderForFeedback(reminder);
        setFeedbackReason(''); // Reset reason
        setOpenFeedbackDialog(true);
        setSuccessMessage(''); // Clear previous success messages
        setError('');
    };

    const handleCloseFeedbackDialog = () => {
        setOpenFeedbackDialog(false);
        setCurrentReminderForFeedback(null);
    };

    const handleSubmitFeedback = async () => {
        if (!firebaseIdToken || !currentReminderForFeedback) return;
        setIsSubmittingFeedback(true);
        setError('');
        setSuccessMessage('');
        try {
            const payload = { feedback_reason_text: feedbackReason };
            await submitReminderFeedback(firebaseIdToken, currentReminderForFeedback.reminder_id, payload);
            setSuccessMessage(`Feedback submitted for reminder: ${currentReminderForFeedback.fixture_details.home_team_name} vs ${currentReminderForFeedback.fixture_details.away_team_name}. This helps improve future suggestions!`);
            handleCloseFeedbackDialog();
            // Optionally, you could visually mark the reminder as "feedback submitted" in the UI
            // or re-fetch reminders if the backend changes its status based on feedback (not currently planned).
        } catch (err) {
            console.error("Failed to submit feedback:", err);
            setError(getDisplayErrorMessage(err, "Failed to submit feedback. Please try again."));
            // Keep dialog open on error to show message, or close and show global error.
        } finally {
            setIsSubmittingFeedback(false);
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
        <Container maxWidth="lg">
            <Typography variant="h4" component="h1" gutterBottom sx={{ mt: 2, mb: 3 }}>
                Your Upcoming Reminders
            </Typography>

            {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
            {successMessage && <Alert severity="success" sx={{ mb: 2 }}>{successMessage}</Alert>}

            {reminders.length === 0 && !isLoading && (
                <Paper elevation={1} sx={{ p: 3, textAlign: 'center' }}>
                    <Typography variant="subtitle1">
                        No upcoming reminders found.
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                        Once Fixture Scout AI identifies matches based on your preferences, they will appear here.
                    </Typography>
                </Paper>
            )}

            {reminders.length > 0 && (
                <List component={Paper} elevation={2}>
                    {reminders.map((reminder, index) => (
                        <React.Fragment key={reminder.reminder_id}>
                            <ListItem alignItems="flex-start">
                                <Box sx={{ display: 'flex', flexDirection: 'column', flexGrow: 1 }}>
                                    <Typography variant="h6" component="div">
                                        <SportsSoccerIcon sx={{ verticalAlign: 'bottom', mr: 0.5 }} />
                                        {reminder.fixture_details.home_team_name} vs {reminder.fixture_details.away_team_name}
                                    </Typography>
                                    <Typography variant="body2" color="text.secondary" gutterBottom>
                                        {reminder.fixture_details.league_name}
                                        {reminder.fixture_details.stage && ` - ${reminder.fixture_details.stage}`}
                                    </Typography>
                                    <Typography variant="body1" sx={{ mb: 0.5 }}>
                                        <CampaignIcon sx={{ verticalAlign: 'bottom', mr: 0.5, fontSize: '1.1rem' }} />
                                        Next Reminder: <strong>{reminder.custom_message}</strong> ({reminder.reminder_mode})
                                    </Typography>
                                    <Box sx={{ display: 'flex', alignItems: 'center', color: 'text.secondary', mb: 0.5, gap: 2 }}>
                                        <Box sx={{ display: 'flex', alignItems: 'center' }}>
                                            <EventIcon sx={{ fontSize: '1rem', mr: 0.5 }} />
                                            <Typography variant="caption">
                                                Kick-off: {new Date(reminder.kickoff_time_utc).toLocaleString()}
                                            </Typography>
                                        </Box>
                                        <Box sx={{ display: 'flex', alignItems: 'center' }}>
                                            <AccessTimeIcon sx={{ fontSize: '1rem', mr: 0.5 }} />
                                            <Typography variant="caption">
                                                Reminder at: {new Date(reminder.actual_reminder_time_utc).toLocaleString()}
                                            </Typography>
                                        </Box>
                                    </Box>
                                    <Box sx={{ display: 'flex', alignItems: 'center', color: 'text.secondary', fontSize: '0.8rem' }}>
                                        <ReminderStatusIcon status={reminder.current_status} />
                                        <Typography variant="caption" sx={{ ml: 0.5 }}>Status: {reminder.current_status}</Typography>
                                        <Typography variant="caption" sx={{ ml: 1 }}>Importance: {reminder.importance_score}/5</Typography>
                                    </Box>
                                </Box>
                                <ListItemSecondaryAction>
                                    <Tooltip title="Mark as Not Interested">
                                        <IconButton edge="end" aria-label="not interested" onClick={() => handleOpenFeedbackDialog(reminder)}>
                                            <ThumbDownOffAltIcon />
                                        </IconButton>
                                    </Tooltip>
                                </ListItemSecondaryAction>
                            </ListItem>
                            {index < reminders.length - 1 && <Divider variant="inset" component="li" />}
                        </React.Fragment>
                    ))}
                </List>
            )}

            {/* Feedback Dialog */}
            <Dialog open={openFeedbackDialog} onClose={handleCloseFeedbackDialog} maxWidth="sm" fullWidth>
                <DialogTitle>Provide Feedback</DialogTitle>
                <DialogContent>
                    {currentReminderForFeedback && (
                        <DialogContentText sx={{ mb: 2 }}>
                            You are marking the reminder for <br />
                            <strong>{currentReminderForFeedback.fixture_details.home_team_name} vs {currentReminderForFeedback.fixture_details.away_team_name}</strong>
                            <br />as "Not Interested".
                        </DialogContentText>
                    )}
                    <TextField
                        autoFocus
                        margin="dense"
                        id="feedback-reason"
                        label="Reason (Optional)"
                        type="text"
                        fullWidth
                        multiline
                        rows={3}
                        variant="outlined"
                        value={feedbackReason}
                        onChange={(e) => setFeedbackReason(e.target.value)}
                        helperText="Why was this reminder not relevant to you?"
                    />
                    {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
                </DialogContent>
                <DialogActions sx={{ p: '16px 24px' }}>
                    <Button onClick={handleCloseFeedbackDialog} disabled={isSubmittingFeedback}>Cancel</Button>
                    <Button
                        onClick={handleSubmitFeedback}
                        variant="contained"
                        color="primary"
                        disabled={isSubmittingFeedback}
                        startIcon={isSubmittingFeedback ? <CircularProgress size={20} color="inherit" /> : null}
                    >
                        {isSubmittingFeedback ? "Submitting..." : "Submit Feedback"}
                    </Button>
                </DialogActions>
            </Dialog>
        </Container>
    );
}

export default RemindersPage;