#!/usr/bin/env python3
"""
Tests for the care plan workflow in agents.py.

Nothing here reaches a real model: the workflow runs against Pydantic AI's
FunctionModel, and the tests that build the real Anthropic model answer its
HTTP requests locally. No API key, no network, no cost.

    python -m unittest test_agents -v
"""

import json
import unittest
from datetime import datetime

import httpx2
from anthropic import AsyncAnthropic
from pydantic_ai import models
from pydantic_ai.messages import ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.providers.anthropic import AnthropicProvider

from agents import (
    NEXT_REVIEW_DATE,
    OUTPUT_RETRIES,
    SYSTEM_PROMPT,
    CarePlanAgents,
    CarePlanGenerationError,
    SectionCarePlans,
    analyst,
    planner,
)

# Any test that would call a real model API fails instead.
models.ALLOW_MODEL_REQUESTS = False

SECTIONS = list(SectionCarePlans.model_fields)
SECTION_FIELDS = ["description", "identified_need", "planned_outcomes", "how_to_achieve", "level_of_need"]

ASSESSMENT = {
    "assessment_id": "test-assessment",
    "health_wellbeing": {"conditions": "Type 2 diabetes", "medications": "Metformin"},
    "risks_safeguarding": {"falls_risk": "High - two falls this year"},
}


def section(level):
    return {
        "description": "Support with diabetes management",
        "identified_need": "Blood sugar monitoring",
        "planned_outcomes": "Stable blood sugar",
        "how_to_achieve": "Daily checks by carer",
        "level_of_need": level,
    }


def last_prompt(messages):
    """The user prompt of the most recent request, as the model received it."""
    for message in reversed(messages):
        for part in getattr(message, "parts", []):
            if isinstance(part, UserPromptPart):
                return part.content
    return ""


class FakeModel:
    """Plays all three agents, telling them apart by the output they ask for.

    The planner and reviewer use native structured output, so their answers
    come back as JSON text checked against the schema in the request.
    """

    def __init__(self, plan_levels=("High",), approved=True):
        # One level per planner attempt; the last one repeats.
        self.plan_levels = list(plan_levels)
        self.approved = approved
        self.planner_calls = 0
        self.prompts = {}

    def __call__(self, messages, info: AgentInfo) -> ModelResponse:
        output = info.model_request_parameters.output_object
        if output is None:
            self.prompts["analysis"] = last_prompt(messages)
            return ModelResponse(parts=[TextPart("ANALYSIS: high falls risk, diabetes needs monitoring.")])

        if "care_plans" in output.json_schema["properties"]:
            self.prompts["planning"] = last_prompt(messages)
            level = self.plan_levels[min(self.planner_calls, len(self.plan_levels) - 1)]
            self.planner_calls += 1
            plan = {"care_plans": {name: section(level) for name in SECTIONS}}
            return ModelResponse(parts=[TextPart(json.dumps(plan))])

        self.prompts["review"] = last_prompt(messages)
        review = {
            "approved": self.approved,
            "recommendations": [] if self.approved else ["Add a falls prevention plan"],
            "summary": "Approved." if self.approved else "NOT APPROVED: falls risk is not addressed.",
        }
        return ModelResponse(parts=[TextPart(json.dumps(review))])


class CarePlanWorkflowTests(unittest.IsolatedAsyncioTestCase):

    async def generate(self, fake):
        return await CarePlanAgents(model=FunctionModel(fake)).generate_care_plan(ASSESSMENT)

    async def test_payload_matches_what_frontend_and_database_read(self):
        plan = await self.generate(FakeModel())

        self.assertEqual(
            sorted(plan),
            ["analysis", "care_plans", "generated_at", "next_review_date", "qa_review", "status"],
        )
        self.assertEqual(list(plan["care_plans"]), SECTIONS)
        for name in SECTIONS:
            self.assertEqual(list(plan["care_plans"][name]), SECTION_FIELDS)
            self.assertIn(plan["care_plans"][name]["level_of_need"], ("High", "Medium", "Low"))
        self.assertEqual(plan["status"], "approved")
        self.assertEqual(plan["next_review_date"], NEXT_REVIEW_DATE)
        self.assertIsNotNone(datetime.fromisoformat(plan["generated_at"]).tzinfo)
        self.assertIsInstance(plan["qa_review"], str)
        json.dumps(plan)  # the API returns it and the database stores it

    async def test_each_step_receives_the_previous_steps_output(self):
        fake = FakeModel()
        await self.generate(fake)

        self.assertIn("Type 2 diabetes", fake.prompts["analysis"])
        self.assertIn("ANALYSIS: high falls risk", fake.prompts["planning"])
        self.assertIn("Daily checks by carer", fake.prompts["review"])

    async def test_invalid_level_of_need_is_sent_back_and_corrected(self):
        fake = FakeModel(plan_levels=("Urgent", "High"))
        plan = await self.generate(fake)

        self.assertEqual(fake.planner_calls, 2)
        self.assertEqual(plan["care_plans"]["daily_living"]["level_of_need"], "High")

    async def test_output_that_never_validates_fails_instead_of_inventing_a_plan(self):
        fake = FakeModel(plan_levels=("Urgent",))

        with self.assertRaises(CarePlanGenerationError):
            await self.generate(fake)
        self.assertEqual(fake.planner_calls, 1 + OUTPUT_RETRIES)

    async def test_rejected_review_is_not_approved(self):
        plan = await self.generate(FakeModel(approved=False))

        # The old check searched the review text for "APPROVED" and so passed this.
        self.assertEqual(plan["status"], "review_needed")
        self.assertIn("NOT APPROVED", plan["qa_review"])
        self.assertIn("Add a falls prevention plan", plan["qa_review"])


class AnthropicRequestTests(unittest.IsolatedAsyncioTestCase):
    """What actually goes over the wire to Anthropic, answered locally."""

    async def run_step(self, agent, step, reply_text):
        sent = []

        def anthropic_api(request):
            sent.append(json.loads(request.content))
            return httpx2.Response(200, json={
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "model": "claude-opus-5-5",
                "content": [{"type": "text", "text": reply_text}],
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {"input_tokens": 10, "output_tokens": 2},
            })

        client = AsyncAnthropic(
            api_key="test-key",
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(anthropic_api)),
        )
        model = AnthropicModel("claude-opus-5-5", provider=AnthropicProvider(anthropic_client=client))

        with models.override_allow_model_requests(True):
            output = await CarePlanAgents(model=model)._run(agent, step, "Assess this.")
        return output, sent[0]

    async def test_request_carries_settings_claude_opus_5_5_accepts(self):
        output, body = await self.run_step(analyst, "analysis", "Analysis.")

        self.assertEqual(output, "Analysis.")
        self.assertEqual(body["model"], "claude-opus-5-5")
        self.assertEqual(body["max_tokens"], 16000)
        self.assertEqual(body["output_config"]["effort"], "medium")
        # Each of these is a 400 on Claude Opus 5.5.
        self.assertNotIn("temperature", body)
        self.assertNotEqual(body.get("thinking", {}).get("type"), "disabled")
        self.assertIn(SYSTEM_PROMPT, json.dumps(body["system"]))

    async def test_plan_is_requested_as_structured_output_without_forcing_a_tool(self):
        plan = {"care_plans": {name: section("Medium") for name in SECTIONS}}
        output, body = await self.run_step(planner, "planning", json.dumps(plan))

        self.assertEqual(output.care_plans.daily_living.level_of_need, "Medium")
        self.assertEqual(body["output_config"]["format"]["type"], "json_schema")
        self.assertIn("care_plans", json.dumps(body["output_config"]["format"]["schema"]))
        # Forced tool choice is a 400 on Claude Opus 5.5.
        self.assertNotIn(body.get("tool_choice", {}).get("type"), ("any", "tool"))


if __name__ == "__main__":
    unittest.main()
