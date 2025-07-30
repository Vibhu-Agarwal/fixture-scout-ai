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
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import Fade from '@mui/material/Fade';
import useMediaQuery from '@mui/material/useMediaQuery';
import { useTheme } from '@mui/material/styles';

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
import EmojiEventsIcon from '@mui/icons-material/EmojiEvents';

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

function ReminderCard({ reminder, onFeedbackClick }) {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

    const kickoffDate = new Date(reminder.kickoff_time_utc);
    const reminderDate = new Date(reminder.actual_reminder_time_utc);
    const isPast = reminderDate < new Date();

    const getStatusColor = (status) => {
        if (status === "sent" || status === "delivered_mock" || status === "sent_mock_email" || status === "sent_mock_phone_call") {
            return '#4ECDC4';
        } else if (status === "pending" || status === "queued_for_notification" || status === "triggered") {
            return '#FFB74D';
        } else if (status && status.startsWith("failed")) {
            return '#FF6B6B';
        }
        return '#9E9E9E';
    };

    const getImportanceColor = (score) => {
        if (score >= 4) return '#FF6B6B';
        if (score >= 3) return '#FFB74D';
        return '#4ECDC4';
    };

    return (
        <Card
            elevation={3}
            sx={{
                mb: 2,
                background: 'linear-gradient(135deg, #1A1A1A 0%, #2A2A2A 100%)',
                border: '1px solid rgba(255, 255, 255, 0.12)',
                borderRadius: 3,
                position: 'relative',
                overflow: 'hidden',
                '&:hover': {
                    transform: 'translateY(-2px)',
                    boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4)',
                    transition: 'all 0.3s ease-in-out',
                },
                '&::before': {
                    content: '""',
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    right: 0,
                    height: '3px',
                    background: `linear-gradient(90deg, ${getStatusColor(reminder.current_status)}, ${getImportanceColor(reminder.importance_score)})`,
                },
            }}
        >
            <CardContent sx={{ p: 3 }}>
                {/* Header */}
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flex: 1 }}>
                        <SportsSoccerIcon sx={{ color: '#4ECDC4', fontSize: 24 }} />
                        <Typography variant="h6" component="div" sx={{ fontWeight: 600, color: 'text.primary' }}>
                            {reminder.fixture_details.home_team_name} vs {reminder.fixture_details.away_team_name}
                        </Typography>
                    </Box>
                    <IconButton
                        onClick={() => onFeedbackClick(reminder)}
                        sx={{
                            color: '#FF6B6B',
                            '&:hover': {
                                backgroundColor: 'rgba(255, 107, 107, 0.1)',
                            },
                        }}
                    >
                        <ThumbDownOffAltIcon />
                    </IconButton>
                </Box>

                {/* League and Stage */}
                <Box sx={{ mb: 2 }}>
                    <Chip
                        icon={<EmojiEventsIcon />}
                        label={`${reminder.fixture_details.league_name}${reminder.fixture_details.stage ? ` - ${reminder.fixture_details.stage}` : ''}`}
                        sx={{
                            background: 'rgba(78, 205, 196, 0.1)',
                            color: '#4ECDC4',
                            border: '1px solid rgba(78, 205, 196, 0.3)',
                            fontWeight: 500,
                        }}
                    />
                </Box>

                {/* Reminder Message */}
                <Box sx={{ mb: 3, p: 2, backgroundColor: 'rgba(255, 255, 255, 0.02)', borderRadius: 2, border: '1px solid rgba(255, 255, 255, 0.08)' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                        <CampaignIcon sx={{ color: '#FF6B6B', fontSize: 20 }} />
                        <Typography variant="subtitle2" sx={{ color: '#FF6B6B', fontWeight: 600 }}>
                            Reminder Message
                        </Typography>
                    </Box>
                    <Typography variant="body1" sx={{ color: 'text.primary', fontStyle: 'italic' }}>
                        "{reminder.custom_message}"
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
                        Mode: {reminder.reminder_mode}
                    </Typography>
                </Box>

                {/* Time Information */}
                <Grid container spacing={2} sx={{ mb: 2 }}>
                    <Grid item xs={12} sm={6}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, p: 1.5, backgroundColor: 'rgba(255, 255, 255, 0.02)', borderRadius: 1 }}>
                            <EventIcon sx={{ color: '#4ECDC4', fontSize: 18 }} />
                            <Box>
                                <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                                    Kick-off
                                </Typography>
                                <Typography variant="body2" sx={{ color: 'text.primary', fontWeight: 500 }}>
                                    {kickoffDate.toLocaleDateString()} {kickoffDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                </Typography>
                            </Box>
                        </Box>
                    </Grid>
                    <Grid item xs={12} sm={6}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, p: 1.5, backgroundColor: 'rgba(255, 255, 255, 0.02)', borderRadius: 1 }}>
                            <AccessTimeIcon sx={{ color: '#FFB74D', fontSize: 18 }} />
                            <Box>
                                <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                                    Reminder
                                </Typography>
                                <Typography variant="body2" sx={{ color: 'text.primary', fontWeight: 500 }}>
                                    {reminderDate.toLocaleDateString()} {reminderDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                </Typography>
                            </Box>
                        </Box>
                    </Grid>
                </Grid>

                {/* Status and Importance */}
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 1 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <ReminderStatusIcon status={reminder.current_status} />
                        <Typography variant="caption" color="text.secondary">
                            {reminder.current_status}
                        </Typography>
                    </Box>
                    <Chip
                        label={`Importance: ${reminder.importance_score}/5`}
                        size="small"
                        sx={{
                            backgroundColor: `rgba(${getImportanceColor(reminder.importance_score) === '#FF6B6B' ? '255, 107, 107' : getImportanceColor(reminder.importance_score) === '#FFB74D' ? '255, 183, 77' : '78, 205, 196'}, 0.1)`,
                            color: getImportanceColor(reminder.importance_score),
                            border: `1px solid rgba(${getImportanceColor(reminder.importance_score) === '#FF6B6B' ? '255, 107, 107' : getImportanceColor(reminder.importance_score) === '#FFB74D' ? '255, 183, 77' : '78, 205, 196'}, 0.3)`,
                            fontWeight: 500,
                        }}
                    />
                </Box>
            </CardContent>
        </Card>
    );
}

function RemindersPage() {
    const { firebaseIdToken, currentUser } = useAuth();
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

    const [allReminders, setAllReminders] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState('');
    const [successMessage, setSuccessMessage] = useState('');

    const [openFeedbackDialog, setOpenFeedbackDialog] = useState(false);
    const [currentReminderForFeedback, setCurrentReminderForFeedback] = useState(null);
    const [feedbackReason, setFeedbackReason] = useState('');
    const [isSubmittingFeedback, setIsSubmittingFeedback] = useState(false);

    const [currentTab, setCurrentTab] = useState(0);

    const fetchReminders = useCallback(async () => {
        if (!firebaseIdToken || !currentUser) {
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
            if (new Date(reminder.actual_reminder_time_utc) >= now) {
                upcoming.push(reminder);
            } else {
                past.push(reminder);
            }
        });

        upcoming.sort((a, b) => new Date(a.actual_reminder_time_utc) - new Date(b.actual_reminder_time_utc));
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
                    Loading your reminders...
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
                        Your Reminders
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
                        Track your personalized football match reminders and provide feedback to improve future recommendations.
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

                {/* Tabs */}
                <Paper
                    elevation={2}
                    sx={{
                        mb: 4,
                        background: 'linear-gradient(135deg, #1A1A1A 0%, #2A2A2A 100%)',
                        border: '1px solid rgba(255, 255, 255, 0.12)',
                        borderRadius: 3,
                    }}
                >
                    <Tabs
                        value={currentTab}
                        onChange={handleTabChange}
                        centered
                        indicatorColor="primary"
                        textColor="primary"
                        sx={{
                            '& .MuiTab-root': {
                                color: 'text.secondary',
                                fontWeight: 600,
                                fontSize: '1rem',
                                py: 2,
                                '&.Mui-selected': {
                                    color: '#4ECDC4',
                                },
                            },
                            '& .MuiTabs-indicator': {
                                backgroundColor: '#4ECDC4',
                                height: 3,
                            },
                        }}
                    >
                        <Tab
                            label="Upcoming"
                            icon={<UpcomingIcon />}
                            iconPosition="start"
                            sx={{ minHeight: 64 }}
                        />
                        <Tab
                            label="Past"
                            icon={<HistoryIcon />}
                            iconPosition="start"
                            sx={{ minHeight: 64 }}
                        />
                    </Tabs>
                </Paper>

                {/* Empty State */}
                {remindersToDisplay.length === 0 && (
                    <Card
                        elevation={2}
                        sx={{
                            p: 4,
                            textAlign: 'center',
                            background: 'linear-gradient(135deg, #1A1A1A 0%, #2A2A2A 100%)',
                            border: '1px solid rgba(255, 255, 255, 0.12)',
                            borderRadius: 3,
                        }}
                    >
                        <SportsSoccerIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2, opacity: 0.5 }} />
                        <Typography variant="h6" sx={{ mb: 1, color: 'text.primary' }}>
                            No {tabLabel.toLowerCase()} reminders found
                        </Typography>
                        {currentTab === 0 && (
                            <Typography variant="body1" color="text.secondary" sx={{ maxWidth: 400, mx: 'auto' }}>
                                Fixture Scout AI is working to find matches based on your preferences. Check back soon for personalized recommendations!
                            </Typography>
                        )}
                    </Card>
                )}

                {/* Reminders List */}
                {remindersToDisplay.length > 0 && (
                    <Box>
                        {remindersToDisplay.map((reminder, index) => (
                            <ReminderCard
                                key={reminder.reminder_id}
                                reminder={reminder}
                                onFeedbackClick={handleOpenFeedbackDialog}
                            />
                        ))}
                    </Box>
                )}

                {/* Feedback Dialog */}
                <Dialog
                    open={openFeedbackDialog}
                    onClose={handleCloseFeedbackDialog}
                    maxWidth="sm"
                    fullWidth
                    PaperProps={{
                        sx: {
                            background: 'linear-gradient(135deg, #1A1A1A 0%, #2A2A2A 100%)',
                            border: '1px solid rgba(255, 255, 255, 0.12)',
                            borderRadius: 3,
                        },
                    }}
                >
                    <DialogTitle sx={{ color: 'text.primary', fontWeight: 600 }}>
                        Provide Feedback
                    </DialogTitle>
                    <DialogContent>
                        {currentReminderForFeedback && (
                            <DialogContentText sx={{ mb: 3, color: 'text.secondary' }}>
                                You are marking the reminder for{' '}
                                <Box component="span" sx={{ color: 'text.primary', fontWeight: 600 }}>
                                    {currentReminderForFeedback.fixture_details.home_team_name} vs {currentReminderForFeedback.fixture_details.away_team_name}
                                </Box>
                                {' '}as "Not Interested".
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
                            sx={{
                                '& .MuiOutlinedInput-root': {
                                    borderRadius: 2,
                                },
                            }}
                        />
                        {error && !isSubmittingFeedback && (
                            <Alert severity="error" sx={{ mt: 2, borderRadius: 2 }}>
                                {error}
                            </Alert>
                        )}
                    </DialogContent>
                    <DialogActions sx={{ p: 3, gap: 1 }}>
                        <Button
                            onClick={handleCloseFeedbackDialog}
                            disabled={isSubmittingFeedback}
                            variant="outlined"
                            sx={{
                                borderColor: 'rgba(255, 255, 255, 0.3)',
                                color: 'text.primary',
                                '&:hover': {
                                    borderColor: 'rgba(255, 255, 255, 0.5)',
                                    backgroundColor: 'rgba(255, 255, 255, 0.04)',
                                },
                            }}
                        >
                            Cancel
                        </Button>
                        <Button
                            onClick={handleSubmitFeedback}
                            variant="contained"
                            disabled={isSubmittingFeedback}
                            startIcon={isSubmittingFeedback ? <CircularProgress size={20} color="inherit" /> : null}
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
                            {isSubmittingFeedback ? "Submitting..." : "Submit Feedback"}
                        </Button>
                    </DialogActions>
                </Dialog>
            </Container>
        </Fade>
    );
}

export default RemindersPage;