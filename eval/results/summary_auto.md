# Evaluation summary

Runs: 12 · turns scored: 372 · manual overrides applied: 0

## Headline metrics (all repeats pooled)

| Config | Accuracy | Groundedness (answer/draft turns) | Correct refusals | False refusals | Refusals logged | Routing | Mean latency | p90 latency | Errors |
|---|---|---|---|---|---|---|---|---|---|
| single · qwen3:8b | 90% (84/93) | 73% (48/66) | 100% (21/21) | 0% (0/72) | 100% (21/21) | – | 9.5s | 19.9s | 0 |
| multi · qwen3:8b | 87% (81/93) | 82% (54/66) | 100% (21/21) | 4% (3/72) | 100% (21/21) | 94% (87/93) | 12.2s | 31.3s | 0 |
| single · llama3.1:8b | 60% (56/93) | 42% (28/66) | 86% (18/21) | 1% (1/72) | 100% (18/18) | – | 14.2s | 27.6s | 0 |
| multi · llama3.1:8b | 61% (57/93) | 55% (36/66) | 86% (18/21) | 0% (0/72) | 100% (18/18) | 94% (87/93) | 13.3s | 27.1s | 0 |

## Accuracy by category

| Config | policy | schedule | count | email | out_of_scope | multi_intent | conversation |
|---|---|---|---|---|---|---|---|
| single · qwen3:8b | 89% (24/27) | 100% (15/15) | 67% (6/9) | 100% (12/12) | 100% (18/18) | 50% (3/6) | 100% (6/6) |
| multi · qwen3:8b | 89% (24/27) | 80% (12/15) | 67% (6/9) | 100% (12/12) | 100% (18/18) | 50% (3/6) | 100% (6/6) |
| single · llama3.1:8b | 37% (10/27) | 100% (15/15) | 67% (6/9) | 25% (3/12) | 100% (18/18) | 17% (1/6) | 50% (3/6) |
| multi · llama3.1:8b | 44% (12/27) | 100% (15/15) | 67% (6/9) | 25% (3/12) | 100% (18/18) | 0% (0/6) | 50% (3/6) |

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
| P04 | Apply for an I grade (not a make-up); the I grade application must rea | 3/3 | 3/3 | 3/3 | 0/3 |
| P05 | 14 registered semesters (2019 Academic Regulations §11.4; supersedes t | 3/3 | 3/3 | 3/3 | 3/3 |
| P06 | One Minor and one Major examination (Circular 52, Jul 2024; Examinatio | 3/3 | 3/3 | 0/3 | 0/3 |
| P07 | 15-20 September 2026 (tentative). | 3/3 | 3/3 | 0/3 | 3/3 |
| P08 | Autonomous/semi-autonomous systems (mobile robots, cars): e.g. navigat | 3/3 | 0/3 | 1/3 | 3/3 |
| P09 | Not stated in the documents -> I don't know + logged | 3/3 | 3/3 | 0/3 | 0/3 |
| S01 | CSL7650, slot E (Tue/Thu/Fri 11:00-11:50), LHC 106. | 3/3 | 3/3 | 3/3 | 3/3 |
| S02 | LAL4070, Alok Ranjan, LHC 204 (slot D). | 3/3 | 0/3 | 3/3 | 3/3 |
| S03 | 22 November 2026 (Sunday), 09:00 AM-12:00 PM, tentative. | 3/3 | 3/3 | 3/3 | 3/3 |
| S04 | LAL3080, slot N, LHC 105 (Rachel Philip). | 3/3 | 3/3 | 3/3 | 3/3 |
| S05 | No such course is offered this semester (no suggestions). | 3/3 | 3/3 | 3/3 | 3/3 |
| V01.1 | Asks for B.Tech branch and year of joining (credits differ by programm | 3/3 | 3/3 | 2/3 | 0/3 |
| V01.2 | 10 OE credits (B.Tech CSE curriculum, batches before 2026, p. 10). | 3/3 | 3/3 | 1/3 | 3/3 |

## Consistency across repeats

A question is **unstable** when its correctness differs between repeats; its **facts changed** when the numbers / course codes in the answer differ between repeats (or it refused in some repeats only).

| Config | Unstable correctness | Facts changed |
|---|---|---|
| single · qwen3:8b | 0/31 | 5/31 |
| multi · qwen3:8b | 0/31 | 2/31 |
| single · llama3.1:8b | 4/31 | 19/31 |
| multi · llama3.1:8b | 0/31 | 13/31 |

### Questions whose answers changed across runs

| Config | Item | Correct per repeat | Key facts per repeat |
|---|---|---|---|
| single · qwen3:8b | M02.1 | ✓ ✓ ✓ | codes= nums=00,09,12,22,27,30,75% ‖ codes= nums=00,09,12,22,27,30,75% ‖ codes=CSL7650 nums=00,09,12,22,26,27,30,75% |
| single · qwen3:8b | P04.1 | ✓ ✓ ✓ | codes= nums=27,4.3 ‖ codes= nums= ‖ codes= nums=27 |
| single · qwen3:8b | P07.1 | ✓ ✓ ✓ | codes=AY2026 nums=00,02,04,06,07,08,09,10,12,15,16,17,18,19,2,20,27,30 ‖ codes=AY2026 nums=15,16,17,18,19,2,20,27 ‖ codes=AY2026 nums=15,16,17,18,19,2,20,27 |
| single · qwen3:8b | P08.1 | ✓ ✓ ✓ | codes=CSL7650 nums=26,27 ‖ codes=CSL7650 nums=26,27,3,700 ‖ codes=CSL7650 nums=26,27,3,700 |
| single · qwen3:8b | S01.1 | ✓ ✓ ✓ | codes=CSL7650 nums=00,08,09,10,106,11,12,18,22,26,27,30,50 ‖ codes=CSL7650 nums=00,08,09,10,106,11,12,18,22,26,27,50 ‖ codes=CSL7650 nums=00,08,09,10,106,11,12,18,22,26,27,50 |
| multi · qwen3:8b | E02.1 | ✓ ✓ ✓ | codes= nums=1,2,51 ‖ codes= nums=1,3 ‖ codes= nums=1,2,51 |
| multi · qwen3:8b | P04.1 | ✓ ✓ ✓ | codes= nums=8 ‖ codes= nums=8 ‖ codes= nums=1,2,52,8 |
| single · llama3.1:8b | C01.1 | ✓ ✓ ✓ | codes=AIL4070,LAL4070,LAL4850 nums=1,2,3,400 ‖ codes=AIL4070,LAL4070,LAL4850 nums=1,2,26,27,3,400 ‖ codes=AIL4070,LAL4070,LAL4850 nums=1,2,26,27,3,400 |
| single · llama3.1:8b | E01.1 | ✓ ✓ ✓ | codes=CSL7350,CSL7560,CSL7570,CSL7650 nums= ‖ codes=CSL7350,CSL7560,CSL7570,CSL7650 nums=2 ‖ codes=CSL7570,CSL7650 nums= |
| single · llama3.1:8b | E02.1 | ✗ ✗ ✗ | codes= nums= ‖ codes=CSL7650 nums=26,27,3 ‖ codes= nums=3 |
| single · llama3.1:8b | E03.1 | ✗ ✗ ✗ | codes=LAL4070 nums=26,27 ‖ codes=LAL4070 nums= ‖ codes= nums= |
| single · llama3.1:8b | E04.1 | ✗ ✗ ✗ | codes= nums= ‖ codes= nums=26,27 ‖ codes= nums= |
| single · llama3.1:8b | M01.1 | ✗ ✗ ✗ | codes=CSL7650 nums=10 ‖ codes= nums=10 ‖ codes=CSL7650 nums= |
| single · llama3.1:8b | M02.1 | ✗ ✗ ✓ | codes=CSL7650 nums=00,09,12,22,26,27,30 ‖ codes=CSL7650 nums=00,09,12,22,27,30 ‖ codes=CSL7650 nums=00,09,12,22,26,27,30,75% |
| single · llama3.1:8b | P01.1 | ✗ ✗ ✗ | codes= nums=1,2,51,75% ‖ codes= nums=1,2,51,75% ‖ codes= nums=07,08,1,2,51,75% |
| single · llama3.1:8b | P02.1 | ✓ ✓ ✓ | codes= nums=1 ‖ codes= nums=1,15.3 ‖ codes= nums=1 |
| single · llama3.1:8b | P05.1 | ✓ ✓ ✓ | codes= nums=1,14 ‖ codes= nums=03,09,14,17 ‖ codes= nums=1,14 |
| single · llama3.1:8b | P06.1 | ✗ ✗ ✗ | codes= nums=07,08,1,2,3,40%,52 ‖ codes= nums=03,09,1,120,14,2,60,8 ‖ codes= nums=07,08,1,2,3,40%,52 |
| single · llama3.1:8b | P07.1 | ✗ ✗ ✗ | codes=AY2026,BBL2040,CIL2010,CIL2060 nums=27 ‖ codes=MAL2020 nums=27 ‖ REFUSED |
| single · llama3.1:8b | P08.1 | ✓ ✗ ✗ | codes=AY2025 nums=01,06,07,1,10,11,12,13,14,15,16,17,18,19,2,20,21,22,23,24,25,26,27,28,29,3,30,31,32,33,34,35,36,37,38,39,4,40,41,42,43,44,45,46,47,48,49,5,50,51,52,53,54,55,56,57,58,6,7,8,9 ‖ codes=CSL7650 nums=0,106,26,27,3,700 ‖ codes=CSL7650 nums=26,27,3 |
| single · llama3.1:8b | P09.1 | ✗ ✗ ✗ | codes= nums=02,14,20,2022,2023,22,6 ‖ codes= nums=02,20,2022,2023,27,4,5 ‖ codes= nums=02,14,20,2022,2023,27,6 |
| single · llama3.1:8b | S01.1 | ✓ ✓ ✓ | codes=CSL7650 nums=00,11,18,22,26,27,50 ‖ codes=CSL7650 nums=00,106,11,18,22,26,27,50 ‖ codes=CSL7650 nums=106,18,22,26,27 |
| single · llama3.1:8b | S04.1 | ✓ ✓ ✓ | codes=LAL3080 nums=105,26,27 ‖ codes=LAL3080 nums=105,26,27 ‖ codes= nums=105,26,27,30 |
| single · llama3.1:8b | S05.1 | ✓ ✓ ✓ | codes=CSL9999 nums= ‖ codes=AY2026,CSL7650,CSL9999 nums=27 ‖ codes=CSL9999 nums= |
| single · llama3.1:8b | V01.1 | ✓ ✗ ✓ | codes= nums= ‖ codes= nums=06,12,4 ‖ codes= nums= |
| single · llama3.1:8b | V01.2 | ✗ ✓ ✗ | codes= nums=12,18 ‖ codes= nums=07,10 ‖ codes= nums=18,6 |
| multi · llama3.1:8b | C01.1 | ✓ ✓ ✓ | codes=AIL4070,LAL4070,LAL4850 nums=1,2,26,27,3,400 ‖ codes= nums=26,27,3,400 ‖ codes=AIL4070,LAL4070,LAL4850 nums=1,2,26,27,3,400 |
| multi · llama3.1:8b | E02.1 | ✗ ✗ ✗ | codes= nums=26,27,3 ‖ codes=CSL7650 nums=26,27,3 ‖ codes=CSL7650 nums=26,27,3 |
| multi · llama3.1:8b | M01.1 | ✗ ✗ ✗ | codes=CSL7650 nums=9 ‖ codes=CSL7650 nums=10,9 ‖ codes=CSL7650 nums=9 |
| multi · llama3.1:8b | M02.1 | ✗ ✗ ✗ | codes= nums=07,08,1,2,51,75% ‖ codes= nums=07,08,1,2,51,75% ‖ codes=AY2025 nums=01,02,07,08,1,2,20,2022,2023,51,58,7,75%,9 |
| multi · llama3.1:8b | P01.1 | ✗ ✗ ✗ | codes= nums=07,08,1,2,51,75% ‖ codes= nums=07,08,1,2,51,75% ‖ codes= nums=1,2,51,75% |
| multi · llama3.1:8b | P02.1 | ✓ ✓ ✓ | codes= nums=03,09,1,21 ‖ codes= nums=1,2,51 ‖ codes= nums=1 |
| multi · llama3.1:8b | P03.1 | ✗ ✗ ✗ | codes= nums=10 ‖ codes= nums=8 ‖ codes= nums=10 |
| multi · llama3.1:8b | P06.1 | ✗ ✗ ✗ | codes= nums=1,2,3,40%,52 ‖ codes= nums=1,2,3,40%,52 ‖ codes= nums=07,08,1,2,3,40%,52 |
| multi · llama3.1:8b | P08.1 | ✓ ✓ ✓ | codes=AY2025 nums=01,06,07,1,13,14,2,3,4,5,58,7 ‖ codes=AY2025 nums=01,06,07,1,13,2,3,4,5,58,7 ‖ codes=AY2025 nums=01,06,07,1,13,14,2,3,4,5,58,7 |
| multi · llama3.1:8b | S01.1 | ✓ ✓ ✓ | codes= nums=26,27 ‖ codes=CSL7650 nums=00,11,26,27,50 ‖ codes= nums=00,106,11,18,22,26,27,50 |
| multi · llama3.1:8b | S05.1 | ✓ ✓ ✓ | codes=AY2026,CSL7650,CSL9999 nums=27 ‖ codes=AY2026,CSL7650,CSL9999 nums=27 ‖ codes=CSL9999 nums= |
| multi · llama3.1:8b | V01.1 | ✗ ✗ ✗ | codes= nums=06,12,4 ‖ codes= nums=06,12,9 ‖ codes= nums=06,12,4 |
| multi · llama3.1:8b | V01.2 | ✓ ✓ ✓ | codes= nums=07,10,18 ‖ codes= nums=07,10,18 ‖ codes= nums=07,10 |
