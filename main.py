"""PawPal+ CLI demo: exercises the logic layer end to end (no Streamlit needed).

Run with:  python main.py
"""

import os
import tempfile
from datetime import date, timedelta

from pawpal_system import Caregiver, Owner, Pet, Scheduler, Task


def banner(title: str) -> None:
    """Print a section heading."""
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def build_demo_owner() -> Owner:
    """Create an owner, two pets and two caregivers (everything the demo uses)."""
    owner = Owner("Jordan")

    jordan = Caregiver("Jordan", [("07:00", "09:00"), ("17:00", "21:00")])
    sam = Caregiver("Sam (dog walker)", [("12:00", "14:00"), ("17:00", "19:00")])
    owner.add_caregiver(jordan)
    owner.add_caregiver(sam)

    owner.add_pet(Pet("Luna", "dog", 4, "Loves fetch"))
    owner.add_pet(Pet("Whiskers", "cat", 7, "Needs meds with breakfast"))
    return owner


def main() -> None:
    """Run the full demo."""
    today = date.today()
    owner = build_demo_owner()
    scheduler = Scheduler(owner)

    # --- Tasks are added deliberately OUT OF ORDER to prove sorting works --- #
    banner("1. Adding tasks (out of order) for two pets")
    scheduler.schedule_task("Luna", Task("Evening walk", "18:00", 30, "Daily", "high", "walk", today, "Jordan"))
    scheduler.schedule_task("Luna", Task("Breakfast", "07:30", 10, "Daily", "high", "feeding", today, "Jordan"))
    scheduler.schedule_task("Whiskers", Task("Medication", "07:40", 5, "Daily", "high", "meds", today, "Jordan"))
    scheduler.schedule_task("Luna", Task("Midday walk", "12:30", 30, "Daily", "medium", "walk", today, "Sam (dog walker)"))
    scheduler.schedule_task("Whiskers", Task("Laser-pointer play", "17:15", 20, "Once", "low", "play", today))
    scheduler.schedule_task("Luna", Task("Bath", "20:00", 40, "Weekly", "medium", "grooming", today, "Jordan"))
    print(f"Added {len(scheduler.get_all_tasks())} tasks across {len(owner.pets)} pets.")

    banner(f"2. Today's Schedule ({today:%A, %B %d}) -- sorted by time, all pets")
    print(scheduler.format_schedule(scheduler.get_schedule_for_day(today)))

    banner("3. Why this plan?")
    for line in scheduler.explain_schedule(today):
        print("  " + line)

    banner("4. Filtering")
    print("Luna only:")
    print(scheduler.format_schedule(scheduler.sort_by_time(scheduler.filter_tasks(pet_name="Luna"))))
    print("\nWalks only (all pets):")
    print(scheduler.format_schedule(scheduler.sort_by_time(scheduler.filter_tasks(category="walk"))))
    print("\nAssigned to Sam:")
    print(scheduler.format_schedule(scheduler.filter_tasks(caregiver="Sam (dog walker)")))

    banner("5. Priority-first view (high -> low, then by time)")
    print(scheduler.format_schedule(scheduler.sort_by_priority()))

    banner("6. Conflict detection (warnings, never crashes)")
    print("Adding Luna 'Fetch' at 12:30 -- the exact same time as her midday walk (same pet):")
    for warning in scheduler.schedule_task("Luna", Task("Fetch", "12:30", 15, "Once", "low", "play", today)):
        print("  " + warning)
    print("\nAdding Whiskers 'Brush fur' at 18:15 -- overlaps Luna's walk, and Jordan can't do both:")
    for warning in scheduler.schedule_task(
        "Whiskers", Task("Brush fur", "18:15", 15, "Once", "low", "grooming", today, "Jordan")
    ):
        print("  " + warning)
    print("\nFull-day conflict scan across all pets:")
    for warning in scheduler.detect_conflicts(today):
        print("  " + warning)

    banner("7. Who is available? (caregiver windows minus tasks they already have)")
    for start, mins in [("08:00", 30), ("12:00", 30), ("12:30", 30), ("18:00", 30), ("23:00", 30)]:
        people = scheduler.available_caregivers(today, start, mins)
        print(f"  {start} for {mins}m -> {', '.join(people) if people else 'nobody available'}")

    banner("8. Next available slot (stretch: finds a free caregiver + time)")
    slot = scheduler.find_next_available_slot(today, 45, pet_name="Luna")
    print(f"  Next free 45-minute slot for Luna: {slot[0]} with {slot[1]}" if slot else "  No slot found")
    slot = scheduler.find_next_available_slot(today, 30, caregiver_name="Sam (dog walker)", earliest="12:00")
    print(f"  Next free 30-minute slot with Sam from 12:00: {slot[0]}" if slot else "  Sam has no free slot")

    banner("9. Recurring tasks: completing a Daily task spawns tomorrow's")
    breakfast = next(t for t in scheduler.get_all_tasks() if t.description == "Breakfast")
    new_task = scheduler.mark_task_complete(breakfast.task_id)
    print(f"  Completed: {breakfast.description} ({breakfast.due_date})")
    print(f"  Created:   {new_task.description} due {new_task.due_date} at {new_task.due_time} "
          f"(today + 1 day = {today + timedelta(days=1)})")
    bath = next(t for t in scheduler.get_all_tasks() if t.description == "Bath")
    weekly = scheduler.mark_task_complete(bath.task_id)
    print(f"  Weekly 'Bath' completed -> next one due {weekly.due_date} (today + 7 days)")
    print("\nPending vs. completed:")
    print("  Completed:", [t.description for t in scheduler.filter_tasks(completed=True)])

    banner("10. Persistence: save to JSON and load it back")
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "data.json")
        owner.save_to_json(path)
        loaded = Owner.load_from_json(path)
    print(f"  Saved + reloaded owner '{loaded.name}' with {len(loaded.pets)} pets, "
          f"{len(loaded.get_all_tasks())} tasks, {len(loaded.caregivers)} caregivers "
          f"(original had {len(owner.get_all_tasks())} tasks).")


if __name__ == "__main__":
    main()
