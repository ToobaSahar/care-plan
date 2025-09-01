from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from service import CarePlanService
from models import CarePlanRequest, CarePlanResponse
from config import Config
import uvicorn

app = FastAPI(
    title="Care Plan Generator API",
    description="AI-powered care plan generation",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize service
care_plan_service = CarePlanService()

@app.get("/")
async def root():
    return {"message": "Care Plan Generator API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "care-plan-generator"}

@app.post("/generate-care-plan", response_model=CarePlanResponse)
async def generate_care_plan(request: CarePlanRequest):
    """
    Generate a care plan for the specified or most recent assessment
    """
    try:
        response = care_plan_service.generate_care_plan(
            assessment_id=request.assessment_id,
            use_recent=request.use_recent
        )
        
        if not response.success:
            raise HTTPException(status_code=400, detail=response.message)
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/generate-care-plan/recent", response_model=CarePlanResponse)
async def generate_care_plan_recent():
    """
    Generate a care plan for the most recent assessment
    """
    try:
        response = care_plan_service.generate_care_plan(use_recent=True)
        
        if not response.success:
            raise HTTPException(status_code=400, detail=response.message)
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/generate-care-plan/{assessment_id}", response_model=CarePlanResponse)
async def generate_care_plan_by_id(assessment_id: str):
    """
    Generate a care plan for a specific assessment ID
    """
    try:
        response = care_plan_service.generate_care_plan(assessment_id=assessment_id)
        
        if not response.success:
            raise HTTPException(status_code=400, detail=response.message)
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=Config.HOST,
        port=Config.PORT,
        reload=True
    )
