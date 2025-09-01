from supabase import create_client, Client
from config import Config
from typing import Dict, List, Optional
import json

class DatabaseManager:
    def __init__(self):
        # Use service role key for care plan operations to bypass RLS
        self.supabase: Client = create_client(Config.SUPABASE_URL, Config.SUPABASE_SERVICE_KEY)
    
    def get_recent_assessment(self) -> Optional[Dict]:
        """Fetch the most recently saved row from each of the 7 specified tables"""
        try:
            # Define the 7 tables to fetch from
            tables = [
                'health_wellbeing', 'daily_living', 'risks_safeguarding',
                'social_emotional', 'environment_lifestyle', 'advance_preferences', 'optional_areas'
            ]
            
            # Initialize assessment data structure
            assessment_data = {
                'assessment_id': None,
                'health_wellbeing': None,
                'daily_living': None,
                'risks_safeguarding': None,
                'social_emotional': None,
                'environment_lifestyle': None,
                'advance_preferences': None,
                'optional_areas': None
            }
            
            # Fetch the most recent row from each table
            for table in tables:
                try:
                    # Get the most recent row from each table (ordering by created_at to get the latest)
                    response = self.supabase.table(table).select('*').order('created_at', desc=True).limit(1).execute()
                    if response.data:
                        assessment_data[table] = response.data[0]
                        # Use the assessment_id from the first table that has data
                        if assessment_data['assessment_id'] is None and 'assessment_id' in response.data[0]:
                            assessment_data['assessment_id'] = response.data[0]['assessment_id']
                    else:
                        print(f"No data found in table {table}")
                except Exception as e:
                    print(f"Error fetching from {table}: {e}")
                    assessment_data[table] = None
            
            # Check if we got data from at least one table
            has_data = any(assessment_data[table] is not None for table in tables)
            if not has_data:
                print("No data found in any of the specified tables")
                return None
            
            return assessment_data
            
        except Exception as e:
            print(f"Error fetching recent assessment: {e}")
            return None
    
    def get_assessment_by_id(self, assessment_id: str) -> Optional[Dict]:
        """Fetch data from the 7 specified tables for a specific assessment ID"""
        try:
            # Fetch data from the 7 specified tables for this assessment
            assessment_data = {
                'assessment_id': assessment_id,
                'health_wellbeing': None,
                'daily_living': None,
                'risks_safeguarding': None,
                'social_emotional': None,
                'environment_lifestyle': None,
                'advance_preferences': None,
                'optional_areas': None
            }
            
            # Fetch from each of the 7 specified tables
            tables = [
                'health_wellbeing', 'daily_living', 'risks_safeguarding',
                'social_emotional', 'environment_lifestyle', 'advance_preferences', 'optional_areas'
            ]
            
            for table in tables:
                try:
                    response = self.supabase.table(table).select('*').eq('assessment_id', assessment_id).execute()
                    if response.data:
                        assessment_data[table] = response.data[0]
                except Exception as e:
                    print(f"Error fetching from {table}: {e}")
                    assessment_data[table] = None
            
            return assessment_data
            
        except Exception as e:
            print(f"Error fetching assessment {assessment_id}: {e}")
            return None
    
    def save_care_plan(self, assessment_id: str, care_plan: Dict) -> bool:
        """Save the generated care plan to the individual care plan tables"""
        try:
            print(f"🔍 Starting to save care plan for assessment_id: {assessment_id}")
            print(f"📋 Care plan structure: {list(care_plan.keys())}")
            print(f"📄 Full care plan data: {json.dumps(care_plan, indent=2)}")
            
            # Define the mapping between care plan sections and their corresponding tables
            care_plan_tables = {
                'health_wellbeing': 'health_care_plan',
                'daily_living': 'daily_living_care_plan',
                'risks_safeguarding': 'risks_safeguarding_care_plan',
                'social_emotional': 'social_emotional_care_plan',
                'environment_lifestyle': 'environment_lifestyle_care_plan',
                'advance_preferences': 'advance_preferences_care_plan',
                'optional_areas': 'optional_areas_care_plan'
            }
            
            # Get the next review date from the care plan
            next_review_date = care_plan.get('next_review_date', '3 months from generation date')
            print(f"📅 Next review date: {next_review_date}")
            
            # Check if care_plans key exists
            if 'care_plans' not in care_plan:
                print("❌ No 'care_plans' key found in care plan data")
                print(f"Available keys: {list(care_plan.keys())}")
                
                # Try to extract care plans from the raw response if it exists
                if 'raw_planning_result' in care_plan:
                    print("🔍 Attempting to extract care plans from raw planning result...")
                    raw_result = care_plan['raw_planning_result']
                    try:
                        # Try to find JSON in the raw result
                        if "{" in raw_result and "}" in raw_result:
                            start = raw_result.find("{")
                            end = raw_result.rfind("}") + 1
                            json_str = raw_result[start:end]
                            extracted_care_plan = json.loads(json_str)
                            if 'care_plans' in extracted_care_plan:
                                care_plan = extracted_care_plan
                                print("✅ Successfully extracted care plans from raw result")
                            else:
                                print("❌ No care_plans found in extracted JSON")
                                return False
                        else:
                            print("❌ No JSON found in raw planning result")
                            return False
                    except json.JSONDecodeError as e:
                        print(f"❌ Failed to parse JSON from raw result: {e}")
                        return False
                else:
                    return False
            
            # Save each section's care plan to its corresponding table
            print(f"📊 Found {len(care_plan['care_plans'])} care plan sections")
            success_count = 0
            
            for section_name, section_data in care_plan['care_plans'].items():
                print(f"🔍 Processing section: {section_name}")
                print(f"📄 Section data: {json.dumps(section_data, indent=2)}")
                
                if section_name in care_plan_tables:
                    table_name = care_plan_tables[section_name]
                    print(f"📋 Mapping to table: {table_name}")
                    
                    # Prepare the data for this section
                    section_care_plan_data = {
                        'assessment_id': assessment_id,
                        'description': section_data.get('description', ''),
                        'identified_need': section_data.get('identified_need', ''),
                        'planned_outcomes': section_data.get('planned_outcomes', ''),
                        'how_to_achieve_outcomes': section_data.get('how_to_achieve', ''),
                        'level_of_need': section_data.get('level_of_need', ''),
                        'next_review_date': next_review_date
                    }
                    
                    print(f"💾 Saving data for {section_name}: {json.dumps(section_care_plan_data, indent=2)}")
                    
                    # Insert or update the care plan for this section
                    try:
                        # First try to insert, if it fails due to existing record, update instead
                        response = self.supabase.table(table_name).upsert(section_care_plan_data).execute()
                        print(f"✅ Successfully saved care plan for {section_name} to {table_name}")
                        print(f"📊 Response: {response}")
                        success_count += 1
                    except Exception as e:
                        print(f"❌ Error saving care plan for {section_name} to {table_name}: {e}")
                        print(f"🔍 Error details: {type(e).__name__}: {str(e)}")
                        
                        # Try to get more details about the error
                        try:
                            # Check if table exists
                            table_check = self.supabase.table(table_name).select('assessment_id').limit(1).execute()
                            print(f"✅ Table {table_name} exists and is accessible")
                        except Exception as table_error:
                            print(f"❌ Table {table_name} may not exist or be accessible: {table_error}")
                        
                        # Try alternative approach - insert only
                        try:
                            print(f"🔄 Trying insert-only approach for {section_name}...")
                            response = self.supabase.table(table_name).insert(section_care_plan_data).execute()
                            print(f"✅ Successfully inserted care plan for {section_name}")
                            success_count += 1
                        except Exception as insert_error:
                            print(f"❌ Insert also failed for {section_name}: {insert_error}")
                else:
                    print(f"⚠️ No table mapping found for section: {section_name}")
            
            print(f"📊 Care plan save summary: {success_count}/{len(care_plan['care_plans'])} sections saved successfully")
            
            # Return True if at least one section was saved successfully
            return success_count > 0
            
        except Exception as e:
            print(f"❌ Error saving care plan: {e}")
            print(f"🔍 Error type: {type(e).__name__}")
            print(f"🔍 Error details: {str(e)}")
            return False
