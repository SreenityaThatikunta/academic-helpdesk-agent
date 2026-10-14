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
