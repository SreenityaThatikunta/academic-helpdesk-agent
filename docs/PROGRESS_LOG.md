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

---

## Phase 5: Multi-Agent Version (in progress)

**Date:** 2026-10-15

### Design
- **`helpdesk_orchestrator`** (root `LlmAgent`) with `sub_agents=[policy_agent, schedule_agent, email_agent]`. It routes with ADK's built-in `transfer_to_agent` (generated from `sub_agents`; each sub-agent's `description` is its area). Its only tool is `log_unanswered_question`, so it never answers academic questions itself: out of scope → refuse + log.
- **`policy_agent`**: `search_documents`. Handles regulations, credits/curriculum (including the programme/batch clarification), calendar, circulars.
- **`schedule_agent`**: `get_slot`, `lookup_course`, `list_courses`, `search_documents`. Handles course slots/timings/rooms/instructors/exam dates and course counts.
- **`email_agent`**: `get_instructor_email`, `lookup_course`, `draft_email`, plus `search_documents`. The plan listed only the first three; search was added so a make-up request can quote the make-up vs I-grade rule, which the email prompt asks for.
- Every agent also has `log_unanswered_question` and the `log_refusals` guard (`after_model_callback`), so a refusal is logged whichever agent makes it.
- **Mixed requests:** the orchestrator transfers to the agent for the first part. Specialists may transfer to a peer (ADK allows peer transfer by default) after finishing their part; each specialist's prompt has a "HANDING OVER" block listing the other specialists.
- One `LiteLlm` model object is shared by all four agents (same Ollama model, with `think=False` for qwen3).

### Prompts (`helpdesk/prompts.py`)
- `TOOLS_FIRST` is now built by `tools_first(*areas)` from one line per area, so each specialist only sees the routing lines for its own tools. The single-agent prompt is textually unchanged (5,683 characters).
- `AGENT_AREAS`: one description per specialist, used as the ADK `description` (what the router reads) and in the prompts.
- `orchestrator_instruction()` (2.1k characters): router rules (transfer, don't answer; mixed → first part; out of scope → refuse + log; greetings).
- `policy_instruction()` / `schedule_instruction()` / `email_instruction()` (3.8–4.2k characters): SCOPE + their own tools-first block + GROUNDING + their section + HANDING OVER.
- `build_agent("multi")` now returns the orchestrator; `--mode multi` works in the CLI and `manual_check.py`; `HELPDESK_MODE=multi` works for `adk web`.

### Manual check, multi run 1 (qwen3:8b)
**Routing: 7/7 correct.** Attendance → policy_agent; Autonomous Systems slot → schedule_agent; Humanities 400-level → schedule_agent; OE credits → policy_agent; CSL7570 email → email_agent; dining and transport → the orchestrator refused them itself.

**Answers:** same as single mode (attendance ✅ Circular 51; slot ✅ plus the minor/major exam dates; Humanities ✅ 3; CSL7570 ✅ "Did you mean CSL7650…?"; refusals ✅). **One exception:** for OE credits the policy_agent answered "12" (AIDE curriculum) instead of asking for the programme. 0/3 over repeated runs.

### Debugging "ask for programme/batch" in multi mode
| Attempt | Result (3 runs each) |
|---|---|
| Add a "clarify" exception line to the tools-first block (the generic "call search_documents FIRST" line came before the ask rule) | single 3/3 ask; **multi 0/3** (policy agent assumed `document="CSE Curriculum"`, copying the prompt's example) |
| Make the example generic (`"<their branch> Curriculum"`, "never assume the branch") | multi 0/3 (searched everything, answered 12) |
| Put a `STEP 0` clarification rule at the very top of the policy prompt | multi 0/3 |
| Dumped the policy agent's actual LLM request | After a transfer ADK (a) **appends its own transfer instructions to the end of the system prompt** ("If you are the best to answer the question according to your description, you can answer it… call `transfer_to_agent`…"), (b) adds a `transfer_to_agent` tool, and (c) adds the router's `transfer_to_agent` call and its `None` result as extra "For context:" **user** messages after the student's question |
| `drop_transfer_noise` before_model_callback: remove (c) from specialists' context | multi 0/3 |
| **Isolation:** the policy prompt + tools as a standalone root agent | **3/3 ask** |
| Multi-agent with specialists that **can't transfer** (`disallow_transfer_to_parent/peers=True`; ADK then adds neither (a) nor (b)) | **3/3 ask** |

**Root cause:** ADK's auto-appended transfer instructions (a/b) sit at the end of the system prompt and tell the agent it may simply answer. For an 8B model these generic lines override the agent's own "ask first" rule.

### Design change
- **Specialists don't transfer** (`disallow_transfer_to_parent=True`, `disallow_transfer_to_peers=True`). Only the orchestrator routes. Because a specialist can't keep control, ADK's runner sends **every new student message back to the orchestrator**, which re-routes it, so multi-turn follow-ups ("I'm CSE, 2023") still work.
- **Mixed requests** go to the one specialist that can do all of it: email_agent and schedule_agent also have `search_documents`. Rule + email → email_agent; course slot + rule → schedule_agent. A specialist answers what it can and tells the student to ask anything else separately.
- `drop_transfer_noise` stays on the specialists (it removes bookkeeping messages that carry no information).
- The prompts' "HANDING OVER" blocks are replaced by an "outside your area" line, and the orchestrator's mixed-request rule changes as above.

**Implemented:** specialists have `disallow_transfer_to_parent/peers=True`; `_own_area()` replaces the HANDING OVER block; orchestrator rule 2 now sends mixed requests to the specialist that can do all of it. (An edit accidentally deleted `CLARIFY_FIRST`; the next run crashed and briefly showed stale JSON before this was noticed and fixed.) OE question in multi mode: **5/5 ask** for programme and year.

`manual_check.py` gained `CONVERSATIONS`, each run in one session: the two-turn OE flow and two mixed requests.

### Manual check, multi run 2 (qwen3:8b)
**Routing 11/11 correct**, including the OE follow-up being re-routed by the orchestrator to policy_agent, and both mixed requests going to the specialist that can do all of it.
| Request | Route | Result |
|---|---|---|
| Attendance | → policy | ✅ 75% / de-registration (Circular 51) |
| Slot | → schedule | ✅ |
| 400-level Humanities | → schedule | ✅ 3 |
| OE credits | → policy | ✅ asks for branch + year |
| Email to the CSL7570 instructor | → email | ❌ "I don't know the answer…" (it called `lookup_course`, which returned suggestions, but the generic refusal rule won) |
| Dining / transport | orchestrator | ✅ refused + logged |
| OE turn 2 "B.Tech CSE, joined 2023" | → policy (re-routed) | ✅ **10**, CSE curriculum p. 10 |
| Mixed: make-up rule + email (CSL7650, ill) | → email | ⚠️ `search_documents` → `get_instructor_email` → `draft_email` ✅ (draft saved), but the reply **didn't state the rule or show the draft**, and cited the course list instead of the exam guidelines |
| Mixed: major exam date + attendance rule | → schedule | ⚠️ date ✅ (22 Nov, tentative), but it **didn't search** for the attendance rule ("not provided… consult the regulations") |

**Fixes:**
- GROUNDING: "a course that isn't found but comes with suggestions is **not** an 'I don't know': offer the suggestions".
- The email and schedule specialists also get the `policy` tools-first line, so they search when part of the request is about a rule.
- EMAIL: if the student also asked a question, answer it first with its source, then show the full draft text.

**Fixes after run 2 (implemented):** GROUNDING exception (a course that isn't found but has suggestions → "Did you mean…", not a refusal); email/schedule specialists get the `policy` tools-first line; EMAIL answers the student's question first, then shows the full draft.

### Manual check, multi run 3 and follow-ups (qwen3:8b)
- CSL7570 → "Did you mean CSL7650…?" ✅. The make-up mixed request shows the full draft ✅.
- **Exam date + attendance:** the answer said "75%", but the tool calls showed **no `search_documents`**. The number came from the model's own knowledge (right by luck, ungrounded, cited to the exam timetable). **Fix:** a "MULTI-PART REQUESTS" rule in every specialist's `_own_area`: each part needs its own tool call; rule parts must call `search_documents` and get their own Source line. Re-check 3/3: `get_slot` + `search_documents` for both mixed requests.
- **But** the schedule agent then used `search_documents(document="Exam Guidelines")` and presented a passage about *online-exam camera rules* as "the attendance requirement" ❌. This is the **second time the `document` filter was misused**. **Fix:** schedule_agent and email_agent get `search_documents_all`, the same tool name for the model but **without** the `document` parameter (checked: ADK schema `['query', 'top_k']`). Only policy_agent keeps the scoped version, for curricula.
- **Make-up rule:** grounded, but taken from the **2019 regulations** (application to the Dean, make-up week of the *next* semester). The **2024 Examination Guidelines (D31)** changed this. Fixes:
  1. Amendment register: 2019 §8 make-up passages in D01, D21 **and the PG Regulations D05** (which repeat the same text) → superseded by D31.
  2. **New status `amended`**: a passage replaced by a specific named document is **dropped from search results**. Whole superseded documents (D04/D18/D20/D32) stay at 0.5× weight, because they are sometimes the only source.
  3. **Keyword-search spelling normalisation:** "make-up" / "make up" / "makeup" → `makeup` (and "re-exam" → `reexam`). The guidelines spell it "Makeup", so keyword search had never matched the query "make-up exam"; **D31 wasn't in the top 5 at all.** Now D31 pp. 10 and 8 rank 1st and 2nd. New test.
  - Retrieval check after these changes: hit@1 12/18, hit@5 18/18.
  - Make-up mixed request: multi **2/2** cite the 2024 Guidelines and save a draft. **Single mode 2/2 answers the rule but skips the email part.**

### Manual check, final (multi mode)
| Request | qwen3:8b | llama3.1:8b (before the last retrieval fixes) |
|---|---|---|
| Attendance | ✅ policy, Circular 51 | ❌ policy, mixed old and new rules ("allowed to appear… need C grade") |
| Slot | ✅ schedule | ✅ schedule, + timings, room, exams |
| 400-level Humanities | ✅ schedule, 3 | ✅ schedule, 3 with names |
| OE credits | ✅ policy, asks for branch + year | ❌ policy, "12" (AIDE) |
| Email to the CSL7570 instructor | ✅ email, "Did you mean CSL7650…?" | ✅ email, "Did you mean…?" |
| Dining / transport | ✅ orchestrator refusal | ✅ orchestrator refusal, tool called |
| OE turn 2 (CSE, 2023) | ✅ policy, 10 (CSE p. 10) | ✅ policy, 10 (cites p. 18) |
| Make-up rule + email | ✅ email, 2024 Guidelines + draft | ❌ **mis-routed to policy**, no draft |
| Exam date + attendance | ✅ schedule, 22 Nov + Circular 51 | ❌ schedule, skipped `get_slot` ("not mentioned") |
| **Routing** | **11/11** | 10/11 |

### Observations for the report
- **ADK's auto-appended transfer instructions override specialist prompts for 8B models.** This was the key multi-agent finding. Router-only transfer (specialists can't transfer) fixed it, and every new message still gets re-routed, so multi-turn works.
- **Multi-agent helps mixed requests:** with qwen3, the make-up rule + email request was fully handled in multi mode (2/2) but only half in single mode (2/2 skipped the email). Specialists have shorter, focused prompts.
- **Multi-agent costs latency:** every request takes an extra router call (~1–2 s) before the specialist starts. Out-of-scope refusals are *faster* (~0.9 s, the router answers directly).
- **Tool parameters that small models can misuse should be removed, not explained** (`course_type`, then `document` twice).
- **Conflicting versions of a rule are the main source of wrong-but-grounded answers.** An amendment register plus dropping amended passages worked better than prompt rules like "the newest source wins".

### Status
- [x] Policy agent (`search_documents` with document scoping, `log_unanswered_question`)
- [x] Schedule agent (`get_slot`, `lookup_course`, `list_courses`, `search_documents` (unscoped), `log_unanswered_question`)
- [x] Email agent (`get_instructor_email`, `lookup_course`, `draft_email`, `search_documents` (unscoped), `log_unanswered_question`)
- [x] Orchestrator root agent with `sub_agents` and a routing/refusal prompt
- [x] Mixed questions (routed to the specialist that can do all of it; each part has its own tool call + source)
- [x] `--mode single|multi` in the CLI, `manual_check.py`, `HELPDESK_MODE` for `adk web` (the eval runner in Phase 6 uses `build_agent(mode, model)`)
- 26/26 unit tests pass

---

## Phase 6: Evaluation (in progress)

**Date:** 2026-10-15

### Design decisions
1. **Question set (`eval/questions.jsonl`): 30 items** in 7 categories, close to the plan's mix:
   - policy (9): rules, regulations, calendar, syllabus; includes **one in-scope question that is not in the documents** (PhD maximum duration), to test honest refusal on academic topics
   - schedule (5): slot, instructor, classroom, exam date of a course; includes **one non-existent course code**
   - count (3): courses floated by department/level
   - email (4): drafts, an unknown course code (CSL7570 → suggest CSL7650), lookup by instructor name
   - out_of_scope (6): the 2 assignment examples + 4 more (weather, hostel, cricket, placements)
   - multi_intent (2): rule + email; exam date + rule
   - conversation (1, two turns): OE credits → clarifying question → "B.Tech CSE, joined 2023" → 10
   All 5 example questions from the assignment are included. **Every expected answer is checked against the data before it goes into the file** (tool output or document text), not written from memory.
2. **Each item records:** `expected_behavior` (answer | clarify | refuse | suggest | draft), `expected_answer` (human-readable), `must_include` (regex groups; all must match, alternatives inside a group), `must_not_include` (e.g. the superseded attendance rule), `expected_sources` (strings that must appear in the answer's citation), `expected_agent` (for routing in multi mode), and for drafts `expected_to` (recipient address).
3. **Runs:** 2 models (qwen3:8b, llama3.1:8b) × 2 modes (single, multi) × **3 repeats** = 12 runs of the set (≈ 372 question-turns). Each question gets a **fresh session**; the conversation item runs its turns in one session. Temperature stays at 0.2 (the configured default), so differences between repeats reflect realistic sampling, not forced randomness.
4. **Isolation:** each run writes drafts and unanswered-question logs to its own folder under `eval/results/<run>/`, by pointing `config.DRAFTS_DIR` / `config.UNANSWERED_LOG` there. The tools read config at call time, so this works without touching the real `logs/` and `drafts/`. "Logged" for a question = the run's unanswered log grew during that question. This counts the guard's auto-logging too, which tool calls alone would miss.
5. **Metrics (`eval/score.py`):**
   - **Accuracy:** the expected behaviour is met. answer → all `must_include` groups match, no `must_not_include`; refuse → the refusal sentence is present; clarify → asks for branch/programme and year, gives no credit number; suggest → mentions CSL7650 and does not call `draft_email`; draft → `draft_email` called with the expected recipient.
   - **Groundedness** (answer/draft items): the answer cites at least one expected source, **and** the relevant tool was called. An answer that is right but cites nothing, or cites the wrong document, is accurate but not grounded.
   - **Refusals:** correct-refusal rate on out-of-scope + unanswerable items; false-refusal rate on in-scope items; logging rate for refusals.
   - **Routing** (multi): the first specialist the orchestrator transfers to = `expected_agent` (orchestrator itself for out-of-scope).
   - **Consistency:** per model × mode × question, whether the correctness label differs across the 3 repeats, and whether the **key facts** in the answer (numbers, course codes, dates) differ. These are "the questions whose answers changed across runs" that the assignment asks for.
   - Latency (mean, p90) per model × mode.
6. **Manual review:** regex scoring can misjudge paraphrases. Every answer the script marks wrong gets read by hand. Overrides go in `eval/overrides.csv` with a reason, and the report shows the numbers both before and after review.

### Building the question set
- Checked candidate facts with the tools and search before writing them as expected answers: Health Economics = LAL4070, Alok Ranjan, slot D (Mon/Wed 11:00–11:50, Fri 10:00–10:50), LHC 204; Digital Society = LAL3080, Rachel Philip, slot N, LHC 105; CSE 700-level courses = 16; CSL9999 → not offered, no suggestions; Minor exams Sem I = 15–20 Sep 2026 (calendar + slot system); Circular 52 = one Minor and one Major exam per course; the Autonomous Systems syllabus covers multi-agent systems, navigation / obstacle avoidance, planning (CSE course details p. 58, M.Tech AI curriculum p. 7).
- **Dropped candidate:** "last date for course withdrawal". The calendar row reads "Course withdrawal from the instructors and adding courses in lieu of dropped courses: 10 Aug 2026", which is ambiguous, and the PG regulations say withdrawal is "typically within four weeks". An item with no clear ground truth would test the answer key, not the agent.
- **`eval/build_questions.py` → `eval/questions.jsonl`**, generated from a Python script so the regexes are readable and the file is always valid JSON. **30 items / 31 turns**: policy 9, schedule 5, count 3, email 4, out_of_scope 6, multi_intent 2, conversation 1 (2 turns). Expected behaviours: 18 answer, 7 refuse (6 out of scope + PhD duration), 4 draft (3 email + the make-up multi-intent), 1 suggest (CSL7570), 1 clarify (OE turn 1).
- **Routing ambiguity:** "When are the minor exams?" (P07) and "How many IH2 courses…?" (C02) can reasonably go to either the policy or the schedule agent (both have the needed tools). For these two, `agent` is a list and either route counts as correct.
- `must_not` guards against **superseded rules** (attendance: "C grade" / "allowed to appear"; make-up: "supplementary week"; B.Tech duration: "8 years"; OE for CSE: "12"), so a fluent but outdated answer scores as wrong.
- **`eval/run_eval.py`**: runs the item list for each (repeat, model, mode) in **repeat-major order**, so if the eval is interrupted every configuration has the same number of repeats. Each run gets its own folder `eval/results/<mode>__<model>__r<k>/` with `raw.jsonl` (one line per turn: answer, error, latency, agent path, tool calls, truncated tool results, `logged`, new drafts with their text), `drafts/` and `unanswered.jsonl`. Finished runs are skipped, so the eval can resume.
- Smoke test (qwen3, multi, P01/E02/O01): routing recorded, the E02 draft captured in the run's own `drafts/`, O01 `logged=True`. The smoke-test folder was deleted before the full run.
- **Full run started** in the background: 2 models × 2 modes × 3 repeats = 12 runs × 31 turns = 372 turns; console log in `eval/results/run.log`.
- **`eval/score.py`**: scores every turn (accuracy, the reason it was marked wrong, groundedness, refused, routed, key facts) and writes `results/scored.jsonl`, `results/summary.md` (headline metrics per model × mode, accuracy by category, a per-question k/3 table, consistency) and `results/review.md` (every turn scored wrong or ungrounded, with question, expected answer, route, tools and full answer, for manual review). `eval/overrides.csv` (run, id, turn, field, value, reason) is applied on top; `--no-overrides` gives the raw automatic scores.
  - Scoring rules as decided above. For draft items without a source requirement, "grounded" = the recipient came from `get_instructor_email` (not made up). Routing = the first non-router agent in the event sequence. Key facts = course codes + numbers (excluding years) or `REFUSED`.
- **`tests/test_score.py`**: 9 tests for the scoring rules (superseded content → wrong; right but uncited → not grounded; false refusal; clarification can't contain a credit number; suggest must not draft; draft recipient check; routing; key facts). **It caught a bug in `key_facts`**: "CSL 7650" also added 7650 to the numbers, and numbers kept a trailing space, so identical answers would have counted as "changed across runs". Fixed. 35/35 tests pass.

### Full run finished
12 runs × 31 turns = **372 turns, 0 errors**, ~78 min total. Per run: single qwen3 ≈ 4.8 min, multi qwen3 ≈ 6.3 min, single llama3.1 ≈ 7.4 min, multi llama3.1 ≈ 6.9 min.

### Automatic scores (before manual review; saved as `eval/results/summary_auto.md`)
| Config | Accuracy | Grounded | Correct refusals | False refusals | Refusals logged | Routing | Mean latency |
|---|---|---|---|---|---|---|---|
| single · qwen3:8b | 90% (84/93) | 73% (48/66) | 100% (21/21) | 0% | 100% | – | 9.5 s |
| multi · qwen3:8b | 87% (81/93) | 82% (54/66) | 100% (21/21) | 4% (3/72) | 100% | 94% (87/93) | 12.2 s |
| single · llama3.1:8b | 60% (56/93) | 42% (28/66) | 86% (18/21) | 1% | 100% | – | 14.2 s |
| multi · llama3.1:8b | 61% (57/93) | 55% (36/66) | 86% (18/21) | 0% | 100% | 94% (87/93) | 13.3 s |

**Red flags to check in the manual review before trusting these numbers:**
- **C02 (IH2 count) and M01 (make-up rule + email) score 0/3 in all four configurations.** When every configuration fails an item, the answer key or the scoring rule is the likely problem, so these are checked first.
- Cells where one config is 0/3 and another is 3/3 on the same model: multi qwen3 S02 (0/3 vs single 3/3), P08 (0/3 vs 3/3), single qwen3 P03 (0/3 vs multi 3/3).
- **The "facts changed" metric is noisy:** it counts every number in the answer, so incidental numbers (page numbers, extra times, citation dates) flag answers whose actual answer didn't change (e.g. single qwen3 S01: slot E in all three repeats, but the second-run answer omitted "30"). It needs to compare only the facts the question asks for.

### Manual review, part 1: answer-key and scorer corrections (apply to all configurations equally)
1. **P09 answer key was wrong. Correction to Phase 2.** PG Regulations §11.5 (D05 p. 22): "Ph.D. and M.Tech.-Ph.D. dual degree (Regular and Part-time/External) – **14 registered semesters**, which may include a maximum of 6 semesters of Registration kept Alive (RKA)". In Phase 2 I concluded "the PhD maximum duration is not stated in any document" from a regex that only looked for "maximum … *years*", and the text says "registered semesters". **llama3.1's "14 registered semesters, PG Regulations p. 22" was right, and qwen3's refusals were false refusals.** P09 is now an `answer` item (must include 14, source "PG Regulations"). The eval now has **6** refusal items (all out of scope) and no in-scope-but-undocumented item. `check_retrieval.py` was updated the same way (PhD question moved to in-scope, expected D05). *Lesson: an "it's not in the documents" claim needs a full-text read of the likely section, not a regex.*
2. **P06 regex was too literal.** llama3.1 answered "two examinations… Minor and Major (Circular 52)", the same fact as "one Minor and one Major", but the key required the literal words "one minor" / "one major". Now: must mention both minor and major, and must not say "two minor" / "three exams".

### Manual review, part 2: automatic "wrong" labels confirmed as genuine failures (no override)
- **C02 IH2 count, 0/3 everywhere:** every config called `list_courses(department="Humanities", level="5")`, reading "5th semester" as course level 5xx, got 0, and answered "no IH2 courses". This is model misreading **plus a tool gap**: `list_courses` cannot filter by IH group, and the IH2 list is only in D33. Kept as a failure; noted as a tool improvement for the report. Not fixed now: changing tools during scoring would be tuning on the test set.
- **M01 make-up rule + email:** single qwen3 **never called `draft_email`** (it wrote placeholder email text in the chat, "To: [Instructor's Email Address]"). Multi qwen3 saved a correct draft to gaurav.harit@ with the rule from the 2024 Guidelines, but **left out the 10-day deadline**, a key part of the rule asked for. Kept as wrong under the strict rubric; the report will note that multi was "correct except the deadline".
- **multi qwen3 S02 (who teaches Health Economics + classroom): the orchestrator returned an empty answer 3/3** (no transfer, no text). A new failure mode: the router produced an empty final response.
- **multi qwen3 P08 (Autonomous Systems topics): false refusal 3/3.** The policy agent searched, received the syllabus, then said "I don't know". The "a related passage is not an answer" rule is over-applied by the shorter specialist prompt (single qwen3: 3/3 correct).
- **single qwen3 P03 (how to apply for a make-up): no tool call 3/3.** It gave a generic procedure from its own knowledge ("contact the instructor…"); ungrounded and missing the 10-day / Office of Academic Affairs facts.
- **llama3.1 drafts (E02–E04): 0/3 in both modes.** Either it asks for details that were already given ("please provide the subject and the reason for your sick leave"), or it **writes the email in the chat without calling `draft_email`**, so nothing is saved for review.
- **llama3.1 P01 attendance: 0/3 in both modes.** It reads the *existing policy* paragraph that Circular 51 quotes ("allowed to appear… need at least a C grade") as the current rule, even though it is the same single chunk that also contains the revised rule.
- **Misroutes (multi):** qwen3 P09 → the router refused it itself (3/3); qwen3 S02 → empty router answer (3/3); llama3.1 P03 "how do I apply for a make-up exam" → email_agent (3/3; the word "apply" read as a request to write); llama3.1 M01 → policy_agent (3/3, so no draft).
3. **P04 regex missed a quoted grade.** multi llama3.1 wrote 'request for an **"I"** grade'; the pattern `\bI[ -]?grade` doesn't allow quotes. It now allows straight or curly quotes. Applied to all configurations.

### Manual review, part 3: groundedness labels checked
The 14 "correct but not grounded" turns were read one by one; all labels are fair:
- llama3.1 C01/C03: cited the **tool name** ("Source: list_courses") instead of a document.
- **single qwen3 P04: no tool call at all and an invented citation** ("Academic Regulations 2026-27, Section 4.3"). The answer happened to be right. This is the clearest **fabricated citation** in the eval.
- single qwen3 P08: only called `lookup_course`, then listed syllabus topics from its own knowledge with the course-list citation.
- single qwen3 / llama3.1 M02: **never searched** for the attendance half; "75%" came from the model's own knowledge (and it even says "refer to the official regulations").

### Scoring changes after the first look (no agent changes)
- **Consistency metric replaced.** "Facts changed" originally compared *every* number in the answer, so page numbers and extra timings flagged answers that hadn't really changed (e.g. qwen3 S01: slot E in all repeats). It now compares only **the facts the question asks for**: values matched by the `must_include` patterns (+ STALE if a superseded rule appears), refused vs answered, draft recipient + saved, asked vs not asked. The broad number list is kept in `scored.jsonl` (`all_numbers`). New test; 36/36 pass.
- `summary.csv` added next to `summary.md` (as the plan asked).
- **`eval/overrides.csv` is empty (header only).** Every scoring problem found was a rule-level error in the answer key (P09, P06, P04), fixed for all configurations alike, rather than a one-off override. `summary_auto.md` keeps the very first automatic scores for comparison.

### Final results (30 items / 31 turns × 3 repeats per config; `eval/results/summary.md`)
| Config | Accuracy | Grounded | Correct refusals (OOS) | False refusals | Refusals logged | Routing | Mean / p90 latency | Unstable correctness | Answer changed |
|---|---|---|---|---|---|---|---|---|---|
| single · qwen3:8b | **87%** (81/93) | 70% (48/69) | 100% (18/18) | 4% (3/75) | 100% | – | **9.5 s** / 19.9 s | 0/31 | **0/31** |
| multi · qwen3:8b | 84% (78/93) | **78%** (54/69) | 100% (18/18) | 8% (6/75) | 100% | 94% (87/93) | 12.2 s / 31.3 s | 0/31 | **0/31** |
| single · llama3.1:8b | 65% (60/93) | 46% (32/69) | 100% (18/18) | 1% (1/75) | 100% | – | 14.2 s / 27.6 s | 6/31 | 8/31 |
| multi · llama3.1:8b | 69% (64/93) | 62% (43/69) | 100% (18/18) | **0%** | 100% | 94% (87/93) | 13.3 s / 27.1 s | 1/31 | 3/31 |

Accuracy by category:
| Config | policy | schedule | count | email | out of scope | multi-intent | conversation |
|---|---|---|---|---|---|---|---|
| single · qwen3 | 78% | 100% | 67% | 100% | 100% | 50% | 100% |
| multi · qwen3 | 78% | 80% | 67% | 100% | 100% | 50% | 100% |
| single · llama3.1 | 52% | 100% | 67% | 25% | 100% | 17% | 50% |
| multi · llama3.1 | 70% | 100% | 67% | 25% | 100% | 0% | 50% |

### Findings
1. **Model matters more than architecture.** qwen3:8b (with `think=False`) beats llama3.1:8b by about 15–22 accuracy points in both modes, is faster in single mode, and is **completely deterministic in its answers across repeats** (0/31 changed, at temperature 0.2). llama3.1 changed its answer on 8/31 questions in single mode.
2. **Multi-agent: better grounding, slightly lower accuracy for qwen3.** Multi raised groundedness (qwen3 70→78%, llama3.1 46→62%) because the specialists search and cite more consistently. qwen3 accuracy dropped 3 points, from three failures specific to multi mode: an **empty router answer** (S02 3/3), a **specialist over-refusing** (P08 3/3), and the router refusing the in-scope PhD question itself (P09). For llama3.1, multi *raised* accuracy (+4) and stability (answer changed 8→3), but llama3.1 still can't call `draft_email` reliably in either mode.
3. **Out-of-scope refusals are solved:** 100% correct and 100% logged in all 4 configs (72/72), with no out-of-scope question answered. The remaining refusal problem is *false* refusals of in-scope questions (qwen3 multi 8%).
4. **Routing 94% for both models.** All misroutes are systematic (the same item 3/3), not random: qwen3 P09 → router refusal, S02 → empty router; llama3.1 P03 ("apply for a make-up") → email_agent, M01 → policy_agent.
5. **Superseded rules still catch llama3.1:** P01 attendance 0/6 (it reads the "existing policy" that Circular 51 quotes as the current rule); P06 once cited the 2019 "Minor 1, Minor 2, Major" scheme. qwen3 got P01 right 6/6.
6. **Hardest items:** C02 IH2 count (0/12 in every config: "5th semester" read as course level 5xx, plus `list_courses` can't filter by IH group); M01 rule + email (0/12: single mode skips the draft; multi qwen3 drafts correctly but leaves out the 10-day deadline).
7. **Fabricated citations still happen** when the model skips tools: qwen3 P04 cited a non-existent "Academic Regulations 2026-27, Section 4.3". Groundedness is a separate metric from accuracy for exactly this reason.
8. **The evaluation found an error in my own ground truth** (PhD maximum duration). Manual review of every "wrong" answer is necessary; automatic scoring alone would have penalised a correct model and rewarded false refusals.

### Status
- [x] `eval/questions.jsonl`: 30 prompts (31 turns), categories, expected answers, sources
- [x] `run_eval.py`: 3 repeats × 2 models × 2 modes; raw answers, tool calls, routing, latency, drafts, logging
- [x] `score.py`: accuracy, groundedness, refusals, routing, consistency (+ manual review: 3 answer-key fixes, 0 per-answer overrides)
- [x] Summary tables (`summary.md`, `summary.csv`, `review.md`)

---

## Cleanup: folder structure and redundant code

**Date:** 2026-10-15

**Principle:** nothing that changes the **evaluated agent's behaviour** is removed or rewritten (prompts, guards, tools, retrieval). Phase 6 measured exactly this code. Only dead code, superseded scripts and file locations change. Example: `drop_transfer_noise` showed no measurable effect while I was debugging, but it was active during the eval, so it stays.

### Dead / redundant code found (static check: names defined but never referenced)
| Item | Decision |
|---|---|
| `config.DOCS_DIR` | Remove: never read (the loaders use `manifest.csv` paths) |
| `tools/unanswered.read_unanswered()` | **Wire up instead of deleting**: the assignment says unanswered questions are "referred to the human". The CLI gets an `/unanswered` command that lists open questions, so the helper is used |
| `eval/score.py::key_facts` (+ `all_numbers` field + its test) | Remove: replaced by `asked_facts` for the consistency metric |
| `scripts/smoke_test.py` | Remove: Phase 0 check, now covered by the CLI (`--ask`), the unit tests and the eval |
| `scripts/manual_check.py` + `eval/results/manual_*.json` | Remove: Phase 4/5 development harness, replaced by `eval/run_eval.py --only <ids>` (same questions + conversations, with scoring). The manual-check results are summarised in this log and stay in git history |
| `scripts/check_retrieval.py` | Keep, **move to `eval/`**: it is the retrieval-only evaluation (hit@k, threshold) |

### New layout
```
docs/            PROBLEM_STATEMENT.md, PLAN.md, PROGRESS_LOG.md   (README.md stays at the root)
data/raw/        all 33 source documents (merges data/docs + data/raw_html; manifest paths updated)
data/ocr/        OCR text of scanned PDFs           (derived)
data/csv/        courses / slots / exam_schedule / faculty   (derived)
data/index/      ChromaDB vector store (was ./chroma_db; git-ignored)
data/manifest.csv, data/amendments.csv
scripts/         data pipeline only: ocr_scanned.py, build_csvs.py
helpdesk/        the package (agents/, tools/, ingest, rag, prompts, llm, runner, cli, config)
agent/           ADK dev-UI entry point (adk web agent)
eval/            questions + build_questions, run_eval, score, check_retrieval, overrides.csv
eval/results/    summary.md/.csv, summary_auto.md, review.md, scored.jsonl, run.log
eval/results/runs/<mode>__<model>__r<k>/   raw.jsonl, drafts/, unanswered.jsonl
tests/
logs/, drafts/   runtime outputs (git-ignored; local test leftovers deleted)
```

### Done
- Moved with `git mv` (history kept): docs → `docs/`; `data/docs/*` + `data/raw_html/*` → `data/raw/` (33 files; `manifest.csv` paths rewritten `docs/…`/`raw_html/…` → `raw/…`); `scripts/check_retrieval.py` → `eval/`; run folders → `eval/results/runs/`. `chroma_db/` → `data/index/` (`config.CHROMA_DIR` default, `.env`, `.env.example` and `.gitignore` updated).
- Removed: `scripts/smoke_test.py`, `scripts/manual_check.py`, `eval/results/manual_*.json`, `config.DOCS_DIR` (and `DOCS_DIR` from `.env*`), `score.key_facts` + its test.
- Added: CLI `/unanswered` lists the open questions forwarded to a human (uses `read_unanswered`).
- Deleted local runtime leftovers from development: 11 test drafts in `drafts/`, `logs/unanswered.jsonl` (git-ignored, not part of the eval; the eval keeps its own per-run copies). `.gitignore` gains `.pytest_cache/` and `data/index/`.
- Path updates: `scripts/build_csvs.py` and `scripts/ocr_scanned.py` read `data/raw/`; `run_eval.py` writes and `score.py` reads `eval/results/runs/`; `PLAN.md` now shows the layout as built (it replaces the original target layout).

### Checks that nothing changed in behaviour or results
- `scripts/build_csvs.py` from `data/raw/` → `data/csv/*` **byte-identical** (empty `git diff`).
- Ingestion dry run from the new manifest paths: **1,134 chunks from 33 documents** (same as before). The moved index answers queries ("attendance…" → Circular 51 first).
- `eval/score.py` reading `runs/` → `summary.md` / `summary.csv` **identical** to before the move.
- No references to the old paths remain outside this log (`git grep`). Unit tests: **35/35 pass** (36 before, minus the removed `key_facts` test).

---

## Phase 7: Report and Docs (in progress)

**Date:** 2026-10-15

### Deliverables (user request)
- `README.md` (root): problem statement, solution, features, quick start, results at a glance, repo layout.
- `docs/TECHNICAL.md`: technical deep dive (architecture, data pipeline, RAG, tools, agents and guards, prompts, evaluation method, design decisions and lessons).
- `report/report.tex`: the findings report in **LaTeX** (compiled to `report/report.pdf` if a TeX toolchain is available).
- Re-ran `eval/check_retrieval.py` for the final numbers (its question list changed in Phase 6 when the PhD question moved to in-scope): **hit@1 12/19, hit@5 18/19**; best distance in-scope 0.150–0.278 vs out-of-scope 0.264–0.430; the 0.35 threshold keeps 19/19 in-scope and rejects 4/8 out-of-scope.
- **`README.md`** written: problem statement (summarised, linking the full text), solution (mermaid architecture diagram; data, RAG, agents, evaluation in one paragraph each), features table, results at a glance, quick start (models, environment, ingest, CLI, ADK web, an example session, optional data rebuild, evaluation and tests), repo layout, data and privacy, license. `adk web agent` checked to exist in the venv (`.venv/bin/adk`).
- **`docs/TECHNICAL.md`** written: architecture (mermaid diagram + stack table), data pipeline (sources by category, OCR, CSV construction, amendment register), ingestion, retrieval (the 7-step algorithm + the iteration table + the threshold analysis), tools, LLM configuration, prompt blocks, agents (single, multi, **router-only transfer** with the isolation table, guards), runtime, evaluation method (including the answer-key corrections), results and analysis, design decisions and lessons, limitations and future work, configuration reference.
- Fact check while writing: I had written "llama3.1: 0/18 drafts saved". The data says llama3.1 **never called `draft_email` in any of its 24 draft turns** (E02–E04 + M01, 3 repeats, both modes); qwen3 saved drafts in 9/12 turns (single; it skips the draft in all three M01 runs) and 12/12 (multi). Corrected.
- **Report tables are generated, not typed:** `report/make_tables.py` reads `eval/results/scored.jsonl` and `eval/questions.jsonl` and writes `report/tables/{headline,category,chart,consistency,changed,perquestion,questions,misroutes}.tex`, which `report.tex` pulls in with `\input`. Re-running the eval + `score.py` + `make_tables.py` updates the report with no transcription step. The generated headline rows were checked against `summary.md` and match.
- **`report/report.tex`** (LaTeX, compiled to **`report/report.pdf`, 10 pages**): abstract; problem; data (sources table, structured data, amendment register); system design (TikZ retrieval-pipeline and multi-agent diagrams, tools table, agents, guards); engineering findings during development; evaluation method; results (headline table, accuracy/groundedness bar chart, category table, consistency, **the questions whose answers changed across runs**, routing errors); analysis; limitations and future work; conclusion; appendices with the full question set and per-question results.
- **Build issues and decisions:** the TeX install is **BasicTeX** (no `multirow`, no `pgfplots`). Rather than download packages (`tlmgr` would need admin rights), I removed the unused `multirow`, and `make_tables.py` now **generates the bar chart in plain TikZ** from the data. `\input` inside a `tabular` followed by `\bottomrule` gives "Misplaced \noalign", so the table bodies use an `\inputrows` macro (the primitive `\@@input`). Layout was checked by rendering every page to an image: Figure 1 was 30 pt too wide and its dashed arrow crossed a box (rerouted and scaled); the headline table was 55 pt too wide (scaled); the tools table floated away from its heading and the routing table overflowed the page (both made non-floating with `\captionof`). Final build: **0 overfull boxes**. LaTeX build files are git-ignored (`report/.gitignore`).
- The author line uses the name and roll number from the user's institute account (B23CS1072); flagged for the user to confirm.
- **README: all 9 emojis removed (user request).** Checked that the arrows (→) were not in the removed character range; TECHNICAL.md and the report had none.

### Final pass: fresh clone → follow the README
Cloned the GitHub repo into a scratch folder and followed the README steps, reusing the existing Python environment (so `uv pip install` itself was **not** re-run; Ollama models were already pulled):
- `pytest` **before** ingest: 1 failure. `test_search_scoped_to_document_finds_cse_oe_credits` needs the vector index (and Ollama), which a fresh clone doesn't have, and the README had claimed the tests need "no LLM". **Fix:** the test is skipped with the reason "needs the vector index: run `python -m helpdesk.ingest` (and Ollama)", and the README now says one test needs the index. Re-check: 34 passed, 1 skipped.
- `python -m helpdesk.ingest --reset` → **1,134 chunks from 33 documents** (same as the working copy) → `pytest`: **35/35 pass**.
- `python -m helpdesk.cli --mode multi --ask "What is the slot for the course Autonomous Systems?"` → routed to schedule_agent → "slot E… Source: 26_Slot_System…".
- `python eval/score.py` on the committed raw results → the same headline numbers as the report.

### Status
- [x] `README.md`: problem statement, solution, features, quick start, results, layout, data/privacy (no emojis)
- [x] `docs/TECHNICAL.md`: technical deep dive
- [x] `report/report.tex` → `report/report.pdf` (LaTeX, tables generated from the eval data)
- [x] Final pass: fresh clone → README steps → tests, ingest, CLI and scoring all work

### Report revision (user feedback, 2026-10-15; **not committed or pushed**, per the user)
1. Subtitle under the title removed.
2. Course name removed from the author line (name + roll number + date remain).
3. Table of contents removed.
4. No mention of the assignment or of the author's mailbox: the problem is stated as the goal; the 9 non-public sources are described as "official Registration and Examination Cell circulars sent to students".
5. **No em dashes** anywhere: source, generated tables, and PDF text (checked: 0). En dashes in number ranges (2026–27, 15–22) are kept.
6. Tone rewritten as a student group would write it: short sections, bullets and phrases, "we".
7. The "Questions whose answers changed across runs" table was removed (hard to read). The consistency summary table stays, plus two bullets with concrete examples. (`tables/changed.tex` is still generated but not used.)
8. Limitations cut to three points: regex scoring is unreliable → an LLM as judge; time tables are tentative and semester-specific → re-run the (idempotent) pipeline each semester; more models and comparisons.
9. No repository paths (no `data/…`, `.csv`, `.jsonl`, `drafts/`, `logs/`, `docs/`; the closing "Code and data" paragraph removed). Tool names stay, since they describe the system rather than file locations.
- Build: 10 pages, 0 overfull boxes; pages checked visually.

### Report revision 2 (user feedback; **not committed or pushed**)
- **Bullets vs paragraphs rebalanced** ("why does every section have bullets?"). Paragraphs now carry explanation and narrative: documents, privacy, amendment register, retrieval tuning, agents, every "what we learned" finding, the evaluation setup, consistency, the analysis, and the conclusion. Bullets are kept only for real lists: problem capabilities, structured tables, retrieval pipeline steps, the two transfer experiments, metric definitions, guards, the two hardest items, limitations. Itemize blocks went from about 20 to 8.
- **Abstract removed** (user request); the report starts with the Problem section.
- Build: 9 pages, 0 overfull boxes, no em dashes; pages checked visually.

### Report revision 3 (**not committed**)
- Authors set to the team: Sreenitya Thatikunta (B23CS1072), Arpita Deshmukh (B23CM1007), Prajna Agrawal (B23CS1054). Names stacked one per line. Still 9 pages, 0 overfull boxes.

---

## Post-evaluation fix: router refusing calendar questions (user-reported, 2026-10-15)

### What the user saw (multi mode, qwen3:8b, interactive CLI)
"When do we have vacation in this semester?", "Do we have any holidays during the semester?" and "Do we have any fests this semester?" were each **refused by the orchestrator itself** ("out of scope: campus vacation dates / campus events"), never routed to policy_agent. The reply was also a **paraphrase** ("The academic office has been notified…") instead of the fixed refusal sentence.

### Diagnosis
- **All three are answerable from the Academic Calendar AY 2026-27 (D17)**, which is indexed: semester break 2–8 Nov 2026, winter break 2–30 Dec 2026 (UG), holiday list on p. 10 (e.g. Dussehra 20 Oct, Diwali 8 Nov), Institute Foundation Day 2 Aug; fests as "No class days": Prometeo 2–4 Oct 2026, Varchas 30 Oct–1 Nov 2026 (Sem II: IGNUS 29–31 Jan 2027, Spandan 12–14 Mar 2027). Searching "vacation holidays semester…" returns calendar pp. 2 and 10 first, so retrieval is fine.
- **This is a router error**, the same kind as eval item P09 (PhD duration refused by the router): policy_agent's description only said "academic calendar dates", and the router's out-of-scope examples (dining, hostels…) made it judge "vacation" / "fests" as campus life.
- The paraphrased refusal also bypassed the wording rule; logging still happened because the tool was called.

### Fix
1. `AGENT_AREAS["policy_agent"]` names the calendar contents explicitly: holidays, vacations, semester breaks, no-class days and institute events / fests listed in the calendar, exam / registration / withdrawal dates.
2. The router's refusal rule is narrowed: refuse only requests **clearly unrelated** to academics or the academic calendar (food, hostels, transport, weather, placements, general knowledge). **If a question could be answered by the academic calendar, regulations or circulars, or if unsure, transfer it to policy_agent**, which can search and still refuse (and log) if nothing is found.
3. New guard `standardize_router_refusal` (router only): if `log_unanswered_question` ran in this turn and the router's final text is not the fixed refusal sentence, it is replaced by the sentence. This keeps refusals consistent in code.
- Tests: 36/36 pass (new test for the guard).

### Live check after the routing fix (multi, qwen3:8b)
| Question | Before | After the routing fix |
|---|---|---|
| Vacation this semester | router refused | ✅ policy_agent: semester break 2–8 Nov, winter break 2–30 Dec 2026 (2/2) |
| Holidays during the semester | router refused | ⚠️ routed, but lists **May/June 2026** holidays (before the Jul–Nov semester) |
| Fests this semester | router refused | ⚠️ routed, but policy_agent refuses (2/2) |
| 6 out-of-scope eval questions | refused | ✅ still refused, exact sentence (no over-correction) |
| P09 PhD maximum duration | router refused | ⚠️ routed now, but policy_agent refuses |
| S02 who teaches Health Economics | empty reply | ❌ still an empty router reply |

### Causes of the remaining problems
1. **Fests:** the calendar never says "fest"; it lists IGNUS / Prometeo / Varchas / Spandan as "No Class day" rows. Even the query "IGNUS Prometeo Varchas no class day" returns `found=False`: the not-found guard looks only at the dense distance and vetoes a strong keyword (BM25) match.
2. **Holidays:** the holiday list on calendar p. 10 covers the **calendar year** (01 May → 25 Dec 2026); the model listed everything instead of only Semester I dates.
3. **PhD:** the answer chunk (PG Regulations p. 22: "Ph.D. … 14 registered semesters") never reaches the top 5. The BM25 tokenizer splits "Ph.D." into `ph` + `d` (`d` is dropped), so it never matches the query token `phd`. This is the same kind of problem as "make-up" vs "Makeup".

### Fixes
1. **Document keywords:** new manifest column `keywords`, added to every chunk header of that document (like the title), so both dense and BM25 search can match a student's words that the document itself doesn't use. Filled for the three calendars (holidays, vacation, semester / winter break, fests / festivals / events with their names, no class days, exam and registration dates). Re-ingest needed.
2. **Abbreviation normalisation** in the BM25 tokenizer: Ph.D. / PhD → `phd`, B.Tech → `btech`, M.Tech → `mtech`, M.Sc → `msc` (no re-ingest needed; BM25 is built at query time).
3. **Prompt (POLICY):** when listing dated items "this semester", include only dates inside the current semester.

### Iteration on the fixes
- **First version of the keywords included the fest names** (IGNUS, Prometeo…) on *every* calendar chunk. Retrieval then returned calendar pp. 3/5 (no fest rows), because every chunk matched "fests" equally, and the header's names could also be mistaken for facts. **Changed:**
  - Keywords are now **generic** ("holidays; vacation; semester / winter / summer break; fests / festivals / cultural, technical and sports events; no class days; exam dates; registration dates").
  - New **query expansion** for keyword search maps student words to the documents' own terms: fest / festival → IGNUS, Prometeo, Varchas, Spandan, Inter IIT, no class day; vacation → semester / winter / summer break; holiday → holidays, class holiday.
  - **The keyword header is excluded from the BM25 index:** keywords help *find the document* (dense search), BM25 picks *the chunk inside it*. Before this, the holiday-list page (p. 10) was crowded out by other calendar pages that all carried "holidays" in their header.
- Result: fests → calendar pp. 7, 6 (the Prometeo / Varchas rows); vacation → p. 2 (breaks); holidays → p. 2 (breaks) + **p. 10 (holiday list)**. Retrieval check: hit@1 12/19, **hit@5 19/19** (was 18/19). Tests: 38/38 (+ degree-abbreviation and query-expansion tests).
- **PhD (P09) still open:** with the abbreviation fix the §11.5 chunk ("Ph.D. … 14 registered semesters") now contains the token `phd`, but it ranks 13th in BM25 (other PhD chunks mention the same words more often), and the p. 22 chunk that does reach the top 5 is §11.2. Left as a known retrieval-ranking limitation rather than tuning for one question.
- **S02 empty reply (also an eval failure) diagnosed:** the router model returns an **empty message**: no text, no tool call, `finish_reason=STOP`, no error, for both "Who teaches Health Economics this semester, and in which classroom?" and "Who teaches Health Economics?". The cause is in qwen3's output, not in parsing. **Fix: deterministic fallback** `route_empty_router_reply` (router `after_model_callback`). If the router returns nothing, the reply becomes a `transfer_to_agent` call chosen by keyword rules: write / email / draft → email_agent; slot / teach / instructor / classroom / timing / how many courses → schedule_agent; otherwise policy_agent (which can search and refuse properly).

### Final live check (multi, qwen3:8b; logs and drafts isolated in a temp folder)
| Question | Result |
|---|---|
| Vacation this semester (×2) | ✅ policy_agent: semester break 2–8 Nov 2026, winter break 2–30 Dec 2026 (Academic Calendar 2026-27) |
| Fests this semester (×2) | ✅ policy_agent: Varchas no-class days 30 Oct–1 Nov 2026 (calendar) |
| Holidays during the semester (×2) | ✅ routed + grounded; ⚠️ one run also listed Republic Day (26 Jan), outside the semester, despite the new rule |
| 6 out-of-scope eval questions | ✅ refused by the router with the exact sentence |
| S02 who teaches Health Economics | ✅ **fixed by the fallback**: schedule_agent, "Alok Ranjan, LHC 204" |
| P09 PhD maximum duration | ⚠️ routed now, but policy_agent says it's not in the documents (ranking issue above) |
| Regression: attendance, Autonomous Systems slot, Humanities 400-level, CSL7570 email, OE credits, minor exam dates | ✅ unchanged (Circular 51; E; 3; "Did you mean CSL7650"; asks branch + year; 15 Sep onwards) |
| E02 sick-leave email | ✅ draft to gaurav.harit@iitj.example, saved and shown |

- **Bug found by this check:** `draft_email` computed the draft path relative to the project folder, so it **crashed** when `DRAFTS_DIR` points outside the project (as `.env` allows; the check put drafts in a temp folder). The eval never hit it because it keeps drafts inside the repo. Fixed (falls back to the absolute path) + test.
- Note: `run_eval.py --only …` was **not** used for spot checks: a partial run would overwrite the committed run folders (`raw.jsonl` is rewritten when its line count doesn't match). A separate script was used instead.
- Also in this commit: the CLI now hides ADK's `context_cache_config` warning (logger `google_adk` set to ERROR; it concerns Gemini prompt caching, irrelevant for Ollama).
- **The evaluation numbers in the report and README are for the evaluated version** (before these fixes); the fixes are documented in TECHNICAL.md §15. Re-running the eval would measure them.
- Tests: **40/40 pass**.
- **Branch mix-up while committing (resolved):** another Claude session ("Agent UI with chat and graph") had switched this shared working copy to a new branch `web-ui` and started a web UI (`helpdesk/web/`). My `git add -A` committed this fix *and* its in-progress files onto `web-ui` (the push failed: no upstream). Undone with `git reset --soft HEAD~1` + unstage (no files touched, nothing pushed). With the user's agreement, **only my 12 files were committed onto `main` through a separate `git worktree`**, so the other session's checkout was not switched. Lesson: stage explicit paths, and check `git branch --show-current` before committing when other sessions may share the folder.

### Follow-ups from live use
- User asked to clear the earlier questions from `/unanswered`: the vacation / holidays / fests entries in the local `logs/unanswered.jsonl` were marked `status: resolved` (with a note) rather than deleted; `/unanswered` lists only open questions. The health-centre / campus-address question stays open (correctly out of scope).
- **Refusals no longer carry a source line:** policy_agent answered a refusal with "Source: I don't know the answer to that…". `log_refusals` (all agents) now strips any `Source:` line from a reply that contains the refusal sentence; normal answers keep theirs. Test added (41/41 pass).

### Why interactive answers took 23–74 s (user question)
Measured (eval average for multi qwen3 was 12.2 s per question, one fresh session per question):
- **Memory pressure:** 13.8 of 14 GB swap in use, 8.3 M swap-outs, 19% memory free (qwen3 with an 8k context takes 6.2 GB of unified memory; Claude, Chrome, the CLI and the web-UI server also running). Warm generation is fine (39 tok/s), but **prompt processing runs at ~240 tok/s**: a specialist prompt of ~4,400 tokens takes ~18 s before the first output token.
- **Three model calls per multi-agent question** (router → specialist tool call → specialist answer), each with a different system prompt, so Ollama can't reuse its prompt cache between them.
- **History growth (main cause in the CLI):** the CLI keeps one session, so every earlier question's retrieved passages and tool results are re-sent. Measured in one 4-question session: prompt tokens per call went from [1.3k, 1.9k, 4.7k] (36 s) to [4.5k, 4.8k, 7.8k] (50 s) to **[8.0k, 7.9k, 5.5k] (71 s)**. From the third question **the prompt hits the 8,192-token context window**, so Ollama truncates the oldest tokens, which is slow and can cut off the system instructions.

**Fix:** `trim_history` (before_model_callback, all agents in both modes). For earlier turns, keep the user's messages and the agents' text answers, so follow-ups like "how many for CSE?" still have context, but drop tool calls, tool results and the "For context: … called tool / tool returned result" transcripts. The current turn is untouched. The evaluation is unaffected (fresh session per question; the one two-turn item has no tool results in its first turn).
- **First version of `trim_history` was wrong and was not shipped:** it removed old tool calls *and* results. Measured: fast (71 s → 4–7 s), but after the first question **the specialist stopped calling tools** (2 model calls instead of 3) and answered from its own knowledge with made-up facts and citations ("Diwali 25 October", an invented "IITJ Tech Fest 23–25 October", "Academic Regulations, p. 12"). The model imitated a history in which answers carried a `Source:` line but no tool use was visible.
- **Final version:** earlier turns keep their tool *calls*, user messages and agent answers; each old tool *result* is replaced by a placeholder ("result omitted from history; call the tool again if you need it"), including ADK's "tool returned result" transcripts. Test updated (42/42).
- **Measured, same 4-question session:**

| Turn | Before (calls' prompt tokens → time) | After |
|---|---|---|
| 1 semester end | 1.3k / 1.9k / 4.7k → 36 s | 1.3k / 1.9k / 4.7k → 20 s |
| 2 holidays | 4.5k / 4.8k / 7.8k → 50 s | 1.7k / 2.0k / 5.1k → 27 s |
| 3 fests | **8.0k / 7.9k** / 5.5k → 71 s (context full) | 2.4k / 2.3k / 5.8k → 31 s |
| 4 attendance | 5.6k / 5.8k / 5.0k → 66 s | 3.0k / 2.6k / 5.5k → 24 s |

  Every turn now calls `search_documents` again and stays grounded (fests → Varchas; attendance → Circular 51). Prompts still grow slowly (by the length of earlier answers); `/new` resets them.
- Remaining time per question (~20–30 s here vs 12 s in the eval) is mostly memory pressure: prompt processing at ~240 tok/s while the machine swaps. Practical advice: close unused apps and the second helpdesk process (web UI server), use `/new` between unrelated topics, or `--mode single` (one model call fewer).
- **Open answer-quality issue found:** "When does this semester end?" → "29 July 2026" (wrong). The calendar's "Last Day of classes" is **17 Nov 2026**, followed by Major exams 19–26 Nov. Not fixed yet.
- **Correction (user):** "When does this semester end?" → the user's re-run answered **30 November 2026**, which is correct. The calendar (pp. 2, 8) gives 30 Nov 2026 as the "Last date of submission of online grades" for Semester I, the last item before the winter break (2 Dec). The "29 July 2026" answer in my 4-question test was a one-off; the "open issue" above is withdrawn. (17 Nov 2026 is the last day of *classes*, a narrower reading of the question.)

---

## Report update: post-evaluation work + figures (user request, 2026-10-15)

**Decisions (user):**
- Add a post-evaluation improvements section, the response-time analysis, and the history-trimming lesson.
- Replace the consistency table with one sentence.
- **Keep the evaluation numbers** and state that the later fixes were checked live, not re-measured.
- Figures:
  - **graphs** (user's choice): accuracy-by-category heatmap (replaces the category table), answer-outcome stacked bars, failure reasons per configuration, per-question result grid (replaces the appendix table), routing matrix (multi mode);
  - **diagrams** (my choice, user delegated): one multi-agent request step by step (with the three model calls; supports the response-time section), the amendment timeline (2019 rule → Circular 51), the safety-check pipeline around each reply (most post-eval fixes are checks). Skipped: the ADK-transfer diagram (the text + its 0/3 → 3/3 numbers already carry it).
- Limitations stay at the three points the user specified earlier.
- All graphs are generated by `report/make_tables.py` from `scored.jsonl` / `questions.jsonl` (plain TikZ; the TeX install has no pgfplots). The response-time numbers are the measured values from this log (Phase "Post-evaluation fix").

### Done (report now 11 pages, 0 overfull boxes, no em dashes)
- **New figures** (graphs generated by `make_tables.py`): accuracy heatmap (replaces the category table), answer-outcome stacked bars, routing matrices (replace the misroutes table), failure reasons (Analysis), per-question grid (replaces the appendix table); diagrams: amendment timeline (§2.3), safety-check pipeline (new checks dashed amber), one multi-agent request with its three model calls.
- **New section 8, "Improvements after the evaluation"**: calendar questions refused → fixes (router scope, document keywords, query expansion, abbreviation normalisation; retrieval 19/19 in the top 5); new safety checks; response time (causes + before/after table of prompt tokens per call and seconds per question).
- **"What we learned"**: added "Shrinking the history must keep the tool calls".
- Consistency table → one sentence; a note in the evaluation setup that the results describe the evaluated version and the later fixes were checked live, not re-measured.
- **Layout work:** the first heatmap palette mixed red→green through brown, so it now goes red → amber → green; the outcome legend overflowed by 50 pt and overlapped, so it is now 2 columns; the routing-matrix and grid column labels overlapped, so they now have smaller / stacked labels; the sequence diagram's "transfer" label sat on a box and was moved into the box text. Floats drifted out of their sections (the failure figure appeared after section 8), so all 13 figures/tables are pinned with `[H]` (`float` package; `placeins` isn't installed). Every page was checked visually.
- Not committed yet (user to review).
- **User revision:** the accuracy heatmap and the outcome bars went back to **tables** (category table; new outcome table with Correct: grounded / refuse-clarify-suggest / not grounded and Wrong: false refusal / other, generated as `tables/outcomes.tex`), and the per-question grid went back to the appendix **table**. The unused heatmap / outcome-bar / grid generators (and the colour-scale helper) were removed from `make_tables.py`. Remaining figures: retrieval pipeline, agents, amendment timeline, accuracy/groundedness bars, routing matrices, failure reasons, safety-check pipeline, request sequence. 11 pages, 0 overfull boxes, all references resolved. Not committed yet.
- **User revision (response time):** the paragraph now explains what drives the time (3 model calls; prompts growing with the chat history up to the 8k limit) and lists **what we did to make answers faster**: trimming old tool results (20–31 s instead of growing to 71 s), Qwen3 `think=False` (19 s → 1.9 s on a one-tool question), small retrieved context (5 passages, at most 2 per document). Memory pressure / swapping / 240 tok/s / the 16 GB laptop are no longer mentioned; the "~18 s" in the sequence diagram was removed (it was measured under that memory pressure), and the table caption says "command-line chat" instead of "the same laptop". 11 pages, 0 overfull, no em dashes. Not committed yet.

---

## Fix: make-up exam questions routed to email_agent (2026-10-21)

**Found** while timing the web UI: in multi mode, "Can I get a make-up exam if I miss the Minor exam due to illness?" went to `email_agent` instead of `policy_agent`. The answer was still correct (email_agent can search the documents), but the routing was wrong.

- **Only after earlier turns.** In a fresh session the router got it right 3/3. After "attendance requirement" (→ policy) and "slot for Autonomous Systems" (→ schedule) in the same session it chose email_agent **3/3**. The likely reading: "email the Autonomous Systems instructor about a make-up exam". The email agent's description lists "sick leave … permission for a make-up exam", so a question that mentions a make-up exam and illness is pulled towards it.
- **Fix: a deterministic router check, not a prompt change.** The eval numbers stay comparable, and the check can be unit-tested. `keep_email_agent_for_email_requests` (after_model_callback on the router, in `guards.py`) keeps a transfer to email_agent only if the student's message asks for something to be written (`email / mail / draft / write / compose / letter / message`), or the email agent's previous reply asked a question (so "Did you mean CSL7650?" → "Yes, I meant CSL7650" still reaches it). Otherwise it transfers to policy_agent. The same `EMAIL_REQUEST` pattern now drives the empty-reply fallback route.
- **Checked:**
  - The reproduction (attendance → slot → make-up, same session) → policy_agent 3/3, answered with `search_documents`.
  - The CSL7570 email with "Did you mean" → "Yes, I meant CSL7650" stays with email_agent and drafts the email.
  - A routing probe of 8 questions × 3 runs in fresh sessions (5 rule questions about make-up / I grade / sick leave, 3 email requests) → 24/24, the same as before the fix.
  - Every eval turn that should reach email_agent (E01–E04, M01) contains an email word, so the eval routing is unaffected.
  - Unit test `test_email_agent_only_for_email_requests`.
