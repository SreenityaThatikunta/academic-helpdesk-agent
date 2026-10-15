# Progress Log

A running log of what was done in each phase of [PLAN.md](PLAN.md), with decisions and issues along the way.

---

## Phase 0: Environment Setup

**Date:** 2026-10-14

### What was done
- **Machine check:** macOS, Apple Silicon (arm64), 16 GB RAM. Ollama 0.34.2 is already running as the desktop app (`localhost:11434`).
- **Models pulled with Ollama:**
  - `qwen3:8b` (5.2 GB), the primary chat model
  - `llama3.1:8b` (4.9 GB), the comparison chat model
  - `nomic-embed-text` (274 MB) was already installed and is the embedding model
- **Python environment:** created `.venv` with **Python 3.12** using `uv`. The system Python is 3.14, which is too new for some dependencies (chromadb / onnxruntime wheels), so 3.12 is pinned for the project.
- **`requirements.txt`** added: `google-adk`, `litellm`, `chromadb`, `ollama`, `pandas`, `pypdf`, `pymupdf`, `python-docx`, `python-dotenv`, `rich`, `pytest`.

### Issues
- The first `uv pip install` timed out fetching from PyPI because it was competing for bandwidth with the ~10 GB model download. Retried with `UV_HTTP_TIMEOUT=300`.
- The second attempt also failed: the `onnxruntime` wheel (a chromadb dependency) timed out mid-download. Retrying in a loop (up to 3 attempts) with `UV_HTTP_TIMEOUT=600` and fewer concurrent downloads.
- Added so far: `.env.example` / `.env`, `helpdesk/config.py` (env-driven settings), `scripts/smoke_test.py` (embedding call + ADK agent with one tool call), and the `logs/`, `drafts/`, `data/docs/`, `data/csv/` folders.

- The third attempt (retry loop, `UV_HTTP_TIMEOUT=600`, 4 concurrent downloads) succeeded.

### Smoke test result
`scripts/smoke_test.py` embeds a string with `nomic-embed-text` (768-dim), then runs an ADK `LlmAgent` via `LiteLlm` with one tool, `get_course_slot`.
| Model | Tool called? | Final answer |
|---|---|---|
| `qwen3:8b` | yes, `get_course_slot({'course_code': 'CSL7570'})` | **Leaked its reasoning** ("Okay, the user asked for…") into the answer, even with `/no_think` |
| `llama3.1:8b` | yes, same call | Clean: "The slot for CSL7570 is D." |

**To fix in Phase 4:** turn off qwen3 thinking properly (Ollama `think: false` via LiteLLM extra args) or strip the reasoning text from its output.

### Status
- [x] Ollama models pulled
- [x] `requirements.txt`
- [x] Dependencies installed (google-adk 2.12.0, chromadb 1.5.9; `openpyxl` added later for the xlsx files)
- [x] `.env.example` + `helpdesk/config.py`
- [x] Smoke test: ADK agent → LiteLLM → Ollama, with one tool call (`scripts/smoke_test.py`)

---

## Phase 1: Data Collection

**Date:** 2026-10-14

### What was done
- Started looking for public IIT Jodhpur documents (the example question CSL7570 and the Jodhpur references point to IIT Jodhpur). Categories: UG/PG regulations, B.Tech curriculum, course catalogue, time table / slot chart, registration guidelines / academic calendar, academic office circulars, faculty directory.
- The first research pass was cut off by a dropped connection, so it was restarted.
- Plan: list the candidate documents with their URLs and sizes, confirm the list, then download them to `data/docs/` and record them in `data/manifest.csv`.

### Research findings (2026-10-14)
I checked 30 candidate public documents on iitj.ac.in / intranet.iitj.ac.in. Nothing has been downloaded yet.

**Access quirks**
- The iitj.ac.in TLS certificate chain is broken, so fetching needs `curl -k`.
- The site returns 404 for HEAD requests, so file sizes were checked with a 1-byte ranged GET.

**Coverage of the example questions**
| Question | Public source? |
|---|---|
| Attendance requirement for the Major exam | Yes: Academic Regulations §4.1.9 + Circular 51 (Jul 2024 amendment; it is a scanned PDF and needs OCR) |
| Open Elective credits for a B.Tech | Yes: **10 credits** (Regulations Table 11.3, CSE curriculum credit table) |
| Slot for Autonomous Systems | Partly. The course exists as **CSL7650** (M.Tech AI curriculum), but no current-semester time table is public. The only slot chart is a 2023 first-year XLSX. |
| 400-level HSS electives floated this semester | No. The HSS catalogue/bouquets exist, but there is no "floated this semester" list. |
| Instructor / email for CSL7570 | No. CSL7570 does not appear in any public CSE document, and the faculty directories load dynamically. |

**Gaps to fill:** the current-semester time table / course offerings and the instructor-course mapping are not public (they are on the ERP / intranet). These need synthetic CSVs that are clearly labelled as synthetic and built from the real course catalogue, with dummy faculty emails.

**Other issues:** several PDFs (Circulars 51/52, the 2026 CSE curriculum, the 2026-27 academic calendar) have no usable text layer and need OCR or PyMuPDF.

### Document download (public)
With the user's approval, 20 public files were downloaded with `curl -k` into `data/docs/` (01–20), and 4 web pages were saved to `data/raw_html/` (21–24). All are listed in `data/manifest.csv`.

### Filling the gaps from the IITJ inbox
The current time table, which courses were floated, and who teaches what are not public. With the user's approval, I searched their IITJ Gmail (`/u/2` in Chrome) and downloaded 5 more files:
| File | From |
|---|---|
| `25_Finalized_Courses_List_AY2026-27_SemI.xlsx` | Registration Cell email "Finalized Courses and Slot System for Semester-1 of AY 2026-27" (Google Sheet export). 20 department tabs: code, name, L-T-P, credits, **instructor, slot** |
| `26_Slot_System_AY2026-27_SemI.xlsx` | Same email: slot → day/time grid, **minor exam slot schedule**, time table committee, classroom allocation |
| `27_Circular_2283_Course_Registration.pdf` | "Main Registration for Semester-I, AY 2026-27" attachment (scanned) |
| `28/29_IH2/IH3_Courses_Syllabus_AY2026-27_SemI.pdf` | "Course preferences for IH category" attachments: the humanities electives offered this semester |

Also found: the Google Classroom post for this assignment (course **CSL7650 Autonomous Systems**, Gaurav Harit, **due Oct 30**).

### Structured data (`scripts/build_csvs.py` → `data/csv/`)
- `courses.csv`: **599 course offerings across 20 departments.** Columns: code, name, level (100–900), L-T-P, credits, instructor, slot, category, offered_for, remarks, source. Each department tab had a different header layout, so columns are matched by header-name patterns.
- `slots.csv`: 61 rows, 34 slots → day + time (theory and lab slots).
- `faculty.csv`: 349 unique instructors, each with an ID and a **dummy email** (`firstname.lastname@iitj.example`; `.example` is a reserved domain, so nothing can be sent to it by accident).

### OCR (`scripts/ocr_scanned.py` → `data/ocr/`)
Three PDFs had no text layer: Circulars 51, 52 and 2283. They were OCR'd with tesseract at 300 dpi, with page breaks kept so citations can still give page numbers. The OCR quality is good.

### Findings that matter for the agent and the eval
1. **Attendance (Major exam).** Circular 51 (08 Jul 2024) *supersedes* §4.1.9 of the 2019 regulations. Under the old rule, a student below 75% could still sit exams but needed at least a C. Under the new rule, attendance must not fall below 75%. Below that, without a valid reason, the instructor can recommend de-registration. Absence of 4+ weeks means automatic semester withdrawal. The agent must cite the circular, not the 2019 rule.
2. **Autonomous Systems** = **CSL7650**, slot **E** (Tue/Thu/Fri 11:00–11:50), instructor Gaurav Harit.
3. **CSL7570 does not exist** in this semester's list (the closest is MTL7570, a Materials course). It is probably a typo for CSL7650 in the assignment. Decide in Phase 6 whether the eval expects "course not found" or a suggestion of CSL7650.
4. **400-level Humanities electives.** The SoLA tab has only **LAL4070** Health Economics. The IH3 syllabus also lists **LAL4850**. So the answer is 1 or 2 depending on the source. Document this in the answer key.
5. **Open Elective credits for B.Tech = 10** (Regulations Table 11.3, CSE curriculum).

### Status
- [x] 29 documents collected (24 public + 5 from the IITJ inbox), listed in `data/manifest.csv`
- [x] `courses.csv`, `slots.csv`, `faculty.csv` built (dummy emails)
- [x] Scanned PDFs OCR'd
- [x] Answers to all 5 example questions confirmed in the data
- Repo is **private**, so the source documents are committed. Faculty names are kept; every email address in the CSVs is a dummy.

### Decisions (user, 2026-10-14)
- **CSL7570 is a typo for CSL7650** (Autonomous Systems). When a course code isn't found, the agent should *suggest the closest match* ("Did you mean CSL7650 Autonomous Systems?") rather than just refusing. The email answer key uses CSL7650 / Gaurav Harit.
- **400-level Humanities electives this semester = 2**: LAL4070 (Health Economics) and LAL4850, using the IH3 syllabus together with the SoLA tab.

### Exam time tables
- **Minor exams (Sem I 2026-27):** the slot-wise tentative schedule is in the `Examination` tab of the slot-system sheet. It is now `data/csv/exam_schedule.csv`: 45 rows (date, time window, slot) for 15–20 Sep 2026. Example: slot E → 18 Sep 2026, 08:00–10:00 AM.
- **Exam windows** from the Academic Calendar AY 2026-27 (D17): Minor 15–20 Sep 2026; **Major 19–26 Nov 2026**; Sem II Minor 16–21 Feb 2027, Major 22–29 Apr 2027; Summer Minor 04–06 Jun 2027, Major 10–13 Jul 2027.
- **Not yet available:** a slot-wise **Major** exam time table, and the final (non-tentative) minor schedule. The latter may be in the "Details of Minor Examinations of Semester-I AY 2026-27" email (Examination cell, 1 Sep).

### Exam time tables found in the IITJ inbox (2026-10-14)
With the user's approval, 2 more files were downloaded (bringing the total to **31 documents**):
| File | From |
|---|---|
| `30_Major_Exam_Timetable_AY2026-27_SemI.xlsx` | Examination Cell email "Time-Table for Major Examinations of Semester I, AY 2026-27" (Aug 17). Tentative, 19–26 Nov 2026, 3 sessions a day (09–12, 14–17, 18–21); 24 Nov is an institute holiday. |
| `31_Examination_Guidelines_2024.pdf` | Examination Cell email "Details of Minor Examinations… Sem I 2026-27" (Sep 1): "New Guidelines for Institute Examination (2024)" Google Doc, exported to PDF |

- I **skipped** the "Offline/Online Student Mapping" and "Examination Venue" sheets linked in the same email, because they contain other students' names and roll numbers.
- `exam_schedule.csv` now has **89 rows: 45 Minor + 44 Major**. Example: slot E (CSL7650) → Minor 18 Sep 2026 08:00–10:00 AM; **Major 22 Nov 2026 09:00 AM–12:00 PM**.
- **Exam guidelines (D31), the key policy for make-up emails:**
  - A **make-up exam** is only for a missed **Minor**. The form (Annexure A) must reach the Office of Academic Affairs **within 10 days** of the missed exam.
  - An **I grade** is only for a missed **Major**. The form must arrive **before the last day of the exams**.
  - Valid reasons: medical (a certificate issued or verified by the IITJ Medical Officer, Annexure B format; prescriptions and bills are not accepted), or personal (a competitive exam, interview or academic event; apply *before* the exams, recommended by the instructor and HoD).
  - Make-up / I-grade exams are held by the instructor before the end of that semester's Major exams.
  - The email says the last date for Sem I 2026-27 make-up applications was 30 Sep 2026.
- I could not open the Sep 29 "Regarding Major Examinations Slot Clashes" email (Student Grievance cell). Its preview only points back to the same exam slot system, so nothing is missing.

---

## Phase 2: RAG Pipeline

**Date:** 2026-10-14

### What was built
- **`helpdesk/ingest.py`**: reads `data/manifest.csv`, loads each document page by page, chunks it, embeds with `nomic-embed-text`, and stores the result in a persistent ChromaDB collection (`chroma_db/academic_docs`, cosine distance).
  - **Loaders:**
    - PDF via PyMuPDF, one page at a time. Scanned PDFs use the OCR text in `data/ocr/`, keeping page breaks.
    - HTML via a small `html.parser` subclass that drops nav/script/header/footer and **renders tables as `a | b | c` rows**. Without that, the OE credit table (Table 11.3) came out as one cell per line and lost its meaning.
    - XLSX: one "page" per sheet, rows rendered as `a | b | c`.
  - **Personal data:** the time-table committee, minor/specialization coordinator and classroom allocation sheets are skipped. Any email that isn't an office mailbox (`examhelp@`, `registration@`, …) is masked as `[faculty email: use lookup]`, so the only email addresses the agent sees are the dummy ones from `faculty.csv`.
  - **Chunking:** about 1800 characters (~450 tokens) with a 250-character overlap. Splits prefer paragraph, then line, then sentence boundaries.
  - **Contextual header:** every chunk starts with `[<title> | <date> | page N]` (see the iterations below for why).
  - **Metadata per chunk:** `doc_id`, `title`, `filename`, `category`, `date`, `status`, `source` URL, `page`, `chunk`. Chunk IDs are stable hashes, and re-ingesting a document first deletes its old chunks. `--reset` rebuilds everything.
  - Uses nomic's task prefixes: `search_document:` for chunks, `search_query:` for queries.
  - **Result:** 1,139 chunks from 31 documents in about 40 s on the laptop.
- **`helpdesk/rag.py`**: `search(query, k)` returns chunks with a ready-made `citation` ("<title>, p. N" or "sheet '<name>'"), plus `doc_id`, `date`, `status` and `distance`.
  - **Hybrid retrieval:** a dense Chroma top-30 and a BM25 top-30 (implemented in ~30 lines, no extra dependency) merged with reciprocal rank fusion (k=60).
  - **Superseded documents** (D04 2018 B.Tech regulations, D18 2025-26 calendar, D20 2023 slot chart; marked in the manifest's new `status` column) get **0.5× weight**, not removed.
  - **Refusal guard:** if the best dense distance is above `MAX_DISTANCE` (**0.35**), it returns `found: false` with no results.
- **`scripts/check_retrieval.py`**: 18 in-scope questions with their acceptable source documents, plus 9 out-of-scope or unanswerable questions. Reports hit@1, hit@k and the distance spread, and tries several thresholds.
- **`tests/test_ingest.py`**: 6 unit tests (chunk sizes and overlap, HTML table rendering, email masking, tokenizer keeps course codes, BM25 exact-code match). All pass.

### Retrieval iterations (k=5)
| Version | hit@1 | hit@5 | Notes |
|---|---|---|---|
| Dense only | 9/18 | 17/18 | Course codes and short terms (IH2, LAL4070, PE) blurred; the 246-chunk 2022 HSS concept note crowded out the IH2 syllabus |
| + BM25 hybrid (RRF) | 9/18 | 15/18 | Worse: chunk text rarely names its document ("IH2", "PG"), so keywords had nothing to match |
| + contextual chunk header (title, date, page) | 10/18 | 16/18 | LAL4070 → IH3 syllabus now ranks first; IH2 syllabus enters the top 3 |
| + superseded docs at 0.5× | 11/18 | 16/18 | 2018 regulations stop outranking the 2019 ones |
| + corrected answer key | **12/18** | **17/18** | See "B.Tech max duration" below |

### Findings
- **B.Tech maximum duration:** I had expected the 2018 regulations (D04, "8 years") to be the only source. Retrieval instead returned the 2019 regulations §11.4: **14 registered semesters**, which supersedes the 8-year rule. Retrieval was right and the answer key was wrong. This is a good example of why superseded documents need handling.
- **PhD maximum duration is not stated in any document.** The "maximum of 6 years" text is about a different degree mode. The question moved to the unanswerable list. The agent should say it doesn't know and log the question, but retrieval still returns plausible-looking chunks (distance 0.21), so the **LLM has to decide whether the retrieved text actually answers the question**.
- **The distance threshold cannot separate out-of-scope questions on its own.** In-scope best distances were 0.15–0.27; out-of-scope ones were 0.21–0.43 ("restaurant near IIT Jodhpur" scored 0.26 against the regulations page). At 0.35, every in-scope question is kept and 4 of 9 out-of-scope ones are rejected. **The rest of the refusals must come from the prompt rule** ("answer only if the retrieved text answers the question; otherwise say you don't know and log it"). This goes into the Phase 4 system prompt.
- **Program-specific curricula can outrank institute-wide rules.** "How many PE credits for B.Tech?" returns the AIDE curriculum (D10) ahead of the institute Table 11.3 (18 PE). This is a known weakness; the prompt should ask which programme when it matters.
- **Attendance:** the 2019 regulations page (old §4.1.9, superseded) ranks first and Circular 51 second. Both reach the LLM, and each result carries its `date`, so the prompt must say "**when sources conflict, follow the most recent circular**".

### Status
- [x] Loaders for PDF / OCR text / HTML / XLSX, with page numbers and sheet names
- [x] Chunking + contextual headers + metadata
- [x] Embedding + ChromaDB (repeatable; `--reset`)
- [x] Hybrid retrieval + superseded down-weighting
- [x] Retrieval check (12/18 at rank 1, 17/18 in top 5)
- [x] Threshold tuned (0.35), with its limits written down for Phase 4

---

## Phase 3: Tools

**Date:** 2026-10-15

### Data change: course list rebuilt from the Classroom Allocation sheet
While checking how the tools would answer the "400-level Humanities" question, I found that **LAL4850 Introduction to Climate Change Economics** (IH3 syllabus) was missing from `courses.csv`. So were the IH2 courses (LAL3030/3040/3060/3080/3090/3130). The slot-system workbook (D26) has a **Classroom Allocation** sheet I had skipped. It is the *final* allocation: **738 rows / 612 course codes**, with uniform columns (code, subject, L-T-P, credits, slot, department, instructor, students registered, classroom) and full instructor names ("Alok Ranjan" rather than just "Alok").
- `courses.csv` is now built **from the allocation first** (738 rows). The Finalized Courses list (D25) adds category / offered_for where the codes match, plus **83 courses that aren't in the allocation**. Total: 821 rows across 25 departments.
- New columns: `slot_code` (`G (Wed)` → `G`, `R (Thu 6 - 7 PM)` → `R`) for joining with `slots.csv` and `exam_schedule.csv`; `classroom`; `registered`.
- The Co-Instructor column is dropped because it mixes staff ID numbers into names. The 26 sections of OAE1010 (first-year Engineering Design, no department) are labelled "Institute (common course)".
- `faculty.csv` was rebuilt: **312 instructors** (full names now merge duplicates), still with dummy `@iitj.example` emails.
- **The 400-level Humanities count of 2 now comes straight from the data**: LAL4070 Health Economics (Alok Ranjan, slot D, LHC 204) and LAL4850 Introduction to Climate Change Economics (Souryabrata Mohapatra, slot D, LHC 2 103).

### Tools (`helpdesk/tools/`)
All are plain functions with type hints and Google-style docstrings (ADK builds the tool schema from these), and all return dicts with a `source` field for citations.
| Tool | File | What it does |
|---|---|---|
| `search_documents(query, top_k=5)` | `retrieval.py` | Hybrid search (Phase 2). Returns `found`, plus passages with `citation`, `date` and `status` (`superseded`) |
| `lookup_course(course)` | `timetable.py` | By code (normalises `csl 7650` / `CSL-7650`) or by name (substring, then all-words match). Sections are merged into one record (instructors, slots, classrooms). **If not found, returns "did you mean" suggestions**: closest codes, same department prefix first |
| `get_slot(course)` | `timetable.py` | Slot + weekly class times (from `slots.csv`) + classroom + **minor and major exam date/time** (from `exam_schedule.csv`) |
| `list_courses(department, level, course_type)` | `timetable.py` | Counts **distinct** courses floated this semester. Department aliases ("Humanities"/"HSS"/"Liberal Arts" → SoLA, …); level "400"/"4" → course numbers 4xxx |
| `get_instructor_email(course_or_instructor)` | `faculty.py` | Course → instructors → dummy email, or an instructor name → email. Unknown course codes return the same suggestions |
| `draft_email(to, subject, body, cc="")` | `email_draft.py` | Validates the addresses and saves `drafts/<timestamp>_<subject>.md` with a "NOT SENT" header. Returns the draft text and `sent: false` |
| `log_unanswered_question(question, reason)` | `unanswered.py` | Appends `{id, timestamp, question, reason, status: open}` to `logs/unanswered.jsonl` and returns a ticket id. `read_unanswered()` is a helper for humans and the report |

### Example questions through the tools
- "Slot for Autonomous Systems?" → **CSL7650, slot E**, Tue/Thu/Fri 11:00–11:50, LHC 106, Gaurav Harit; Minor 18 Sep 2026 08:00–10:00; Major 22 Nov 2026 09:00–12:00 (tentative)
- "400-level electives floated by Humanities?" → **2** (LAL4070, LAL4850)
- "Email the instructor of CSL7570" → not found; **suggestions: CSL7650 Autonomous Systems** (first), CSL7560, CSL7350
- "Instructor of CSL7650" → Gaurav Harit, `gaurav.harit@iitj.example`
- "OE credits for a B.Tech" (`search_documents`) → Academic Regulations 2019, p. 16–17 (Table 11.3) among the top 3. The AIDE curriculum also appears, which is the programme-specific problem noted in Phase 2.

### Tests
`tests/test_tools.py`: 15 tests covering code normalisation; code and name lookups agreeing; CSL7570 → CSL7650 suggestion; get_slot for Autonomous Systems (slot, weekly times, major exam date); Humanities 400-level = 2; unknown department → 0; dummy instructor email by course and by name; draft saved with "NOT SENT" and bad addresses rejected; unanswered log appends JSONL; and **every tool builds an ADK `FunctionTool` declaration**. Together with the Phase 2 tests: **21/21 pass**.

### Status
- [x] `search_documents`, `lookup_course`, `get_slot`, `list_courses`, `get_instructor_email`, `draft_email`, `log_unanswered_question`
- [x] Unit tests for every tool (pure Python, no LLM)

### Decision update (user, 2026-10-15): "Humanities" = IH (Institute Humanities)
This **replaces** the earlier "400-level Humanities = 2" decision.
- "Humanities" / "HSS" / "IH" now means **every course that counts as IH**: all SoLA courses (including the Digital Humanities and Economics groups) **plus** the IH2/IH3 bouquet courses taught by other departments, i.e. the six AIDE economics courses AIL4070, AIL6010, AIL6110, AIL7160, AIL7320, AIL7380.
- New `courses.csv` column `ih_group` (IH2/IH3), filled by `build_csvs.py` from the course codes in the IH2/IH3 syllabus PDFs (D28/D29), so the tag can be traced to its source. All 15 IH codes exist in this semester's allocation.
- `list_courses(department="Humanities")` → **60 courses** (54 SoLA + 6 AIDE IH).
- **"How many 400-level electives has Humanities floated?" → 3**: LAL4070 Health Economics (Alok Ranjan, D), LAL4850 Introduction to Climate Change Economics (Souryabrata Mohapatra, D), **AIL4070 Fundamentals of Economics** (Souryabrata Mohapatra, I; AIDE, IH3). The eval answer key uses 3.
- Tests updated: Humanities 400-level = 3, plus a new test that IH2/IH3 tags come from the syllabi and that untagged SoLA courses still count as Humanities. **22/22 pass.**

### D32: previous year's IH list (user-provided, kept as outdated)
- The user pasted the Registration Cell email of **25 Mar 2025** listing the IH-2 and IH-3 courses. That is the list for **Semester I, AY 2025-26 (the previous year)**, not the current semester. Instructors and slots differ (e.g. LAL3030 was Rachel Philip / N, now Bhaskar Kumar Kakati / K). Five of its courses are not offered this semester: LAL3070, LAL3110, LAL3120, **LAL4090** Health and Development, AIL7120.
- **Decision (user): keep it as an outdated document.** Saved as `data/docs/32_IH_Course_List_AY2025-26_SemI.txt` (with a header that says it is outdated) and added to the manifest as D32, `status=superseded`, date 2025-03-25. Added a `.txt`/`.md` loader to `ingest.py`. Now 32 documents → 1,141 chunks.
- It does **not** feed `courses.csv`. The current-semester counts are unchanged: Humanities (IH) = 60 courses, 400-level = 3. Using the old list would have wrongly added LAL4090.
- Check: "What IH3 courses are offered this semester?" → all top 5 results come from the 2026-27 IH3 syllabus (D29). The superseded D32 is down-weighted and doesn't push in.
- Open point: **AIL7310 Machine Learning for Economics** was IH3 last year and is offered this semester (AIDE, slot G), but it is not in the 2026-27 IH3 syllabus, so it is **not** tagged IH.

### D33: current IH course list (user-provided)
- The user pasted the Registration Cell email of **1 Jun 2026**: the official IH2 (6 courses, 5th-semester students) and IH3 (9 courses, 7th-semester students) lists for **Semester I, AY 2026-27**, with credits, L-T-P, instructor and slot. Saved as `data/docs/33_IH_Course_List_AY2026-27_SemI.txt` (pipe tables), manifest D33, `status=current`.
- Checked against our data first: all 15 courses match `courses.csv` on IH group, slot and instructor, and the IH-tagged set was exactly this list.
- `build_csvs.py` now takes `ih_group` **from D33** instead of pulling course codes out of the syllabus PDFs (D28/D29 stay as the syllabus documents). The rebuilt CSVs are byte-identical, which confirms the two sources agree.
- Re-ingested: 33 documents → 1,143 chunks. "Which IH3 courses are offered this semester?" now cites the IH Course List (D33) first.
- Unchanged: Humanities (IH) = 60 courses; 400-level = 3 (LAL4070, LAL4850, AIL4070). 22/22 tests pass.

---

## Phase 4: Single-Agent Baseline (in progress)

**Date:** 2026-10-15

### Fixing the qwen3 reasoning leak (carried over from Phase 0)
Tested ways to pass options through ADK `LiteLlm(..., **kwargs)` → LiteLLM → Ollama, with a one-tool agent asked "What is the slot for CSL7650?":
| Setting | Time | Final answer |
|---|---|---|
| default | 19.1 s | "Okay, the user asked for the slot of CSL7650. I called the get_course_slot function…" (**reasoning leaked**) |
| `think=False` | **1.9 s** | "The slot for CSL7650 is E." |
| `think=False, num_ctx=8192` | 6.1 s | "The slot for CSL7650 is E." |
| `reasoning_effort="none"` | 5.5 s | "The slot for CSL7650 is E." |

**Decision:** pass Ollama's `think=False` for qwen3. It is clean and about 10× faster than leaving thinking on. It is only sent to qwen3, because Ollama rejects `think` for models without thinking support (llama3.1).

### Done so far
- `helpdesk/llm.py`: `make_model(name)` returns `LiteLlm` with `num_ctx=8192` (the system prompt + 7 tool schemas + 5 retrieved passages overflow Ollama's default context), `temperature` (default 0.2), and `think=False` for qwen3.
- `config.py` / `.env.example`: new `TEMPERATURE`, `HELPDESK_MODE` (single | multi) and `CURRENT_SEMESTER` (included in the prompt so "this semester" has a meaning).

- `helpdesk/prompts.py`: the system prompt built from reusable blocks, so the Phase 5 sub-agents can share them:
  - `SCOPE`: IIT Jodhpur academic matters only; the current semester is included.
  - `GROUNDING`: never answer from the model's own knowledge. Out of scope or not found → the exact sentence "I don't know the answer to that. I've forwarded your question to the academic office." plus `log_unanswered_question`. **A passage on a related topic is not an answer.** **The newest source wins**; superseded documents are used only as a fallback; amendments override the base rules. End every answer with `Source: <citation>`. Keep answers concise.
  - `POLICY`: search, and search again with other wording before giving up. If the answer depends on the programme, give the institute-wide rule and flag it.
  - `SCHEDULE`: which tool for slot / lookup / counts. "Humanities" = IH. For an unknown code, ask "Did you mean CSL7650 (Autonomous Systems)?". Exam dates are tentative.
  - `EMAIL`: `get_instructor_email` → `draft_email`. Never invent an address. If the course isn't found, **don't draft**; offer the suggestion and wait. Formal body; placeholders for missing dates/name/roll number. Mention the make-up vs I-grade rule. Say the draft is NOT sent.
- `helpdesk/agents/`: `build_agent(mode, model)`, and `single_agent.py` with one `LlmAgent` holding all 7 tools.
- `helpdesk/runner.py`: a `Helpdesk` wrapper around ADK's `InMemoryRunner`. `ask()` returns a `Turn` with the answer, tool calls (agent, name, args), tool results, the **sequence of agents that produced events** (for routing accuracy in Phase 5), latency and any error. It strips stray `<think>` blocks. One long session for the CLI, `fresh=True` per question for the eval.
- `helpdesk/cli.py`: rich REPL (`/new`, `/quit`) that shows tool calls as they happen, `--ask` for a single question, `--mode` / `--model` overrides.
- `agent/academic_helpdesk/agent.py`: `root_agent` for the ADK dev UI (`adk web agent`).

- `scripts/manual_check.py`: runs the 7 assignment questions (5 in scope + 2 out of scope), each in a fresh session, and saves `eval/results/manual_<mode>_<model>.json`.

### Manual check, run 1 (single agent, qwen3:8b)
| Question | Tools called | Result |
|---|---|---|
| Attendance for the Major exam | **none** | ❌ Hallucinated "75%… Source: Academic Regulations, Page 12". It made up a citation without searching. |
| Slot for Autonomous Systems | `get_slot` | ✅ CSL7650, slot E, Tue/Thu/Fri 11:00–11:50, LHC 106, cited |
| 400-level Humanities electives | `list_courses(Humanities, 400, course_type="Elective")` | ❌ "0". `course_type="Elective"` filtered on the `category` column, which most departments leave blank |
| OE credits for a B.Tech | **none** | ❌ Hallucinated "12 credits" (correct: 10) |
| Email to the CSL7570 instructor | `get_instructor_email` | ✅ Not found → "Did you mean CSL7650 (Autonomous Systems)…? Please confirm" |
| Dining options | `log_unanswered_question` | ✅ Exact refusal sentence, logged |
| Reaching campus from the city | `log_unanswered_question` | ✅ Exact refusal sentence, logged |

**Problems found:**
1. **The model skips `search_documents` on policy questions** and answers from its own knowledge, with made-up citations. The rule "never answer from your own knowledge" wasn't strong enough for an 8B model.
2. **The `course_type` filter is a trap.** "Elective" is in the question, so the model passes it, but categories are only recorded for a few departments.

**Fixes after run 1:**
- The prompt now starts with a `TOOLS_FIRST` block: "YOU MUST CALL A TOOL BEFORE EVERY ANSWER", with a question-type → tool map and "Never write a Source: you did not get from a tool".
- `list_courses`: generic `course_type` values ("elective", "course"…) are ignored, with a note. Test added (23/23 pass).

### Manual check, run 2 (qwen3:8b)
| Question | Tools | Result |
|---|---|---|
| Attendance | `search_documents` | ⚠️ Searched, but answered with the **old** rule ("below 75% may still appear, needs ≥C"). Circular 51 quotes the "Existing policy" before the "Revised Policy", and the model used the wrong paragraph. It also cited 5 sources. |
| Slot | `get_slot` | ✅ |
| 400-level Humanities | `list_courses(..., course_type="OE")` | ❌ "0". The model now passes "OE" instead of "Elective". |
| OE credits | `search_documents` | ❌ "12 credits", taken from the **AIDE curriculum**, which outranks the institute-wide Table 11.3 (10) |
| Email CSL7570 | `get_instructor_email` | ✅ Suggests CSL7650 |
| Dining / transport | **none** | ⚠️ Correct refusal sentence, but **it didn't call `log_unanswered_question`** (regression) |

**Fixes for run 3:**
- Remove `course_type` from `list_courses` entirely. Categories aren't recorded for most departments, so an 8B model keeps using the filter wrongly. Counting questions are answered by department + level.
- **Make logging refusals deterministic in code** instead of relying on the prompt. An ADK `after_model_callback` notices the refusal sentence in the model's final answer and logs the question if the tool wasn't called during that turn (the tool sets a `temp:` state flag).
- Prompt: "circulars quote the existing policy before the revised one; only the revised policy applies"; "for degree credit requirements prefer the institute Academic Regulations (Table 11.3) over a single programme's curriculum unless the student names their programme"; "cite only the 1–2 sources you actually used".

**Fixes after run 2:** `course_type` removed from `list_courses`. Refusal guard `helpdesk/agents/guards.py::log_refusals` added as an `after_model_callback`; `log_unanswered_question` now takes ADK's injected `tool_context` and sets the `temp:unanswered_logged` flag. Prompt: revised-vs-existing policy rule, "use the Academic Regulations table for degree credits", cite only 1–2 sources.

### Manual check, run 3 (qwen3:8b)
| Question | Tools | Result |
|---|---|---|
| Attendance | `search_documents` | ❌ Still the old "may appear with ≥C" rule, now citing only Circular 51 |
| Slot | `get_slot` | ✅ |
| 400-level Humanities | `list_courses(Humanities, 400)` | ✅ **3** (it doesn't list the names) |
| OE credits | `search_documents` (once) | ❌ Still "12" from the AIDE curriculum; it didn't search again |
| Email CSL7570 | `get_instructor_email` | ✅ Suggests CSL7650 |
| Dining | `log_unanswered_question` | ✅, but **logged twice** (see below) |
| Transport | none | ✅ Refused; **the guard auto-logged it** ("auto-logged by academic_helpdesk: refused without calling the tool") |

**Root causes:**
- **Double logging:** qwen3 returned the refusal text *and* the `log_unanswered_question` call in the **same** response, so the guard fired before the tool ran. Fix: the guard ignores responses that contain a function call.
- **Attendance:** 3 of the 5 passages state the *old* rule: the 2019 regulations web page and PDF (§4.1.9), plus the "Existing policy" paragraph that Circular 51 quotes. The circular's "Revised Policy" starts 1,072 characters into the chunk and its de-registration bullets spill into a second chunk. Facing three statements of the old rule, the 8B model follows the majority.
- **OE credits:** curriculum chunks for one programme crowd the top 5.

**Fixes for run 4 (retrieval and data, not just the prompt):**
1. **Amendment register** `data/amendments.csv` (doc_id, text that identifies the passage, superseded_by, note). At ingestion, chunks containing the amended text get `status=superseded` and a header saying what replaces them. First entries: 2019 regulations §4.1.9 attendance (D01 PDF + D21 web page) → Circular 51. Circular 51 itself says "This policy supersedes the earlier policy in totality."
2. **Short documents stay whole:** a document of ≤ 3,200 characters is one chunk, so Circular 51's revised rule and its bullets stay together.
3. **Per-document cap in search results:** at most 2 chunks per document in the top k, so one curriculum can't fill all 5 slots.

**Fixes after run 3 (implemented):**
- Guard: ignores model responses that contain a function call, which fixes the double logging.
- `data/amendments.csv` + ingestion: chunks matching an amended passage get `status=superseded` and the header note `SUPERSEDED by <title>: <note>`. Exactly one chunk each in D01/D21 (old §4.1.9) is marked. New test.
- Documents of ≤ 3,200 characters are kept as **one chunk** (D02, D03, D27 → 1 chunk each; citations show "pp. 1-2"). Collection: 1,134 chunks.
- `rag.search`: at most **2 chunks per document** in the top k.
- Retrieval check after these changes: hit@1 12/18, **hit@5 18/18** (was 17/18).

### Manual check, run 4 (both models)
| Question | qwen3:8b | llama3.1:8b |
|---|---|---|
| Attendance | ✅ "≥75%; below 75% without valid reason → instructor may recommend de-registration" (Circular 51) | ✅ "should not fall below 75%" (Circular 51) |
| Slot | ✅ E, Tue/Thu/Fri 11:00–11:50, LHC 106 | ✅ E, LHC 106, + minor/major exam dates |
| 400-level Humanities | ✅ 3 (no names listed) | ✅ 3, lists LAL4070, LAL4850, AIL4070 |
| OE credits | ⚠️ 12 (AIDE curriculum) | ⚠️ 12 (AIDE curriculum; searched with `top_k=1`) |
| Email CSL7570 | ✅ Suggests CSL7650, waits for confirmation | ⚠️ Suggests CSL7650, but **also writes 3 inline drafts** (not saved) despite "don't draft" |
| Dining | ✅ tool called, logged once | ⚠️ **Wrote the tool call as JSON text** in the answer instead of calling it; the guard logged it |
| Transport | ✅ the guard logged it | ✅ tool called |
| Latency (avg) | ~8 s | ~14 s |

Both models logged exactly 2 unanswered questions (no duplicates).

### Open question: the OE credits answer key
This is **not a retrieval bug**: the documents disagree depending on the batch. Regulations 2019 Table 11.3 = **10**, CSE curriculum (pre-2026) = **10**, EE curriculum 2025+ = **12**, AIDE curriculum 2026+ (4 × 3 credits) = **12**. Both models answer 12 from the AIDE curriculum, and the prompt's "newest source wins" rule pushes them that way. Waiting for the user to decide the expected answer.

### Next fix
- The guard strips tool calls written as JSON text (`{"name": "...", "parameters": {...}}`) from llama3.1 answers.

**Fix after run 4:** the guard also strips tool calls written as JSON text (test added).

### Decision (user, 2026-10-15): OE credits → **ask the student**
For degree credit requirements (OE / PE / IH / total) the agent must **ask for the B.Tech programme (branch) and the year of joining before answering**, then answer from *that* curriculum. The eval expects a clarifying question to "How many OE credits do I need for a B.Tech?"; after "B.Tech CSE, joined 2023" it expects **10** (CSE curriculum, batches before 2026, p. 10).

To make the follow-up work:
- **Document-scoped search:** `search_documents(query, top_k, document="CSE Curriculum")` searches only documents whose title contains those words. When scoped, it skips the out-of-scope distance guard (that guard is for the whole collection; inside one curriculum the best match was 0.38, which hid the credit table) and the 2-per-document cap. Without scoping, the CSE credit table (p. 10, a table) never reached the top 5, because the AIDE curriculum's prose section "Open Elective (OE) Courses" matched the query better.
- Manifest: D09 renamed **"B.Tech CSE Curriculum (batches before 2026)"** so the agent can match it to a batch.
- Prompt: ask for programme + year; then search only that curriculum and check that its title covers the batch; never answer from another programme's curriculum; **never quote credit numbers that weren't retrieved**. My first version of this rule included example numbers (10/12), and qwen3 repeated them in its clarifying question, so they were removed.
- New test: the scoped search finds "Open Electives (OE) 10" in the CSE curriculum.

Two-turn check ("How many OE credits…?" → "I am in B.Tech CSE, joined in 2023."):
| | Turn 1 | Turn 2 |
|---|---|---|
| qwen3:8b | ✅ asks for branch + year (no tool call) | ✅ **10**, "B.Tech CSE Curriculum (batches before 2026), p. 10" |
| llama3.1:8b | ❌ answers directly (10, then 12 on a later run) | ❌ "12", citing p. 18, which doesn't support it |

### Manual check, run 5 (final)
**One more regression, from the new `document` parameter:** qwen3 used `document="Academic Regulations"` on its own for the attendance question. That excluded Circular 51, and it answered about make-up exams. **Fix:** the tool docstring and prompt now say to leave `document` empty unless the student named their programme, because amendments live in separate circulars. Re-check: attendance on qwen3 **3/3 correct** (≥75%, de-registration; Circular 51), with no document filter.

| Question | qwen3:8b | llama3.1:8b |
|---|---|---|
| Attendance for the Major exam | ✅ 75% / de-registration (Circular 51), 3/3 after the fix | ✅ 75% (Circular 51) |
| Slot for Autonomous Systems | ✅ CSL7650, E, Tue/Thu/Fri 11:00–11:50, LHC 106 | ✅ E, Tue/Thu/Fri, Gaurav Harit |
| 400-level Humanities | ✅ 3, lists all three with instructors and slots | ✅ 3 (no names) |
| OE credits | ✅ asks for programme + year | ⚠️ guessed CSE, searched only that, then refused + "check the website" |
| Email to the CSL7570 instructor | ✅ "Did you mean CSL7650…?", waits | ✅ "Did you mean CSL7650…?", waits (no inline drafts this time) |
| Dining | ✅ refused (logged by the guard) | ✅ refused, tool called |
| Transport | ✅ refused (logged by the guard) | ✅ refused (logged by the guard) |

### Observations for the report (Phase 6/7)
- **Prompt-only grounding is not enough for 8B models.** The fixes that worked best changed the *data and tools*: the amendment register, whole short circulars, a per-document cap, document-scoped search, removing the misleading `course_type` parameter. These held up better than extra prompt wording.
- **Fixes can cause regressions** (`course_type` "Elective" → "OE"; the `document` parameter used unprompted). This is why Phase 6 needs repeated runs.
- **Logging refusals has to be enforced in code:** qwen3 often writes the refusal sentence without calling the tool (≈50% here); the `after_model_callback` guard catches every case.
- **llama3.1 is weaker at multi-step instructions** (asking for clarification, not drafting before confirmation) and sometimes prints tool calls as text. qwen3 (with `think=False`) follows the rules better and is faster (~6 s vs ~13 s per question).

### Status
- [x] System prompt: scope, tools-first policy, citation format, refusal rule (+ newest-source, amendments, programme/batch clarification)
- [x] `single_agent.py`: one `LlmAgent` with all tools + the refusal/JSON-text guard
- [x] `cli.py` REPL (`--ask`, `--mode`, `--model`) + `adk web agent` entry point
- [x] Manually checked the 5 example questions + 2 out-of-scope on qwen3:8b and llama3.1:8b
- 25/25 unit tests pass
