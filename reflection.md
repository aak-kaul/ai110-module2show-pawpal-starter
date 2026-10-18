# PawPal+ Project Reflection

## 1. System Design

**a. Initial design**

**Three core actions a user must be able to do** (in plain language):

1. **Add pets and the people who can help.** A pet owner can add several pets (a dog and a cat, say) and list the people who can help with care, along with the hours each is free.
2. **Schedule care tasks for a pet.** The owner schedules walks, feeding, grooming (cleaning), play and medication, each with a time, duration, priority and how often it repeats, and can say who will do it.
3. **See today's plan and know it's workable.** The owner sees every pet's tasks in one sorted schedule, gets warned when two tasks collide, can ask "is anyone free at 12:30?", and can tick tasks off (repeating ones come back automatically).

**Initial UML (`diagrams/uml_draft.mmd`)** has four classes:

- **Task**: one care activity. It holds a description, time, duration, frequency and completion status, and knows how to `mark_complete()`.
- **Pet**: a pet's profile (name, species, age) plus its own list of Tasks, with `add_task()`.
- **Owner**: has a list of Pets and one method, `get_all_tasks()`, that gathers every pet's tasks into a single list.
- **Scheduler**: the "brain". It is given an Owner and reads tasks **through the Owner**, so it works across all pets. It sorts, filters and detects conflicts, and holds no data of its own.

Relationships: Owner *has* Pets, Pet *has* Tasks, Scheduler *reads from* Owner.

**b. Design changes**

Yes, the design changed in four ways:

1. **Scheduler no longer holds pets.** The very first skeleton I had (visible in a leftover compiled file in the repo) gave the Scheduler its own `pets` list and an `add_pet()`. That duplicates the Owner's data, and a Scheduler built that way can end up looking at a different set of pets than the Owner. I changed it so the Scheduler takes an `Owner` and always calls `Owner.get_all_tasks()`. This is what makes every algorithm work across multiple pets.
2. **Added a `Caregiver` class.** My four-class draft had no answer to "is someone available to walk the dog at this time?", which is one of the main things I wanted. A Caregiver has a name and daily availability windows, and the Scheduler checks windows against the tasks they already have. This was the only new class.
3. **Task grew fields:** `priority`, `category` (walk / feeding / grooming / play / meds), `due_date`, `assigned_to`, a `pet_name` stamped by `Pet.add_task`, and a `task_id`. `due_date` is needed so "daily" recurrence can compute *today + 1 day*. `pet_name` lets a task be described and filtered without carrying the pet around. `task_id` gives the UI and recurrence logic a safe way to refer to one task.
4. **Return type of `get_all_tasks`.** The first skeleton returned `(pet_name, task)` tuples. Putting `pet_name` on the Task itself made every method (sort, filter, conflict messages) simpler, because they all deal with a plain list of Tasks.

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

The scheduler considers:

- **Time:** start time and duration, so it knows when a task ends and whether it overlaps another.
- **Date:** tasks belong to a day, and recurring tasks move to a new day.
- **Priority:** low / medium / high, used by the priority-first view.
- **People:** each caregiver's availability windows, and what they're already booked for.
- **Pet:** a pet can't do two things at once (checked when looking for an open slot for that pet).

I ranked **time conflicts and availability** as the most important constraints because those are what actually make a plan fail in real life: you can't walk Luna and brush Whiskers at 18:15 if you're the only person home. **Priority** matters less for *when* a task happens (the owner picks the time), so it only orders the "what's most important" view rather than moving tasks automatically.

**b. Tradeoffs**

**Tradeoff: conflict detection warns instead of blocking or auto-rescheduling, and it only compares tasks on the same date with fixed start times.** When two tasks overlap, the scheduler still saves the task and returns a clear warning message (same pet / different pets / person double-booked). It doesn't refuse the task, and it doesn't try to shuffle the day automatically. It also doesn't model travel time between tasks or availability that differs by weekday.

This is reasonable for a pet owner because they know things the app doesn't (the dog walker can take the dog and the cat at the same time; a feeding can happen while the walk is waiting). A hard block would be annoying and an automatic reshuffle would be surprising. A visible warning leaves the decision with the human.

A related choice: I first considered the "lightweight" approach of only checking for **identical start times**. I compared it against full interval overlap on real inputs. Exact-match missed a 08:00-08:30 walk overlapping an 08:20 feeding (0 conflicts found vs. 1). The overlap version costs only a few extra lines, so I kept it (details in `ai_interactions.md`).

---

## 3. AI Collaboration

**a. How you used AI**

I used Claude as an agent for the whole build: it created the logic layer, demo script, tests, UI wiring, both UML diagrams, and the docs from my instructions and the assignment rubric. In practice that covered design brainstorming (turning my list of actions into classes), generating the code, writing and running the tests, and reviewing its own output.

The most helpful prompts were **specific and constraint-heavy**: pointing at the assignment's exact requirements ("the Scheduler must read from an Owner method rather than from a single pet", "return a warning rather than crashing", "use `timedelta`") and describing real scenarios I care about (walk, feed, clean, play with the dog; who is free at what time; multiple pets). Vague prompts like "make it smarter" give generic answers; specific ones give testable code.


**b. Judgment and verification**

Things I didn't accept as-is:

- **Scheduler owning pets** (see 1b): the first skeleton's design would have broken the multi-pet requirement, so I redesigned it to read from the Owner.
- **"Lightweight" exact-time conflict checks:** I rejected this after testing it against partial and contained overlaps (see 2b).
- **A bug the demo exposed.** The first run printed a conflict warning as `overlaps 's 'Brush fur'`, with the pet's name missing. The cause was that conflicts were checked *before* the task was attached to its pet (which is when `pet_name` is filled in). Fixing it meant swapping two lines in `Scheduler.schedule_task`, and I added a test asserting the pet name appears in the warning.
- **Table formatting:** an early version put emoji inside padded columns, which misaligned the table because an emoji is one character but two screen columns wide. I moved the emoji to fixed-width fields.

How I verified correctness:

1. **Ran `main.py`** and read the output for each feature, rather than trusting that it "looked right". That is how the bug above showed up.
2. **Wrote 32 pytest tests** covering happy paths and edge cases (empty pets, month rollover, back-to-back tasks, completing twice, bad input).
3. **Mutation-checked the tests:** I deliberately broke the code (daily recurrence +2 days, reversed sort, `<=` instead of `<` in the overlap check) and confirmed the right tests failed. A test suite that can't fail isn't evidence of anything.
4. **Cross-checked the conflict sweep** against a brute-force all-pairs comparison on 3,000 tasks; both found exactly the same pairs.
5. **Smoke-tested the UI flows** (add pets, duplicate pet, add task, conflict banner, mark done, reload from `data.json`, corrupted file) against a mocked Streamlit. For the final checks I ran `python -m pytest` and `streamlit run app.py` locally and clicked through the example workflow in the README.

---

## 4. Testing and Verification

**a. What you tested**

I tested: task completion; adding tasks to pets; sorting by time (across pets and dates) and by priority; filtering by pet / status / activity / person; daily and weekly recurrence (including Dec 31 → Jan 1 and not duplicating when completed twice); conflict detection (identical times, partial overlap, back-to-back tasks *not* flagged, ignoring completed tasks and other days, caregiver double-booking); availability and next-open-slot; JSON save/load; and input validation.

These matter because they're the behaviours a user would notice immediately if wrong: a walk shown in the wrong order, a daily feeding that never comes back, or a false/missed conflict.

**b. Confidence**

**4 out of 5.** The logic layer is well covered, and I know the tests can fail. What keeps it from 5 is that the UI isn't covered by automated tests and a few modelling choices are simplified (see 2b).

Edge cases I'd test next: tasks that cross midnight (e.g. 23:45 + 30 minutes), a daily task that's skipped for several days (should it catch up?), caregivers with different hours on different weekdays, daylight-saving transitions, and very large numbers of tasks in the UI.

---

## 5. Reflection

**a. What went well**

I'm most satisfied with the separation between the logic layer and the interface. Because `pawpal_system.py` contains all the rules and the Streamlit app and `main.py` only call it, I could verify nearly everything from the terminal and with fast tests. The Scheduler reading everything through `Owner.get_all_tasks()` kept every feature multi-pet from the start instead of retrofitting it.

**b. What you would improve**

- Let tasks have **per-weekday** caregiver availability and a notion of **"can be done together"** (walking two dogs at once) so fewer warnings are false alarms.
- Add **edit/delete** for tasks in the UI (the logic exists: `Pet.remove_task`).
- Offer **one-click fixes** for a conflict ("move to next open slot" using `find_next_available_slot`).
- Handle tasks that **cross midnight**.

**c. Key takeaway**

Being the "lead architect" means the AI can write code quickly, but *I* decide what the system is for, which tradeoffs are acceptable, and what counts as proof it works. The best moments were when I pushed back (the Scheduler's data ownership, exact-match conflicts) or when running the output revealed something that looked fine in the code but wasn't. Trust, but verify: run it, read the output, and try to break it.
