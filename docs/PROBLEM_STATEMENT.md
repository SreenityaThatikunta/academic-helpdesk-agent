# Problem Statement: Multi-Agent Academic Helpdesk Agent

## Overview

Design a multi-agent **Academic Helpdesk Agent**. The agent can answer questions about the academic programs, course contents, academic rules and regulations, and draft an email to a course instructor to apply for sick leave or seek permission for makeup exams.

It should be able to handle questions such as:

- "What is the attendance requirement to sit in the Major exam?"
- "What is the slot for the course Autonomous Systems?"
- "How many 400 level electives have been floated by the Humanities department in this semester?"
- "How many Open Elective credits do I need to earn in order to get a B.Tech. Degree?"
- "Write an email to the course instructor of CSL7570 that I need leave for 2 days."

For any other question, such as "What are the available dining options on the campus?" or "What is the best way to reach the campus from Jodhpur city center?", the agent should answer that it does not know, instead of guessing an answer.

## Data Collection

The team should collect **20 to 30 real documents** related to rules and regulations, time table, course registration, recent office orders, faculty email IDs, etc. Personal data can be replaced with dummy values.

## Requirements

### RAG and Tools

The agent should use RAG and will require several tools to assist in generating a response. Example tools:

- Searching the most relevant chunks from the vector store
- Looking up time table and course codes from CSV files
- Looking up the email ID of the instructor of a course
- Writing an email draft for the student to review (the email need not actually be sent)

Additionally:

- The agent should keep a **log of the questions it cannot answer**, so that these questions can be referred to a human to answer.
- The generated answer should **refer to / cite the document** it came from.

### Platform Constraints

- The project should be executable on a laptop/computer with **16GB RAM**.
- **Google ADK** can be used for the agent framework.
- ADK can invoke **Ollama-hosted models** through its **LiteLLM** connector.
- 8B chat models such as **Qwen3** or **Llama 3.1** can be used.
- For RAG, use a **local embedding model via Ollama** and a **local vector store such as ChromaDB**.

### Multi-Agent Extension

Once the base version with a single agent, the RAG pipeline, and all the tools is implemented, augment it to a multi-agent version. There can be a **helpdesk orchestrator** which transfers the question to:

- **Policy agent** — answers questions related to rules, regulations, and curriculum
- **Schedule agent** — answers questions related to slots and time table
- **Email agent** — gets the instructor contact and drafts an email

## Evaluation

For a collection of **20 to 30 prompts**, analyze the performance of the multi-agent system on metrics such as:

- Accuracy of answers
- Groundedness (correct citation) of answers
- Correct refusals to answer out-of-scope questions

Optionally, replace the LLM used and compare performance. Note down the questions whose answers changed across multiple runs.

## Deliverables

- Code repository with a README file
- The set of questions
- A report with the findings
