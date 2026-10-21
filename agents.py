"""Care plan generation as a three-step Pydantic AI workflow.

The steps run in a fixed order in code - analyse, plan, review - rather than
leaving a model to decide what to do next. For care records that is the point:
every plan takes the same path, so every plan can be audited the same way.

What the framework adds over hand-written API calls is validation. The plan and
the review are checked against the models below; a response that does not fit
is sent back to the model with the validation error to correct, and if it still
does not fit the run fails loudly. Nothing is guessed at or filled in.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field
from pydantic_ai import Agent, NativeOutput
from pydantic_ai.exceptions import (
    AgentRunError,
    ContentFilterError,
    ModelHTTPError,
    UnexpectedModelBehavior,
)
from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel, AnthropicModelSettings
from pydantic_ai.providers.anthropic import AnthropicProvider

from config import Config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Output contract
#
# These models are the shape the frontend renders and database.save_care_plan
# writes, field for field. Changing a name here changes the API.
# ---------------------------------------------------------------------------

LevelOfNeed = Literal["High", "Medium", "Low"]


class SectionCarePlan(BaseModel):
    description: str = Field(description="General description of the care plan area")
    identified_need: str = Field(description="What specific need was identified from the assessment")
    planned_outcomes: str = Field(description="What outcomes are planned to address the need")
    how_to_achieve: str = Field(description="Specific steps and methods to achieve the planned outcomes")
    level_of_need: LevelOfNeed = Field(description="Priority level based on the assessment")


class SectionCarePlans(BaseModel):
    health_wellbeing: SectionCarePlan
    daily_living: SectionCarePlan
    risks_safeguarding: SectionCarePlan
    social_emotional: SectionCarePlan
    environment_lifestyle: SectionCarePlan
    advance_preferences: SectionCarePlan
    optional_areas: SectionCarePlan


class CarePlanDraft(BaseModel):
    care_plans: SectionCarePlans


class QualityReview(BaseModel):
    # A boolean, not a keyword to search for: the old check looked for the word
    # "APPROVED" in free text, so "NOT APPROVED" counted as an approval.
    approved: bool = Field(
        description="True only if the care plans meet every criterion and are safe to use as written"
    )
    recommendations: List[str] = Field(
        description="Specific improvements, one per item. Empty only when approved with no changes."
    )
    summary: str = Field(description="One or two sentences stating the overall verdict")


# Not generated: the model was only ever told to repeat this literal.
NEXT_REVIEW_DATE = "3 months from generation date"


# ---------------------------------------------------------------------------
# Agents
#
# Defined once at import and reused across requests, as Pydantic AI intends -
# they hold no per-request state. The model is supplied per run, which is what
# lets the tests substitute a fake one.
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are an experienced healthcare professional specializing in geriatric "
    "care assessment and care plan generation. Respond clearly and helpfully "
    "with detailed, actionable care plans."
)

# How many times a response that fails validation is sent back for correction.
OUTPUT_RETRIES = 2

analyst = Agent(name="assessment_analyst", output_type=str, instructions=SYSTEM_PROMPT)

# NativeOutput sends the schema as Claude's structured output format, so the
# response is constrained to it. The default - an output tool - relies on
# forcing the tool call, which Claude Opus 5.5 rejects; unforced, the model
# could answer in prose instead.
planner = Agent(
    name="care_planner",
    output_type=NativeOutput(CarePlanDraft),
    instructions=SYSTEM_PROMPT,
    retries={"output": OUTPUT_RETRIES},
)

reviewer = Agent(
    name="quality_reviewer",
    output_type=NativeOutput(QualityReview),
    instructions=SYSTEM_PROMPT,
    retries={"output": OUTPUT_RETRIES},
)


def build_analysis_prompt(assessment_data: Dict) -> str:
    return f"""
        You are an experienced healthcare professional specializing in geriatric care assessment.

        Analyze the following patient assessment data from 7 different assessment sections and provide a comprehensive analysis for each section:

        ASSESSMENT DATA:
        {json.dumps(assessment_data, indent=2, default=str)}

        For each of these 7 sections, analyze:
        1. HEALTH & WELLBEING - Health conditions, medications, mental health, cognition
        2. DAILY LIVING - Personal care, mobility, continence, communication
        3. RISKS & SAFEGUARDING - Falls risk, choking risk, safeguarding concerns
        4. SOCIAL & EMOTIONAL WELLBEING - Family involvement, social activities, emotional support
        5. ENVIRONMENT & LIFESTYLE - Living arrangements, community access, transport needs
        6. ADVANCE PREFERENCES - DNACPR, advance care planning, power of attorney
        7. OPTIONAL AREAS - Financial management, EDI considerations, other specific needs

        Provide a detailed analysis for each section that can be used to create specific care plans.
        """


def build_planning_prompt(analysis: str) -> str:
    # The JSON template the old prompt spelled out is gone: the output schema
    # now travels with the request and the response is validated against it.
    return f"""
        You are a senior care planning specialist with expertise in developing comprehensive care plans for elderly patients.

        Based on the following assessment analysis, create care plans for each of the 7 assessment sections:

        ASSESSMENT ANALYSIS:
        {analysis}

        For each section, include:
        1. DESCRIPTION - General description of the care plan area
        2. IDENTIFIED NEED - What specific need was identified from the assessment
        3. PLANNED OUTCOMES - What outcomes are planned to address the need
        4. HOW TO ACHIEVE OUTCOMES - Specific steps and methods to achieve the planned outcomes
        5. LEVEL OF NEED - Priority level (High/Medium/Low) based on the assessment

        Create care plans for these 7 sections:
        - health_wellbeing
        - daily_living
        - risks_safeguarding
        - social_emotional
        - environment_lifestyle
        - advance_preferences
        - optional_areas

        Make each care plan specific, actionable, and tailored to the individual's assessment data for that particular section.
        """


def build_review_prompt(draft: CarePlanDraft) -> str:
    return f"""
        You are a healthcare quality assurance expert with extensive experience in reviewing care plans.

        Review the following generated care plans for each of the 7 sections:

        1. Completeness - All 7 sections are addressed
        2. Safety - No potential risks or harmful recommendations
        3. Practicality - Recommendations are feasible to implement
        4. Personalization - Plans address individual needs from each section
        5. Evidence-based - Recommendations follow best practices
        6. Measurability - Goals and outcomes can be tracked

        GENERATED CARE PLANS:
        {draft.model_dump_json(indent=2)}

        If you find any issues, provide specific recommendations for improvement.
        If the plans meet all criteria, approve them with any minor suggestions.

        Approve only if every criterion is met.
        """


def format_review(review: QualityReview) -> str:
    """The review as the single text field the API has always returned."""
    lines = [review.summary]
    lines.extend(f"- {item}" for item in review.recommendations)
    return "\n".join(lines)


class CarePlanGenerationError(RuntimeError):
    """A step failed. The message is safe to show a user; details are logged."""


class CarePlanAgents:
    """Runs the analyse -> plan -> review workflow and assembles the API payload."""

    # Claude Opus 5.5 always thinks and rejects `temperature` and disabled
    # thinking with a 400, so neither is sent. Effort is the control instead:
    # it sets how hard the model thinks, and with it latency and cost.
    MODEL_SETTINGS = AnthropicModelSettings(
        # Set explicitly - "medium" is also this model's default, but a silent
        # default can change under a model upgrade.
        anthropic_effort="medium",
        # Thinking tokens count against this as well as the plan itself, so it
        # is sized for both; a lower cap truncates the plan mid-section.
        max_tokens=16000,
        # Per attempt, in seconds.
        timeout=240,
        # The Anthropic client retries throttling and transient upstream
        # errors with exponential backoff, honouring Retry-After.
        max_retries=3,
    )

    def __init__(self, model: Optional[Model] = None):
        self.model = model if model is not None else self._build_anthropic_model()

    @staticmethod
    def _build_anthropic_model() -> Model:
        if not Config.ANTHROPIC_API_KEY:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Add it to your .env file or host environment."
            )
        return AnthropicModel(
            Config.ANTHROPIC_MODEL,
            provider=AnthropicProvider(api_key=Config.ANTHROPIC_API_KEY),
        )

    async def _run(self, agent: Agent, step: str, prompt: str):
        try:
            result = await agent.run(prompt, model=self.model, model_settings=self.MODEL_SETTINGS)
        except ModelHTTPError as e:
            # The provider's error body names the problem (credit, bad model
            # name) and carries none of the assessment.
            logger.error("Care plan %s step: model API returned %s: %s", step, e.status_code, e.body)
            raise CarePlanGenerationError(
                f"The AI service rejected the {step} step (HTTP {e.status_code})."
            ) from e
        except ContentFilterError as e:
            # Claude declined the request (stop_reason "refusal"). The
            # explanation is not logged: it can describe the input.
            logger.error("Care plan %s step: model declined the request", step)
            raise CarePlanGenerationError(
                f"The AI declined the {step} step. Please review the assessment and try again."
            ) from e
        except UnexpectedModelBehavior as e:
            # Deliberately not logging the message: it can quote the model's
            # output, and that output is about a real person.
            logger.error("Care plan %s step: output still invalid after %d retries", step, OUTPUT_RETRIES)
            raise CarePlanGenerationError(
                f"The AI response for the {step} step could not be validated. Please try again."
            ) from e
        except AgentRunError as e:
            logger.error("Care plan %s step failed: %s", step, type(e).__name__)
            raise CarePlanGenerationError(f"The {step} step failed. Please try again.") from e

        # Counts only - enough to watch cost per plan without logging content.
        usage = result.usage
        print(
            f"   {step}: {usage.requests} request(s), "
            f"{usage.input_tokens} input / {usage.output_tokens} output tokens"
        )
        return result.output

    async def generate_care_plan(self, assessment_data: Dict) -> Dict:
        """Generate care plans for each of the 7 assessment sections"""
        print("🔍 Step 1: Analyzing assessment data...")
        analysis: str = await self._run(analyst, "analysis", build_analysis_prompt(assessment_data))

        print("📋 Step 2: Generating care plans for each section...")
        draft: CarePlanDraft = await self._run(planner, "planning", build_planning_prompt(analysis))

        print("✅ Step 3: Quality assurance review...")
        review: QualityReview = await self._run(reviewer, "quality review", build_review_prompt(draft))

        return {
            **draft.model_dump(),
            "next_review_date": NEXT_REVIEW_DATE,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "approved" if review.approved else "review_needed",
            "analysis": analysis,
            "qa_review": format_review(review),
        }
