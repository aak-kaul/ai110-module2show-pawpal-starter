"""PawPal+ logic layer: Task, Pet, Caregiver, Owner and Scheduler.

The UI (app.py) and the CLI demo (main.py) are thin clients of this module.
Dependency direction: Scheduler -> Owner -> Pet -> Task  (Owner -> Caregiver).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

# --------------------------------------------------------------------------- #
# Constants & small helpers
# --------------------------------------------------------------------------- #

FREQUENCIES = ("Once", "Daily", "Weekly")
PRIORITIES = ("low", "medium", "high")
PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}  # lower rank = more urgent
CATEGORIES = ("walk", "feeding", "grooming", "play", "meds", "other")
CATEGORY_EMOJI = {
    "walk": "🐕",
    "feeding": "🍖",
    "grooming": "🛁",
    "play": "🎾",
    "meds": "💊",
    "other": "📝",
}
PRIORITY_EMOJI = {"high": "🔴", "medium": "🟡", "low": "🟢"}
TimeWindow = Tuple[str, str]  # ("HH:MM", "HH:MM")


def parse_time(value: str) -> int:
    """Convert an 'HH:MM' string into minutes after midnight (raises ValueError if invalid)."""
    try:
        hours_text, minutes_text = value.strip().split(":")
        hours, minutes = int(hours_text), int(minutes_text)
    except (ValueError, AttributeError):
        raise ValueError(f"Time must look like 'HH:MM', got {value!r}") from None
    if not (0 <= hours <= 23 and 0 <= minutes <= 59):
        raise ValueError(f"Time out of range: {value!r}")
    return hours * 60 + minutes


def format_time(minutes: int) -> str:
    """Convert minutes after midnight into a zero-padded 'HH:MM' string."""
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


# --------------------------------------------------------------------------- #
# Task
# --------------------------------------------------------------------------- #


@dataclass
class Task:
    """A single care activity (walk, feeding, grooming, play, meds...) for one pet."""

    description: str
    due_time: str  # "HH:MM" (24h) -- sorts correctly as a plain string
    duration_mins: int = 15
    frequency: str = "Once"  # Once | Daily | Weekly
    priority: str = "medium"  # low | medium | high
    category: str = "other"  # walk | feeding | grooming | play | meds | other
    due_date: date = field(default_factory=date.today)
    assigned_to: Optional[str] = None  # caregiver name, or None if unassigned
    pet_name: str = ""  # filled in automatically by Pet.add_task
    is_completed: bool = False
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    def __post_init__(self) -> None:
        """Normalise and validate fields so bad data fails fast."""
        self.frequency = self.frequency.capitalize()
        self.priority = self.priority.lower()
        self.category = self.category.lower()
        parse_time(self.due_time)
        if self.frequency not in FREQUENCIES:
            raise ValueError(f"frequency must be one of {FREQUENCIES}")
        if self.priority not in PRIORITIES:
            raise ValueError(f"priority must be one of {PRIORITIES}")
        if self.category not in CATEGORIES:
            raise ValueError(f"category must be one of {CATEGORIES}")
        if self.duration_mins <= 0:
            raise ValueError("duration_mins must be positive")

    @property
    def start_minutes(self) -> int:
        """Start time as minutes after midnight."""
        return parse_time(self.due_time)

    @property
    def end_minutes(self) -> int:
        """End time (start + duration) as minutes after midnight."""
        return self.start_minutes + self.duration_mins

    @property
    def end_time(self) -> str:
        """End time formatted as 'HH:MM' (capped at 23:59 for display)."""
        return format_time(min(self.end_minutes, 23 * 60 + 59))

    def mark_complete(self) -> None:
        """Mark this task as completed."""
        self.is_completed = True

    def overlaps(self, other: "Task") -> bool:
        """Return True if both tasks fall on the same date and their time ranges intersect."""
        return (
            self.due_date == other.due_date
            and self.start_minutes < other.end_minutes
            and other.start_minutes < self.end_minutes
        )

    def next_occurrence(self) -> Optional["Task"]:
        """Return a fresh copy due tomorrow (Daily) or in 7 days (Weekly); None for 'Once'."""
        if self.frequency == "Daily":
            delta = timedelta(days=1)
        elif self.frequency == "Weekly":
            delta = timedelta(weeks=1)
        else:
            return None
        return replace(
            self,
            due_date=self.due_date + delta,
            is_completed=False,
            task_id=uuid.uuid4().hex[:8],
        )

    def to_dict(self) -> dict:
        """Serialise to a JSON-friendly dict."""
        return {
            "description": self.description,
            "due_time": self.due_time,
            "duration_mins": self.duration_mins,
            "frequency": self.frequency,
            "priority": self.priority,
            "category": self.category,
            "due_date": self.due_date.isoformat(),
            "assigned_to": self.assigned_to,
            "pet_name": self.pet_name,
            "is_completed": self.is_completed,
            "task_id": self.task_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        """Rebuild a Task from a dict produced by to_dict."""
        data = dict(data)
        data["due_date"] = date.fromisoformat(data["due_date"])
        return cls(**data)


# --------------------------------------------------------------------------- #
# Pet
# --------------------------------------------------------------------------- #


@dataclass
class Pet:
    """A pet profile that owns a list of care tasks."""

    name: str
    species: str = "dog"
    age: int = 0
    notes: str = ""
    tasks: List[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> Task:
        """Attach a task to this pet (stamps the pet's name on it) and return it."""
        task.pet_name = self.name
        self.tasks.append(task)
        return task

    def remove_task(self, task_id: str) -> bool:
        """Remove a task by id; return True if something was removed."""
        before = len(self.tasks)
        self.tasks = [t for t in self.tasks if t.task_id != task_id]
        return len(self.tasks) < before

    def get_task(self, task_id: str) -> Optional[Task]:
        """Look up one of this pet's tasks by id."""
        return next((t for t in self.tasks if t.task_id == task_id), None)

    def get_tasks(self, include_completed: bool = True) -> List[Task]:
        """List this pet's tasks, optionally hiding completed ones."""
        if include_completed:
            return list(self.tasks)
        return [t for t in self.tasks if not t.is_completed]

    def to_dict(self) -> dict:
        """Serialise to a JSON-friendly dict (tasks included)."""
        return {
            "name": self.name,
            "species": self.species,
            "age": self.age,
            "notes": self.notes,
            "tasks": [t.to_dict() for t in self.tasks],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Pet":
        """Rebuild a Pet (and its tasks) from a dict produced by to_dict."""
        pet = cls(data["name"], data.get("species", "dog"), data.get("age", 0), data.get("notes", ""))
        pet.tasks = [Task.from_dict(t) for t in data.get("tasks", [])]
        return pet


# --------------------------------------------------------------------------- #
# Caregiver (who can do the task, and when)
# --------------------------------------------------------------------------- #


@dataclass
class Caregiver:
    """A person who can carry out pet tasks, with daily availability windows."""

    name: str
    availability: List[TimeWindow] = field(default_factory=list)

    def add_window(self, start: str, end: str) -> None:
        """Add a daily availability window like ('07:00', '09:00')."""
        if parse_time(start) >= parse_time(end):
            raise ValueError("Availability window must end after it starts")
        self.availability.append((start, end))

    def is_available(self, start: str, duration_mins: int) -> bool:
        """True if one availability window fully contains [start, start + duration]."""
        begin = parse_time(start)
        end = begin + duration_mins
        return any(parse_time(s) <= begin and end <= parse_time(e) for s, e in self.availability)

    def to_dict(self) -> dict:
        """Serialise to a JSON-friendly dict."""
        return {"name": self.name, "availability": [list(w) for w in self.availability]}

    @classmethod
    def from_dict(cls, data: dict) -> "Caregiver":
        """Rebuild a Caregiver from a dict produced by to_dict."""
        return cls(data["name"], [tuple(w) for w in data.get("availability", [])])


# --------------------------------------------------------------------------- #
# Owner
# --------------------------------------------------------------------------- #


@dataclass
class Owner:
    """The account holder: manages multiple pets and the people who can care for them."""

    name: str
    pets: List[Pet] = field(default_factory=list)
    caregivers: List[Caregiver] = field(default_factory=list)

    def add_pet(self, pet: Pet) -> Pet:
        """Add a pet; pet names must be unique (case-insensitive) so tasks stay unambiguous."""
        if self.get_pet(pet.name) is not None:
            raise ValueError(f"A pet named {pet.name!r} already exists")
        self.pets.append(pet)
        return pet

    def remove_pet(self, name: str) -> bool:
        """Remove a pet (and its tasks) by name; return True if found."""
        pet = self.get_pet(name)
        if pet is None:
            return False
        self.pets.remove(pet)
        return True

    def get_pet(self, name: str) -> Optional[Pet]:
        """Find a pet by name, ignoring case."""
        return next((p for p in self.pets if p.name.lower() == name.strip().lower()), None)

    def add_caregiver(self, caregiver: Caregiver) -> Caregiver:
        """Register a person (the owner included) who can do tasks."""
        if self.get_caregiver(caregiver.name) is not None:
            raise ValueError(f"A caregiver named {caregiver.name!r} already exists")
        self.caregivers.append(caregiver)
        return caregiver

    def get_caregiver(self, name: str) -> Optional[Caregiver]:
        """Find a caregiver by name, ignoring case."""
        return next((c for c in self.caregivers if c.name.lower() == name.strip().lower()), None)

    def get_all_tasks(self) -> List[Task]:
        """Return every task from every pet in one flat list (the Scheduler reads this)."""
        return [task for pet in self.pets for task in pet.tasks]

    # ---- persistence (stretch: data persistence layer) ---- #

    def to_dict(self) -> dict:
        """Serialise the whole owner -> pets -> tasks tree to a dict."""
        return {
            "name": self.name,
            "pets": [p.to_dict() for p in self.pets],
            "caregivers": [c.to_dict() for c in self.caregivers],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Owner":
        """Rebuild an Owner tree from a dict produced by to_dict."""
        return cls(
            data["name"],
            [Pet.from_dict(p) for p in data.get("pets", [])],
            [Caregiver.from_dict(c) for c in data.get("caregivers", [])],
        )

    def save_to_json(self, path: str = "data.json") -> None:
        """Write the owner, pets, caregivers and tasks to a JSON file."""
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(self.to_dict(), handle, indent=2)

    @classmethod
    def load_from_json(cls, path: str = "data.json") -> "Owner":
        """Read an Owner from a JSON file (raises FileNotFoundError / JSONDecodeError)."""
        with open(path, "r", encoding="utf-8") as handle:
            return cls.from_dict(json.load(handle))


# --------------------------------------------------------------------------- #
# Scheduler (the "brain")
# --------------------------------------------------------------------------- #


class Scheduler:
    """Retrieves, sorts, filters and validates tasks across ALL of an owner's pets."""

    def __init__(self, owner: Owner) -> None:
        """Create a scheduler bound to one owner (it always reads live data from them)."""
        self.owner = owner

    # ---- retrieval ---- #

    def get_all_tasks(self) -> List[Task]:
        """Fetch every task for every pet via Owner.get_all_tasks()."""
        return self.owner.get_all_tasks()

    def get_schedule_for_day(self, day: Optional[date] = None, include_completed: bool = True) -> List[Task]:
        """Return one day's tasks (all pets) in chronological order."""
        day = day or date.today()
        tasks = [t for t in self.get_all_tasks() if t.due_date == day]
        if not include_completed:
            tasks = [t for t in tasks if not t.is_completed]
        return self.sort_by_time(tasks)

    # ---- sorting ---- #

    def sort_by_time(self, tasks: Optional[List[Task]] = None) -> List[Task]:
        """Sort tasks chronologically by (date, 'HH:MM'); 24h strings sort correctly as text."""
        tasks = self.get_all_tasks() if tasks is None else tasks
        return sorted(tasks, key=lambda t: (t.due_date, t.due_time))

    def sort_by_priority(self, tasks: Optional[List[Task]] = None) -> List[Task]:
        """Sort by priority (high first), then date, then time -- most urgent first."""
        tasks = self.get_all_tasks() if tasks is None else tasks
        return sorted(tasks, key=lambda t: (PRIORITY_RANK[t.priority], t.due_date, t.due_time))

    # ---- filtering ---- #

    def filter_tasks(
        self,
        tasks: Optional[List[Task]] = None,
        pet_name: Optional[str] = None,
        completed: Optional[bool] = None,
        category: Optional[str] = None,
        caregiver: Optional[str] = None,
    ) -> List[Task]:
        """Filter by pet, completion status, category and/or caregiver (None = don't filter)."""
        result = self.get_all_tasks() if tasks is None else list(tasks)
        if pet_name is not None:
            result = [t for t in result if t.pet_name.lower() == pet_name.lower()]
        if completed is not None:
            result = [t for t in result if t.is_completed == completed]
        if category is not None:
            result = [t for t in result if t.category == category.lower()]
        if caregiver is not None:
            result = [t for t in result if (t.assigned_to or "").lower() == caregiver.lower()]
        return result

    # ---- recurring tasks ---- #

    def mark_task_complete(self, task_id: str) -> Optional[Task]:
        """Complete a task; if it is Daily/Weekly, add the next occurrence and return it."""
        for pet in self.owner.pets:
            task = pet.get_task(task_id)
            if task is None:
                continue
            if task.is_completed:  # already done -> don't spawn a duplicate
                return None
            task.mark_complete()
            follow_up = task.next_occurrence()
            if follow_up is not None:
                pet.add_task(follow_up)
            return follow_up
        raise KeyError(f"No task with id {task_id!r}")

    # ---- conflict detection (lightweight: returns warnings, never raises) ---- #

    def _describe_conflict(self, a: Task, b: Task) -> str:
        """Build a human-readable warning for two overlapping tasks."""
        scope = "same pet" if a.pet_name == b.pet_name else "different pets"
        message = (
            f"⚠️ Conflict on {a.due_date.isoformat()} ({scope}): "
            f"{a.pet_name}'s '{a.description}' ({a.due_time}-{a.end_time}) overlaps "
            f"{b.pet_name}'s '{b.description}' ({b.due_time}-{b.end_time})"
        )
        if a.assigned_to and a.assigned_to == b.assigned_to:
            message += f" -- {a.assigned_to} is double-booked"
        return message

    def detect_conflicts(self, day: Optional[date] = None) -> List[str]:
        """Return a warning for every pair of pending tasks whose time ranges overlap.

        Sorts once, then sweeps: each task is only compared with tasks that start
        before it ends, so the cost is O(n log n + number of conflicts).
        """
        tasks = [t for t in self.get_all_tasks() if not t.is_completed]
        if day is not None:
            tasks = [t for t in tasks if t.due_date == day]
        tasks.sort(key=lambda t: (t.due_date, t.start_minutes))
        warnings: List[str] = []
        for i, first in enumerate(tasks):
            for second in tasks[i + 1:]:
                if second.due_date != first.due_date or second.start_minutes >= first.end_minutes:
                    break  # sorted: nothing later can overlap `first`
                warnings.append(self._describe_conflict(first, second))
        return warnings

    def find_conflicts_for(self, task: Task) -> List[str]:
        """Return warnings for existing pending tasks (any pet) that overlap `task`."""
        return [
            self._describe_conflict(other, task)
            for other in self.get_all_tasks()
            if other is not task and not other.is_completed and other.overlaps(task)
        ]

    def schedule_task(self, pet_name: str, task: Task) -> List[str]:
        """Add a task to a pet and return any conflict warnings (the task is still added)."""
        pet = self.owner.get_pet(pet_name)
        if pet is None:
            raise KeyError(f"No pet named {pet_name!r}")
        pet.add_task(task)  # add first so the task carries its pet's name in any warning text
        warnings = self.find_conflicts_for(task)
        if task.assigned_to and not self.caregiver_can_do(task.assigned_to, task):
            warnings.append(
                f"⚠️ {task.assigned_to} is not available {task.due_time}-{task.end_time} "
                f"for '{task.description}'"
            )
        return warnings

    # ---- caregiver availability ---- #

    def _caregiver_is_free(self, caregiver: Caregiver, day: date, start_minutes: int, end_minutes: int,
                           ignore: Optional[Task] = None) -> bool:
        """True if the caregiver has no pending assigned task overlapping the interval."""
        for task in self.get_all_tasks():
            if task is ignore or task.is_completed or task.due_date != day:
                continue
            if task.assigned_to and task.assigned_to.lower() == caregiver.name.lower():
                if task.start_minutes < end_minutes and start_minutes < task.end_minutes:
                    return False
        return True

    def caregiver_can_do(self, caregiver_name: str, task: Task) -> bool:
        """True if the caregiver's windows cover the task and they have no clashing task."""
        caregiver = self.owner.get_caregiver(caregiver_name)
        if caregiver is None:
            return False
        return caregiver.is_available(task.due_time, task.duration_mins) and self._caregiver_is_free(
            caregiver, task.due_date, task.start_minutes, task.end_minutes, ignore=task
        )

    def available_caregivers(self, day: date, start: str, duration_mins: int) -> List[str]:
        """Names of caregivers who are in a window AND unbooked for [start, start + duration]."""
        begin = parse_time(start)
        return [
            c.name
            for c in self.owner.caregivers
            if c.is_available(start, duration_mins)
            and self._caregiver_is_free(c, day, begin, begin + duration_mins)
        ]

    def assign_caregiver(self, task: Task, caregiver_name: str) -> bool:
        """Assign a caregiver only if they're available; return whether it was assigned."""
        if self.caregiver_can_do(caregiver_name, task):
            task.assigned_to = self.owner.get_caregiver(caregiver_name).name
            return True
        return False

    def find_next_available_slot(
        self,
        day: date,
        duration_mins: int,
        caregiver_name: Optional[str] = None,
        pet_name: Optional[str] = None,
        earliest: str = "06:00",
        latest: str = "22:00",
        step_mins: int = 15,
    ) -> Optional[Tuple[str, str]]:
        """Find the first free (start_time, caregiver) slot on `day`, or None if there isn't one.

        A slot qualifies when a caregiver (the named one, or anyone) is inside an
        availability window with no clashing task, and -- if pet_name is given --
        that pet isn't already busy then.
        """
        if caregiver_name is not None:
            chosen = self.owner.get_caregiver(caregiver_name)
            candidates = [chosen] if chosen else []
        else:
            candidates = list(self.owner.caregivers)
        pet_tasks = []
        if pet_name is not None:
            pet = self.owner.get_pet(pet_name)
            pet_tasks = [t for t in (pet.tasks if pet else []) if not t.is_completed and t.due_date == day]
        for start in range(parse_time(earliest), parse_time(latest) - duration_mins + 1, step_mins):
            end = start + duration_mins
            if any(t.start_minutes < end and start < t.end_minutes for t in pet_tasks):
                continue
            for person in candidates:
                if person.is_available(format_time(start), duration_mins) and self._caregiver_is_free(
                    person, day, start, end
                ):
                    return format_time(start), person.name
        return None

    # ---- explanation & formatting ---- #

    def explain_schedule(self, day: Optional[date] = None) -> List[str]:
        """Return one plain-English sentence per task explaining why it sits where it does."""
        lines = []
        for task in self.get_schedule_for_day(day, include_completed=False):
            who = task.assigned_to or "nobody assigned yet"
            reason = f"{task.due_time} {task.pet_name}: {task.description} -- {task.priority} priority, {who}"
            if task.frequency != "Once":
                reason += f", repeats {task.frequency.lower()}"
            lines.append(reason)
        return lines

    def format_schedule(self, tasks: Optional[List[Task]] = None) -> str:
        """Render tasks as an aligned text table with emoji icons for the terminal."""
        tasks = self.get_all_tasks() if tasks is None else tasks
        if not tasks:
            return "  (no tasks)"
        headers = ["Time", "Pet", "Task", "Dur", "Priority", "Who"]
        rows = [
            [
                f"{t.due_time}-{t.end_time}",
                t.pet_name,
                t.description,
                f"{t.duration_mins}m",
                t.priority,
                t.assigned_to or "-",
            ]
            for t in tasks
        ]
        widths = [max(len(headers[i]), *(len(r[i]) for r in rows)) for i in range(len(headers))]

        def pad(values: List[str]) -> str:
            """Join cells padded to the column widths."""
            return "  ".join(v.ljust(widths[i]) for i, v in enumerate(values))

        # Emoji are 2 columns wide on screen but len() 1, so they go in fixed-width
        # leading/trailing fields instead of inside the padded cells.
        lines = ["  " + "   " + pad(headers) + "  Done", "  " + "-" * (sum(widths) + 2 * len(widths) + 10)]
        for task, row in zip(tasks, rows):
            icon = CATEGORY_EMOJI[task.category]
            lines.append("  " + icon + " " + pad(row) + "  " + ("✅" if task.is_completed else "⬜"))
        return "\n".join(lines)
