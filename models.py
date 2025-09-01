from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime

class AssessmentData(BaseModel):
    assessment_id: Optional[str] = None
    health_wellbeing: Optional[Dict] = None
    daily_living: Optional[Dict] = None
    risks_safeguarding: Optional[Dict] = None
    social_emotional: Optional[Dict] = None
    environment_lifestyle: Optional[Dict] = None
    advance_preferences: Optional[Dict] = None
    optional_areas: Optional[Dict] = None

class CarePlanRequest(BaseModel):
    assessment_id: Optional[str] = None
    use_recent: bool = True

class CarePlanResponse(BaseModel):
    success: bool
    care_plan: Optional[Dict] = None
    assessment_id: Optional[str] = None
    message: str

class CarePlan(BaseModel):
    assessment_id: str
    care_plan: Dict
    status: str
    created_at: datetime
