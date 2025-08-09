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
# Database Manager Class
# ------------------------------------------------------------------------------
class DatabaseManager:
    def __init__(self):
        self.services_conn = None
        self.appointments_conn = None
        self.connect_databases()
    
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
                return cursor.rowcount
            else:
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.exception(f"Error executing query: {e}")
            return []

# Initialize database manager
db_manager = DatabaseManager()

# ------------------------------------------------------------------------------
# Gemini AI Manager Class
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
3. APPOINTMENT BOOKING: Guide patients through complete booking process
4. DYNAMIC ADAPTATION: Always query database for real-time information
5. PATIENT CARE: Show empathy, provide reassurance, maintain professionalism

🔄 CONVERSATION FLOW:
1. GREETING: Warm, professional welcome
2. NEEDS ASSESSMENT: Understand health concerns or service needs
3. SYMPTOM ANALYSIS: If health issue, analyze symptoms intelligently
4. SERVICE RECOMMENDATION: Suggest appropriate services/doctors based on analysis
5. AVAILABILITY CHECK: Show real-time available slots
6. PATIENT INFORMATION: Collect necessary details
7. BOOKING CONFIRMATION: Complete appointment booking
8. FOLLOW-UP: Provide confirmation and next steps

⚠️ CRITICAL GUIDELINES:
- NEVER provide medical diagnosis - only suggest appropriate healthcare services
- For urgent symptoms (chest pain, severe bleeding, difficulty breathing), immediately recommend emergency care
- Always verify information with database queries
- Be empathetic about health concerns
- Ensure all appointment details are confirmed before booking
- Maintain patient privacy and confidentiality
- Use Indian context (₹ for prices, Indian names, local references)

🗣️ COMMUNICATION STYLE:
- Warm, friendly, and professional
- Use empathetic language for health concerns
- Clear explanations of medical services
- Patient and understanding with questions
- Culturally appropriate for Indian patients

💡 SMART FEATURES:
- Analyze conversation context to understand patient needs
- Remember information from current conversation
- Suggest alternatives when preferred slots unavailable
- Provide estimated costs and time requirements
- Explain what to expect during appointments

Always start conversations with a warm greeting and ask how you can help with their healthcare needs today.
"""
            return context
            
        except Exception as e:
            logger.exception(f"Error building dynamic context: {e}")
            return "You are a healthcare appointment scheduling assistant."
    
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
            response = await asyncio.get_event_loop().run_in_executor(
                None, self.model.generate_content, conversation_prompt
            )
            
            ai_response = response.text
            
            # Update conversation history
            self.conversation_history[session_id].append(f"Patient: {user_message}")
            self.conversation_history[session_id].append(f"HealthBot AI: {ai_response}")
            
            # Log interaction
            db_manager.execute_dynamic_query("""
                INSERT INTO interaction_logs 
                (session_id, user_input, ai_response, conversation_step, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (session_id, user_message, ai_response, "conversation", datetime.now().isoformat()), "appointments")
            
            return ai_response
            
        except Exception as e:
            logger.exception(f"Error generating AI response: {e}")
            return "I apologize, but I'm having trouble processing your request right now. Please try again or contact our clinic directly."

# Initialize AI manager
ai_manager = GeminiAIManager()

# ------------------------------------------------------------------------------
# MCP Server Initialization
# ------------------------------------------------------------------------------
mcp = FastMCP("Healthcare Gemini AI Assistant")

# ------------------------------------------------------------------------------
# Dynamic Database Resources
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
# Intelligent MCP Tools
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
        
        # Insert patient
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
            "message": f"Patient {data.get('name')} created successfully"
        })
        
    except Exception as e:
        logger.exception(f"Error creating patient: {e}")
        return json.dumps({"success": False, "error": str(e)})

@mcp.tool()
def book_appointment_intelligent(booking_data: str) -> str:
    """Intelligent appointment booking with full validation"""
    logger.info("Processing intelligent appointment booking")
    try:
        data = json.loads(booking_data) if isinstance(booking_data, str) else booking_data
        
        patient_id = data.get('patient_id')
        doctor_id = data.get('doctor_id')
        service_id = data.get('service_id')
        time_slot_id = data.get('time_slot_id')
        appointment_date = data.get('appointment_date', datetime.now().strftime('%Y-%m-%d'))
        
        # Validate time slot availability
        slot_check = db_manager.execute_dynamic_query("""
            SELECT ts.*, d.name as doctor_name, s.name as service_name, c.name as clinic_name
            FROM time_slots ts
            JOIN doctors d ON ts.doctor_id = d.id
            LEFT JOIN services s ON ? = s.id
            JOIN clinics c ON d.clinic_id = c.id
            WHERE ts.id = ? AND ts.is_available = 1
        """, (service_id, time_slot_id))
        
        if not slot_check:
            return json.dumps({"success": False, "error": "Time slot not available"})
        
        slot_info = slot_check[0]
        
        # Create appointment
        db_manager.execute_dynamic_query("""
            INSERT INTO appointments 
            (patient_id, doctor_id, service_id, clinic_id, appointment_date, appointment_time, 
             duration_minutes, patient_complaint, symptoms_description, urgency_level, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'scheduled')
        """, (
            patient_id, doctor_id, service_id, 1,  # Default clinic_id, should be dynamic
            appointment_date, slot_info['start_time'], 30,  # Default duration
            data.get('complaint', ''), data.get('symptoms', ''), data.get('urgency', 'normal')
        ), "appointments")
        
        # Mark time slot as unavailable
        db_manager.execute_dynamic_query("""
            UPDATE time_slots SET is_available = 0 WHERE id = ?
        """, (time_slot_id,))
        
        return json.dumps({
            "success": True,
            "appointment_details": {
                "doctor": slot_info['doctor_name'],
                "service": slot_info['service_name'],
                "clinic": slot_info['clinic_name'],
                "date": appointment_date,
                "time": slot_info['start_time'],
                "duration": "30 minutes"
            },
            "message": "Appointment booked successfully!"
        })
        
    except Exception as e:
        logger.exception(f"Error booking appointment: {e}")
        return json.dumps({"success": False, "error": str(e)})

# ------------------------------------------------------------------------------
# Advanced MCP Prompts
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

# ------------------------------------------------------------------------------
# Main Chat Interface for Terminal
# ------------------------------------------------------------------------------
async def main_chat_loop():
    """Main chat loop for terminal interaction"""
    print("\n" + "="*60)
    print("🏥 HEALTHBOT AI - Healthcare Appointment Assistant")
    print("="*60)
    print("💡 Type 'quit', 'exit', or 'bye' to end the conversation")
    print("💡 Type 'help' for available commands")
    print("💡 Type 'reset' to start a new conversation")
    print("-"*60)
    
    session_id = f"terminal_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Welcome message
    welcome_response = await ai_manager.generate_response(
        "Hello! Please provide a warm welcome message and ask how you can help with healthcare needs today.",
        session_id
    )
    print(f"\n🤖 HealthBot AI: {welcome_response}\n")
    
    while True:
        try:
            user_input = input("👤 You: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'bye']:
                print("\n🤖 HealthBot AI: Thank you for using our healthcare service. Take care and stay healthy! 👋")
                break
            
            if user_input.lower() == 'help':
                print("\n📋 AVAILABLE COMMANDS:")
                print("• 'services' - View all available healthcare services")
                print("• 'doctors' - View all available doctors")
                print("• 'clinics' - View all clinic locations")
                print("• 'reset' - Start a new conversation")
                print("• 'quit/exit/bye' - End conversation")
                print("• Just type naturally to book appointments or ask health questions!\n")
                continue
            
            if user_input.lower() == 'reset':
                session_id = f"terminal_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                ai_manager.conversation_history[session_id] = []
                print("\n🔄 Conversation reset! Starting fresh...\n")
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
            
            # Process with AI
            print("\n🤔 Processing your request...")
            response = await ai_manager.generate_response(user_input, session_id)
            print(f"\n🤖 HealthBot AI: {response}\n")
            
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye! Stay healthy!")
            break
        except Exception as e:
            logger.exception(f"Error in main chat loop: {e}")
            print(f"\n❌ Sorry, I encountered an error: {str(e)}")
            print("Please try again or contact our clinic directly.\n")

# ------------------------------------------------------------------------------
# Server Startup
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info("🚀 Starting Healthcare Gemini AI MCP Server...")
    
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
        
        print("\n🏥 Database Status:")
        print(f"   ✅ Services: {test_services[0]['count']} available")
        print(f"   ✅ Doctors: {test_doctors[0]['count']} available") 
        print(f"   ✅ Clinics: {test_clinics[0]['count']} locations")
        
        # Test Gemini AI connection
        test_response = ai_manager.model.generate_content("Hello! Just testing the connection.")
        print("   ✅ Gemini AI: Connected and responsive")
        
        print("\n🚀 All systems ready! Starting chat interface...")
        print("="*60)
        
        # Start the interactive chat interface
        asyncio.run(main_chat_loop())
        
    except Exception as e:
        logger.exception(f"Server startup failed: {e}")
        print(f"\n❌ Startup Error: {str(e)}")
        print("\n🔧 Troubleshooting:")
        print("1. Check if databases are properly created")
        print("2. Verify Gemini API key is valid")
        print("3. Ensure all dependencies are installed")
        print("4. Check network connection")
        
    finally:
        # Clean shutdown
        try:
            if 'db_manager' in globals():
                db_manager.services_conn.close()
                db_manager.appointments_conn.close()
                logger.info("Database connections closed successfully.")
        except Exception as e:
            logger.warning(f"Error closing database connections: {e}")
        
        logger.info("🏥 Healthcare Gemini AI MCP Server shutdown complete.")
        print("\n👋 Thank you for using Healthcare AI Assistant!")
        print("💚 Stay healthy and take care!")