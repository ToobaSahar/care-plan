#!/usr/bin/env python3
"""
Test script for the Care Plan Generator API
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_health():
    """Test the health endpoint"""
    print("🏥 Testing health endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print("✅ Health check passed")
            print(f"Response: {response.json()}")
        else:
            print(f"❌ Health check failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Health check error: {e}")

def test_generate_recent():
    """Test generating care plan for recent assessment"""
    print("\n📋 Testing care plan generation for recent assessment...")
    try:
        response = requests.get(f"{BASE_URL}/generate-care-plan/recent")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Care plan generated successfully")
            print(f"Assessment ID: {data.get('assessment_id')}")
            print(f"Message: {data.get('message')}")
            
            if data.get('care_plan'):
                print("📄 Care plan structure:")
                care_plan = data['care_plan']
                if 'sections' in care_plan:
                    for section_name in care_plan['sections'].keys():
                        print(f"  - {section_name}")
        else:
            print(f"❌ Failed to generate care plan: {response.text}")
            
    except Exception as e:
        print(f"❌ Error generating care plan: {e}")

def test_generate_by_id():
    """Test generating care plan for specific assessment ID"""
    print("\n🆔 Testing care plan generation by assessment ID...")
    try:
        # Try with a test ID (you may need to adjust this)
        test_id = 1
        response = requests.get(f"{BASE_URL}/generate-care-plan/{test_id}")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Care plan generated successfully")
            print(f"Assessment ID: {data.get('assessment_id')}")
        else:
            print(f"❌ Failed to generate care plan: {response.text}")
            
    except Exception as e:
        print(f"❌ Error generating care plan: {e}")

def test_post_request():
    """Test POST request for care plan generation"""
    print("\n📤 Testing POST request for care plan generation...")
    try:
        payload = {
            "assessment_id": None,
            "use_recent": True
        }
        
        response = requests.post(
            f"{BASE_URL}/generate-care-plan",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ POST request successful")
            print(f"Assessment ID: {data.get('assessment_id')}")
        else:
            print(f"❌ POST request failed: {response.text}")
            
    except Exception as e:
        print(f"❌ Error with POST request: {e}")

def main():
    """Run all tests"""
    print("🧪 Starting API Tests...")
    print("=" * 50)
    
    # Test health endpoint
    test_health()
    
    # Wait a moment
    time.sleep(1)
    
    # Test care plan generation
    test_generate_recent()
    
    # Wait a moment
    time.sleep(1)
    
    # Test by ID
    test_generate_by_id()
    
    # Wait a moment
    time.sleep(1)
    
    # Test POST request
    test_post_request()
    
    print("\n" + "=" * 50)
    print("🏁 API testing completed!")

if __name__ == "__main__":
    main()
