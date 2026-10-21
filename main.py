from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from service import CarePlanService
from models import CarePlanRequest, CarePlanResponse
from config import Config
from auth import require_write_access
from staff_api import router as staff_router
import uvicorn

app = FastAPI(
    title="Care Plan Generator API",
    description="AI-powered care plan generation",
    version="1.0.0"
)

# CORS
#
# `allow_origins=["*"]` together with `allow_credentials=True` is rejected by
# every browser anyway, so the old setting was both unsafe and non-working.
# Origins are now an explicit allow-list from ALLOWED_ORIGINS, which must name
# the deployed frontend (e.g. https://careframe.vercel.app). Credentials are
# off because the session travels in an Authorization header, not a cookie.
app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=600,
)

# Managing the care team needs the service role key, which only exists on
# this side of the wire. See staff_api for why it is not a browser call.
app.include_router(staff_router)

# Initialize service
care_plan_service = CarePlanService()

@app.get("/")
async def root():
    return {"message": "Care Plan Generator API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "care-plan-generator"}

@app.post("/generate-care-plan", response_model=CarePlanResponse)
async def generate_care_plan(
    request: CarePlanRequest,
    staff: dict = Depends(require_write_access),
):
    """
    Generate a care plan for the specified or most recent assessment
    """
    try:
        response = await care_plan_service.generate_care_plan(
            assessment_id=request.assessment_id,
            use_recent=request.use_recent
        )
        
        if not response.success:
            raise HTTPException(status_code=400, detail=response.message)
        
        return response

    except HTTPException:
        # Already carries a deliberate status code - do not flatten to 500.
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/generate-care-plan/recent", response_model=CarePlanResponse)
async def generate_care_plan_recent(staff: dict = Depends(require_write_access)):
    """
    Generate a care plan for the most recent assessment
    """
    try:
        response = await care_plan_service.generate_care_plan(use_recent=True)
        
        if not response.success:
            raise HTTPException(status_code=400, detail=response.message)
        
        return response

    except HTTPException:
        # Already carries a deliberate status code - do not flatten to 500.
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/generate-care-plan/{assessment_id}", response_model=CarePlanResponse)
async def generate_care_plan_by_id(
    assessment_id: str,
    staff: dict = Depends(require_write_access),
):
    """
    Generate a care plan for a specific assessment ID
    """
    try:
        response = await care_plan_service.generate_care_plan(assessment_id=assessment_id)
        
        if not response.success:
            raise HTTPException(status_code=400, detail=response.message)
        
        return response

    except HTTPException:
        # Already carries a deliberate status code - do not flatten to 500.
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=Config.HOST,
        port=Config.PORT,
        reload=True
    )
