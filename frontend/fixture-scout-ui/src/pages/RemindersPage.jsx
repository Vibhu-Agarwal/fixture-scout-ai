// src/pages/RemindersPage.jsx
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { getUserReminders, submitReminderFeedback } from '../services/api';

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
import Tabs from '@mui/material/Tabs';
import Tab from '@mui/material/Tab';
import Grid from '@mui/material/Grid';

import ThumbDownOffAltIcon from '@mui/icons-material/ThumbDownOffAlt';
import EventIcon from '@mui/icons-material/Event';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import SportsSoccerIcon from '@mui/icons-material/SportsSoccer';
import CampaignIcon from '@mui/icons-material/Campaign';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import HourglassEmptyIcon from '@mui/icons-material/HourglassEmpty';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
import HistoryIcon from '@mui/icons-material/History';
import UpcomingIcon from '@mui/icons-material/Upcoming';

function ReminderStatusIcon({ status }) {
    if (status === "sent" || status === "delivered_mock" || status === "sent_mock_email" || status === "sent_mock_phone_call") {
        return <Tooltip title={`Status: ${status}`}><CheckCircleOutlineIcon color="success" fontSize="small" /></Tooltip>;
    } else if (status === "pending" || status === "queued_for_notification" || status === "triggered") {
        return <Tooltip title={`Status: ${status}`}><HourglassEmptyIcon color="action" fontSize="small" /></Tooltip>;
    } else if (status && status.startsWith("failed")) {
        return <Tooltip title={`Status: ${status}`}><ErrorOutlineIcon color="error" fontSize="small" /></Tooltip>;
    }
    return <Tooltip title={`Status: ${status || 'Unknown'}`}><HelpOutlineIcon color="disabled" fontSize="small" /></Tooltip>;
}

function ReminderListItem({ reminder, onFeedbackClick }) {
    return (
        <React.Fragment>
            <ListItem alignItems="flex-start" sx={{ py: 2 }}>
                <Box sx={{ display: 'flex', flexDirection: 'column', flexGrow: 1 }}>
                    <Typography variant="h6" component="div" sx={{ display: 'flex', alignItems: 'center', mb: 0.5 }}>
                        <SportsSoccerIcon sx={{ verticalAlign: 'middle', mr: 1 }} />
                        {reminder.fixture_details.home_team_name} vs {reminder.fixture_details.away_team_name}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                        {reminder.fixture_details.league_name}
                        {reminder.fixture_details.stage && ` - ${reminder.fixture_details.stage}`}
                    </Typography>
                    <Typography variant="body1" sx={{ mb: 1 }}>
                        <CampaignIcon sx={{ verticalAlign: 'middle', mr: 0.5, fontSize: '1.1rem' }} />
                        Reminder: <strong>{reminder.custom_message}</strong> ({reminder.reminder_mode})
                    </Typography>
                    <Grid container spacing={1} sx={{ color: 'text.secondary', fontSize: '0.875rem' }}>
                        <Grid item xs={12} sm={6} sx={{ display: 'flex', alignItems: 'center' }}>
                            <EventIcon sx={{ fontSize: '1rem', mr: 0.5 }} />
                            Kick-off: {new Date(reminder.kickoff_time_utc).toLocaleString()}
                        </Grid>
                        <Grid item xs={12} sm={6} sx={{ display: 'flex', alignItems: 'center' }}>
                            <AccessTimeIcon sx={{ fontSize: '1rem', mr: 0.5 }} />
                            Reminder at: {new Date(reminder.actual_reminder_time_utc).toLocaleString()}
                        </Grid>
                    </Grid>
                    <Box sx={{ display: 'flex', alignItems: 'center', color: 'text.secondary', mt: 1, gap: 1 }}>
                        <ReminderStatusIcon status={reminder.current_status} />
                        <Typography variant="caption">Status: {reminder.current_status}</Typography>
                        <Typography variant="caption">Importance: {reminder.importance_score}/5</Typography>
                    </Box>
                </Box>
                <ListItemSecondaryAction sx={{ top: '50%', transform: 'translateY(-50%)' }}>
                    <Tooltip title="Mark as Not Interested">
                        <IconButton edge="end" aria-label="not interested" onClick={() => onFeedbackClick(reminder)}>
                            <ThumbDownOffAltIcon />
                        </IconButton>
                    </Tooltip>
                </ListItemSecondaryAction>
            </ListItem>
        </React.Fragment>
    );
}


function RemindersPage() {
    const { firebaseIdToken, currentUser } = useAuth();
    const [allReminders, setAllReminders] = useState([]); // Store all fetched reminders
    const [isLoading, setIsLoading] = useState(true); // Start with loading true
    const [error, setError] = useState('');
    const [successMessage, setSuccessMessage] = useState('');

    const [openFeedbackDialog, setOpenFeedbackDialog] = useState(false);
    const [currentReminderForFeedback, setCurrentReminderForFeedback] = useState(null);
    const [feedbackReason, setFeedbackReason] = useState('');
    const [isSubmittingFeedback, setIsSubmittingFeedback] = useState(false);

    const [currentTab, setCurrentTab] = useState(0); // 0 for Upcoming, 1 for Past

    const fetchReminders = useCallback(async () => {
        if (!firebaseIdToken || !currentUser) {
            // If not authenticated, set loading to false and don't fetch
            setIsLoading(false);
            return;
        }
        setIsLoading(true);
        setError('');
        try {
            const response = await getUserReminders(firebaseIdToken);
            setAllReminders(response.reminders || []);
        } catch (err) {
            console.error("Failed to load reminders:", err);
            setError(err.detail || err.message || "Failed to load reminders. Please try again.");
            setAllReminders([]);
        } finally {
            setIsLoading(false);
        }
    }, [firebaseIdToken, currentUser]);

    useEffect(() => {
        fetchReminders();
    }, [fetchReminders]);

    const { upcomingReminders, pastReminders } = useMemo(() => {
        const now = new Date();
        const upcoming = [];
        const past = [];

        allReminders.forEach(reminder => {
            // The key for grouping is the reminder.actual_reminder_time_utc
            if (new Date(reminder.actual_reminder_time_utc) >= now) {
                upcoming.push(reminder);
            } else {
                past.push(reminder);
            }
        });

        // Sort Upcoming: earliest reminder time at the top
        upcoming.sort((a, b) => new Date(a.actual_reminder_time_utc) - new Date(b.actual_reminder_time_utc));
        // Sort Past: latest reminder time at the top (most recent past)
        past.sort((a, b) => new Date(b.actual_reminder_time_utc) - new Date(a.actual_reminder_time_utc));

        return { upcomingReminders: upcoming, pastReminders: past };
    }, [allReminders]);


    const handleTabChange = (event, newValue) => {
        setCurrentTab(newValue);
    };

    const handleOpenFeedbackDialog = (reminder) => {
        setCurrentReminderForFeedback(reminder);
        setFeedbackReason('');
        setOpenFeedbackDialog(true);
        setSuccessMessage('');
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
            setSuccessMessage(`Feedback submitted for reminder regarding: ${currentReminderForFeedback.fixture_details.home_team_name} vs ${currentReminderForFeedback.fixture_details.away_team_name}.`);
            handleCloseFeedbackDialog();
            // No need to re-fetch reminders here, as feedback doesn't change the reminder list itself,
            // but rather influences future scouting runs.
        } catch (err) {
            console.error("Failed to submit feedback:", err);
            setError(err.detail || err.message || "Failed to submit feedback. Please try again.");
        } finally {
            setIsSubmittingFeedback(false);
        }
    };

    const remindersToDisplay = currentTab === 0 ? upcomingReminders : pastReminders;
    const tabLabel = currentTab === 0 ? "Upcoming" : "Past";

    if (isLoading) {
        return (
            <Container maxWidth="lg" sx={{ mt: 2, display: 'flex', justifyContent: 'center' }}>
                <CircularProgress />
            </Container>
        );
    }

    return (
        <Container maxWidth="lg">
            <Typography variant="h4" component="h1" gutterBottom sx={{ mt: 2, mb: 1 }}>
                Your Reminders
            </Typography>

            {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
            {successMessage && <Alert severity="success" sx={{ mb: 2, mt: openFeedbackDialog ? 0 : 2 }}>{successMessage}</Alert>}

            <Paper elevation={1} sx={{ mb: 3 }}>
                <Tabs value={currentTab} onChange={handleTabChange} centered indicatorColor="primary" textColor="primary">
                    <Tab label="Upcoming" icon={<UpcomingIcon />} iconPosition="start" />
                    <Tab label="Past" icon={<HistoryIcon />} iconPosition="start" />
                </Tabs>
            </Paper>

            {remindersToDisplay.length === 0 && (
                <Paper elevation={1} sx={{ p: 3, textAlign: 'center', mt: 2 }}>
                    <Typography variant="subtitle1">
                        No {tabLabel.toLowerCase()} reminders found.
                    </Typography>
                    {currentTab === 0 &&
                        <Typography variant="body2" color="text.secondary">
                            Fixture Scout AI is working to find matches based on your preferences. Check back soon!
                        </Typography>
                    }
                </Paper>
            )}

            {remindersToDisplay.length > 0 && (
                <List component={Paper} elevation={2}>
                    {remindersToDisplay.map((reminder, index) => (
                        <React.Fragment key={reminder.reminder_id}>
                            <ReminderListItem reminder={reminder} onFeedbackClick={handleOpenFeedbackDialog} />
                            {index < remindersToDisplay.length - 1 && <Divider variant="inset" component="li" />}
                        </React.Fragment>
                    ))}
                </List>
            )}

            {/* Feedback Dialog (same as before) */}
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
                    {error && !isSubmittingFeedback && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>} {/* Show error in dialog if not submitting */}
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