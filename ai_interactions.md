# AI Interactions Log

> Covers the stretch features I attempted: **Advanced algorithmic capability via agent mode (SF7)** and **Prompt/model comparison (SF11)**. The other stretch features (persistence, priority scheduling, output formatting) are documented in `README.md`.

---

## Agent Workflow (SF7)

**Third algorithmic capability added:** `Scheduler.find_next_available_slot()`, a "next available slot" finder that scans a 15-minute grid for the first time when a caregiver is inside an availability window, has no clashing task, and (optionally) the pet isn't already busy. It builds on `Scheduler.available_caregivers()` and `Caregiver.is_available()`. Also added: `Scheduler.sort_by_priority()` (priority-first scheduling) and `Scheduler.explain_schedule()`.

**What task did you give the agent?**

Implement all six phases of the PawPal+ assignment against the grading rubric in one pass, starting from a mostly empty starter repo. The behaviours I asked for: walking, feeding, cleaning (grooming), and playing with a pet; finding out whether someone is available at a given time; support for multiple pets. Documentation, the UML and the reflection were to go in the repo files.

**What did the agent do?**

Files created or modified, in the order the agent worked:

| File | What was done |
|---|---|
| `pawpal_system.py` (new) | `Task`, `Pet`, `Caregiver`, `Owner`, `Scheduler`; sorting, filtering, conflict detection, recurrence, availability, next-slot, JSON persistence, table formatter. One-line docstrings on every method. |
| `main.py` (new) | CLI demo: 1 owner, 2 pets, 2 caregivers, 8+ tasks added out of order; demonstrates sort, filter, priority view, conflicts, availability, next slot, recurrence, persistence. |
| `tests/test_pawpal.py` (new), `pytest.ini` (new) | 32 tests; `pytest.ini` sets `pythonpath = .` so plain `pytest` finds the module. |
| `app.py` (rewritten) | Streamlit UI: `Owner` in `st.session_state`, forms for pets / caregivers / tasks, availability tools, sorted + filtered schedule, conflict banners, mark-done buttons, autosave. |
| `diagrams/uml_draft.mmd`, `diagrams/uml_final.mmd` (new) | Mermaid class diagrams (draft and final); the placeholder `diagrams/uml.mmd` was removed. PNG exports rendered with Mermaid CLI. |
| `README.md`, `reflection.md`, `ai_interactions.md` | Filled in with real output from the demo and tests. |
| `.gitignore` | Added `data.json`. |

Commands run by the agent: `python main.py` (repeatedly, reading the output), the test suite, a mutation check (deliberately breaking three behaviours and confirming tests fail), a brute-force comparison of the conflict sweep, and a mocked-Streamlit smoke test of every UI flow.

**What did you have to verify or fix manually?**

- **Bug found by reading demo output:** the conflict warning printed `overlaps 's 'Brush fur'` (pet name missing) because `schedule_task` checked conflicts *before* `Pet.add_task` stamped the pet's name on the task. Fixed by adding the task first and having `find_conflicts_for` skip the task itself; a regression assertion was added to the tests.
- **Test-runner mistake:** the first run of the local test stand-in reported 28 failures. That was a bug in the throwaway runner (two copies of a module), not in the project code; fixed and re-run (32 passed).
- **A "surviving mutant":** my first mutation check changed only one half of the two-sided overlap test and the suite still passed. That was an equivalent mutant (the other half still made the result correct), not a test gap. Mutating both halves made `test_back_to_back_tasks_do_not_conflict` fail as it should.
- **UML rendering:** inline `%%` comments inside a Mermaid class body showed up as text in the attributes. Moved them to a header comment and re-rendered.
- **Table alignment:** emoji inside padded columns misaligned the CLI table; moved them to fixed-width fields.
- **Left for a human:** running the real `streamlit run app.py` and the real `python -m pytest`, and pasting your own pytest output into the README.

---

## Prompt Comparison (SF11)

> **Task compared:** conflict detection for the scheduler. This table compares two *strategies* for the same task. Both implementations were run on the same inputs and the numbers below are the real results.

| | Option A | Option B |
|-|----------|----------|
| **Model / tool used** | Claude (agent mode) | Claude (agent mode) |
| **Prompt / strategy** | "Lightweight" conflict detection, as the assignment words it: group tasks by `(date, due_time)` and flag any group with more than one task. | Constraint-heavy: "detect **overlapping time ranges** (not just identical start times) across all pets, report same-pet / cross-pet / person-double-booked, return warning strings, never raise." |
| **Response summary** | A 6-line `defaultdict` grouping. | `Task.overlaps()` plus `Scheduler.detect_conflicts()`: sort once, then sweep; `find_conflicts_for()` checks a single new task. |
| **What was useful** | Very short and trivially readable; 1.7 ms on 3,000 tasks. | Catches partial and contained overlaps; message says *who* collides and whether someone is double-booked; result matched a brute-force all-pairs check exactly (126,255 pairs on a 3,000-task stress test) and ran ~11× faster than brute force (485 ms vs 5,564 ms). |
| **Problems noticed** | Missed real conflicts: 08:00-08:30 vs a task at 08:20 → **0 conflicts found**; 08:00-09:00 vs 08:15-08:25 → **0 found**. Also can't say whether a person is double-booked. | More code to read, and an early version had a bug in the warning text (see Agent Workflow). Sweep is slower than exact-match because it reports far more conflicts on that dense stress input. |
| **Decision** | Rejected for the real scheduler. | **Kept.** Correctness matters more than 6 lines saved. |

| Scenario | A: exact-match | B: overlap sweep |
|---|---:|---:|
| same start, two pets | 1 | 1 |
| partial overlap (08:00+30m / 08:20) | 0 | 1 |
| contained (08:00+60m / 08:15) | 0 | 1 |
| back-to-back (08:00+30m / 08:30) | 0 | 0 |

**Which approach did you use in your final implementation and why?**

Option B. A pet scheduler that only notices *identical* start times will happily let you book a 30-minute walk and a feeding 20 minutes into it. The overlap check is only a few lines longer, it is correct against a brute-force reference, and it enables the "person is double-booked" warning that the availability feature builds on. The tradeoff (it warns rather than blocks, and it ignores travel time) is documented in `reflection.md` section 2b.

### Multi-model comparison: Claude vs. Gemini

**Task:** the same conflict-detection task given to two different models, with the output compared on real inputs. Screenshots of the Gemini session are in [`screenshots/gemini/`](screenshots/gemini/).

**Prompt used for both models:** "Write a Python method for a pet-care scheduler that takes a list of Task objects (each has `due_date`, `due_time` as 'HH:MM', and `duration_mins`) and returns a list of human-readable warnings for every pair that overlaps in time. It must not raise exceptions."

Gemini's version of the prompt ended with one extra sentence, "I have included the zip file with everything here", and the starter zip attached ([prompt](screenshots/gemini/01_prompt.png)). Claude worked inside the repo directly.

**How I compared them:** I copied Gemini's `check_overlaps` verbatim ([code](screenshots/gemini/02_check_overlaps_code.png), [its summary](screenshots/gemini/03_key_features.png)) and ran it against the real `Task` objects from `pawpal_system.py`, next to Claude's `Scheduler.detect_conflicts()`, on seven scenarios plus a 3,000-task stress test.

| | Option A | Option B |
|-|----------|----------|
| **Model / tool used** | Claude (agent mode, working in the repo) | Gemini (chat, starter zip attached) |
| **Prompt / task** | The prompt above, plus the project's Task/Pet/Owner design and rubric. | The prompt above plus "I have included the zip file with everything here". |
| **Response summary** | `Task.overlaps()` plus `Scheduler.detect_conflicts()`: sort once, sweep forward, stop at the first task that starts after the current one ends. `_describe_conflict()` builds the message. | A standalone `check_overlaps(tasks)`: `getattr` for every field, `strptime` into datetimes inside `try/except`, then compare every pair with `max(starts) < min(ends)`. |
| **What was useful** | Messages say who collides and how ("different pets", "Jordan is double-booked") and include end times. Skips completed tasks. About 3x faster on the stress test (0.6 s vs 2.0 s for 3,000 tasks). | Correct overlap test, in one readable line. Matched Claude on every overlap scenario (same start, partial, contained, back-to-back, different days) and returned the identical 126,255 pairs on the stress test. Genuinely never raises. Combines date and time into one datetime, so tasks on different days are handled right. |
| **Problems noticed** | The "never raises" guarantee is weaker. `Task` rejects bad times when it is created, so the method does not defend itself, and I confirmed that a task whose `due_time` is changed to junk *after* creation makes `detect_conflicts` raise `ValueError`. Also more code to read. | It invented attribute names (`pet_id`, `task_type`) that my `Task` doesn't have, so on real data every warning read *"Conflict detected between 'Task' for Unknown Pet ... and 'Task' for Unknown Pet"*, with no pet or activity named, even though the zip was attached. `except Exception: continue` silently drops a task with a bad time (e.g. "25:99"), so a possible conflict is never reported and nothing says so. It flags **completed** tasks as conflicts (1 vs 0 in my test). It doesn't say whether the clash is same-pet, cross-pet or a double-booked person. Plain all-pairs loop with no early exit. |
| **Decision** | **Used in the final project.** | Not used. Its overlap line and its defensive try/except are good ideas, but the unusable messages and the ignored completed tasks would have failed the multi-pet and caregiver features. |

| Scenario (real `Task` objects) | Gemini | Claude |
|---|---:|---:|
| same start, two pets | 1 | 1 |
| partial overlap | 1 | 1 |
| contained | 1 | 1 |
| back-to-back (should be 0) | 0 | 0 |
| different days (should be 0) | 0 | 0 |
| one task already completed (should be 0) | **1** | 0 |
| same person double-booked | 1 | 1 |

**Takeaway:** both models got the algorithm right. The difference was in fitting it to my actual code: Gemini wrote generic code against guessed attribute names, while Claude's version used the real fields and carried the project's rules (completed tasks, caregivers). The fair criticism of Claude's version is that it would be safer if `detect_conflicts` also skipped any task it cannot parse and reported it; that is a possible next improvement.

#### The same comparison at project scale

I also gave Gemini the full assignment and rubric ([its reply](screenshots/gemini/project_01_summary.png)) and read the result against the instructions and rubric. What was good: a compact merge-intervals "next free slot" search, a `mark_incomplete()` toggle, and an interactive menu that uses `tabulate` when installed. What I found missing or wrong:

| Check | Gemini's full-project reply | Final project (Claude) |
|---|---|---|
| Streamlit UI (Phases 3 and 6) | No `app.py`; replaced with a terminal `input()` menu ([main.py](screenshots/gemini/project_06_main_a.png)) | `app.py` with `st.session_state`, forms, banners |
| `Owner.get_all_tasks()` that the Scheduler reads | Not present; the Scheduler loops over pets itself ([scheduler](screenshots/gemini/project_04_scheduler.png)) | Present, and the Scheduler reads through it |
| Dataclasses for Task and Pet (Phase 1) | Plain classes | `@dataclass` |
| Recurring daily/weekly tasks (Phase 4) | Not implemented | `Task.next_occurrence()` + `Scheduler.mark_task_complete()` |
| "Is someone available?" | Only avoids other tasks; no people or availability | `Caregiver` windows + `available_caregivers()` |
| UML draft + final | Final only; it and the README list a `PawPalPersistence` class that does not exist in the code (just two functions) ([UML](screenshots/gemini/project_10_uml.png)) | `uml_draft.mmd` and `uml_final.mmd`, matching the code |
| Tests | 7 tests; the "sorting" test only asserts the first item's priority is High or Medium, and there is no recurrence test ([tests](screenshots/gemini/project_09_tests.png)) | 32 tests with ordering, recurrence and edge cases, checked by breaking the code |
| README sample outputs | Not from a real run: the pytest block contains placeholders (`Python 3.10.x`, `pytest-7.x.x`, `/path/to/pawpal`) and the CLI table shows "Fetch with ball" and a *Completed* task, but its own `main.py` seeds "Fetch with tennis ball" and *Pending* ([README](screenshots/gemini/project_11_readme.png)) | Pasted from real runs |
| Model comparison in `ai_interactions.md` | Describes "Claude 3.5 Sonnet / Gemini 1.5 Pro" and "GPT-4o Agent" comparisons that were never run ([file](screenshots/gemini/project_12_ai_interactions_reflection.png)) | Only comparisons that were actually run, with numbers |

**Final decision:** I kept Claude's implementation for the whole project and did not merge any Gemini code into the repo. The most useful lesson was verification: Gemini's summary looked complete, but running its code against my real classes and checking it against the assignment's exact requirements showed where it fell short. An AI answer that sounds finished still has to be tested against your own data and requirements.
