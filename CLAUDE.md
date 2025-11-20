# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Intelligent Medical Consultation System - A multi-agent AI system built with Langchain for ophthalmology healthcare consultations, smart triage, appointment scheduling, medical report generation, and prescription management.

## Common Commands

### Running the Application

```bash
# Start the FastAPI server with auto-reload
python main.py

# Or using uvicorn directly
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Database Setup

```bash
# Initialize database schema (run SQL script manually in MySQL)
# File: database/init_database_v2.sql
mysql -u root -p medical_db < database/init_database_v2.sql

# Or use the Python execution script
python database/execute_init_v2.py
```

### Testing

```bash
# Test prescription generation functionality
python test_prescription_fix.py

# Test agent2 functionality
python test_agent2_fix.py

# Test barcode generation
python test_barcode_header.py
```

### Installing Dependencies

```bash
pip install -r requirements.txt
```

## Architecture

### Multi-Agent System

The system uses an **Agent-based architecture** where different specialized AI agents handle specific tasks:

1. **HealthAgent** (agent_1.py) - Health consultation, symptom assessment, appointment booking
2. **ReportAgent** (agent_2.py) - Medical report generation, historical analysis, prescription generation
3. **Future: ReminderAgent** (agent_3.py) - Appointment reminders and follow-up scheduling

**Agent Management:**
- `AgentManager` maintains agent instances and session mappings
- Supports automatic agent switching based on user intent
- Each agent has conversation stages (Enum-based state machine)
- Role-based permissions (patient vs doctor)

### Intent Detection & Routing

The system uses `IntentDetector` (utils/intent_detector.py) to:
- Analyze user messages using keyword matching
- Route conversations to appropriate agents automatically
- Enforce role-based access control (e.g., patients cannot generate reports)

### Database Architecture (3-Layer Model)

**Core Tables:**
- `patient` - User basic info (one person, identified by phone number)
- `medical_record` - Visit records (one visit per record, linked to patient)
- `appointment` - Appointments (linked to medical_record and doctor)
- `prescription` - Prescriptions with detailed drug information
- `doctor` - Doctor profiles

**Key Design:**
- User identified by `phone_number` (unique, recommended) or `Patient_ID` (single record only)
- One patient can have multiple medical records (historical visits)
- Services in `database/` provide V2 versions that properly handle phone-based queries

### LLM Integration

**Configuration:** `utils/llm_config.py`
- Uses SiliconFlow API with Qwen models
- API key configured in `.env` file
- Shared LLM instance via `get_llm()`

**Environment Variables Required (.env):**
```
# LLM API Configuration
SILICONFLOW_API_KEY=your_api_key
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
MODEL_NAME=Qwen/Qwen2.5-7B-Instruct

# Database Configuration
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password_here
DB_NAME=medical_db
DB_CHARSET=utf8mb4
DB_AUTOCOMMIT=False
```

### Document Generation

**Report Generator** (utils/report_generator.py):
- Generates medical reports from database using Word templates
- Template: `example/bingli_template.docx`
- Outputs: `example/reports/` (both .docx and .pdf)
- Uses `python-docx` for Word manipulation, `docx2pdf` for conversion

**Prescription Generator** (utils/prescription_generator.py):
- Generates prescription PDFs with barcodes
- Template: `example/prescription_template.docx`
- Outputs: `example/prescriptions/`
- Generates Code128 barcodes for prescription numbers
- Doctor-only feature (role-based access control)

### API Structure

**Main Routes (main.py):**
- `/api/chat` - Main chat endpoint with automatic agent routing
- `/api/chat/report` - Direct ReportAgent interface
- `/api/report/*` - Report generation and analysis
- `/api/prescription/*` - Prescription management
- `/api/appointments` - Appointment queries
- `/api/patients` - Patient record queries

**Session Management:**
- In-memory sessions dict (production should use Redis)
- Session stores: messages, current_agent, role, appointment_result

## Key Implementation Details

### Agent Lifecycle

Each agent follows this pattern:
```python
# 1. Initialize with user context
agent = HealthAgent(user_id=None, phone_number="13800000000", role="patient")

# 2. Load historical data automatically on first message
agent._load_user_history()  # Called internally

# 3. Process messages through conversation chain
response = agent.chat(message)

# 4. Track conversation stage
current_stage = agent.stage  # ConversationStage enum

# 5. Check completion
is_done = agent.is_completed()
```

### Database Services Pattern

All database services follow this structure:
```python
# V2 services support phone-based queries
service = UserHistoryServiceV2()
history = service.get_user_complete_info_by_phone(phone_number)
formatted_text = service.format_user_history_text_by_phone(phone_number)
```

**Important:** Always use V2 services (e.g., `AppointmentServiceV2`, `UserHistoryServiceV2`) for proper multi-record support.

### Role-Based Access Control

Agents check role before privileged operations:
```python
if self.role == "doctor":
    # Allow report/prescription generation
    pass
else:
    # Block with appropriate message
    return "抱歉，只有医生才能生成报告"
```

### Conversation State Management

Agents use Enum-based stages:
```python
class ConversationStage(Enum):
    GREETING = "greeting"
    SYMPTOM_ASSESSMENT = "symptom_assessment"
    # ... etc
```

State transitions controlled by `_determine_next_stage()` logic in each agent.

## Database Configuration

**Connection:** `database/db_config.py`

Database configuration is loaded from environment variables for security:

```python
import os
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '3306')),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME', 'medical_db'),
    'charset': os.getenv('DB_CHARSET', 'utf8mb4'),
    'autocommit': os.getenv('DB_AUTOCOMMIT', 'False').lower() == 'true',
}
```

**Important:** Configure database credentials in `.env` file. Never commit passwords to version control.

## Project File Structure

```
pythonProject1/
├── main.py                           # FastAPI application entry point
├── agents/
│   ├── agent_manager.py              # Agent lifecycle management
│   ├── agent_1.py                    # HealthAgent (consultation & appointments)
│   └── agent_2.py                    # ReportAgent (reports & prescriptions)
├── database/
│   ├── db_config.py                  # Database connection config
│   ├── db_connection.py              # Database connection wrapper
│   ├── init_database_v2.sql          # Current database schema
│   ├── appointment_service_v2.py     # Appointment DB operations
│   ├── user_history_service_v2.py    # User history queries
│   ├── report_service.py             # Medical report DB operations
│   └── prescription_service.py       # Prescription DB operations
├── utils/
│   ├── llm_config.py                 # LLM initialization and config
│   ├── intent_detector.py            # Agent routing logic
│   ├── data_handler.py               # JSON data processing
│   ├── report_generator.py           # Medical report PDF generation
│   └── prescription_generator.py     # Prescription PDF generation
├── example/
│   ├── bingli_template.docx          # Medical report Word template
│   ├── prescription_template.docx    # Prescription Word template
│   ├── logo@1x.png                   # Logo for documents
│   ├── reports/                      # Generated reports output
│   └── prescriptions/                # Generated prescriptions output
├── static/                           # Frontend static files
└── templates/                        # Jinja2 HTML templates
```

## Adding New Agents

To add a new agent (e.g., agent_3):

1. Create `agents/agent_3.py` with similar structure to existing agents
2. Define conversation stages using Enum
3. Implement `chat()`, `is_completed()`, state management
4. Add agent type to `AgentManager.create_agent()`
5. Update `IntentDetector` with new keywords and routing rules
6. Add API routes in `main.py` if needed
7. Create corresponding database service if data access required

## Important Notes

- **Always use phone_number** when querying user data for complete history
- **V2 services** are current - avoid V1 services
- **Role parameter** must be passed when creating agents for access control
- **Session management** is in-memory - implement Redis for production
- **PDF generation** requires Microsoft Word on Windows for docx2pdf
- **Environment variables** - All sensitive configuration (API keys, database passwords) must be in `.env` file, never hardcoded
- **Security** - Never commit `.env` file to version control (already in `.gitignore`)
