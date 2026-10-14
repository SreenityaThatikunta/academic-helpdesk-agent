# Implementation Plan: Academic Helpdesk Agent

See [PROBLEM_STATEMENT.md](PROBLEM_STATEMENT.md) for the full assignment.

## Tech Stack

| Component        | Choice                                                        |
| ---------------- | ------------------------------------------------------------- |
| Language         | Python 3.11+                                                  |
| Agent framework  | Google ADK (`google-adk`)                                     |
| LLM connector    | ADK `LiteLlm` → Ollama (`ollama_chat/qwen3:8b`, `ollama_chat/llama3.1:8b`) |
| Embeddings       | Ollama `nomic-embed-text` (fallback: `mxbai-embed-large`)     |
| Vector store     | ChromaDB (persistent, local `chroma_db/`)                     |
| Doc parsing      | `pypdf` / `pymupdf` for PDFs, `python-docx`, plain text/HTML  |
| Structured data  | CSV files + `pandas`                                          |
| Eval / report    | Python scripts + JSONL results, Markdown report               |

Everything runs locally and fits in 16GB RAM (8B model at Q4 ≈ 5–6GB, plus embeddings and Chroma).

## Target Repository Layout

```
academic-helpdesk-agent/
├── README.md
├── PROBLEM_STATEMENT.md
├── PLAN.md
├── requirements.txt
├── .env.example                 # MODEL, OLLAMA_API_BASE, EMBED_MODEL, paths
├── data/
│   ├── docs/                    # 20–30 source documents (PDF/DOCX/TXT/MD)
│   ├── csv/
│   │   ├── timetable.csv        # course_code, course_name, slot, days, time, room, semester
│   │   ├── courses.csv          # course_code, name, dept, level, credits, type (core/elective/OE), instructor_id
│   │   └── faculty.csv          # instructor_id, name, dept, email (dummy)
│   └── manifest.csv             # doc_id, filename, title, category, source_url, date
├── helpdesk/
│   ├── config.py                # env-driven settings
│   ├── ingest.py                # load → chunk → embed → store in Chroma
│   ├── tools/
│   │   ├── retrieval.py         # search_documents
│   │   ├── timetable.py         # lookup_course, get_slot, list_courses (filters)
│   │   ├── faculty.py           # get_instructor_email
│   │   ├── email_draft.py       # draft_email (writes to drafts/)
│   │   └── unanswered.py        # log_unanswered_question
│   ├── agents/
│   │   ├── single_agent.py      # baseline: one agent with all tools
│   │   ├── policy_agent.py
│   │   ├── schedule_agent.py
│   │   ├── email_agent.py
│   │   └── orchestrator.py      # root agent, routes via sub_agents / transfer
│   ├── prompts.py               # system instructions (citation + refusal rules)
│   └── cli.py                   # interactive chat: `python -m helpdesk.cli --mode multi`
├── agent/                       # ADK entry point for `adk web` / `adk run`
│   └── __init__.py / agent.py   # exposes root_agent
├── logs/
│   └── unanswered.jsonl         # questions referred to a human
├── drafts/                      # generated email drafts
├── eval/
│   ├── questions.jsonl          # 20–30 prompts with expected answer, source doc, category
│   ├── run_eval.py              # runs N repeats × M models, saves raw outputs
│   ├── score.py                 # accuracy, groundedness, refusal metrics
│   └── results/                 # per-run JSONL + summary CSV
└── report/
    └── REPORT.md                # findings
```

## Design Notes

**Citations.** Every chunk stored in Chroma carries metadata `{doc_id, title, filename, page, chunk_id}`. `search_documents` returns text *with* the metadata, and the system prompt requires answers to end with `Sources: [title, p. N]`. CSV-backed tools return a `source` field (e.g. `timetable.csv`) so schedule answers get cited too.

**Refusals.** Two layers:
1. The prompt rule: answer only from tool results; if nothing relevant comes back, say "I don't know" and call `log_unanswered_question`.
2. A retrieval guard: if the best chunk's similarity is below a tuned threshold, the tool returns `{"found": false}` so the model has nothing to make things up from.

**Counting questions** (e.g. "How many 400-level HSS electives?") are handled by structured filters on `courses.csv` (`list_courses(dept=, level=, type=)` returning a count), not by RAG. Small LLMs are bad at counting across chunks.

**Email drafting.** The email agent calls `lookup_course(code)` → `get_instructor_email(instructor_id)` → `draft_email(to, subject, body)`. The draft is saved to `drafts/<timestamp>.md` and shown to the student. Nothing is ever sent.

**Multi-agent routing.** The ADK root `LlmAgent` (orchestrator) has `sub_agents=[policy, schedule, email]` with clear `description`s so it can transfer control (`transfer_to_agent`). The orchestrator handles out-of-scope questions itself: it refuses and logs them.

**Qwen3 thinking mode.** Turn off thinking or strip `<think>` blocks (e.g. `/no_think` in the prompt) so tool calls and outputs stay clean.

---

## Task Breakdown

### Phase 0: Environment Setup
- [ ] Install Ollama and pull models: `qwen3:8b`, `llama3.1:8b`, `nomic-embed-text`
- [ ] Create `requirements.txt` (`google-adk`, `litellm`, `chromadb`, `ollama`, `pandas`, `pypdf`, `python-docx`, `python-dotenv`, `rich`)
- [ ] Create `.env.example` and `helpdesk/config.py`
- [ ] Smoke test: a minimal ADK agent talking to Ollama through `LiteLlm`, including one tool call

### Phase 1: Data Collection (20–30 documents)
- [ ] Academic regulations (UG/PG rulebook: attendance, grading, makeup exams, leave)
- [ ] B.Tech curriculum / credit structure (core, PE, OE, HSS credit requirements)
- [ ] Course catalogue / course descriptions for a few departments
- [ ] Current semester time table (slot chart + course-slot mapping)
- [ ] Course registration guidelines / academic calendar
- [ ] Recent office orders / circulars (3–5)
- [ ] Faculty directory (replace real data with dummy names/emails)
- [ ] Record every file in `data/manifest.csv` (title, category, source URL, date)
- [ ] Build `timetable.csv`, `courses.csv`, `faculty.csv` from those documents
- [ ] Make sure the example questions in the problem statement are answerable from the data (Autonomous Systems slot, CSL7570 instructor, HSS 400-level electives, OE credits, Major exam attendance)

### Phase 2: RAG Pipeline
- [ ] `ingest.py`: loaders for PDF/DOCX/TXT that keep page numbers
- [ ] Chunking (~500–800 tokens, ~100 overlap, split on headings/sections where possible)
- [ ] Embed with Ollama and upsert into a persistent Chroma collection with metadata
- [ ] Make ingestion repeatable (stable chunk IDs; `--reset` flag)
- [ ] Quick retrieval check: top-k results for 10 sample questions look right
- [ ] Tune the similarity threshold used for refusals

### Phase 3: Tools
- [ ] `search_documents(query, k)` → chunks + citation metadata, or `found: false`
- [ ] `lookup_course(code_or_name)` → course row (fuzzy match on name)
- [ ] `get_slot(course)` → slot, days, time, room
- [ ] `list_courses(dept, level, type, semester)` → matching courses + count
- [ ] `get_instructor_email(course_code | instructor_name)` → name, email
- [ ] `draft_email(to, subject, body)` → saves the draft and returns its path + text
- [ ] `log_unanswered_question(question, reason)` → appends to `logs/unanswered.jsonl`
- [ ] Unit tests for each tool (pure Python, no LLM)

### Phase 4: Single-Agent Baseline
- [ ] System prompt with scope, tool-use policy, citation format and refusal rule
- [ ] `single_agent.py`: one `LlmAgent` with all tools
- [ ] `cli.py` REPL + `adk web` entry point
- [ ] Manually check the 5 example questions + the 2 out-of-scope ones

### Phase 5: Multi-Agent Version
- [ ] Policy agent (tools: `search_documents`, `log_unanswered_question`)
- [ ] Schedule agent (tools: `lookup_course`, `get_slot`, `list_courses`, `search_documents`)
- [ ] Email agent (tools: `lookup_course`, `get_instructor_email`, `draft_email`)
- [ ] Orchestrator root agent with `sub_agents` and a routing/refusal prompt
- [ ] Handle mixed questions (e.g. "what's the leave rule, and email my CSL7570 instructor")
- [ ] `--mode single|multi` switch in the CLI and the eval runner

### Phase 6: Evaluation
- [ ] Write `eval/questions.jsonl` with 20–30 prompts, each tagged with category (`policy`, `schedule`, `count`, `email`, `out_of_scope`), expected answer and expected source doc
  - [ ] about 8 policy, 6 schedule/count, 4 email, 6 out-of-scope, 2–3 multi-intent
- [ ] `run_eval.py`: run every question × N=3 repeats × each model (qwen3:8b, llama3.1:8b) × each mode (single, multi); save raw responses, tool calls, routed agent and latency
- [ ] `score.py` metrics:
  - [ ] **Accuracy**: key facts match (rule-based check, then manual review of borderline cases)
  - [ ] **Groundedness**: cited doc matches the expected source
  - [ ] **Refusal correctness**: out-of-scope questions refused + logged; no false refusals on in-scope ones
  - [ ] **Routing accuracy** (multi-agent): routed to the right sub-agent
  - [ ] **Consistency**: questions whose answers changed across repeats
- [ ] Summary table (CSV + Markdown) per model × mode

### Phase 7: Report and Docs
- [ ] `README.md`: setup, model pulls, ingestion, running CLI / `adk web`, running eval, repo layout
- [ ] `report/REPORT.md`:
  - [ ] Architecture diagram (single vs multi-agent) and tool list
  - [ ] Dataset description (documents, CSVs, how personal data was anonymized)
  - [ ] Results tables: accuracy, groundedness, refusals, routing, per model/mode
  - [ ] Questions with unstable answers across runs, and why
  - [ ] Error analysis (retrieval misses, wrong routing, hallucinated citations)
  - [ ] Limitations and future work
- [ ] Final pass: fresh clone → follow the README → everything runs on a 16GB machine

---

## Final Deliverables Checklist

- [ ] 20–30 real documents collected (personal data replaced with dummy values)
- [ ] RAG pipeline using a local Ollama embedding model + ChromaDB
- [ ] Tools: vector search, time table/course CSV lookup, instructor email lookup, email draft writer
- [ ] Unanswered-question log for human follow-up
- [ ] Answers cite their source document
- [ ] Out-of-scope questions get an "I don't know"
- [ ] Single-agent baseline working via ADK + LiteLLM + Ollama (8B model)
- [ ] Multi-agent version: orchestrator → policy / schedule / email agents
- [ ] Runs on a 16GB RAM laptop
- [ ] 20–30 evaluation prompts (`eval/questions.jsonl`)
- [ ] Metrics reported: accuracy, groundedness, correct refusals
- [ ] Comparison across at least 2 LLMs
- [ ] Questions whose answers changed across multiple runs documented
- [ ] README with setup and usage instructions
- [ ] Report with findings
- [ ] Everything committed and pushed to GitHub
