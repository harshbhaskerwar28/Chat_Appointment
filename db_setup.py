#!/usr/bin/env python3
"""
Healthcare Database Setup Script
Creates two SQLite databases with proper synchronization:
1. healthcare_services.db - Contains services, doctors, clinics and time slots
2. appointments.db - Contains patient appointments and chat summaries

Key Features:
- Proper doctor-service-clinic synchronization
- Indian phone numbers
- Time ranges for doctors (e.g., 10:00 AM - 6:00 PM)
- No date dependency - only time slots
- Clinic information integrated
"""

import sqlite3
import json
import random
from datetime import datetime, timedelta

def create_services_database():
    """Create and populate the healthcare services database"""
    print("Creating healthcare_services.db...")
    
    conn = sqlite3.connect('healthcare_services.db')
    cursor = conn.cursor()
    
    # Create clinics table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clinics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            address TEXT,
            city TEXT DEFAULT 'Karimnagar',
            state TEXT DEFAULT 'Telangana',
            pincode TEXT,
            phone TEXT,
            email TEXT,
            operating_hours TEXT, -- e.g., "9:00 AM - 8:00 PM"
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create services table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            duration_minutes INTEGER DEFAULT 30,
            price DECIMAL(10,2),
            department TEXT,
            clinic_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (clinic_id) REFERENCES clinics (id)
        )
    ''')
    
    # Create doctors table with proper time ranges
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            specialty TEXT,
            phone TEXT,
            email TEXT,
            clinic_id INTEGER,
            available_days TEXT, -- JSON array of available days
            working_hours_start TIME, -- e.g., "10:00:00"
            working_hours_end TIME,   -- e.g., "18:00:00"
            working_hours_display TEXT, -- e.g., "10:00 AM - 6:00 PM"
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (clinic_id) REFERENCES clinics (id)
        )
    ''')
    
    # Create doctor_services junction table (many-to-many relationship)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS doctor_services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doctor_id INTEGER,
            service_id INTEGER,
            FOREIGN KEY (doctor_id) REFERENCES doctors (id),
            FOREIGN KEY (service_id) REFERENCES services (id),
            UNIQUE(doctor_id, service_id)
        )
    ''')
    
    # Create time slots table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS time_slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doctor_id INTEGER,
            day_of_week INTEGER, -- 1=Monday, 7=Sunday
            start_time TIME NOT NULL,
            end_time TIME NOT NULL,
            is_available BOOLEAN DEFAULT 1,
            slot_type TEXT DEFAULT 'regular', -- regular, emergency, consultation
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (doctor_id) REFERENCES doctors (id)
        )
    ''')
    
    # Insert clinics
    clinics = [
        ("HealthCare Plus Clinic", "Main Road, Beside SBI Bank", "Karimnagar", "Telangana", "505001", "+91-8765-432109", "info@healthcareplus.in", "9:00 AM - 8:00 PM"),
        ("City Medical Center", "Gandhi Chowk, Near Bus Stand", "Karimnagar", "Telangana", "505001", "+91-9876-543210", "contact@citymedical.in", "8:00 AM - 9:00 PM"),
        ("Wellness Hospital", "Collectorate Road, Opp. District Court", "Karimnagar", "Telangana", "505002", "+91-7654-321098", "info@wellnesshospital.in", "24 Hours"),
        ("Family Care Clinic", "Rekurthi Road, Near Railway Station", "Karimnagar", "Telangana", "505003", "+91-8912-345678", "familycare@clinic.in", "10:00 AM - 7:00 PM")
    ]
    
    cursor.executemany('''
        INSERT INTO clinics (name, address, city, state, pincode, phone, email, operating_hours)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', clinics)
    
    # Insert healthcare services
    services = [
        ("General Checkup", "Complete health examination and consultation", 45, 150.00, "General Medicine", 1),
        ("Blood Test", "Comprehensive blood work and analysis", 15, 75.00, "Laboratory", 2),
        ("X-Ray", "Digital X-ray imaging service", 20, 100.00, "Radiology", 2),
        ("Dental Cleaning", "Professional teeth cleaning and oral exam", 60, 120.00, "Dentistry", 4),
        ("Eye Examination", "Complete eye health and vision checkup", 30, 90.00, "Ophthalmology", 1),
        ("Cardiology Consultation", "Heart health assessment and consultation", 45, 200.00, "Cardiology", 3),
        ("Dermatology Consultation", "Skin condition evaluation and treatment", 30, 180.00, "Dermatology", 2),
        ("Physical Therapy", "Rehabilitation and physical therapy session", 60, 85.00, "Physical Therapy", 3),
        ("Vaccination", "Immunization and vaccination services", 15, 50.00, "General Medicine", 1),
        ("Mental Health Counseling", "Psychological counseling and therapy", 60, 160.00, "Mental Health", 4),
        ("Pediatric Checkup", "Child health examination and consultation", 40, 140.00, "Pediatrics", 1),
        ("Gynecology Consultation", "Women's health examination and consultation", 45, 170.00, "Gynecology", 3),
        ("Orthopedic Consultation", "Bone and joint health assessment", 40, 190.00, "Orthopedics", 2),
        ("ENT Consultation", "Ear, Nose, Throat examination", 35, 160.00, "ENT", 4),
        ("Diabetes Consultation", "Blood sugar management and counseling", 30, 180.00, "Endocrinology", 3)
    ]
    
    cursor.executemany('''
        INSERT INTO services (name, description, duration_minutes, price, department, clinic_id)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', services)
    
    # Insert doctors with proper working hours
    doctors = [
        ("Dr. Rajesh Kumar", "General Medicine", "+91-9876-543201", "rajesh.kumar@clinic.in", 1, '["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]', "09:00:00", "17:00:00", "9:00 AM - 5:00 PM"),
        ("Dr. Priya Sharma", "Cardiology", "+91-8765-432102", "priya.sharma@clinic.in", 3, '["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]', "10:00:00", "18:00:00", "10:00 AM - 6:00 PM"),
        ("Dr. Suresh Reddy", "Dermatology", "+91-7654-321903", "suresh.reddy@clinic.in", 2, '["Tuesday", "Thursday", "Friday", "Saturday"]', "11:00:00", "19:00:00", "11:00 AM - 7:00 PM"),
        ("Dr. Meera Patel", "Ophthalmology", "+91-9123-456704", "meera.patel@clinic.in", 1, '["Monday", "Wednesday", "Thursday", "Friday", "Saturday"]', "08:30:00", "16:30:00", "8:30 AM - 4:30 PM"),
        ("Dr. Vikram Singh", "Mental Health", "+91-8234-567105", "vikram.singh@clinic.in", 4, '["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]', "10:00:00", "18:00:00", "10:00 AM - 6:00 PM"),
        ("Dr. Anita Gupta", "Pediatrics", "+91-7345-678906", "anita.gupta@clinic.in", 1, '["Monday", "Tuesday", "Wednesday", "Friday", "Saturday"]', "09:00:00", "17:00:00", "9:00 AM - 5:00 PM"),
        ("Dr. Ravi Krishnan", "Gynecology", "+91-9456-789107", "ravi.krishnan@clinic.in", 3, '["Monday", "Wednesday", "Thursday", "Friday"]', "14:00:00", "20:00:00", "2:00 PM - 8:00 PM"),
        ("Dr. Sunita Rao", "Orthopedics", "+91-8567-891208", "sunita.rao@clinic.in", 2, '["Tuesday", "Wednesday", "Thursday", "Saturday"]', "09:30:00", "17:30:00", "9:30 AM - 5:30 PM"),
        ("Dr. Arun Kumar", "ENT", "+91-7678-912309", "arun.kumar@clinic.in", 4, '["Monday", "Tuesday", "Friday", "Saturday"]', "10:30:00", "18:30:00", "10:30 AM - 6:30 PM"),
        ("Dr. Kavitha Nair", "Endocrinology", "+91-9789-123410", "kavitha.nair@clinic.in", 3, '["Monday", "Wednesday", "Thursday", "Friday"]', "11:00:00", "19:00:00", "11:00 AM - 7:00 PM")
    ]
    
    cursor.executemany('''
        INSERT INTO doctors (name, specialty, phone, email, clinic_id, available_days, working_hours_start, working_hours_end, working_hours_display)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', doctors)
    
    # Create doctor-service relationships
    doctor_service_mappings = [
        # Dr. Rajesh Kumar (General Medicine) - services 1, 9
        (1, 1), (1, 9),
        # Dr. Priya Sharma (Cardiology) - service 6
        (2, 6),
        # Dr. Suresh Reddy (Dermatology) - service 7
        (3, 7),
        # Dr. Meera Patel (Ophthalmology) - service 5
        (4, 5),
        # Dr. Vikram Singh (Mental Health) - service 10
        (5, 10),
        # Dr. Anita Gupta (Pediatrics) - service 11
        (6, 11),
        # Dr. Ravi Krishnan (Gynecology) - service 12
        (7, 12),
        # Dr. Sunita Rao (Orthopedics) - service 13
        (8, 13),
        # Dr. Arun Kumar (ENT) - service 14
        (9, 14),
        # Dr. Kavitha Nair (Endocrinology) - service 15
        (10, 15),
        # Add some doctors to multiple services
        (1, 2), (1, 3),  # General medicine doctor can do basic tests
        (2, 8),  # Cardiologist can do physical therapy consultation
        (4, 1),  # Eye doctor can do general checkups
    ]
    
    cursor.executemany('''
        INSERT OR IGNORE INTO doctor_services (doctor_id, service_id)
        VALUES (?, ?)
    ''', doctor_service_mappings)
    
    # Generate time slots for each doctor based on their working hours
    time_slots = []
    
    for doctor_id in range(1, 11):  # We have 10 doctors
        # Get doctor's working hours
        cursor.execute('SELECT working_hours_start, working_hours_end, available_days FROM doctors WHERE id = ?', (doctor_id,))
        doctor_info = cursor.fetchone()
        start_time_str, end_time_str, available_days_json = doctor_info
        available_days = json.loads(available_days_json)
        
        # Convert day names to numbers (Monday=1, Sunday=7)
        day_mapping = {
            "Monday": 1, "Tuesday": 2, "Wednesday": 3, "Thursday": 4,
            "Friday": 5, "Saturday": 6, "Sunday": 7
        }
        
        for day_name in available_days:
            day_num = day_mapping[day_name]
            
            # Parse working hours
            start_hour, start_min = map(int, start_time_str.split(':')[:2])
            end_hour, end_min = map(int, end_time_str.split(':')[:2])
            
            # Create 30-minute slots
            current_hour, current_min = start_hour, start_min
            
            while (current_hour < end_hour) or (current_hour == end_hour and current_min < end_min):
                slot_start = f"{current_hour:02d}:{current_min:02d}:00"
                
                # Calculate end time (30 minutes later)
                end_slot_min = current_min + 30
                end_slot_hour = current_hour
                if end_slot_min >= 60:
                    end_slot_min -= 60
                    end_slot_hour += 1
                
                slot_end = f"{end_slot_hour:02d}:{end_slot_min:02d}:00"
                
                # Don't create slot if it goes beyond working hours
                if end_slot_hour > end_hour or (end_slot_hour == end_hour and end_slot_min > end_min):
                    break
                
                time_slots.append((
                    doctor_id,
                    day_num,
                    slot_start,
                    slot_end,
                    1,  # is_available
                    'regular'
                ))
                
                # Move to next slot
                current_min += 30
                if current_min >= 60:
                    current_min = 0
                    current_hour += 1
    
    cursor.executemany('''
        INSERT INTO time_slots (doctor_id, day_of_week, start_time, end_time, is_available, slot_type)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', time_slots)
    
    conn.commit()
    conn.close()
    print(f"✅ Created healthcare_services.db with {len(clinics)} clinics, {len(services)} services, {len(doctors)} doctors, and {len(time_slots)} time slots")

def create_appointments_database():
    """Create the appointments and patient data database"""
    print("Creating appointments.db...")
    
    conn = sqlite3.connect('appointments.db')
    cursor = conn.cursor()
    
    # Create patients table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            phone TEXT,
            email TEXT,
            age INTEGER,
            gender TEXT,
            address TEXT,
            medical_history TEXT,
            emergency_contact TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create appointments table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER,
            doctor_id INTEGER,
            service_id INTEGER,
            clinic_id INTEGER,
            appointment_date DATE NOT NULL,
            appointment_time TIME NOT NULL,
            duration_minutes INTEGER DEFAULT 30,
            status TEXT DEFAULT 'scheduled', -- scheduled, completed, cancelled, no_show
            patient_complaint TEXT,
            symptoms_description TEXT,
            urgency_level TEXT DEFAULT 'normal', -- urgent, normal, routine
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (patient_id) REFERENCES patients (id)
        )
    ''')
    
    # Create chat summaries table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            appointment_id INTEGER,
            patient_id INTEGER,
            conversation_text TEXT,
            ai_analysis TEXT,
            recommended_service TEXT,
            recommended_doctor TEXT,
            recommended_clinic TEXT,
            symptoms_extracted TEXT, -- JSON array of symptoms
            urgency_assessment TEXT,
            conversation_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (appointment_id) REFERENCES appointments (id),
            FOREIGN KEY (patient_id) REFERENCES patients (id)
        )
    ''')
    
    # Create interaction logs table for tracking all user interactions
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS interaction_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            patient_phone TEXT,
            user_input TEXT,
            ai_response TEXT,
            intent_detected TEXT,
            entities_extracted TEXT, -- JSON
            conversation_step TEXT, -- greeting, symptom_collection, appointment_booking, etc.
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create appointment history table for tracking changes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS appointment_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            appointment_id INTEGER,
            old_status TEXT,
            new_status TEXT,
            change_reason TEXT,
            changed_by TEXT, -- system, patient, doctor, admin
            change_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (appointment_id) REFERENCES appointments (id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Created appointments.db with patient, appointment, and comprehensive tracking tables")

def verify_databases():
    """Verify both databases were created successfully and show sample data"""
    print("\n🔍 Verifying databases...")
    
    # Check services database
    try:
        conn = sqlite3.connect('healthcare_services.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM clinics")
        clinics_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM services")
        services_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM time_slots")
        slots_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM doctors")
        doctors_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM doctor_services")
        doctor_services_count = cursor.fetchone()[0]
        
        print(f"📋 Services Database:")
        print(f"   • {clinics_count} clinics")
        print(f"   • {services_count} services") 
        print(f"   • {doctors_count} doctors")
        print(f"   • {doctor_services_count} doctor-service mappings")
        print(f"   • {slots_count} time slots")
        
        # Show sample doctor with their working hours
        cursor.execute('''
            SELECT d.name, d.specialty, d.working_hours_display, c.name as clinic_name
            FROM doctors d 
            JOIN clinics c ON d.clinic_id = c.id 
            LIMIT 3
        ''')
        sample_doctors = cursor.fetchall()
        print(f"\n📋 Sample Doctors:")
        for doctor in sample_doctors:
            print(f"   • {doctor[0]} ({doctor[1]}) - {doctor[2]} at {doctor[3]}")
        
        conn.close()
    except Exception as e:
        print(f"❌ Error checking services database: {e}")
    
    # Check appointments database
    try:
        conn = sqlite3.connect('appointments.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        table_names = [table[0] for table in tables]
        
        print(f"\n📅 Appointments Database:")
        print(f"   • Created tables: {', '.join(table_names)}")
        conn.close()
    except Exception as e:
        print(f"❌ Error checking appointments database: {e}")

if __name__ == "__main__":
    print("🏥 Setting up Healthcare Appointment System Databases")
    print("=" * 60)
    
    create_services_database()
    create_appointments_database()
    verify_databases()
    
    print("\n✅ Database setup complete!")
    print("\nNext steps:")
    print("1. Run the MCP server: python healthcare_mcp_server.py")
    print("2. Test with MCP Inspector or integrate with your chatbot")
    print("3. Use the Gemini AI integration for natural language processing")
    print("\n📖 See README.md for database structure details")