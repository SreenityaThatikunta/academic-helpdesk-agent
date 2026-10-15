# Evaluation summary

Runs: 12 · turns scored: 372 · manual overrides applied: 0

## Headline metrics (all repeats pooled)

| Config | Accuracy | Groundedness (answer/draft turns) | Correct refusals | False refusals | Refusals logged | Routing | Mean latency | p90 latency | Errors |
|---|---|---|---|---|---|---|---|---|---|
| single · qwen3:8b | 87% (81/93) | 70% (48/69) | 100% (18/18) | 4% (3/75) | 100% (18/18) | – | 9.5s | 19.9s | 0 |
| multi · qwen3:8b | 84% (78/93) | 78% (54/69) | 100% (18/18) | 8% (6/75) | 100% (18/18) | 94% (87/93) | 12.2s | 31.3s | 0 |
| single · llama3.1:8b | 65% (60/93) | 46% (32/69) | 100% (18/18) | 1% (1/75) | 100% (18/18) | – | 14.2s | 27.6s | 0 |
| multi · llama3.1:8b | 69% (64/93) | 62% (43/69) | 100% (18/18) | 0% (0/75) | 100% (18/18) | 94% (87/93) | 13.3s | 27.1s | 0 |

## Accuracy by category

| Config | policy | schedule | count | email | out_of_scope | multi_intent | conversation |
|---|---|---|---|---|---|---|---|
| single · qwen3:8b | 78% (21/27) | 100% (15/15) | 67% (6/9) | 100% (12/12) | 100% (18/18) | 50% (3/6) | 100% (6/6) |
| multi · qwen3:8b | 78% (21/27) | 80% (12/15) | 67% (6/9) | 100% (12/12) | 100% (18/18) | 50% (3/6) | 100% (6/6) |
| single · llama3.1:8b | 52% (14/27) | 100% (15/15) | 67% (6/9) | 25% (3/12) | 100% (18/18) | 17% (1/6) | 50% (3/6) |
| multi · llama3.1:8b | 70% (19/27) | 100% (15/15) | 67% (6/9) | 25% (3/12) | 100% (18/18) | 0% (0/6) | 50% (3/6) |

## Per question (correct runs out of repeats)

| Item | Expected | single · qwen3:8b | multi · qwen3:8b | single · llama3.1:8b | multi · llama3.1:8b |
|---|---|---|---|---|---|
| C01 | 3: LAL4070 Health Economics, LAL4850 Introduction to Climate Change Ec | 3/3 | 3/3 | 3/3 | 3/3 |
| C02 | 6: LAL3030, LAL3060, LAL3080, LAL3090, LAL3040, LAL3130. | 0/3 | 0/3 | 0/3 | 0/3 |
| C03 | 16. | 3/3 | 3/3 | 3/3 | 3/3 |
| E01 | CSL7570 is not offered; 'Did you mean CSL7650 (Autonomous Systems)?' - | 3/3 | 3/3 | 3/3 | 3/3 |
| E02 | Draft to gaurav.harit@iitj.example (sick leave, 3 days), saved, not se | 3/3 | 3/3 | 0/3 | 0/3 |
| E03 | Draft to alok.ranjan@iitj.example (make-up for missed minor), saved, n | 3/3 | 3/3 | 0/3 | 0/3 |
| E04 | Draft to rachel.philip@iitj.example, saved, not sent | 3/3 | 3/3 | 0/3 | 0/3 |
| M01 | Rule: make-up for missed Minor, apply within 10 days with verified med | 0/3 | 0/3 | 0/3 | 0/3 |
| M02 | 22 November 2026, 09:00-12:00 (tentative); attendance >= 75%, else de- | 3/3 | 3/3 | 1/3 | 0/3 |
| O01 | I don't know + logged | 3/3 | 3/3 | 3/3 | 3/3 |
| O02 | I don't know + logged | 3/3 | 3/3 | 3/3 | 3/3 |
| O03 | I don't know + logged | 3/3 | 3/3 | 3/3 | 3/3 |
| O04 | I don't know + logged | 3/3 | 3/3 | 3/3 | 3/3 |
| O05 | I don't know + logged | 3/3 | 3/3 | 3/3 | 3/3 |
| O06 | I don't know + logged | 3/3 | 3/3 | 3/3 | 3/3 |
| P01 | At least 75% attendance in each course (full attendance expected); bel | 3/3 | 3/3 | 0/3 | 0/3 |
| P02 | Absence from all academic activities for 4+ weeks (with or without lea | 3/3 | 3/3 | 3/3 | 3/3 |
| P03 | Make-up is for a missed Minor; submit the Makeup/I-grade application ( | 0/3 | 3/3 | 0/3 | 0/3 |
| P04 | Apply for an I grade (not a make-up); the I grade application must rea | 3/3 | 3/3 | 3/3 | 1/3 |
| P05 | 14 registered semesters (2019 Academic Regulations §11.4; supersedes t | 3/3 | 3/3 | 3/3 | 3/3 |
| P06 | One Minor and one Major examination (Circular 52, Jul 2024; Examinatio | 3/3 | 3/3 | 2/3 | 3/3 |
| P07 | 15-20 September 2026 (tentative). | 3/3 | 3/3 | 0/3 | 3/3 |
| P08 | Autonomous/semi-autonomous systems (mobile robots, cars): e.g. navigat | 3/3 | 0/3 | 1/3 | 3/3 |
| P09 | 14 registered semesters, which may include up to 6 semesters of Regist | 0/3 | 0/3 | 2/3 | 3/3 |
| S01 | CSL7650, slot E (Tue/Thu/Fri 11:00-11:50), LHC 106. | 3/3 | 3/3 | 3/3 | 3/3 |
| S02 | LAL4070, Alok Ranjan, LHC 204 (slot D). | 3/3 | 0/3 | 3/3 | 3/3 |
| S03 | 22 November 2026 (Sunday), 09:00 AM-12:00 PM, tentative. | 3/3 | 3/3 | 3/3 | 3/3 |
| S04 | LAL3080, slot N, LHC 105 (Rachel Philip). | 3/3 | 3/3 | 3/3 | 3/3 |
| S05 | No such course is offered this semester (no suggestions). | 3/3 | 3/3 | 3/3 | 3/3 |
| V01.1 | Asks for B.Tech branch and year of joining (credits differ by programm | 3/3 | 3/3 | 2/3 | 0/3 |
| V01.2 | 10 OE credits (B.Tech CSE curriculum, batches before 2026, p. 10). | 3/3 | 3/3 | 1/3 | 3/3 |

## Consistency across repeats

A question is **unstable** when its correctness differs between repeats. Its **answer changed** when the facts the question asks for differ between repeats: the values matched by the expected-fact patterns, refused vs answered, the draft recipient, or asked vs not asked.

| Config | Unstable correctness | Answer changed |
|---|---|---|
| single · qwen3:8b | 0/31 | 0/31 |
| multi · qwen3:8b | 0/31 | 0/31 |
| single · llama3.1:8b | 6/31 | 8/31 |
| multi · llama3.1:8b | 1/31 | 3/31 |

### Questions whose answers changed across runs

| Config | Item | Correct per repeat | Asked-for facts per repeat |
|---|---|---|---|
| single · llama3.1:8b | M02.1 | ✗ ✗ ✓ | 22 | nov | - ‖ 22 | nov | - ‖ 22 | nov | 75% |
| single · llama3.1:8b | P01.1 | ✗ ✗ ✗ | 75% | - | STALE ‖ 75% | - | STALE ‖ 75% | - |
| single · llama3.1:8b | P06.1 | ✓ ✗ ✓ | minor | major ‖ minor | major | STALE ‖ minor | major |
| single · llama3.1:8b | P07.1 | ✗ ✗ ✗ | - | 20 | - ‖ - | 20 | - ‖ REFUSED |
| single · llama3.1:8b | P08.1 | ✓ ✗ ✗ | navigation ‖ - ‖ - |
| single · llama3.1:8b | P09.1 | ✓ ✗ ✓ | 14 ‖ - ‖ 14 |
| single · llama3.1:8b | V01.1 | ✓ ✗ ✓ | ASKED ‖ NOT_ASKED ‖ ASKED |
| single · llama3.1:8b | V01.2 | ✗ ✓ ✗ | - | STALE ‖ 10 ‖ - |
| multi · llama3.1:8b | M02.1 | ✗ ✗ ✗ | - | - | 75% ‖ - | - | 75% ‖ 22 | - | 75% |
| multi · llama3.1:8b | P01.1 | ✗ ✗ ✗ | 75% | - | STALE ‖ 75% | - ‖ 75% | - | STALE |
| multi · llama3.1:8b | P04.1 | ✓ ✗ ✗ | i"grade ‖ - ‖ - |
