# Care Plan Generator Backend

This is a FastAPI backend service that uses CrewAI to generate comprehensive care plans based on patient assessment data stored in Supabase.

## Features

- **AI-Powered Care Plan Generation**: Uses CrewAI with multiple specialized agents
- **Supabase Integration**: Fetches assessment data from your existing database
- **RESTful API**: Clean FastAPI endpoints for easy integration
- **Quality Assurance**: Built-in validation and review process
- **Comprehensive Care Plans**: Covers all aspects of elderly care

## Architecture

The system uses three specialized AI agents:

1. **Assessment Analyzer**: Analyzes patient data to identify needs and risks
2. **Care Plan Specialist**: Creates comprehensive, personalized care plans
3. **Quality Assurance**: Reviews and validates care plans for safety and completeness

## Setup

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Environment Configuration

Create a `.env` file in the backend directory:

```env
# Supabase Configuration
SUPABASE_URL=your_supabase_url_here
SUPABASE_KEY=your_supabase_anon_key_here

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Server Configuration
HOST=0.0.0.0
PORT=8000
```

### 3. Database Schema

Ensure your Supabase database has the following tables:

```sql
-- Assessments table (your existing table)
CREATE TABLE assessments (
    id SERIAL PRIMARY KEY,
    personal_info JSONB,
    basic_info JSONB,
    health_info JSONB,
    daily_living JSONB,
    social_support JSONB,
    environment JSONB,
    financial JSONB,
    care_needs JSONB,
    goals JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Care plans table (new table for storing generated plans)
CREATE TABLE care_plans (
    id SERIAL PRIMARY KEY,
    assessment_id INTEGER REFERENCES assessments(id),
    care_plan JSONB,
    status VARCHAR(50) DEFAULT 'generated',
    created_at TIMESTAMP DEFAULT NOW()
);
```

## Running the Service

### Development Mode

```bash
python main.py
```

### Production Mode

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

## API Endpoints

### Health Check
- `GET /health` - Check service status

### Generate Care Plan
- `POST /generate-care-plan` - Generate care plan with request body
- `GET /generate-care-plan/recent` - Generate care plan for most recent assessment
- `GET /generate-care-plan/{assessment_id}` - Generate care plan for specific assessment

### API Documentation
- `GET /docs` - Interactive API documentation (Swagger UI)
- `GET /redoc` - Alternative API documentation

## Example Usage

### Generate Care Plan for Recent Assessment

```bash
curl -X GET "http://localhost:8000/generate-care-plan/recent"
```

### Generate Care Plan for Specific Assessment

```bash
curl -X GET "http://localhost:8000/generate-care-plan/123"
```

### Generate Care Plan with Custom Request

```bash
curl -X POST "http://localhost:8000/generate-care-plan" \
  -H "Content-Type: application/json" \
  -d '{
    "assessment_id": 123,
    "use_recent": false
  }'
```

## Care Plan Structure

The generated care plan includes:

1. **Care Goals and Objectives**
   - Short-term goals (3-6 months)
   - Long-term goals (6-12 months)
   - Measurable outcomes

2. **Medical Care Plan**
   - Medication management
   - Medical appointments and monitoring
   - Health maintenance activities
   - Emergency protocols

3. **Daily Living Support**
   - Personal care assistance needs
   - Mobility and safety measures
   - Nutrition and meal planning
   - Home modifications if needed

4. **Social and Emotional Support**
   - Social engagement activities
   - Mental health support
   - Family communication plan
   - Community resources

5. **Safety and Environment**
   - Home safety assessment
   - Fall prevention measures
   - Emergency response plan
   - Environmental modifications

6. **Financial Planning**
   - Budget management
   - Insurance and benefits
   - Cost of care considerations
   - Financial assistance resources

7. **Monitoring and Evaluation**
   - Progress tracking methods
   - Review schedule
   - Adjustment criteria
   - Success indicators

## Integration with Frontend

The backend is designed to work seamlessly with your existing React frontend. You can:

1. Call the API endpoints from your React components
2. Display the generated care plans in a user-friendly format
3. Store and retrieve care plans as needed

## Error Handling

The service includes comprehensive error handling:

- Database connection errors
- Assessment not found errors
- AI generation errors
- Validation errors

All errors are returned with appropriate HTTP status codes and descriptive messages.

## Security Considerations

- Use environment variables for sensitive configuration
- Implement proper authentication in production
- Validate all input data
- Use HTTPS in production environments

## Performance

- The service uses async/await for better performance
- Database queries are optimized
- AI generation is handled efficiently with CrewAI

## Troubleshooting

### Common Issues

1. **Database Connection Error**: Check your Supabase URL and key
2. **OpenAI API Error**: Verify your OpenAI API key and credits
3. **Port Already in Use**: Change the PORT in your .env file
4. **Missing Dependencies**: Run `pip install -r requirements.txt`

### Logs

The service provides detailed logging for debugging:

- Database operations
- AI agent activities
- API requests and responses
- Error details
