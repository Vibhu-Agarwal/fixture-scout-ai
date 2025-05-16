# scout_service/app/llm_prompts.py
import json
from typing import List
from .models import FixtureForLLM


def construct_gemini_scout_prompt(
    user_optimized_prompt: str, fixtures: List[FixtureForLLM]
) -> str:
    """
    Constructs the detailed prompt for Gemini to select fixtures and generate reminder details.
    """
    fixtures_json_str = json.dumps([f.model_dump() for f in fixtures], indent=2)

    prompt = f"""
You are Fixture Scout AI. Your task is to select relevant football matches for a user based on their preferences and a list of upcoming fixtures.
For each match you select, you must provide a brief reason for the selection, assign an importance score, and define specific reminder triggers.

User's Match Selection Criteria:
"{user_optimized_prompt}"

Available Upcoming Fixtures:
{fixtures_json_str}

Instructions for your response:
1. Analyze the user's criteria and the available fixtures.
2. Select ONLY the matches that fit the user's criteria.
3. For EACH selected match, provide:
    a. "fixture_id": The exact fixture_id from the input.
    b. "reason": A brief (1-2 sentences, max 100 characters) explanation of why this match is relevant to the user based on their criteria (e.g., "Important Real Madrid La Liga game.", "Potential title decider in Premier League.", "Champions League clash between top teams.").
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

If no matches meet the criteria, output an empty JSON array: [].
DO NOT include any explanations or text outside of the JSON array.
"""
    return prompt
