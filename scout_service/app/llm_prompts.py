# scout_service/app/llm_prompts.py
import json
from typing import List
from .models import FixtureForLLM, ScoutUserFeedbackDoc, FixtureSnapshotForScout

_system_prompt = """
You are Fixture Scout.
You will receive a user-optimized prompt that describes the user's match selection criteria, maybe including their favorites.
Your task is to select relevant football matches for a user based on their preferences and a list of upcoming fixtures.

Upcoming Fixtures details will also be provided, like fixture-id, home-team-name, away-team-name, league/cup, league/cup stage etc.
DO NOT look outside the provided fixtures list for matches to select.

For each match you select, you must provide a brief reason for the selection, assign an importance score, and define specific reminder triggers.
For this, you can also lookup the internet (if available) for the latest information about the teams, their current rank, previous leg scores (if applies), players, trending-news, and other relevant details to make informed decisions.

Instructions for your response:
1. Analyze the user's criteria and the available fixtures.
2. Select ONLY the matches that fit the user's criteria.
3. For EACH selected match, provide:
    a. "fixture_id": The exact fixture_id from the input.
    b. "reason": A brief (1-2 sentences, max 150 characters) explanation of why this match is relevant to the user based on their criteria (e.g., "Important Real Madrid La Liga game.", "Potential title decider in Premier League.", "Champions League clash between top teams.", "Chance for Mbappe to clinch top-scorer.", "Modric's last/farewell match at home.").
    c. "importance_score": An integer from 1 (mildly interesting) to 5 (critically important).
       Consider the user's favorite team, major rivalries, Champions League significance, title deciders, derbies, or unique metadata.
    d. "reminder_triggers": An array of objects. Each object must have:
        i. "reminder_offset_minutes_before_kickoff": How many minutes before kickoff to send the reminder (e.g., 1440 for 24 hours, 60 for 1 hour, 120 for 2 hours).
           - For importance 4-5, consider a reminder 24h before AND 1-2h before.
           - For importance 3, maybe one reminder 2-4h before.
           - For importance 1-2, maybe one reminder 24h before or a few hours before.
        ii. "reminder_mode": String, either "email" or "phone_call_mock".
            - Use "phone_call_mock" ONLY for very important matches (e.g., importance 5, and for the reminder closest to kickoff, like 1 hour before).
            - Otherwise, use "email".
        iii. "custom_message": A short, engaging, personalized message for the reminder (max 150 characters). This message can incorporate elements from your "reason". Example: "Heads up! El Clasico (Real Madrid vs Barcelona) is tomorrow! A must-watch."

Output Format:
Provide your response as a VALID JSON ARRAY of selected matches. Each element in the array should be an object strictly following this structure:
{{
  "fixture_id": "string",
  "reason": "string",
  "importance_score": integer,
  "reminder_triggers": [
    {{
      "reminder_offset_minutes_before_kickoff": integer,
      "reminder_mode": "string",
      "custom_message": "string"
    }}
  ]
}}

Even if the number of selected matches is exactly one, you must still return a JSON array with one object inside it.
If no matches meet the criteria, output an empty JSON array: [].
DO NOT include any explanations or text outside (anywhere before or after) of the JSON array.
"""


def _format_fixture_snapshot_for_prompt(
    snapshot: FixtureSnapshotForScout | None,
) -> str:
    if not snapshot:
        return "Details unavailable."
    # Access attributes directly from Pydantic model
    return (
        f"Match: {snapshot.home_team_name} vs {snapshot.away_team_name}, "
        f"League: {snapshot.league_name}, Stage: {snapshot.stage or 'N/A'}, "
        f"Date: {snapshot.match_datetime_utc_iso}"
    )


def format_feedback(
    negative_feedback_examples: List[ScoutUserFeedbackDoc],
) -> str:
    feedback_section = ""
    if negative_feedback_examples:
        feedback_section += (
            "\n\nIMPORTANT USER FEEDBACK (Examples of what NOT to suggest):\n"
        )
        feedback_section += "The user has previously indicated they were NOT interested in matches similar to the following. Please learn from these examples to refine your selections according to their preferences:\n"
        for i, fb_item in enumerate(negative_feedback_examples):
            # Ensure fixture_details_snapshot is not None before trying to dump it
            if fb_item.fixture_details_snapshot:
                fixture_details_str = _format_fixture_snapshot_for_prompt(
                    fb_item.fixture_details_snapshot
                )
            else:
                fixture_details_str = (
                    "Fixture details for this feedback item are missing."
                )

            reason = (
                fb_item.feedback_reason_text or "No specific reason provided by user."
            )
            # original_prompt_snippet = (fb_item.original_llm_prompt_snapshot[:150] + "...") if fb_item.original_llm_prompt_snapshot else "N/A"

            feedback_section += (
                f"\n--- Example of a previous unwanted suggestion {i+1} ---\n"
                f"Context of unwanted match: {fixture_details_str}\n"
                f'User\'s reason for disinterest: "{reason}"\n'
                # f"User's general preference prompt at that time was: \"{original_prompt_snippet}\"\n" # This line might make the prompt too verbose and LLM might focus on old prompt instead of current one. Test its utility. For now, let's simplify.
            )
        feedback_section += "--- End of User Feedback Examples ---\n"
    return feedback_section


def construct_gemini_scout_prompt(
    user_optimized_prompt: str,
    fixtures: List[FixtureForLLM],
    negative_feedback_examples: List[ScoutUserFeedbackDoc],
) -> str:
    """
    Constructs the detailed prompt for Gemini to select fixtures and generate reminder details.
    """
    fixtures_json_str = json.dumps([f.model_dump() for f in fixtures], indent=2)
    feedback_section = format_feedback(negative_feedback_examples)

    prompt = f"""
User's Match Selection Criteria:
"{user_optimized_prompt}"

{feedback_section}

Available Upcoming Fixtures:
{fixtures_json_str}

Output Format:
Provide your response as a VALID JSON ARRAY of selected matches. Each element in the array should be an object strictly following this structure:
{{
  "fixture_id": "string",
  "reason": "string",
  "importance_score": integer,
  "reminder_triggers": [
    {{
      "reminder_offset_minutes_before_kickoff": integer,
      "reminder_mode": "string",
      "custom_message": "string"
    }}
  ]
}}

Even if the number of selected matches is exactly one, you must still return a JSON array with one object inside it.
If no matches meet the criteria, output an empty JSON array: [].
DO NOT include any explanations or text outside (anywhere before or after) of the JSON array.
"""
    return prompt


def get_system_prompt() -> str:
    """
    Returns the system instruction for LLM.
    """
    return _system_prompt
