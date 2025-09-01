#!/usr/bin/env python3
"""
Test script to verify care plan generation and saving functionality
"""

import sys
import os
import json
from datetime import datetime

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import DatabaseManager
from agents import CarePlanAgents
from service import CarePlanService

def test_care_plan_generation_and_save():
    """Test the complete care plan generation and saving process"""
    
    print("🧪 Starting care plan generation and save test...")
    
    try:
        # Initialize services
        db = DatabaseManager()
        agents = CarePlanAgents()
        service = CarePlanService()
        
        print("✅ Services initialized successfully")
        
        # Test 1: Check if we can get recent assessment data
        print("\n📋 Test 1: Fetching recent assessment data...")
        assessment_data = db.get_recent_assessment()
        
        if not assessment_data:
            print("❌ No recent assessment data found")
            print("💡 Please ensure you have completed at least one assessment form")
            return False
        
        print(f"✅ Found assessment data for ID: {assessment_data['assessment_id']}")
        print(f"📊 Assessment sections with data: {[k for k, v in assessment_data.items() if v is not None and k != 'assessment_id']}")
        
        # Test 2: Generate care plan using agents
        print("\n🤖 Test 2: Generating care plan using AI agents...")
        care_plan = agents.generate_care_plan(assessment_data)
        
        if 'error' in care_plan:
            print(f"❌ Error generating care plan: {care_plan['error']}")
            return False
        
        print("✅ Care plan generated successfully")
        print(f"📋 Care plan keys: {list(care_plan.keys())}")
        
        if 'care_plans' in care_plan:
            print(f"📊 Care plan sections: {list(care_plan['care_plans'].keys())}")
            for section_name, section_data in care_plan['care_plans'].items():
                print(f"  - {section_name}: {list(section_data.keys())}")
        
        # Test 3: Save care plan to database
        print("\n💾 Test 3: Saving care plan to database...")
        assessment_id = assessment_data['assessment_id']
        save_success = db.save_care_plan(assessment_id, care_plan)
        
        if save_success:
            print("✅ Care plan saved successfully to database")
        else:
            print("❌ Failed to save care plan to database")
            return False
        
        # Test 4: Verify care plan was saved by checking the tables
        print("\n🔍 Test 4: Verifying care plan data in database...")
        
        care_plan_tables = {
            'health_wellbeing': 'health_care_plan',
            'daily_living': 'daily_living_care_plan',
            'risks_safeguarding': 'risks_safeguarding_care_plan',
            'social_emotional': 'social_emotional_care_plan',
            'environment_lifestyle': 'environment_lifestyle_care_plan',
            'advance_preferences': 'advance_preferences_care_plan',
            'optional_areas': 'optional_areas_care_plan'
        }
        
        verification_success = True
        for section_name, table_name in care_plan_tables.items():
            try:
                response = db.supabase.table(table_name).select('*').eq('assessment_id', assessment_id).execute()
                if response.data:
                    print(f"✅ {section_name}: Data found in {table_name}")
                    data = response.data[0]
                    print(f"   - Description: {data.get('description', 'N/A')[:50]}...")
                    print(f"   - Level of need: {data.get('level_of_need', 'N/A')}")
                else:
                    print(f"❌ {section_name}: No data found in {table_name}")
                    verification_success = False
            except Exception as e:
                print(f"❌ {section_name}: Error checking {table_name}: {e}")
                verification_success = False
        
        if verification_success:
            print("\n🎉 All tests passed! Care plan generation and saving is working correctly.")
            return True
        else:
            print("\n⚠️ Some verification tests failed. Check the database tables.")
            return False
            
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_service_integration():
    """Test the complete service integration"""
    
    print("\n🔧 Testing service integration...")
    
    try:
        service = CarePlanService()
        
        # Test generating care plan for recent assessment
        print("📋 Generating care plan for recent assessment...")
        response = service.generate_care_plan(use_recent=True)
        
        if response.success:
            print("✅ Service integration test passed")
            print(f"📊 Response: {response.message}")
            return True
        else:
            print(f"❌ Service integration test failed: {response.message}")
            return False
            
    except Exception as e:
        print(f"❌ Service integration test failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Care Plan Generation and Save Test Suite")
    print("=" * 50)
    
    # Run the main test
    test1_result = test_care_plan_generation_and_save()
    
    # Run service integration test
    test2_result = test_service_integration()
    
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    print(f"  - Care Plan Generation & Save: {'✅ PASSED' if test1_result else '❌ FAILED'}")
    print(f"  - Service Integration: {'✅ PASSED' if test2_result else '❌ FAILED'}")
    
    if test1_result and test2_result:
        print("\n🎉 All tests passed! The care plan system is working correctly.")
        sys.exit(0)
    else:
        print("\n⚠️ Some tests failed. Please check the output above for details.")
        sys.exit(1)
