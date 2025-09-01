from database import DatabaseManager
from agents import CarePlanAgents
from models import CarePlanResponse
from typing import Dict, Optional
import json

class CarePlanService:
    def __init__(self):
        self.db = DatabaseManager()
        self.agents = CarePlanAgents()
    
    def generate_care_plan(self, assessment_id: Optional[str] = None, use_recent: bool = True) -> CarePlanResponse:
        """Generate a care plan for the specified or most recent assessment"""
        
        try:
            # Fetch assessment data
            if assessment_id:
                assessment_data = self.db.get_assessment_by_id(assessment_id)
                if not assessment_data:
                    return CarePlanResponse(
                        success=False,
                        message=f"Assessment with ID {assessment_id} not found"
                    )
            elif use_recent:
                assessment_data = self.db.get_recent_assessment()
                if not assessment_data:
                    return CarePlanResponse(
                        success=False,
                        message="No recent assessment found in database"
                    )
                assessment_id = assessment_data['assessment_id']
            else:
                return CarePlanResponse(
                    success=False,
                    message="Either assessment_id or use_recent=True must be provided"
                )
            
            # Generate care plan using CrewAI agents
            care_plan = self.agents.generate_care_plan(assessment_data)
            
            # Save care plan to database
            if 'error' not in care_plan:
                save_success = self.db.save_care_plan(assessment_id, care_plan)
                if not save_success:
                    print("Warning: Failed to save care plan to database")
            
            return CarePlanResponse(
                success=True,
                care_plan=care_plan,
                assessment_id=assessment_id,
                message="Care plan generated successfully"
            )
            
        except Exception as e:
            print(f"Error generating care plan: {e}")
            return CarePlanResponse(
                success=False,
                message=f"Error generating care plan: {str(e)}"
            )
    
    def get_care_plan(self, assessment_id: str) -> Optional[Dict]:
        """Retrieve a previously generated care plan"""
        try:
            # This would need to be implemented in the database manager
            # For now, we'll return None
            return None
        except Exception as e:
            print(f"Error retrieving care plan: {e}")
            return None
