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

### Multi-model comparison (optional, to complete)

<!--
The rubric asks for a comparison of at least two AI MODELS or prompting strategies. The table above
compares two strategies (done). If you also want to compare two models, paste the SAME prompt below
into a second assistant (e.g. ChatGPT or Gemini), then fill in Option B. Delete this section if you
don't do it.
-->

**Prompt used for both models:** "Write a Python method for a pet-care scheduler that takes a list of Task objects (each has `due_date`, `due_time` as 'HH:MM', and `duration_mins`) and returns a list of human-readable warnings for every pair that overlaps in time. It must not raise exceptions."

| | Option A | Option B |
|-|----------|----------|
| **Model / tool used** | Claude | *(fill in: e.g. ChatGPT / Gemini)* |
| **Response summary** | Sort by (date, start), sweep forward until the next task starts after the current one ends. | |
| **What was useful** | Efficient, agrees with brute force. | |
| **Problems noticed** | Needs a helper to describe the pair. | |
| **Decision** | Used in `Scheduler.detect_conflicts`. | |
