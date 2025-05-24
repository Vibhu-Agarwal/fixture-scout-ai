# prompt_optimization_service/app/models.py
from pydantic import BaseModel, Field


class PromptOptimizeRequest(BaseModel):
    raw_user_prompt: str = Field(
        ...,
        min_length=10,
        examples=["I like Real Madrid and big CL games, especially finals."],
    )


class PromptOptimizeResponse(BaseModel):
    raw_user_prompt: str
    optimized_user_prompt: str
    model_used: str  # To track which model generated the optimization


class TokenData(BaseModel):
    user_id: str
