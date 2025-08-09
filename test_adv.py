#!/usr/bin/env python3
"""
Enhanced Healthcare Appointment Scheduler MCP Server with Gemini AI Integration

This server provides intelligent healthcare appointment scheduling using:
1. Dynamic database access with real-time synchronization
2. Gemini AI for natural language processing and conversation
3. Smart appointment booking with comprehensive data storage
4. AI-generated patient summaries for doctors
5. Complete appointment management with doctor/clinic details

Usage:
    python healthcare_gemini_mcp_server.py
"""

import sqlite3
import json
import logging
import sys
import os
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import google.generativeai as genai
import dotenv
dotenv.load_dotenv()

# Import MCP components
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.prompts.base import UserMessage, Message

# ------------------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------------------
# Set your Gemini API key here or as environment variable
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "your-gemini-api-key-here")
genai.configure(api_key=GEMINI_API_KEY)

# Database paths
SERVICES_DB_PATH = "healthcare_services.db"
APPOINTMENTS_DB_PATH = "appointments.db"

# ------------------------------------------------------------------------------
# Logging Setup
# ------------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("healthcare_gemini_mcp.log"),
    ]
)
logger = logging.getLogger("healthcare_gemini_mcp")

# ------------------------------------------------------------------------------
# Enhanced Database Manager Class
# ------------------------------------------------------------------------------
class DatabaseManager:
    def __init__(self):
        self.services_conn = None
        self.appointments_conn = None
        self.connect_databases()
        self.ensure_enhanced_schema()
    
    def connect_databases(self):
        """Connect to both databases with proper configuration"""
        try:
            self.services_conn = sqlite3.connect(SERVICES_DB_PATH, check_same_thread=False)
            self.services_conn.row_factory = sqlite3.Row
            
            self.appointments_conn = sqlite3.connect(APPOINTMENTS_DB_PATH, check_same_thread=False)
            self.appointments_conn.row_factory = sqlite3.Row
            
            logger.info(f"Connected to databases: {SERVICES_DB_PATH} and {APPOINTMENTS_DB_PATH}")
        except Exception as e:
            logger.exception(f"Failed to connect to databases: {e}")
            raise
    
    def ensure_enhanced_schema(self):
        """Ensure the appointments database has all required tables with enhanced schema"""
        try:
            # Enhanced appointments table with comprehensive data storage
            self.appointments_conn.execute("""
                CREATE TABLE IF NOT EXISTS enhanced_appointments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    appointment_number TEXT UNIQUE NOT NULL,
                    
                    -- Patient Information
                    patient_id INTEGER,
                    patient_name TEXT NOT NULL,
                    patient_phone TEXT,
                    patient_email TEXT,
                    patient_age INTEGER,
                    patient_gender TEXT,
                    patient_address TEXT,
                    patient_medical_history TEXT,
                    patient_emergency_contact TEXT,
                    
                    -- Doctor Information
                    doctor_id INTEGER NOT NULL,
                    doctor_name TEXT NOT NULL,
                    doctor_specialty TEXT NOT NULL,
                    doctor_phone TEXT,
                    doctor_qualifications TEXT,
                    
                    -- Clinic Information
                    clinic_id INTEGER NOT NULL,
                    clinic_name TEXT NOT NULL,
                    clinic_address TEXT NOT NULL,
                    clinic_phone TEXT,
                    clinic_operating_hours TEXT,
                    
                    -- Service Information
                    service_id INTEGER,
                    service_name TEXT NOT NULL,
                    service_description TEXT,
                    service_department TEXT,
                    service_price DECIMAL(10,2),
                    service_duration_minutes INTEGER,
                    
                    -- Appointment Details
                    appointment_date DATE NOT NULL,
                    appointment_time TIME NOT NULL,
                    appointment_end_time TIME,
                    slot_id INTEGER,
                    
                    -- Patient Complaint & Symptoms
                    patient_complaint TEXT,
                    symptoms_description TEXT,
                    symptoms_duration TEXT,
                    pain_level INTEGER CHECK(pain_level >= 0 AND pain_level <= 10),
                    urgency_level TEXT DEFAULT 'normal',
                    
                    -- AI Generated Summary (200 words for doctor)
                    ai_patient_summary TEXT,
                    ai_recommended_focus_areas TEXT,
                    ai_preliminary_assessment TEXT,
                    ai_suggested_questions TEXT,
                    
                    -- Appointment Management
                    status TEXT DEFAULT 'scheduled',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    booking_source TEXT DEFAULT 'ai_assistant',
                    special_instructions TEXT,
                    follow_up_required BOOLEAN DEFAULT 0,
                    
                    -- Communication Log
                    conversation_summary TEXT,
                    patient_mood_assessment TEXT,
                    booking_interaction_quality TEXT
                )
            """)
            
            # Appointment status history
            self.appointments_conn.execute("""
                CREATE TABLE IF NOT EXISTS appointment_status_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    appointment_id INTEGER REFERENCES enhanced_appointments(id),
                    old_status TEXT,
                    new_status TEXT,
                    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    changed_by TEXT,
                    reason TEXT
                )
            """)
            
            # Enhanced interaction logs
            self.appointments_conn.execute("""
                CREATE TABLE IF NOT EXISTS enhanced_interaction_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    appointment_id INTEGER REFERENCES enhanced_appointments(id),
                    user_input TEXT NOT NULL,
                    ai_response TEXT NOT NULL,
                    conversation_step TEXT,
                    intent_detected TEXT,
                    entities_extracted TEXT,
                    confidence_score REAL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processing_time_ms INTEGER
                )
            """)
            
            self.appointments_conn.commit()
            logger.info("Enhanced database schema ensured successfully")
            
        except Exception as e:
            logger.exception(f"Error ensuring enhanced schema: {e}")
            raise
    
    def get_database_schema(self):
        """Dynamically get database schema for AI context"""
        try:
            schema_info = {
                "services_db": {},
                "appointments_db": {}
            }
            
            # Get services database schema
            cursor = self.services_conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            for table_name in cursor.fetchall():
                table = table_name[0]
                cursor = self.services_conn.execute(f"PRAGMA table_info({table})")
                schema_info["services_db"][table] = [dict(row) for row in cursor.fetchall()]
            
            # Get appointments database schema
            cursor = self.appointments_conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            for table_name in cursor.fetchall():
                table = table_name[0]
                cursor = self.appointments_conn.execute(f"PRAGMA table_info({table})")
                schema_info["appointments_db"][table] = [dict(row) for row in cursor.fetchall()]
            
            return schema_info
        except Exception as e:
            logger.exception(f"Error getting database schema: {e}")
            return {}
    
    def execute_dynamic_query(self, query: str, params: tuple = (), db: str = "services"):
        """Execute dynamic queries safely"""
        try:
            conn = self.services_conn if db == "services" else self.appointments_conn
            cursor = conn.execute(query, params)
            if query.strip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')):
                conn.commit()
                return cursor.lastrowid if query.strip().upper().startswith('INSERT') else cursor.rowcount
            else:
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.exception(f"Error executing query: {e}")
            return None
    
    def generate_appointment_number(self):
        """Generate unique appointment number"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        return f"APT-{timestamp}"

# Initialize database manager
db_manager = DatabaseManager()

# ------------------------------------------------------------------------------
# Enhanced Gemini AI Manager Class
# ------------------------------------------------------------------------------
class GeminiAIManager:
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        self.conversation_history = {}
        self.system_context = self.build_dynamic_context()
    
    def build_dynamic_context(self):
        """Build dynamic system context based on current database state"""
        try:
            # Get current database schema
            schema = db_manager.get_database_schema()
            
            # Get current services
            services = db_manager.execute_dynamic_query("""
                SELECT s.id, s.name, s.description, s.duration_minutes, s.price, s.department,
                       c.name as clinic_name, c.address, c.operating_hours
                FROM services s
                JOIN clinics c ON s.clinic_id = c.id
                ORDER BY s.department, s.name
            """)
            
            # Get current doctors
            doctors = db_manager.execute_dynamic_query("""
                SELECT d.id, d.name, d.specialty, d.phone, d.working_hours_display,
                       c.name as clinic_name, d.available_days
                FROM doctors d
                JOIN clinics c ON d.clinic_id = c.id
                ORDER BY d.specialty, d.name
            """)
            
            # Get current clinics
            clinics = db_manager.execute_dynamic_query("""
                SELECT id, name, address, city, state, phone, operating_hours
                FROM clinics
                ORDER BY name
            """)
            
            services_text = "\n".join([
                f"• {s['name']} - {s['department']} - ₹{s['price']} ({s['duration_minutes']} mins)\n"
                f"  Description: {s['description']}\n"
                f"  Available at: {s['clinic_name']} - {s['address']}"
                for s in services
            ])
            
            doctors_text = "\n".join([
                f"• Dr. {d['name']} - {d['specialty']}\n"
                f"  Working Hours: {d['working_hours_display']}\n"
                f"  Available Days: {d['available_days']}\n"
                f"  Contact: {d['phone']} | Clinic: {d['clinic_name']}"
                for d in doctors
            ])
            
            clinics_text = "\n".join([
                f"• {c['name']}\n"
                f"  Address: {c['address']}, {c['city']}, {c['state']}\n"
                f"  Phone: {c['phone']} | Hours: {c['operating_hours']}"
                for c in clinics
            ])
            
            context = f"""
You are HEALTHBOT AI, an intelligent healthcare appointment scheduling assistant for multiple clinics in Karimnagar, Telangana, India.

🏥 CURRENT HEALTHCARE FACILITIES:
{clinics_text}

👩‍⚕️ AVAILABLE DOCTORS:
{doctors_text}

🩺 AVAILABLE SERVICES:
{services_text}

🎯 YOUR PRIMARY RESPONSIBILITIES:
1. INTELLIGENT CONVERSATION: Engage naturally, understand patient concerns, ask clarifying questions
2. SYMPTOM ANALYSIS: Analyze symptoms and recommend appropriate healthcare services
3. APPOINTMENT BOOKING: Guide patients through complete booking process with comprehensive data collection
4. DYNAMIC ADAPTATION: Always query database for real-time information
5. PATIENT CARE: Show empathy, provide reassurance, maintain professionalism
6. DATA COLLECTION: Gather complete patient information for comprehensive appointment records

🔄 ENHANCED CONVERSATION FLOW:
1. GREETING: Warm, professional welcome
2. NEEDS ASSESSMENT: Understand health concerns or service needs
3. SYMPTOM ANALYSIS: If health issue, analyze symptoms intelligently
4. DETAILED INQUIRY: Ask about symptom duration, pain levels, medical history
5. SERVICE RECOMMENDATION: Suggest appropriate services/doctors based on analysis
6. AVAILABILITY CHECK: Show real-time available slots
7. PATIENT INFORMATION: Collect comprehensive details (name, phone, email, age, gender, address, emergency contact)
8. APPOINTMENT CONFIRMATION: Complete booking with all details
9. AI SUMMARY GENERATION: Create detailed patient summary for doctor
10. FOLLOW-UP: Provide confirmation and next steps

⚠️ CRITICAL GUIDELINES:
- NEVER provide medical diagnosis - only suggest appropriate healthcare services
- For urgent symptoms (chest pain, severe bleeding, difficulty breathing), immediately recommend emergency care
- Always verify information with database queries
- Be empathetic about health concerns
- Collect comprehensive patient information for complete records
- Generate detailed AI summaries for doctors
- Ensure all appointment details are confirmed before booking
- Maintain patient privacy and confidentiality
- Use Indian context (₹ for prices, Indian names, local references)

🗣️ COMMUNICATION STYLE:
- Warm, friendly, and professional
- Use empathetic language for health concerns
- Clear explanations of medical services
- Patient and understanding with questions
- Culturally appropriate for Indian patients
- Thorough in data collection

💡 ENHANCED SMART FEATURES:
- Analyze conversation context to understand patient needs
- Remember information from current conversation
- Suggest alternatives when preferred slots unavailable
- Provide estimated costs and time requirements
- Explain what to expect during appointments
- Generate comprehensive 200-word patient summaries for doctors
- Assess patient mood and interaction quality
- Recommend focus areas for doctors
- Create preliminary assessments based on symptoms

🔍 DATA COLLECTION PRIORITIES:
- Complete patient demographics
- Detailed symptom description with duration and severity
- Medical history and current medications
- Pain levels (0-10 scale)
- Urgency assessment
- Patient's primary concerns and expectations
- Emergency contact information

Always start conversations with a warm greeting and ask how you can help with their healthcare needs today.
"""
            return context
            
        except Exception as e:
            logger.exception(f"Error building dynamic context: {e}")
            return "You are a healthcare appointment scheduling assistant."
    
    async def generate_patient_summary(self, patient_data: dict, conversation_history: list) -> dict:
        """Generate comprehensive AI patient summary for doctors (200 words)"""
        try:
            # Build summary prompt
            conversation_text = "\n".join(conversation_history[-20:])  # Last 20 messages
            
            summary_prompt = f"""
Generate a comprehensive 200-word patient summary for the attending doctor based on the appointment booking conversation.

PATIENT INFORMATION:
- Name: {patient_data.get('name', 'N/A')}
- Age: {patient_data.get('age', 'N/A')}
- Gender: {patient_data.get('gender', 'N/A')}
- Phone: {patient_data.get('phone', 'N/A')}
- Service: {patient_data.get('service_name', 'N/A')}
- Complaint: {patient_data.get('complaint', 'N/A')}
- Symptoms: {patient_data.get('symptoms', 'N/A')}
- Pain Level: {patient_data.get('pain_level', 'N/A')}/10
- Urgency: {patient_data.get('urgency', 'normal')}
- Medical History: {patient_data.get('medical_history', 'None reported')}

CONVERSATION EXCERPT:
{conversation_text}

Generate exactly 200 words covering:
1. Patient's primary concern and chief complaint
2. Symptom details, duration, and severity
3. Patient's emotional state and communication style
4. Relevant medical history
5. Recommended focus areas for examination
6. Any red flags or urgent concerns
7. Patient expectations and concerns

Format as a professional medical summary for doctor review.
"""

            # Generate AI summary
            response = await asyncio.get_event_loop().run_in_executor(
                None, self.model.generate_content, summary_prompt
            )
            
            main_summary = response.text[:1000]  # Ensure reasonable length
            
            # Generate additional AI insights
            insights_prompt = f"""
Based on the patient information and conversation, provide:

1. RECOMMENDED FOCUS AREAS (comma-separated list):
2. PRELIMINARY ASSESSMENT (one sentence):
3. SUGGESTED QUESTIONS FOR DOCTOR (3-4 questions):

Patient Data: {json.dumps(patient_data, indent=2)}
"""
            
            insights_response = await asyncio.get_event_loop().run_in_executor(
                None, self.model.generate_content, insights_prompt
            )
            
            insights_text = insights_response.text
            
            # Parse insights
            focus_areas = "General examination, symptom assessment"
            preliminary_assessment = "Patient requires thorough examination based on reported symptoms."
            suggested_questions = "1. When did symptoms first appear? 2. Any triggers? 3. Previous similar episodes? 4. Current medications?"
            
            try:
                lines = insights_text.split('\n')
                for line in lines:
                    if 'FOCUS AREAS' in line.upper():
                        focus_areas = line.split(':', 1)[1].strip() if ':' in line else focus_areas
                    elif 'PRELIMINARY' in line.upper():
                        preliminary_assessment = line.split(':', 1)[1].strip() if ':' in line else preliminary_assessment
                    elif 'QUESTIONS' in line.upper():
                        remaining_lines = lines[lines.index(line):]
                        suggested_questions = '\n'.join(remaining_lines).replace('SUGGESTED QUESTIONS FOR DOCTOR:', '').strip()
            except:
                pass
            
            return {
                'ai_patient_summary': main_summary,
                'ai_recommended_focus_areas': focus_areas,
                'ai_preliminary_assessment': preliminary_assessment,
                'ai_suggested_questions': suggested_questions
            }
            
        except Exception as e:
            logger.exception(f"Error generating patient summary: {e}")
            return {
                'ai_patient_summary': f"Patient {patient_data.get('name', 'Unknown')} scheduled for {patient_data.get('service_name', 'consultation')}. Complaint: {patient_data.get('complaint', 'General consultation')}. Please conduct thorough examination as per standard protocol.",
                'ai_recommended_focus_areas': "General examination, symptom assessment",
                'ai_preliminary_assessment': "Standard consultation required based on patient request.",
                'ai_suggested_questions': "1. Please describe your symptoms in detail. 2. When did this start? 3. Any previous medical history? 4. Current medications?"
            }
    
    async def generate_response(self, user_message: str, session_id: str = "default", context_data: dict = None):
        """Generate AI response using Gemini with conversation history"""
        try:
            # Initialize conversation history for new sessions
            if session_id not in self.conversation_history:
                self.conversation_history[session_id] = []
            
            # Add current database context if provided
            enhanced_context = self.system_context
            if context_data:
                enhanced_context += f"\n\nCURRENT DATABASE CONTEXT:\n{json.dumps(context_data, indent=2)}"
            
            # Build conversation prompt
            conversation_prompt = f"{enhanced_context}\n\n"
            
            # Add conversation history
            for msg in self.conversation_history[session_id][-10:]:  # Keep last 10 messages
                conversation_prompt += f"{msg}\n"
            
            conversation_prompt += f"Patient: {user_message}\nHealthBot AI: "
            
            # Generate response
            start_time = datetime.now()
            response = await asyncio.get_event_loop().run_in_executor(
                None, self.model.generate_content, conversation_prompt
            )
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            ai_response = response.text
            
            # Update conversation history
            self.conversation_history[session_id].append(f"Patient: {user_message}")
            self.conversation_history[session_id].append(f"HealthBot AI: {ai_response}")
            
            # Enhanced logging with analysis
            intent_detected = self.detect_intent(user_message)
            entities = self.extract_entities(user_message)
            confidence = 0.85  # Placeholder for confidence scoring
            
            # Log interaction
            db_manager.execute_dynamic_query("""
                INSERT INTO enhanced_interaction_logs 
                (session_id, user_input, ai_response, conversation_step, intent_detected, 
                 entities_extracted, confidence_score, timestamp, processing_time_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (session_id, user_message, ai_response, "conversation", intent_detected,
                  json.dumps(entities), confidence, datetime.now().isoformat(), int(processing_time)), "appointments")
            
            return ai_response
            
        except Exception as e:
            logger.exception(f"Error generating AI response: {e}")
            return "I apologize, but I'm having trouble processing your request right now. Please try again or contact our clinic directly."
    
    def detect_intent(self, user_message: str) -> str:
        """Simple intent detection"""
        user_lower = user_message.lower()
        if any(word in user_lower for word in ['book', 'appointment', 'schedule']):
            return 'book_appointment'
        elif any(word in user_lower for word in ['pain', 'hurt', 'ache', 'sick']):
            return 'symptom_inquiry'
        elif any(word in user_lower for word in ['doctor', 'specialist']):
            return 'doctor_inquiry'
        elif any(word in user_lower for word in ['cost', 'price', 'fee']):
            return 'pricing_inquiry'
        else:
            return 'general_inquiry'
    
    def extract_entities(self, user_message: str) -> dict:
        """Simple entity extraction"""
        entities = {}
        user_lower = user_message.lower()
        
        # Extract pain level
        import re
        pain_match = re.search(r'(\d+)\s*(?:out of|/)\s*10|pain.*?(\d+)', user_lower)
        if pain_match:
            entities['pain_level'] = pain_match.group(1) or pain_match.group(2)
        
        # Extract time references
        if any(word in user_lower for word in ['today', 'tomorrow', 'morning', 'evening', 'afternoon']):
            entities['time_preference'] = [word for word in ['today', 'tomorrow', 'morning', 'evening', 'afternoon'] if word in user_lower]
        
        return entities

# Initialize AI manager
ai_manager = GeminiAIManager()

# ------------------------------------------------------------------------------
# MCP Server Initialization
# ------------------------------------------------------------------------------
mcp = FastMCP("Enhanced Healthcare Gemini AI Assistant")

# ------------------------------------------------------------------------------
# Enhanced Dynamic Database Resources
# ------------------------------------------------------------------------------

@mcp.resource("healthcare://services/all")
def get_all_services() -> str:
    """Get all available healthcare services with real-time data"""
    logger.info("Fetching all healthcare services")
    try:
        services = db_manager.execute_dynamic_query("""
            SELECT s.*, c.name as clinic_name, c.address, c.phone as clinic_phone
            FROM services s
            JOIN clinics c ON s.clinic_id = c.id
            ORDER BY s.department, s.name
        """)
        return json.dumps(services, indent=2)
    except Exception as e:
        logger.exception(f"Error retrieving services: {e}")
        return json.dumps({"error": str(e)})

@mcp.resource("healthcare://doctors/available")
def get_available_doctors() -> str:
    """Get all doctors with their current availability"""
    logger.info("Fetching available doctors")
    try:
        doctors = db_manager.execute_dynamic_query("""
            SELECT d.*, c.name as clinic_name, c.address, c.operating_hours
            FROM doctors d
            JOIN clinics c ON d.clinic_id = c.id
            ORDER BY d.specialty, d.name
        """)
        
        # Add current time slot availability
        for doctor in doctors:
            today = datetime.now().strftime('%w')  # Get day of week
            slots = db_manager.execute_dynamic_query("""
                SELECT COUNT(*) as available_slots
                FROM time_slots
                WHERE doctor_id = ? AND day_of_week = ? AND is_available = 1
            """, (doctor['id'], today))
            doctor['available_slots_today'] = slots[0]['available_slots'] if slots else 0
        
        return json.dumps(doctors, indent=2)
    except Exception as e:
        logger.exception(f"Error retrieving doctors: {e}")
        return json.dumps({"error": str(e)})

@mcp.resource("healthcare://appointments/recent")
def get_recent_appointments() -> str:
    """Get recent appointments with comprehensive details"""
    logger.info("Fetching recent appointments")
    try:
        appointments = db_manager.execute_dynamic_query("""
            SELECT appointment_number, patient_name, doctor_name, clinic_name, 
                   service_name, appointment_date, appointment_time, status,
                   ai_patient_summary, created_at
            FROM enhanced_appointments 
            ORDER BY created_at DESC 
            LIMIT 10
        """, (), "appointments")
        return json.dumps(appointments, indent=2)
    except Exception as e:
        logger.exception(f"Error retrieving recent appointments: {e}")
        return json.dumps({"error": str(e)})

@mcp.resource("healthcare://clinics/all")
def get_all_clinics() -> str:
    """Get all clinic information"""
    logger.info("Fetching all clinics")
    try:
        clinics = db_manager.execute_dynamic_query("""
            SELECT c.*,
                   COUNT(DISTINCT d.id) as doctor_count,
                   COUNT(DISTINCT s.id) as service_count
            FROM clinics c
            LEFT JOIN doctors d ON c.id = d.clinic_id
            LEFT JOIN services s ON c.id = s.clinic_id
            GROUP BY c.id
            ORDER BY c.name
        """)
        return json.dumps(clinics, indent=2)
    except Exception as e:
        logger.exception(f"Error retrieving clinics: {e}")
        return json.dumps({"error": str(e)})

# ------------------------------------------------------------------------------
# Enhanced Intelligent MCP Tools
# ------------------------------------------------------------------------------

@mcp.tool()
async def chat_with_ai(user_message: str, session_id: str = "default") -> str:
    """Main chat interface with Gemini AI"""
    logger.info(f"Processing chat message for session {session_id}")
    try:
        # Get fresh database context
        context_data = {
            "available_services": db_manager.execute_dynamic_query("SELECT id, name, department FROM services ORDER BY name"),
            "available_doctors": db_manager.execute_dynamic_query("SELECT id, name, specialty FROM doctors ORDER BY name"),
            "clinics": db_manager.execute_dynamic_query("SELECT id, name, phone FROM clinics ORDER BY name"),
            "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "day_of_week": datetime.now().strftime("%A")
        }
        
        # Generate AI response
        ai_response = await ai_manager.generate_response(user_message, session_id, context_data)
        
        return json.dumps({
            "success": True,
            "response": ai_response,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.exception(f"Error in chat_with_ai: {e}")
        return json.dumps({
            "success": False,
            "error": str(e),
            "fallback_response": "I'm sorry, I'm having technical difficulties. Please try again or contact our clinic directly."
        })

@mcp.tool()
def search_services_intelligent(query: str) -> str:
    """Intelligent service search with symptom matching"""
    logger.info(f"Intelligent search for: {query}")
    try:
        # Search in name, description, and department
        services = db_manager.execute_dynamic_query("""
            SELECT s.*, c.name as clinic_name, c.address, c.phone as clinic_phone,
                   d.name as doctor_name, d.specialty, d.working_hours_display
            FROM services s
            JOIN clinics c ON s.clinic_id = c.id
            LEFT JOIN doctor_services ds ON s.id = ds.service_id
            LEFT JOIN doctors d ON ds.doctor_id = d.id
            WHERE s.name LIKE ? OR s.description LIKE ? OR s.department LIKE ?
            ORDER BY s.department, s.name
        """, (f"%{query}%", f"%{query}%", f"%{query}%"))
        
        return json.dumps({
            "query": query,
            "results": services,
            "count": len(services)
        }, indent=2)
        
    except Exception as e:
        logger.exception(f"Error in intelligent search: {e}")
        return json.dumps({"error": str(e)})

@mcp.tool()
def get_real_time_availability(doctor_id: int = None, service_id: int = None, day_preference: str = None) -> str:
    """Get real-time availability based on current database state"""
    logger.info(f"Getting availability - doctor: {doctor_id}, service: {service_id}, day: {day_preference}")
    try:
        query_parts = ["SELECT DISTINCT ts.*, d.name as doctor_name, d.specialty, c.name as clinic_name"]
        from_parts = ["FROM time_slots ts"]
        join_parts = ["JOIN doctors d ON ts.doctor_id = d.id", "JOIN clinics c ON d.clinic_id = c.id"]
        where_parts = ["ts.is_available = 1"]
        params = []
        
        if doctor_id:
            where_parts.append("ts.doctor_id = ?")
            params.append(doctor_id)
        
        if service_id:
            join_parts.append("JOIN doctor_services ds ON d.id = ds.doctor_id")
            where_parts.append("ds.service_id = ?")
            params.append(service_id)
        
        if day_preference:
            day_mapping = {"monday": 1, "tuesday": 2, "wednesday": 3, "thursday": 4, "friday": 5, "saturday": 6, "sunday": 7}
            day_num = day_mapping.get(day_preference.lower())
            if day_num:
                where_parts.append("ts.day_of_week = ?")
                params.append(day_num)
        
        query = f"{' '.join(query_parts)} {' '.join(from_parts)} {' '.join(join_parts)} WHERE {' AND '.join(where_parts)} ORDER BY ts.day_of_week, ts.start_time"
        
        availability = db_manager.execute_dynamic_query(query, tuple(params))
        
        return json.dumps({
            "availability": availability,
            "total_slots": len(availability),
            "query_params": {"doctor_id": doctor_id, "service_id": service_id, "day_preference": day_preference}
        }, indent=2)
        
    except Exception as e:
        logger.exception(f"Error getting availability: {e}")
        return json.dumps({"error": str(e)})

@mcp.tool()
def create_patient_intelligent(patient_data: str) -> str:
    """Create patient with intelligent data parsing"""
    logger.info("Creating patient with intelligent parsing")
    try:
        # Parse JSON patient data
        data = json.loads(patient_data) if isinstance(patient_data, str) else patient_data
        
        # Insert patient if patients table exists
        try:
            result = db_manager.execute_dynamic_query("""
                INSERT INTO patients (name, phone, email, age, gender, address, medical_history, emergency_contact)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data.get('name'),
                data.get('phone'),
                data.get('email'),
                data.get('age'),
                data.get('gender'),
                data.get('address'),
                data.get('medical_history'),
                data.get('emergency_contact')
            ), "appointments")
            
            # Get the created patient
            patient = db_manager.execute_dynamic_query("""
                SELECT * FROM patients WHERE rowid = last_insert_rowid()
            """, (), "appointments")
            
            return json.dumps({
                "success": True,
                "patient": patient[0] if patient else {},
                "patient_id": result,
                "message": f"Patient {data.get('name')} created successfully"
            })
        except:
            # If patients table doesn't exist, return patient data for direct appointment creation
            return json.dumps({
                "success": True,
                "patient_data": data,
                "patient_id": None,
                "message": f"Patient data prepared for appointment creation"
            })
        
    except Exception as e:
        logger.exception(f"Error creating patient: {e}")
        return json.dumps({"success": False, "error": str(e)})

@mcp.tool()
async def book_appointment_comprehensive(booking_data: str, session_id: str = "default") -> str:
    """Enhanced appointment booking with comprehensive data storage and AI summary"""
    logger.info("Processing comprehensive appointment booking")
    try:
        data = json.loads(booking_data) if isinstance(booking_data, str) else booking_data
        
        # Extract booking details
        patient_data = data.get('patient_data', {})
        doctor_id = data.get('doctor_id')
        service_id = data.get('service_id')
        time_slot_id = data.get('time_slot_id')
        appointment_date = data.get('appointment_date', datetime.now().strftime('%Y-%m-%d'))
        
        # Get comprehensive doctor information
        doctor_info = db_manager.execute_dynamic_query("""
            SELECT d.*, c.name as clinic_name, c.address as clinic_address, 
                   c.phone as clinic_phone, c.operating_hours
            FROM doctors d
            JOIN clinics c ON d.clinic_id = c.id
            WHERE d.id = ?
        """, (doctor_id,))
        
        if not doctor_info:
            return json.dumps({"success": False, "error": "Doctor not found"})
        
        doctor = doctor_info[0]
        
        # Get service information
        service_info = db_manager.execute_dynamic_query("""
            SELECT * FROM services WHERE id = ?
        """, (service_id,))
        
        if not service_info:
            return json.dumps({"success": False, "error": "Service not found"})
        
        service = service_info[0]
        
        # Validate and get time slot information
        slot_check = db_manager.execute_dynamic_query("""
            SELECT * FROM time_slots WHERE id = ? AND doctor_id = ? AND is_available = 1
        """, (time_slot_id, doctor_id))
        
        if not slot_check:
            return json.dumps({"success": False, "error": "Time slot not available"})
        
        slot_info = slot_check[0]
        
        # Generate unique appointment number
        appointment_number = db_manager.generate_appointment_number()
        
        # Calculate end time
        duration = service.get('duration_minutes', 30)
        start_time = datetime.strptime(slot_info['start_time'], '%H:%M:%S').time()
        end_time = (datetime.combine(datetime.today(), start_time) + timedelta(minutes=duration)).time()
        
        # Generate AI patient summary
        conversation_history = ai_manager.conversation_history.get(session_id, [])
        
        # Prepare comprehensive patient data for AI summary
        comprehensive_patient_data = {
            **patient_data,
            'service_name': service['name'],
            'doctor_name': doctor['name'],
            'doctor_specialty': doctor['specialty'],
            'appointment_date': appointment_date,
            'appointment_time': slot_info['start_time'],
            'complaint': data.get('complaint', ''),
            'symptoms': data.get('symptoms', ''),
            'pain_level': data.get('pain_level'),
            'urgency': data.get('urgency', 'normal'),
            'symptoms_duration': data.get('symptoms_duration', ''),
            'medical_history': patient_data.get('medical_history', 'None reported')
        }
        
        # Generate AI summary
        ai_summary_data = await ai_manager.generate_patient_summary(
            comprehensive_patient_data, 
            conversation_history
        )
        
        # Assess patient mood and interaction quality
        patient_mood = "cooperative" if len(conversation_history) > 4 else "brief"
        interaction_quality = "excellent" if len(conversation_history) > 10 else "good"
        
        # Create comprehensive appointment record
        appointment_id = db_manager.execute_dynamic_query("""
            INSERT INTO enhanced_appointments (
                appointment_number, patient_name, patient_phone, patient_email, patient_age, 
                patient_gender, patient_address, patient_medical_history, patient_emergency_contact,
                doctor_id, doctor_name, doctor_specialty, doctor_phone, doctor_qualifications,
                clinic_id, clinic_name, clinic_address, clinic_phone, clinic_operating_hours,
                service_id, service_name, service_description, service_department, 
                service_price, service_duration_minutes,
                appointment_date, appointment_time, appointment_end_time, slot_id,
                patient_complaint, symptoms_description, symptoms_duration, pain_level, urgency_level,
                ai_patient_summary, ai_recommended_focus_areas, ai_preliminary_assessment, ai_suggested_questions,
                status, booking_source, special_instructions, conversation_summary,
                patient_mood_assessment, booking_interaction_quality
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            appointment_number,
            patient_data.get('name', ''), patient_data.get('phone', ''), patient_data.get('email', ''),
            patient_data.get('age'), patient_data.get('gender', ''), patient_data.get('address', ''),
            patient_data.get('medical_history', ''), patient_data.get('emergency_contact', ''),
            doctor_id, doctor['name'], doctor['specialty'], doctor.get('phone', ''), doctor.get('qualifications', ''),
            doctor['clinic_id'], doctor['clinic_name'], doctor['clinic_address'], 
            doctor['clinic_phone'], doctor['operating_hours'],
            service_id, service['name'], service.get('description', ''), service.get('department', ''),
            service.get('price', 0), duration,
            appointment_date, slot_info['start_time'], end_time.strftime('%H:%M:%S'), time_slot_id,
            data.get('complaint', ''), data.get('symptoms', ''), data.get('symptoms_duration', ''),
            data.get('pain_level'), data.get('urgency', 'normal'),
            ai_summary_data['ai_patient_summary'], ai_summary_data['ai_recommended_focus_areas'],
            ai_summary_data['ai_preliminary_assessment'], ai_summary_data['ai_suggested_questions'],
            'scheduled', 'ai_assistant', data.get('special_instructions', ''),
            f"Conversation with {len(conversation_history)} exchanges, patient was {patient_mood}",
            patient_mood, interaction_quality
        ), "appointments")
        
        # Mark time slot as unavailable
        db_manager.execute_dynamic_query("""
            UPDATE time_slots SET is_available = 0 WHERE id = ?
        """, (time_slot_id,))
        
        # Log appointment status
        db_manager.execute_dynamic_query("""
            INSERT INTO appointment_status_history (appointment_id, old_status, new_status, changed_by, reason)
            VALUES (?, NULL, 'scheduled', 'ai_assistant', 'Initial booking')
        """, (appointment_id,), "appointments")
        
        # Update interaction log with appointment ID
        db_manager.execute_dynamic_query("""
            UPDATE enhanced_interaction_logs 
            SET appointment_id = ? 
            WHERE session_id = ? AND appointment_id IS NULL
        """, (appointment_id, session_id), "appointments")
        
        # Prepare comprehensive response
        appointment_details = {
            "appointment_number": appointment_number,
            "appointment_id": appointment_id,
            "patient_name": patient_data.get('name', ''),
            "doctor_name": doctor['name'],
            "doctor_specialty": doctor['specialty'],
            "service_name": service['name'],
            "clinic_name": doctor['clinic_name'],
            "clinic_address": doctor['clinic_address'],
            "clinic_phone": doctor['clinic_phone'],
            "appointment_date": appointment_date,
            "appointment_time": slot_info['start_time'],
            "appointment_end_time": end_time.strftime('%H:%M:%S'),
            "duration_minutes": duration,
            "service_price": f"₹{service.get('price', 0)}",
            "ai_summary_generated": True,
            "urgency_level": data.get('urgency', 'normal'),
            "status": "scheduled"
        }
        
        return json.dumps({
            "success": True,
            "appointment_details": appointment_details,
            "ai_summary": {
                "patient_summary": ai_summary_data['ai_patient_summary'][:200] + "..." if len(ai_summary_data['ai_patient_summary']) > 200 else ai_summary_data['ai_patient_summary'],
                "focus_areas": ai_summary_data['ai_recommended_focus_areas'],
                "preliminary_assessment": ai_summary_data['ai_preliminary_assessment']
            },
            "message": f"✅ Appointment successfully booked!\n\n📋 Appointment Details:\n• Number: {appointment_number}\n• Patient: {patient_data.get('name', '')}\n• Doctor: Dr. {doctor['name']} ({doctor['specialty']})\n• Service: {service['name']}\n• Date & Time: {appointment_date} at {slot_info['start_time']}\n• Location: {doctor['clinic_name']}\n• Duration: {duration} minutes\n• Cost: ₹{service.get('price', 0)}\n\n🤖 AI Summary has been generated for the doctor's review.\n\n📞 For any changes, please call {doctor['clinic_phone']}"
        })
        
    except Exception as e:
        logger.exception(f"Error booking comprehensive appointment: {e}")
        return json.dumps({"success": False, "error": str(e)})

@mcp.tool()
def get_appointment_details(appointment_number: str = None, appointment_id: int = None) -> str:
    """Get detailed appointment information including AI summary"""
    logger.info(f"Getting appointment details for {appointment_number or appointment_id}")
    try:
        where_clause = "appointment_number = ?" if appointment_number else "id = ?"
        param = appointment_number or appointment_id
        
        appointment = db_manager.execute_dynamic_query("""
            SELECT * FROM enhanced_appointments WHERE {} LIMIT 1
        """.format(where_clause), (param,), "appointments")
        
        if not appointment:
            return json.dumps({"success": False, "error": "Appointment not found"})
        
        apt = appointment[0]
        
        # Get appointment status history
        status_history = db_manager.execute_dynamic_query("""
            SELECT * FROM appointment_status_history 
            WHERE appointment_id = ? 
            ORDER BY changed_at DESC
        """, (apt['id'],), "appointments")
        
        return json.dumps({
            "success": True,
            "appointment": dict(apt),
            "status_history": status_history,
            "ai_summary": {
                "patient_summary": apt.get('ai_patient_summary', ''),
                "focus_areas": apt.get('ai_recommended_focus_areas', ''),
                "preliminary_assessment": apt.get('ai_preliminary_assessment', ''),
                "suggested_questions": apt.get('ai_suggested_questions', '')
            }
        }, indent=2)
        
    except Exception as e:
        logger.exception(f"Error getting appointment details: {e}")
        return json.dumps({"success": False, "error": str(e)})

@mcp.tool()
def update_appointment_status(appointment_id: int, new_status: str, reason: str = "", changed_by: str = "system") -> str:
    """Update appointment status with history tracking"""
    logger.info(f"Updating appointment {appointment_id} status to {new_status}")
    try:
        # Get current status
        current = db_manager.execute_dynamic_query("""
            SELECT status FROM enhanced_appointments WHERE id = ?
        """, (appointment_id,), "appointments")
        
        if not current:
            return json.dumps({"success": False, "error": "Appointment not found"})
        
        old_status = current[0]['status']
        
        # Update appointment status
        db_manager.execute_dynamic_query("""
            UPDATE enhanced_appointments 
            SET status = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        """, (new_status, appointment_id), "appointments")
        
        # Log status change
        db_manager.execute_dynamic_query("""
            INSERT INTO appointment_status_history 
            (appointment_id, old_status, new_status, changed_by, reason)
            VALUES (?, ?, ?, ?, ?)
        """, (appointment_id, old_status, new_status, changed_by, reason), "appointments")
        
        return json.dumps({
            "success": True,
            "appointment_id": appointment_id,
            "old_status": old_status,
            "new_status": new_status,
            "message": f"Appointment status updated from '{old_status}' to '{new_status}'"
        })
        
    except Exception as e:
        logger.exception(f"Error updating appointment status: {e}")
        return json.dumps({"success": False, "error": str(e)})

@mcp.tool()
def get_doctor_appointment_summary(doctor_id: int, date: str = None) -> str:
    """Get comprehensive appointment summary for doctors with AI insights"""
    logger.info(f"Getting appointment summary for doctor {doctor_id}")
    try:
        date_filter = date or datetime.now().strftime('%Y-%m-%d')
        
        appointments = db_manager.execute_dynamic_query("""
            SELECT appointment_number, patient_name, patient_age, patient_phone,
                   service_name, appointment_time, appointment_end_time, urgency_level,
                   patient_complaint, symptoms_description, pain_level,
                   ai_patient_summary, ai_recommended_focus_areas, ai_preliminary_assessment,
                   ai_suggested_questions, status, patient_mood_assessment
            FROM enhanced_appointments 
            WHERE doctor_id = ? AND appointment_date = ?
            ORDER BY appointment_time
        """, (doctor_id, date_filter), "appointments")
        
        # Get doctor information
        doctor = db_manager.execute_dynamic_query("""
            SELECT name, specialty FROM doctors WHERE id = ?
        """, (doctor_id,))
        
        return json.dumps({
            "success": True,
            "doctor": doctor[0] if doctor else {},
            "date": date_filter,
            "appointments": appointments,
            "total_appointments": len(appointments),
            "urgent_cases": len([apt for apt in appointments if apt.get('urgency_level') == 'urgent']),
            "summary": f"Dr. {doctor[0]['name']} has {len(appointments)} appointments on {date_filter}"
        }, indent=2)
        
    except Exception as e:
        logger.exception(f"Error getting doctor appointment summary: {e}")
        return json.dumps({"success": False, "error": str(e)})

# ------------------------------------------------------------------------------
# Enhanced MCP Prompts
# ------------------------------------------------------------------------------

@mcp.prompt()
def healthcare_system_prompt() -> list[Message]:
    """Comprehensive system prompt with dynamic database context"""
    try:
        # Refresh context with current database state
        ai_manager.system_context = ai_manager.build_dynamic_context()
        return [UserMessage(ai_manager.system_context)]
    except Exception as e:
        logger.exception(f"Error generating system prompt: {e}")
        return [UserMessage("You are a healthcare appointment scheduling assistant.")]

@mcp.prompt()
def analyze_patient_symptoms(symptoms: str, patient_info: str = "") -> list[Message]:
    """Advanced symptom analysis prompt"""
    current_services = db_manager.execute_dynamic_query("""
        SELECT name, description, department FROM services ORDER BY department
    """)
    
    services_list = "\n".join([f"- {s['name']} ({s['department']}): {s['description']}" for s in current_services])
    
    prompt = f"""
    PATIENT SYMPTOM ANALYSIS REQUEST
    
    Patient Information: {patient_info}
    Reported Symptoms: {symptoms}
    
    Available Healthcare Services:
    {services_list}
    
    Please analyze the symptoms and provide:
    1. Most likely relevant healthcare services
    2. Urgency assessment (routine/normal/urgent/emergency)
    3. Recommended medical specialty
    4. Key symptoms to track
    5. Any red flags requiring immediate attention
    6. Suggested questions to ask the patient
    
    Format your response in a structured, actionable way for appointment scheduling.
    """
    
    return [UserMessage(prompt)]

@mcp.prompt()
def generate_appointment_confirmation(appointment_data: str) -> list[Message]:
    """Generate professional appointment confirmation message"""
    prompt = f"""
    Generate a professional, warm appointment confirmation message for the patient based on this appointment data:
    
    {appointment_data}
    
    Include:
    1. Warm greeting and confirmation
    2. Complete appointment details
    3. What to bring/prepare
    4. Clinic location and contact
    5. Cancellation policy reminder
    6. Supportive closing message
    
    Keep it professional yet caring, appropriate for Indian healthcare context.
    """
    
    return [UserMessage(prompt)]

# ------------------------------------------------------------------------------
# Enhanced Main Chat Interface
# ------------------------------------------------------------------------------
async def main_chat_loop():
    """Enhanced main chat loop for terminal interaction"""
    print("\n" + "="*70)
    print("🏥 HEALTHBOT AI - Enhanced Healthcare Appointment Assistant")
    print("="*70)
    print("🤖 Now with AI Patient Summaries & Comprehensive Appointment Management")
    print("💡 Type 'quit', 'exit', or 'bye' to end the conversation")
    print("💡 Type 'help' for available commands")
    print("💡 Type 'reset' to start a new conversation")
    print("💡 Type 'appointments' to view recent bookings")
    print("-"*70)
    
    session_id = f"terminal_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Welcome message
    welcome_response = await ai_manager.generate_response(
        "Hello! Please provide a warm welcome message explaining your enhanced capabilities including AI patient summaries for doctors, and ask how you can help with healthcare needs today.",
        session_id
    )
    print(f"\n🤖 HealthBot AI: {welcome_response}\n")
    
    while True:
        try:
            user_input = input("👤 You: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'bye']:
                print("\n🤖 HealthBot AI: Thank you for using our enhanced healthcare service. Take care and stay healthy! 👋")
                break
            
            if user_input.lower() == 'help':
                print("\n📋 ENHANCED COMMANDS AVAILABLE:")
                print("• 'services' - View all available healthcare services")
                print("• 'doctors' - View all available doctors")
                print("• 'clinics' - View all clinic locations")
                print("• 'appointments' - View recent appointments with AI summaries")
                print("• 'reset' - Start a new conversation")
                print("• 'quit/exit/bye' - End conversation")
                print("\n✨ ENHANCED FEATURES:")
                print("• AI-generated 200-word patient summaries for doctors")
                print("• Comprehensive appointment data storage")
                print("• Smart symptom analysis and service recommendations")
                print("• Complete patient interaction tracking")
                print("• Just type naturally to book appointments or ask health questions!")
                print()
                continue
            
            if user_input.lower() == 'reset':
                session_id = f"terminal_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                ai_manager.conversation_history[session_id] = []
                print("\n🔄 Conversation reset! Starting fresh with enhanced capabilities...\n")
                continue
            
            if user_input.lower() == 'appointments':
                try:
                    recent_appointments = db_manager.execute_dynamic_query("""
                        SELECT appointment_number, patient_name, doctor_name, service_name,
                               appointment_date, appointment_time, status, created_at,
                               SUBSTR(ai_patient_summary, 1, 100) as summary_preview
                        FROM enhanced_appointments 
                        ORDER BY created_at DESC 
                        LIMIT 5
                    """, (), "appointments")
                    
                    if recent_appointments:
                        print("\n📅 RECENT APPOINTMENTS WITH AI SUMMARIES:")
                        for apt in recent_appointments:
                            print(f"\n🆔 {apt['appointment_number']} - {apt['status'].upper()}")
                            print(f"👤 Patient: {apt['patient_name']}")
                            print(f"👩‍⚕️ Doctor: {apt['doctor_name']}")
                            print(f"🩺 Service: {apt['service_name']}")
                            print(f"📅 Date/Time: {apt['appointment_date']} at {apt['appointment_time']}")
                            print(f"🤖 AI Summary Preview: {apt.get('summary_preview', 'No summary')}...")
                            print("-" * 50)
                    else:
                        print("\n📅 No appointments found in the enhanced system yet.")
                except:
                    print("\n📅 No appointments available in enhanced system yet.")
                print()
                continue
            
            if user_input.lower() == 'services':
                services = db_manager.execute_dynamic_query("""
                    SELECT s.name, s.department, s.price, c.name as clinic_name
                    FROM services s JOIN clinics c ON s.clinic_id = c.id
                    ORDER BY s.department, s.name
                """)
                print("\n🩺 AVAILABLE SERVICES:")
                current_dept = ""
                for service in services:
                    if service['department'] != current_dept:
                        current_dept = service['department']
                        print(f"\n📍 {current_dept}:")
                    print(f"  • {service['name']} - ₹{service['price']} at {service['clinic_name']}")
                print()
                continue
            
            if user_input.lower() == 'doctors':
                doctors = db_manager.execute_dynamic_query("""
                    SELECT d.name, d.specialty, d.working_hours_display, c.name as clinic_name
                    FROM doctors d JOIN clinics c ON d.clinic_id = c.id
                    ORDER BY d.specialty, d.name
                """)
                print("\n👩‍⚕️ AVAILABLE DOCTORS:")
                for doctor in doctors:
                    print(f"  • Dr. {doctor['name']} - {doctor['specialty']}")
                    print(f"    Hours: {doctor['working_hours_display']} at {doctor['clinic_name']}")
                print()
                continue
            
            if user_input.lower() == 'clinics':
                clinics = db_manager.execute_dynamic_query("""
                    SELECT name, address, phone, operating_hours FROM clinics ORDER BY name
                """)
                print("\n🏥 OUR CLINICS:")
                for clinic in clinics:
                    print(f"  • {clinic['name']}")
                    print(f"    📍 {clinic['address']}")
                    print(f"    📞 {clinic['phone']} | ⏰ {clinic['operating_hours']}")
                    print()
                continue
            
            if not user_input:
                continue
            
            # Process with enhanced AI
            print("\n🤔 Processing your request with enhanced AI capabilities...")
            response = await ai_manager.generate_response(user_input, session_id)
            print(f"\n🤖 HealthBot AI: {response}\n")
            
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye! Stay healthy!")
            break
        except Exception as e:
            logger.exception(f"Error in enhanced chat loop: {e}")
            print(f"\n❌ Sorry, I encountered an error: {str(e)}")
            print("Please try again or contact our clinic directly.\n")

# ------------------------------------------------------------------------------
# Server Startup
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info("🚀 Starting Enhanced Healthcare Gemini AI MCP Server...")
    
    # Check if Gemini API key is configured
    if GEMINI_API_KEY == "your-gemini-api-key-here" or not GEMINI_API_KEY:
        print("\n⚠️  WARNING: Please set your GEMINI_API_KEY!")
        print("🔧 Option 1: Set environment variable - export GEMINI_API_KEY='your-actual-key'")
        print("🔧 Option 2: Edit the GEMINI_API_KEY variable in this file")
        print("🔗 Get your API key from: https://makersuite.google.com/app/apikey")
        
        # Ask user if they want to input API key now
        api_key_input = input("\n💡 Enter your Gemini API key now (or press Enter to exit): ").strip()
        if api_key_input:
            genai.configure(api_key=api_key_input)
            GEMINI_API_KEY = api_key_input
            print("✅ API key configured!")
        else:
            print("❌ Cannot proceed without API key. Exiting...")
            sys.exit(1)
    
    # Verify database files exist
    if not os.path.exists(SERVICES_DB_PATH):
        print(f"\n❌ Database file not found: {SERVICES_DB_PATH}")
        print("🔧 Please run: python healthcare_db_setup.py")
        sys.exit(1)
    
    if not os.path.exists(APPOINTMENTS_DB_PATH):
        print(f"\n❌ Database file not found: {APPOINTMENTS_DB_PATH}")
        print("🔧 Please run: python healthcare_db_setup.py")
        sys.exit(1)
    
    try:
        # Test database connections
        test_services = db_manager.execute_dynamic_query("SELECT COUNT(*) as count FROM services")
        test_doctors = db_manager.execute_dynamic_query("SELECT COUNT(*) as count FROM doctors")
        test_clinics = db_manager.execute_dynamic_query("SELECT COUNT(*) as count FROM clinics")
        
        print("\n🏥 Enhanced Database Status:")
        print(f"   ✅ Services: {test_services[0]['count']} available")
        print(f"   ✅ Doctors: {test_doctors[0]['count']} available") 
        print(f"   ✅ Clinics: {test_clinics[0]['count']} locations")
        print(f"   ✅ Enhanced appointments table ready")
        print(f"   ✅ AI patient summaries enabled")
        
        # Test Gemini AI connection
        test_response = ai_manager.model.generate_content("Hello! Just testing the enhanced connection with patient summary capabilities.")
        print("   ✅ Enhanced Gemini AI: Connected and responsive")
        
        print("\n🚀 All enhanced systems ready! Starting chat interface...")
        print("✨ Features: AI Patient Summaries | Comprehensive Data Storage | Smart Analytics")
        print("="*70)
        
        # Start the enhanced interactive chat interface
        asyncio.run(main_chat_loop())
        
    except Exception as e:
        logger.exception(f"Enhanced server startup failed: {e}")
        print(f"\n❌ Startup Error: {str(e)}")
        print("\n🔧 Enhanced Troubleshooting:")
        print("1. Check if databases are properly created")
        print("2. Verify Gemini API key is valid")
        print("3. Ensure all dependencies are installed")
        print("4. Check network connection")
        print("5. Verify enhanced database schema creation")
        
    finally:
        # Clean shutdown
        try:
            if 'db_manager' in globals():
                db_manager.services_conn.close()
                db_manager.appointments_conn.close()
                logger.info("Enhanced database connections closed successfully.")
        except Exception as e:
            logger.warning(f"Error closing enhanced database connections: {e}")
        
        logger.info("🏥 Enhanced Healthcare Gemini AI MCP Server shutdown complete.")
        print("\n👋 Thank you for using Enhanced Healthcare AI Assistant!")
        print("💚 Stay healthy and take care!")
        print("🤖 AI Patient Summaries and comprehensive data management enabled!")