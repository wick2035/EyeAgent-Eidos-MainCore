# EyeAgent Eidos

English | [简体中文](README.md)

EyeAgent Eidos is a FastAPI and LangGraph multi-agent medical consultation system focused on ophthalmology. It combines health consultation, medical reports, reminders, research assistance, compliance review, and product recommendations with hybrid intent routing and MySQL-backed conversation state.

> This project is intended for research and development. Model output can be wrong and does not replace professional medical judgment, diagnosis, or treatment. Clinical use requires review by qualified professionals and appropriate safety, privacy, and regulatory assessment.

## Capabilities

| Agent | Capabilities | Intended roles |
| --- | --- | --- |
| Health | Ophthalmic questions, symptom collection, triage, doctor lookup and appointments | Patient, doctor |
| Report | Prescription and examination records, medical report and prescription documents | Patient, doctor |
| Reminder | Follow-up, medication and appointment reminders, notification settings | Patient, doctor |
| Research | Literature search, statistical analysis, study design and writing assistance | Doctor |
| Compliance | Review of prescriptions, diagnoses, medical records and examination choices | Doctor |
| Recommendation | Medication and device suggestions and structured product cards | Patient, doctor |

The application supports synchronous and SSE streaming chat, conversation history, image/PDF attachments and speech recognition. Features depend on the model, business backend, database and relevant third-party services. Shopping cart and prescription actions in the recommendation tools are currently stubs. Role-based routing is not a substitute for server-side authentication and authorization.

## Architecture

```text
Browser / API client
        │
        ▼
FastAPI routes → input and role checks → LangGraph hybrid intent router
                                          │
              Health / Report / Reminder / Research / Compliance / Recommendation
                                          │
                              response handling and persistence
                              │                      │
                            MySQL             external services / APIs
```

Rule-based and LLM routing select an agent. A MySQL checkpointer persists graph state, while message persistence components manage conversation history. Integrations include a business backend, DashScope, SiliconFlow, Search1API and MinIO. See the [architecture documentation](docs/项目结构.md) and [technical roadmap](docs/我们的工作.md) (Chinese).

## Requirements

- Python 3.10 or newer and `pip`; see [requirements.txt](requirements.txt).
- MySQL, including checkpoint tables and the business tables required by the application, for full conversation persistence.
- A DashScope API key for agent models and speech recognition.
- A compatible business backend for patient, appointment and prescription data and operations. The full backend and business database schema are not included in this repository.
- SiliconFlow, Search1API and MinIO as needed. Third-party services may incur charges.
- Some document conversion paths may require system tools such as Microsoft Word or Pandoc, depending on the platform and conversion method.

## Getting started

### 1. Clone and install

```bash
git clone https://github.com/wick2035/EyeAgent-MainCore.git
cd EyeAgent-MainCore
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 2. Configure environment variables

Create `.env` in the project root and replace the examples. Never commit actual credentials.

```dotenv
# Agent models and speech recognition
DASHSCOPE_API_KEY=your_dashscope_key
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
ALIYUN_MODEL_NAME=qwen3.5-plus

# MySQL
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_NAME=eye_agent_db
DB_CHARSET=utf8mb4

# Compatible business backend; set both explicitly
BACKEND_API_URL=http://127.0.0.1:8081
BACKEND_API_TOKEN=your_backend_token

# Optional: LLM intent routing
SILICONFLOW_API_KEY=your_siliconflow_key
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
# Optional: PDF page vision analysis; this is a different variable
SILICON_FLOW_API_KEY=your_siliconflow_key
# Optional: research and compliance search
SEARCH1API_KEY=your_search1api_key
# Optional: attachment and research file storage
MINIO_ENDPOINT=127.0.0.1:9000
MINIO_ACCESS_KEY=your_minio_access_key
MINIO_SECRET_KEY=your_minio_secret_key
MINIO_BUCKET=research-files
```

`SILICONFLOW_API_KEY` and `SILICON_FLOW_API_KEY` are distinct variables in the code. The database pool also accepts `DB_POOL_MIN`, `DB_POOL_MAX` and `DB_POOL_MAX_CONN`. Features that use object storage may be unavailable without MinIO.

### 3. Prepare the database and backend

Create a database and an appropriately privileged user. Review the [checkpoint schema](scripts/create_checkpoint_tables.sql), then import it into the target database with a MySQL client that supports `DELIMITER`:

```bash
mysql -h 127.0.0.1 -u your_db_user -p eye_agent_db < scripts/create_checkpoint_tables.sql
```

This redirection example uses Bash. In PowerShell, use `cmd /c "mysql -h 127.0.0.1 -u your_db_user -p eye_agent_db < scripts/create_checkpoint_tables.sql"`. The script creates LangGraph tables and procedures; **it does not provide the complete business schema**. The separate [chat_message migration](scripts/alter_chat_message_add_status.sql) applies only to an existing compatible business table when the migration is needed. Supply the matching business schema, data and backend service separately. Database connection failure at startup does not stop the application, but dependent features may fail.

### 4. Run

From the project root:

```bash
python -m uvicorn main:app --host 127.0.0.1 --port 20602 --reload
```

- Chat UI: <http://127.0.0.1:20602/>
- Interactive API documentation: <http://127.0.0.1:20602/docs>
- Health endpoint: <http://127.0.0.1:20602/health>
- Research test page: <http://127.0.0.1:20602/research-test>
- Recommendation test page: <http://127.0.0.1:20602/recommendation-test>

Alternatively run `python main.py`, which listens on port `20602`. `/health` reports application status but does not verify all external dependencies.

## API example

`patient_id` must be a UUID; use a patient ID that exists in the backend for real workflows. Doctor requests may include `doctor_id` and `role: "doctor"`; identity must be established by trusted server-side authentication.

```bash
curl -X POST http://127.0.0.1:20602/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"My eyes feel dry. What should I do?","patient_id":"550e8400-e29b-41d4-a716-446655440000","role":"patient"}'
```

This example uses Bash syntax. On PowerShell, use `curl.exe` with appropriate JSON escaping or try the endpoint in `/docs`. The response includes fields such as `response`, `session_id`, `conversation_id`, `stage` and `agent_type`. Pass the returned session identifiers to continue a conversation. Use `POST /api/chat/stream` for SSE streaming.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/chat`, `/api/chat/stream` | Standard and streaming chat |
| GET | `/api/chat/{session_id}/state`, `/messages`, `/checkpoints`, `/agent-history` | State, messages, checkpoints and agent history; the last three paths share the `/api/chat/{session_id}` prefix |
| GET / DELETE | `/api/conversations`, `/api/conversations/{conversation_id}` | List, inspect and delete conversations; DELETE is available only on the detail path |
| POST | `/api/research/chat`, `/api/compliance/chat`, `/api/recommendation/chat` | Agent-specific chat; each also offers a `/stream` path |
| POST | `/api/upload` | Upload an image or PDF attachment |
| GET | `/api/users`, `/api/info`, `/api/export/{session_id}` | Patient list, API information and conversation export |

See the running application's `/docs` for complete parameters, speech endpoints and response schemas. Additional documents (in Chinese): [medical API](docs/AI医问通-接口文档.md), [attachments](docs/多模态附件接口文档.md), [speech recognition](docs/ASR语音识别接口文档.md), and [agent tools](docs/Agent工具API文档.md).

## Repository layout

```text
agents/          LangGraph graph, agent nodes, prompts and tools
application/     Application services and repository interfaces
domain/          Domain models, enums and exceptions
infrastructure/  MySQL, backend API, search, speech and object storage adapters
presentation/    FastAPI routes and request/response models
utils/           Routing, model configuration, input checks and document generation
scripts/         Database scripts
templates/       Jinja2 pages
static/          Frontend assets and test pages
docs/            Architecture and API documentation
main.py          Application entry point
```

## Deployment and security

This repository includes demonstration and integration code. Before deployment, implement reliable authentication, server-side authorization, sensitive data protection, auditing and network isolation. The current CORS configuration allows all origins, and a role field is not proof of identity. Explicitly configure the business backend URL and token; inspect and rotate any credentials that may have been exposed. Checkpoints use Python pickle serialization and must only be read from a trusted database. Do not commit real patient data, `.env` files or secrets, or post sensitive information in public issues.

## Troubleshooting

- **The service starts but chat fails:** check the DashScope key and model access, database, business backend and logs. `/health` does not check dependencies.
- **Conversation state is not saved:** check MySQL connectivity, business tables, checkpoint tables and application logs.
- **Routing or PDF analysis fails:** check `SILICONFLOW_API_KEY` and `SILICON_FLOW_API_KEY` respectively; their names differ.
- **Research search or files fail:** check Search1API and MinIO configuration and connectivity.

## Contributing

Issues and pull requests are welcome. Describe the problem and reproduction steps or the motivation for the change, follow the existing layered structure, and verify affected behavior. Never include secrets, personal health information or production data.

## License

This project is licensed under the [Apache License 2.0](LICENSE). Follow its terms when using, modifying or distributing the project. Third-party dependencies and services are subject to their own licenses and terms. PDF rendering uses [pypdfium2 / PDFium](https://github.com/pypdfium2-team/pypdfium2#licensing); retain its license and bundled dependency notices when redistributing binaries. Dependencies are not fully locked: review the actual resolved versions and transitive dependencies for each release.
