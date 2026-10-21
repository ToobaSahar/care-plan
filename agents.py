import json
import logging
from typing import Dict, List

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import Config

logger = logging.getLogger(__name__)


class CarePlanAgents:
    """Generate care plans via the OpenAI Chat Completions API."""

    API_URL = "https://api.openai.com/v1/chat/completions"
    TEMPERATURE = 0.7
    MAX_COMPLETION_TOKENS = 4000
    # (connect, read) seconds - read is generous because care plans are long.
    TIMEOUT = (10, 120)
    # Retried with exponential backoff on throttling and transient upstream errors.
    MAX_RETRIES = 3
    RETRY_STATUSES = (408, 409, 429, 500, 502, 503, 504)

    SYSTEM_PROMPT = (
        "You are an experienced healthcare professional specializing in geriatric "
        "care assessment and care plan generation. Respond clearly and helpfully "
        "with detailed, actionable care plans."
    )

    def __init__(self):
        self.api_key = Config.OPENAI_API_KEY
        if not self.api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Add it to your .env file or host environment."
            )
        self.model = Config.OPENAI_MODEL
        self._session = self._build_session()

    @classmethod
    def _build_session(cls) -> requests.Session:
        """A pooled session so the three sequential calls reuse one TLS connection."""
        retry = Retry(
            total=cls.MAX_RETRIES,
            backoff_factor=2,
            status_forcelist=cls.RETRY_STATUSES,
            allowed_methods=frozenset({"POST"}),
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        session = requests.Session()
        session.mount("https://", HTTPAdapter(max_retries=retry, pool_maxsize=10))
        return session

    def _call_openai_api(self, messages: List[Dict]) -> str:
        """Make a chat completion request and return the assistant's text."""
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                *messages,
            ],
            "temperature": self.TEMPERATURE,
            "max_completion_tokens": self.MAX_COMPLETION_TOKENS,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = self._session.post(
                self.API_URL,
                headers=headers,
                json=payload,
                timeout=self.TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
        except requests.HTTPError as e:
            # Log the response body only - headers carry the API key.
            status = e.response.status_code if e.response is not None else "unknown"
            body = e.response.text[:500] if e.response is not None else ""
            logger.error("OpenAI API returned %s: %s", status, body)
            raise
        except requests.RequestException as e:
            logger.error("OpenAI API request failed: %s", e)
            raise

        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            logger.error("Unexpected OpenAI response shape: %s", json.dumps(data)[:500])
            raise RuntimeError("Unexpected OpenAI response shape") from e

    def generate_care_plan(self, assessment_data: Dict) -> Dict:
        """Generate care plans for each of the 7 assessment sections"""
        
        # Step 1: Analysis Task
        analysis_prompt = f"""
        You are an experienced healthcare professional specializing in geriatric care assessment.
        
        Analyze the following patient assessment data from 7 different assessment sections and provide a comprehensive analysis for each section:
        
        ASSESSMENT DATA:
        {json.dumps(assessment_data, indent=2)}
        
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
        
        print("🔍 Step 1: Analyzing assessment data...")
        analysis_result = self._call_openai_api([
            {"role": "user", "content": analysis_prompt}
        ])
        
        # Step 2: Care Plan Generation for each section
        planning_prompt = f"""
        You are a senior care planning specialist with expertise in developing comprehensive care plans for elderly patients.
        
        Based on the following assessment analysis, create care plans for each of the 7 assessment sections in the exact format specified:
        
        ASSESSMENT ANALYSIS:
        {analysis_result}
        
        Create care plans for these 7 sections with these exact fields for each:
        
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
        
        ### IMPORTANT ###
        Respond ONLY with a valid JSON object that matches the structure below. Do not include any extra commentary, markdown formatting, or explanations. The response must start with "{" and end with "}".

        Expected structure:
        {{
            "care_plans": {{
                "health_wellbeing": {{
                    "description": "...",
                    "identified_need": "...",
                    "planned_outcomes": "...",
                    "how_to_achieve": "...",
                    "level_of_need": "High/Medium/Low"
                }},
                "daily_living": {{
                    "description": "...",
                    "identified_need": "...",
                    "planned_outcomes": "...",
                    "how_to_achieve": "...",
                    "level_of_need": "High/Medium/Low"
                }},
                "risks_safeguarding": {{
                    "description": "...",
                    "identified_need": "...",
                    "planned_outcomes": "...",
                    "how_to_achieve": "...",
                    "level_of_need": "High/Medium/Low"
                }},
                "social_emotional": {{
                    "description": "...",
                    "identified_need": "...",
                    "planned_outcomes": "...",
                    "how_to_achieve": "...",
                    "level_of_need": "High/Medium/Low"
                }},
                "environment_lifestyle": {{
                    "description": "...",
                    "identified_need": "...",
                    "planned_outcomes": "...",
                    "how_to_achieve": "...",
                    "level_of_need": "High/Medium/Low"
                }},
                "advance_preferences": {{
                    "description": "...",
                    "identified_need": "...",
                    "planned_outcomes": "...",
                    "how_to_achieve": "...",
                    "level_of_need": "High/Medium/Low"
                }},
                "optional_areas": {{
                    "description": "...",
                    "identified_need": "...",
                    "planned_outcomes": "...",
                    "how_to_achieve": "...",
                    "level_of_need": "High/Medium/Low"
                }}
            }},
            "next_review_date": "3 months from generation date"
        }}
        
        Make each care plan specific, actionable, and tailored to the individual's assessment data for that particular section.
        """
        
        print("📋 Step 2: Generating care plans for each section...")
        planning_result = self._call_openai_api([
            {"role": "user", "content": planning_prompt}
        ])
        
        # Step 3: Quality Assurance
        qa_prompt = f"""
        You are a healthcare quality assurance expert with extensive experience in reviewing care plans.
        
        Review the following generated care plans for each of the 7 sections:
        
        1. Completeness - All 7 sections are addressed
        2. Safety - No potential risks or harmful recommendations
        3. Practicality - Recommendations are feasible to implement
        4. Personalization - Plans address individual needs from each section
        5. Evidence-based - Recommendations follow best practices
        6. Measurability - Goals and outcomes can be tracked
        
        GENERATED CARE PLANS:
        {planning_result}
        
        If you find any issues, provide specific recommendations for improvement.
        If the plans meet all criteria, approve them with any minor suggestions.
        
        Respond with either "APPROVED" or specific improvement recommendations.
        """
        
        print("✅ Step 3: Quality assurance review...")
        qa_result = self._call_openai_api([
            {"role": "user", "content": qa_prompt}
        ])
        
        # Parse the result and extract the care plan
        return self._parse_care_plan_result(planning_result, analysis_result, qa_result)
    
    def _parse_care_plan_result(self, planning_result: str, analysis_result: str, qa_result: str) -> Dict:
        """Parse the manual agent result and extract the structured care plan"""
        try:
            # Try to extract JSON from the planning result
            if "{" in planning_result and "}" in planning_result:
                # Find the JSON part
                start = planning_result.find("{")
                end = planning_result.rfind("}") + 1
                json_str = planning_result[start:end]
                
                care_plan = json.loads(json_str)
                
                # Add metadata
                care_plan["generated_at"] = "2024-01-15T10:30:00Z"
                care_plan["status"] = "approved" if "APPROVED" in qa_result.upper() else "review_needed"
                care_plan["analysis"] = analysis_result
                care_plan["qa_review"] = qa_result
                
                return care_plan
            else:
                # Fallback: create structured care plan from text
                care_plan = {
                    "generated_at": "2024-01-15T10:30:00Z",
                    "status": "approved" if "APPROVED" in qa_result.upper() else "review_needed",
                    "care_plans": {
                        "health_wellbeing": {
                            "description": "Health and wellbeing care plan",
                            "identified_need": "Based on assessment analysis",
                            "planned_outcomes": "Better health management and wellbeing",
                            "how_to_achieve": "Regular health monitoring and care",
                            "level_of_need": "High"
                        },
                        "daily_living": {
                            "description": "Daily living activities care plan",
                            "identified_need": "Based on assessment analysis",
                            "planned_outcomes": "Improved daily living independence",
                            "how_to_achieve": "Support with daily activities",
                            "level_of_need": "High"
                        },
                        "risks_safeguarding": {
                            "description": "Risks and safeguarding care plan",
                            "identified_need": "Based on assessment analysis",
                            "planned_outcomes": "Enhanced safety and risk management",
                            "how_to_achieve": "Implement safety measures and monitoring",
                            "level_of_need": "High"
                        },
                        "social_emotional": {
                            "description": "Social and emotional wellbeing care plan",
                            "identified_need": "Based on assessment analysis",
                            "planned_outcomes": "Enhanced social connections and emotional support",
                            "how_to_achieve": "Facilitate social interactions and emotional care",
                            "level_of_need": "Medium"
                        },
                        "environment_lifestyle": {
                            "description": "Environment and lifestyle care plan",
                            "identified_need": "Based on assessment analysis",
                            "planned_outcomes": "Safe and supportive living environment",
                            "how_to_achieve": "Environmental modifications and lifestyle support",
                            "level_of_need": "High"
                        },
                        "advance_preferences": {
                            "description": "Advance preferences care plan",
                            "identified_need": "Based on assessment analysis",
                            "planned_outcomes": "Respect for advance care preferences",
                            "how_to_achieve": "Document and implement advance care plans",
                            "level_of_need": "Medium"
                        },
                        "optional_areas": {
                            "description": "Optional areas care plan",
                            "identified_need": "Based on assessment analysis",
                            "planned_outcomes": "Address specific optional needs",
                            "how_to_achieve": "Implement targeted support for optional areas",
                            "level_of_need": "Medium"
                        }
                    },
                    "next_review_date": "3 months from generation date",
                    "raw_planning_result": planning_result,
                    "analysis": analysis_result,
                    "qa_review": qa_result
                }
                
                return care_plan
                
        except Exception as e:
            print(f"Error parsing care plan result: {e}")
            return {
                "error": "Failed to parse care plan result",
                "raw_planning_result": planning_result,
                "analysis": analysis_result,
                "qa_review": qa_result
            }
