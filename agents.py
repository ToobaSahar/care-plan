import requests
import json
from config import Config
from typing import Dict, List

class CarePlanAgents:
    def __init__(self):
        self.api_key = Config.GEMINI_API_KEY
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self.model = "gemini-2.0-flash"
        
    def _call_gemini_api(self, messages: List[Dict]) -> str:
        """Make a direct API call to Gemini Flash 2.0"""
        headers = {
            "Content-Type": "application/json"
        }
        
        # Convert messages to Gemini format
        system_prompt = "You are an experienced healthcare professional specializing in geriatric care assessment and care plan generation. Respond clearly and helpfully with detailed, actionable care plans."
        full_prompt = self._build_gemini_prompt(system_prompt, messages)
        
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": full_prompt}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 4000
            }
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}",
                headers=headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            return response.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            print(f"Error calling Gemini API: {e}")
            raise e
    
    def _build_gemini_prompt(self, system_prompt: str, messages: List[Dict]) -> str:
        """Build prompt in Gemini format"""
        buffer = []
        
        # Add system prompt at the beginning
        buffer.append(f"System: {system_prompt.strip()}")
        buffer.append("")
        
        # Only take last 5 turns to keep context tight
        recent_messages = messages[-5:] if len(messages) > 5 else messages
        
        for message in recent_messages:
            role = message.get('role', '')
            content = message.get('content', '').strip()
            
            if role == 'user':
                buffer.append(f"User: {content}")
            elif role == 'assistant':
                buffer.append(f"Assistant: {content}")
        
        return "\n".join(buffer)
    
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
        analysis_result = self._call_gemini_api([
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
        planning_result = self._call_gemini_api([
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
        qa_result = self._call_gemini_api([
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
