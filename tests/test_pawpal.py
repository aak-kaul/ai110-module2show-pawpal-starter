"""Automated tests for PawPal+ (run with: python -m pytest)."""

from datetime import date, timedelta

import pytest

from pawpal_system import Caregiver, Owner, Pet, Scheduler, Task

DAY = date(2026, 1, 5)  # fixed date so tests are deterministic


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #


@pytest.fixture
def owner() -> Owner:
    """An owner with two pets and two caregivers, but no tasks yet."""
    o = Owner("Jordan")
    o.add_pet(Pet("Luna", "dog", 4))
    o.add_pet(Pet("Whiskers", "cat", 7))
    o.add_caregiver(Caregiver("Jordan", [("07:00", "09:00"), ("17:00", "21:00")]))
    o.add_caregiver(Caregiver("Sam", [("12:00", "14:00")]))
    return o


@pytest.fixture
def scheduler(owner: Owner) -> Scheduler:
    """A scheduler bound to the fixture owner."""
    return Scheduler(owner)


def make_task(description="Walk", due_time="08:00", **kwargs) -> Task:
    """Build a task on the fixed test date with sensible defaults."""
    kwargs.setdefault("due_date", DAY)
    kwargs.setdefault("duration_mins", 30)
    return Task(description, due_time, **kwargs)


# --------------------------------------------------------------------------- #
# Core classes (Phase 2)
# --------------------------------------------------------------------------- #


def test_mark_complete_changes_status():
    """Calling mark_complete() flips is_completed from False to True."""
    task = make_task()
    assert task.is_completed is False
    task.mark_complete()
    assert task.is_completed is True


def test_adding_task_increases_pet_task_count(owner):
    """Pet.add_task grows the pet's task list and stamps the pet's name on the task."""
    luna = owner.get_pet("Luna")
    assert len(luna.tasks) == 0
    luna.add_task(make_task())
    luna.add_task(make_task("Feed", "09:00"))
    assert len(luna.tasks) == 2
    assert all(t.pet_name == "Luna" for t in luna.tasks)


def test_task_rejects_invalid_values():
    """Bad times, priorities, categories and durations fail fast with ValueError."""
    for kwargs in (
        {"due_time": "25:00"},
        {"due_time": "8am"},
        {"priority": "urgent"},
        {"category": "nap"},
        {"duration_mins": 0},
        {"frequency": "Monthly"},
    ):
        with pytest.raises(ValueError):
            make_task(**kwargs)


def test_owner_rejects_duplicate_pet_names(owner):
    """Pet names are unique (case-insensitive) so tasks stay unambiguous."""
    with pytest.raises(ValueError):
        owner.add_pet(Pet("luna"))


def test_owner_get_all_tasks_spans_every_pet(owner):
    """Owner.get_all_tasks returns tasks from all pets in one list."""
    owner.get_pet("Luna").add_task(make_task("Walk"))
    owner.get_pet("Whiskers").add_task(make_task("Meds", "09:00"))
    assert {t.description for t in owner.get_all_tasks()} == {"Walk", "Meds"}


# --------------------------------------------------------------------------- #
# Sorting
# --------------------------------------------------------------------------- #


def test_sort_by_time_is_chronological_across_pets(owner, scheduler):
    """Tasks added out of order, for different pets, come back earliest first."""
    owner.get_pet("Luna").add_task(make_task("Evening walk", "18:00"))
    owner.get_pet("Whiskers").add_task(make_task("Breakfast", "07:30"))
    owner.get_pet("Luna").add_task(make_task("Midday walk", "12:30"))
    owner.get_pet("Whiskers").add_task(make_task("Late play", "09:05"))  # catches '9:05' vs '12:30' string bugs
    times = [t.due_time for t in scheduler.sort_by_time()]
    assert times == ["07:30", "09:05", "12:30", "18:00"]


def test_sort_by_time_orders_dates_before_times(owner, scheduler):
    """A task tomorrow at 06:00 sorts after a task today at 20:00."""
    luna = owner.get_pet("Luna")
    luna.add_task(make_task("Tomorrow", "06:00", due_date=DAY + timedelta(days=1)))
    luna.add_task(make_task("Today", "20:00"))
    assert [t.description for t in scheduler.sort_by_time()] == ["Today", "Tomorrow"]


def test_sort_by_priority_then_time(owner, scheduler):
    """High priority comes first; ties are broken by time."""
    luna = owner.get_pet("Luna")
    luna.add_task(make_task("low early", "06:00", priority="low"))
    luna.add_task(make_task("high late", "20:00", priority="high"))
    luna.add_task(make_task("high early", "08:00", priority="high"))
    luna.add_task(make_task("medium", "09:00", priority="medium"))
    assert [t.description for t in scheduler.sort_by_priority()] == [
        "high early", "high late", "medium", "low early",
    ]


def test_schedule_for_day_only_includes_that_day(owner, scheduler):
    """get_schedule_for_day filters to one date and sorts it."""
    luna = owner.get_pet("Luna")
    luna.add_task(make_task("B", "10:00"))
    luna.add_task(make_task("A", "08:00"))
    luna.add_task(make_task("Other day", "07:00", due_date=DAY + timedelta(days=2)))
    assert [t.description for t in scheduler.get_schedule_for_day(DAY)] == ["A", "B"]


def test_empty_pets_produce_empty_schedule(scheduler):
    """A pet with no tasks (edge case) doesn't break sorting, filtering or formatting."""
    assert scheduler.sort_by_time() == []
    assert scheduler.filter_tasks(pet_name="Luna") == []
    assert scheduler.detect_conflicts() == []
    assert scheduler.format_schedule() == "  (no tasks)"


# --------------------------------------------------------------------------- #
# Filtering
# --------------------------------------------------------------------------- #


def test_filter_by_pet_status_category_and_caregiver(owner, scheduler):
    """Each filter narrows results correctly and filters can be combined."""
    luna, whiskers = owner.get_pet("Luna"), owner.get_pet("Whiskers")
    walk = luna.add_task(make_task("Walk", "08:00", category="walk", assigned_to="Jordan"))
    luna.add_task(make_task("Feed", "09:00", category="feeding"))
    whiskers.add_task(make_task("Play", "10:00", category="play", assigned_to="Sam"))
    walk.mark_complete()

    assert len(scheduler.filter_tasks(pet_name="luna")) == 2  # case-insensitive
    assert [t.description for t in scheduler.filter_tasks(completed=True)] == ["Walk"]
    assert len(scheduler.filter_tasks(completed=False)) == 2
    assert [t.description for t in scheduler.filter_tasks(category="play")] == ["Play"]
    assert [t.description for t in scheduler.filter_tasks(caregiver="sam")] == ["Play"]
    assert scheduler.filter_tasks(pet_name="Luna", completed=False)[0].description == "Feed"


# --------------------------------------------------------------------------- #
# Recurring tasks
# --------------------------------------------------------------------------- #


def test_completing_daily_task_creates_next_day_task(owner, scheduler):
    """Daily task -> completing it adds an identical, incomplete task for DAY + 1."""
    luna = owner.get_pet("Luna")
    task = luna.add_task(make_task("Breakfast", "07:30", frequency="Daily", priority="high"))
    new_task = scheduler.mark_task_complete(task.task_id)

    assert task.is_completed is True
    assert new_task is not None and new_task is not task
    assert new_task.due_date == DAY + timedelta(days=1)
    assert (new_task.description, new_task.due_time, new_task.priority) == ("Breakfast", "07:30", "high")
    assert new_task.is_completed is False
    assert new_task.pet_name == "Luna" and new_task in luna.tasks
    assert len(luna.tasks) == 2


def test_completing_weekly_task_creates_task_seven_days_later(owner, scheduler):
    """Weekly task -> next occurrence is exactly 7 days later."""
    task = owner.get_pet("Luna").add_task(make_task("Bath", frequency="Weekly"))
    new_task = scheduler.mark_task_complete(task.task_id)
    assert new_task.due_date == DAY + timedelta(days=7)


def test_daily_recurrence_crosses_month_boundary(owner, scheduler):
    """timedelta handles month/year rollover (Dec 31 -> Jan 1)."""
    task = owner.get_pet("Luna").add_task(make_task("Walk", frequency="Daily", due_date=date(2026, 12, 31)))
    assert scheduler.mark_task_complete(task.task_id).due_date == date(2027, 1, 1)


def test_one_time_task_does_not_recur(owner, scheduler):
    """A 'Once' task completes without creating anything new."""
    luna = owner.get_pet("Luna")
    task = luna.add_task(make_task("Vet visit", frequency="Once"))
    assert scheduler.mark_task_complete(task.task_id) is None
    assert len(luna.tasks) == 1


def test_completing_same_task_twice_does_not_duplicate(owner, scheduler):
    """Re-completing an already-completed recurring task must not spawn a second copy."""
    luna = owner.get_pet("Luna")
    task = luna.add_task(make_task("Walk", frequency="Daily"))
    scheduler.mark_task_complete(task.task_id)
    assert scheduler.mark_task_complete(task.task_id) is None
    assert len(luna.tasks) == 2


def test_completing_unknown_task_raises(scheduler):
    """Unknown task ids raise KeyError rather than silently doing nothing."""
    with pytest.raises(KeyError):
        scheduler.mark_task_complete("nope")


# --------------------------------------------------------------------------- #
# Conflict detection
# --------------------------------------------------------------------------- #


def test_conflict_flags_identical_times_for_different_pets(owner, scheduler):
    """Two tasks at exactly the same time (different pets) produce a warning."""
    owner.get_pet("Luna").add_task(make_task("Walk", "08:00"))
    warnings = scheduler.schedule_task("Whiskers", make_task("Meds", "08:00"))
    assert len(warnings) == 1
    assert "different pets" in warnings[0] and "Walk" in warnings[0] and "Meds" in warnings[0]
    assert "Whiskers" in warnings[0]  # pet name is stamped before the warning is built


def test_conflict_flags_same_pet_and_partial_overlap(owner, scheduler):
    """Partially overlapping tasks for the same pet are caught, not just exact matches."""
    scheduler.schedule_task("Luna", make_task("Walk", "08:00", duration_mins=30))
    warnings = scheduler.schedule_task("Luna", make_task("Feed", "08:20", duration_mins=10))
    assert len(warnings) == 1 and "same pet" in warnings[0]


def test_back_to_back_tasks_do_not_conflict(owner, scheduler):
    """08:00-08:30 followed by 08:30-09:00 is fine."""
    scheduler.schedule_task("Luna", make_task("Walk", "08:00", duration_mins=30))
    assert scheduler.schedule_task("Luna", make_task("Feed", "08:30")) == []


def test_conflicts_ignore_completed_tasks_and_other_days(owner, scheduler):
    """Done tasks and tasks on different dates never conflict."""
    done = owner.get_pet("Luna").add_task(make_task("Walk", "08:00"))
    done.mark_complete()
    owner.get_pet("Luna").add_task(make_task("Tomorrow", "08:00", due_date=DAY + timedelta(days=1)))
    assert scheduler.schedule_task("Whiskers", make_task("Meds", "08:00")) == []
    assert scheduler.detect_conflicts() == []


def test_detect_conflicts_scans_everything_and_reports_double_booking(owner, scheduler):
    """detect_conflicts finds every overlapping pair and notes a double-booked caregiver."""
    luna, whiskers = owner.get_pet("Luna"), owner.get_pet("Whiskers")
    luna.add_task(make_task("Walk", "18:00", assigned_to="Jordan"))
    whiskers.add_task(make_task("Brush", "18:15", assigned_to="Jordan"))
    luna.add_task(make_task("Feed", "07:00"))
    whiskers.add_task(make_task("Meds", "07:00"))
    warnings = scheduler.detect_conflicts(DAY)
    assert len(warnings) == 2
    assert sum("double-booked" in w for w in warnings) == 1


def test_scheduling_never_crashes_on_conflict(owner, scheduler):
    """Conflicting tasks are still added (warn, don't block)."""
    scheduler.schedule_task("Luna", make_task("Walk", "08:00"))
    scheduler.schedule_task("Luna", make_task("Feed", "08:00"))
    assert len(owner.get_pet("Luna").tasks) == 2


def test_schedule_task_unknown_pet_raises(scheduler):
    """Scheduling for a pet that doesn't exist is an error, not a silent no-op."""
    with pytest.raises(KeyError):
        scheduler.schedule_task("Ghost", make_task())


# --------------------------------------------------------------------------- #
# Caregiver availability + next slot
# --------------------------------------------------------------------------- #


def test_available_caregivers_respects_windows_and_bookings(owner, scheduler):
    """A caregiver is available only inside a window AND without a clashing task."""
    assert scheduler.available_caregivers(DAY, "08:00", 30) == ["Jordan"]
    assert scheduler.available_caregivers(DAY, "12:30", 30) == ["Sam"]
    assert scheduler.available_caregivers(DAY, "15:00", 30) == []
    assert scheduler.available_caregivers(DAY, "08:45", 30) == []  # runs past Jordan's 09:00 window
    owner.get_pet("Luna").add_task(make_task("Walk", "08:00", assigned_to="Jordan"))
    assert scheduler.available_caregivers(DAY, "08:00", 30) == []  # now booked
    assert scheduler.available_caregivers(DAY + timedelta(days=1), "08:00", 30) == ["Jordan"]


def test_assign_caregiver_only_when_available(owner, scheduler):
    """assign_caregiver refuses people outside their availability."""
    task = owner.get_pet("Luna").add_task(make_task("Walk", "08:00"))
    assert scheduler.assign_caregiver(task, "Sam") is False and task.assigned_to is None
    assert scheduler.assign_caregiver(task, "jordan") is True and task.assigned_to == "Jordan"
    assert scheduler.assign_caregiver(task, "Nobody") is False


def test_schedule_task_warns_when_assigned_caregiver_unavailable(owner, scheduler):
    """Assigning someone outside their hours yields a warning (task still saved)."""
    warnings = scheduler.schedule_task("Luna", make_task("Walk", "15:00", assigned_to="Sam"))
    assert any("not available" in w for w in warnings)


def test_find_next_available_slot_skips_busy_times(owner, scheduler):
    """The first free slot skips caregiver bookings and the pet's own tasks."""
    assert scheduler.find_next_available_slot(DAY, 30) == ("07:00", "Jordan")
    owner.get_pet("Luna").add_task(make_task("Walk", "07:00", assigned_to="Jordan"))
    assert scheduler.find_next_available_slot(DAY, 30) == ("07:30", "Jordan")
    # Luna herself is busy 07:00-07:30, so for Luna the slot is 07:30 as well; add another to push it
    owner.get_pet("Luna").add_task(make_task("Feed", "07:30", assigned_to="Jordan"))
    assert scheduler.find_next_available_slot(DAY, 30, pet_name="Luna") == ("08:00", "Jordan")
    assert scheduler.find_next_available_slot(DAY, 30, caregiver_name="Sam", earliest="06:00") == ("12:00", "Sam")


def test_find_next_available_slot_returns_none_when_impossible(owner, scheduler):
    """No slot -> None (too long for any window, or no caregivers at all)."""
    assert scheduler.find_next_available_slot(DAY, 300) is None
    assert scheduler.find_next_available_slot(DAY, 30, caregiver_name="Nobody") is None
    assert Scheduler(Owner("Solo")).find_next_available_slot(DAY, 15) is None


def test_caregiver_window_validation():
    """A window must end after it starts, and times must be valid."""
    person = Caregiver("Pat")
    with pytest.raises(ValueError):
        person.add_window("10:00", "09:00")
    with pytest.raises(ValueError):
        person.add_window("09:00", "99:00")


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #


def test_json_round_trip_preserves_everything(owner, tmp_path):
    """save_to_json then load_from_json rebuilds pets, tasks, caregivers and dates."""
    task = owner.get_pet("Luna").add_task(
        make_task("Walk", "08:00", frequency="Daily", priority="high", category="walk", assigned_to="Jordan")
    )
    task.mark_complete()
    path = tmp_path / "data.json"
    owner.save_to_json(str(path))

    loaded = Owner.load_from_json(str(path))
    assert loaded.name == "Jordan"
    assert [p.name for p in loaded.pets] == ["Luna", "Whiskers"]
    assert [c.name for c in loaded.caregivers] == ["Jordan", "Sam"]
    assert loaded.get_caregiver("Jordan").availability == [("07:00", "09:00"), ("17:00", "21:00")]
    restored = loaded.get_pet("Luna").tasks[0]
    assert restored == task  # dataclass equality: every field, including due_date and task_id
    assert restored.is_completed is True


def test_load_missing_file_raises(tmp_path):
    """Loading a file that doesn't exist raises FileNotFoundError (the UI catches this)."""
    with pytest.raises(FileNotFoundError):
        Owner.load_from_json(str(tmp_path / "missing.json"))
