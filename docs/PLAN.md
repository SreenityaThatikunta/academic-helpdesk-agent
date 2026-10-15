# Implementation Plan: Academic Helpdesk Agent

See [PROBLEM_STATEMENT.md](PROBLEM_STATEMENT.md) for the full assignment.

## Tech Stack

| Component        | Choice                                                        |
| ---------------- | ------------------------------------------------------------- |
| Language         | Python 3.11+                                                  |
| Agent framework  | Google ADK (`google-adk`)                                     |
| LLM connector    | ADK `LiteLlm` → Ollama (`ollama_chat/qwen3:8b`, `ollama_chat/llama3.1:8b`) |
| Embeddings       | Ollama `nomic-embed-text` (fallback: `mxbai-embed-large`)     |
| Vector store     | ChromaDB (persistent, local `data/index/`)                    |
| Doc parsing      | `pypdf` / `pymupdf` for PDFs, `python-docx`, plain text/HTML  |
| Structured data  | CSV files + `pandas`                                          |
| Eval / report    | Python scripts + JSONL results, Markdown report               |

Everything runs locally and fits in 16GB RAM (8B model at Q4 ≈ 5–6GB, plus embeddings and Chroma).

## Repository Layout (as built)

```
academic-helpdesk-agent/
├── README.md
├── requirements.txt, .env.example
├── docs/            PROBLEM_STATEMENT.md · PLAN.md · PROGRESS_LOG.md
├── data/
│   ├── raw/         33 source documents (PDF / XLSX / HTML / TXT)
│   ├── ocr/         OCR text for scanned PDFs
│   ├── csv/         courses · slots · exam_schedule · faculty (dummy emails)
│   ├── index/       ChromaDB vector store (generated, git-ignored)
│   ├── manifest.csv   one row per document (id, title, category, source, date, status)
│   └── amendments.csv passages superseded by a newer document
├── scripts/         data pipeline: ocr_scanned.py → build_csvs.py  (then python -m helpdesk.ingest)
├── helpdesk/
│   ├── config.py · llm.py · prompts.py · runner.py · cli.py
│   ├── ingest.py (load → chunk → embed → Chroma) · rag.py (hybrid dense + BM25 search)
│   ├── tools/       retrieval · timetable · faculty · email_draft · unanswered
│   └── agents/      single_agent · multi_agent · guards
├── agent/           ADK dev-UI entry point (`adk web agent`)
├── eval/            questions (build_questions.py → questions.jsonl) · run_eval · score · check_retrieval
│   └── results/     summary.md/.csv · review.md · scored.jsonl · runs/<mode>__<model>__r<k>/
├── tests/
└── logs/, drafts/   runtime outputs (unanswered questions, email drafts; git-ignored)
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
- [x] Install Ollama and pull models: `qwen3:8b`, `llama3.1:8b`, `nomic-embed-text`
- [x] Create `requirements.txt` (`google-adk`, `litellm`, `chromadb`, `ollama`, `pandas`, `pypdf`, `python-docx`, `python-dotenv`, `rich`)
- [x] Create `.env.example` and `helpdesk/config.py`
- [x] Smoke test: a minimal ADK agent talking to Ollama through `LiteLlm`, including one tool call

### Phase 1: Data Collection (20–30 documents)
- [x] Academic regulations (UG/PG rulebook: attendance, grading, makeup exams, leave)
- [x] B.Tech curriculum / credit structure (core, PE, OE, HSS credit requirements)
- [x] Course catalogue / course descriptions for a few departments
- [x] Current semester time table (slot chart + course-slot mapping)
- [x] Course registration guidelines / academic calendar
- [x] Recent office orders / circulars (3–5)
- [x] Faculty list (built from the finalized courses list; real names, dummy emails)
- [x] Record every file in `data/manifest.csv` (title, category, source URL, date)
- [x] Build `courses.csv`, `slots.csv`, `exam_schedule.csv`, `faculty.csv` from those documents
- [x] Make sure the example questions in the problem statement are answerable from the data (Autonomous Systems slot, CSL7650 instructor (CSL7570 in the assignment is a typo), HSS 400-level electives, OE credits, Major exam attendance)

### Phase 2: RAG Pipeline
- [x] `ingest.py`: loaders for PDF/DOCX/TXT that keep page numbers
- [x] Chunking (~450 tokens / 1800 chars, 250-char overlap, split on paragraph/line/sentence; title+date header on every chunk)
- [x] Embed with Ollama and upsert into a persistent Chroma collection with metadata
- [x] Make ingestion repeatable (stable chunk IDs; `--reset` flag)
- [x] Quick retrieval check: top-k results for 10 sample questions look right
- [x] Hybrid search (dense + BM25, reciprocal rank fusion) and down-weighting superseded docs
- [x] Tune the similarity threshold used for refusals (0.35)

### Phase 3: Tools
- [x] `search_documents(query, k)` → chunks + citation metadata, or `found: false`
- [x] `lookup_course(code_or_name)` → course row (fuzzy match on name; "did you mean" suggestions for unknown codes)
- [x] `get_slot(course)` → slot, days, time, room, minor/major exam dates
- [x] `list_courses(dept, level, type, semester)` → matching courses + count
- [x] `get_instructor_email(course_code | instructor_name)` → name, email
- [x] `draft_email(to, subject, body)` → saves the draft and returns its path + text
- [x] `log_unanswered_question(question, reason)` → appends to `logs/unanswered.jsonl`
- [x] Unit tests for each tool (pure Python, no LLM)

### Phase 4: Single-Agent Baseline
- [x] System prompt with scope, tool-use policy, citation format and refusal rule
- [x] `single_agent.py`: one `LlmAgent` with all tools
- [x] `cli.py` REPL + `adk web` entry point
- [x] Manually check the 5 example questions + the 2 out-of-scope ones

### Phase 5: Multi-Agent Version
- [x] Policy agent (tools: `search_documents`, `log_unanswered_question`)
- [x] Schedule agent (tools: `lookup_course`, `get_slot`, `list_courses`, `search_documents`)
- [x] Email agent (tools: `lookup_course`, `get_instructor_email`, `draft_email`)
- [x] Orchestrator root agent with `sub_agents` and a routing/refusal prompt
- [x] Handle mixed questions (e.g. "what's the leave rule, and email my CSL7650 instructor (CSL7570 in the assignment is a typo)")
- [x] `--mode single|multi` switch in the CLI and the eval runner

### Phase 6: Evaluation
- [x] Write `eval/questions.jsonl` with 20–30 prompts, each tagged with category (`policy`, `schedule`, `count`, `email`, `out_of_scope`), expected answer and expected source doc
  - [x] about 8 policy, 6 schedule/count, 4 email, 6 out-of-scope, 2–3 multi-intent
- [x] `run_eval.py`: run every question × N=3 repeats × each model (qwen3:8b, llama3.1:8b) × each mode (single, multi); save raw responses, tool calls, routed agent and latency
- [x] `score.py` metrics:
  - [x] **Accuracy**: key facts match (rule-based check, then manual review of borderline cases)
  - [x] **Groundedness**: cited doc matches the expected source
  - [x] **Refusal correctness**: out-of-scope questions refused + logged; no false refusals on in-scope ones
  - [x] **Routing accuracy** (multi-agent): routed to the right sub-agent
  - [x] **Consistency**: questions whose answers changed across repeats
- [x] Summary table (CSV + Markdown) per model × mode

### Phase 7: Report and Docs
- [x] `README.md`: problem statement, solution, features, quick start (setup, ingestion, CLI / `adk web`, eval), results, layout; technical deep dive in `docs/TECHNICAL.md`
- [x] `report/report.tex` → `report/report.pdf` (LaTeX):
  - [x] Architecture diagram (single vs multi-agent) and tool list
  - [x] Dataset description (documents, CSVs, how personal data was anonymized)
  - [x] Results tables: accuracy, groundedness, refusals, routing, per model/mode
  - [x] Questions with unstable answers across runs, and why
  - [x] Error analysis (retrieval misses, wrong routing, hallucinated citations)
  - [x] Limitations and future work
- [x] Final pass: fresh clone → follow the README → everything runs on a 16GB machine

---

## Final Deliverables Checklist

- [x] 20–30 real documents collected (personal data replaced with dummy values)
- [x] RAG pipeline using a local Ollama embedding model + ChromaDB
- [x] Tools: vector search, time table/course CSV lookup, instructor email lookup, email draft writer
- [x] Unanswered-question log for human follow-up
- [x] Answers cite their source document
- [x] Out-of-scope questions get an "I don't know"
- [x] Single-agent baseline working via ADK + LiteLLM + Ollama (8B model)
- [x] Multi-agent version: orchestrator → policy / schedule / email agents
- [x] Runs on a 16GB RAM laptop
- [x] 20–30 evaluation prompts (`eval/questions.jsonl`)
- [x] Metrics reported: accuracy, groundedness, correct refusals
- [x] Comparison across at least 2 LLMs
- [x] Questions whose answers changed across multiple runs documented
- [x] README with setup and usage instructions
- [x] Report with findings
- [x] Everything committed and pushed to GitHub
