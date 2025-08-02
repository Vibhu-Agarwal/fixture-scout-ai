# prompt_optimization_service/app/services/optimization_logic.py
import logging
from google import genai
from google.genai import types

from ..models import PromptOptimizeRequest
from ..config import settings

logger = logging.getLogger(__name__)


class OptimizationError(Exception):
    pass


system_prompt = """
You are an AI assistant specialized in refining user preferences for football match reminders into highly effective prompts for another AI called "Fixture Scout AI".
The "Fixture Scout AI" will use the optimized prompt you generate, along with a list of upcoming fixtures, to select relevant matches and schedule reminders for the user.

Your goal is to transform the user's raw, natural language preferences into a prompt that is:
1.  **Clear and Unambiguous:** Easy for an AI to understand.
2.  **Comprehensive:** Captures the user's key interests without being overly verbose.
3.  **Actionable:** Focuses on criteria that can be used to filter or rank matches (e.g., specific teams, tournament stages, rivalries, match importance).
4.  **Concise:** Avoids unnecessary conversational fluff.
5.  **Structured (if helpful):** You can use bullet points or clear statements if it enhances readability for the Fixture Scout AI.

Consider the following aspects when optimizing:
- **Favorite Teams:** If a primary favorite team is mentioned (e.g., "Real Madrid," "Liverpool"), ensure their matches are prioritized (e.g., "All matches of Real Madrid.").
- **Other Key Teams/Rivalries:** If the user mentions other teams or specific matchups (e.g., "Barcelona vs Atletico Madrid," "Manchester derbies"), make this explicit.
- **Tournament Importance:** Distinguish between league matches, domestic cups, and major international/club tournaments like the Champions League (CL), Europa League (EL), World Cup (WC), Euros (EC). Specify stages if mentioned (e.g., "CL knockout stages," "World Cup final").
- **Match Significance:** Incorporate terms that imply importance if the user uses them (e.g., "big matches," "important games," "title deciders," "derbies").
- **Player Milestones/Special Events:** If the user hints at interest in specific player-related events (e.g., "Messi's last season," "a legend's testimonial"), try to capture this if it's actionable for match selection.
- **Negative Preferences:** If the user states teams or match types they *don't* want, this is also valuable (though the Fixture Scout AI is primarily for positive selection).
"""


def _construct_meta_prompt_for_optimization(raw_user_prompt: str) -> str:
    meta_prompt = f"""
**User's Raw Preferences:**
"{raw_user_prompt}"

**Generate ONLY the Optimized Prompt below, ready for Fixture Scout AI. Do not include any other explanatory text or headers outside of the optimized prompt itself.**
Optimized Prompt for Fixture Scout AI:
"""
    return meta_prompt


async def optimize_user_prompt(
    client: genai.Client, user_id: str, request_data: PromptOptimizeRequest
) -> str:
    """
    Uses the optimizer LLM to refine the user's raw prompt.
    """
    full_meta_prompt = _construct_meta_prompt_for_optimization(
        request_data.raw_user_prompt
    )
    logger.info(
        f"Optimizing prompt for user_id: {user_id}. Raw prompt snippet: {request_data.raw_user_prompt[:100]}..."
    )
    logger.debug(f"Full meta-prompt for optimization: {full_meta_prompt}")

    try:
        safety_settings = {
            types.HarmCategory.HARM_CATEGORY_HARASSMENT: types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            types.HarmCategory.HARM_CATEGORY_HATE_SPEECH: types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
            types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        }

        content_config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=settings.LLM_TEMPERATURE,
            max_output_tokens=settings.LLM_MAX_OUTPUT_TOKENS,
            safety_settings=[
                types.SafetySetting(
                    category=category,
                    threshold=threshold,
                )
                for category, threshold in safety_settings.items()
            ],
        )

        response = await client.aio.models.generate_content(
            model=settings.OPTIMIZER_GEMINI_MODEL_NAME,
            contents=full_meta_prompt,
            config=content_config,
        )

        if hasattr(response, "text") and response.text:
            optimized_prompt_text = response.text.strip()
            # Sometimes LLMs might still add a leading "Optimized Prompt:" or similar, try to strip it.
            if optimized_prompt_text.lower().startswith(
                "optimized prompt for fixture scout ai:"
            ):
                optimized_prompt_text = optimized_prompt_text[
                    len("optimized prompt for fixture scout ai:") :
                ].strip()
            elif optimized_prompt_text.lower().startswith("optimized prompt:"):
                optimized_prompt_text = optimized_prompt_text[
                    len("optimized prompt:") :
                ].strip()

            logger.info(
                f"Successfully optimized prompt for user_id: {user_id}. Optimized snippet: {optimized_prompt_text[:100]}..."
            )
            logger.debug(f"Full optimized prompt: {optimized_prompt_text}")
            return optimized_prompt_text
        else:
            logger.warning(
                f"Optimizer LLM returned no text for user_id: {user_id}. Block reason: {response.prompt_feedback.block_reason if response.prompt_feedback else 'N/A'}"
            )
            raise OptimizationError("LLM returned no text for prompt optimization.")

    except Exception as e:
        logger.error(
            f"Error during prompt optimization LLM call for user_id {user_id}: {e}",
            exc_info=True,
        )
        raise OptimizationError(
            f"LLM interaction failed during prompt optimization: {str(e)}"
        )
