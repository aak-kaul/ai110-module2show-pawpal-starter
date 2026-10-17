"""PawPal+ Streamlit UI -- a thin client over pawpal_system.py.

Run with:  streamlit run app.py
"""

import os
from datetime import date, time

import streamlit as st

from pawpal_system import (
    CATEGORIES,
    CATEGORY_EMOJI,
    FREQUENCIES,
    PRIORITIES,
    PRIORITY_EMOJI,
    Caregiver,
    Owner,
    Pet,
    Scheduler,
    Task,
)

DATA_FILE = "data.json"

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="wide")


# --------------------------------------------------------------------------- #
# Phase 3, step 2: keep the Owner alive across Streamlit reruns
# --------------------------------------------------------------------------- #


def new_owner(name: str = "Jordan") -> Owner:
    """Create a fresh owner who is also the first available caregiver (07:00-21:00)."""
    owner = Owner(name)
    owner.add_caregiver(Caregiver(name, [("07:00", "21:00")]))
    return owner


def load_initial_owner() -> Owner:
    """Load data.json if it exists and is valid; otherwise start fresh."""
    if os.path.exists(DATA_FILE):
        try:
            return Owner.load_from_json(DATA_FILE)
        except (OSError, ValueError, KeyError):  # JSONDecodeError is a ValueError
            st.warning("Saved data couldn't be read, so PawPal+ started fresh.")
    return new_owner()


if "owner" not in st.session_state:  # only true on the very first run of a session
    st.session_state.owner = load_initial_owner()

owner: Owner = st.session_state.owner
scheduler = Scheduler(owner)  # cheap: it just reads the live Owner every time


def autosave() -> None:
    """Persist the owner to data.json after every change (best-effort)."""
    try:
        owner.save_to_json(DATA_FILE)
    except OSError as error:
        st.error(f"Could not save data: {error}")


def hhmm(value: time) -> str:
    """Convert a datetime.time from st.time_input into the 'HH:MM' string the logic layer uses."""
    return value.strftime("%H:%M")


def task_rows(tasks):
    """Turn Task objects into display rows for st.table."""
    return [
        {
            "Time": f"{t.due_time}-{t.end_time}",
            "Date": t.due_date.isoformat(),
            "Pet": t.pet_name,
            "Task": f"{CATEGORY_EMOJI[t.category]} {t.description}",
            "Priority": f"{PRIORITY_EMOJI[t.priority]} {t.priority}",
            "Repeats": t.frequency,
            "Who": t.assigned_to or "—",
            "Status": "✅ Done" if t.is_completed else "⏳ To do",
        }
        for t in tasks
    ]


# --------------------------------------------------------------------------- #
# Header + sidebar (owner, caregivers, saving)
# --------------------------------------------------------------------------- #

st.title("🐾 PawPal+")
st.caption("Plan walks, meals, grooming and playtime for all your pets, and see who is free to help.")

with st.sidebar:
    st.header("👤 Owner")
    new_name = st.text_input("Owner name", value=owner.name)
    if new_name.strip() and new_name != owner.name:
        owner.name = new_name.strip()
        autosave()

    st.header("🤝 People who can help")
    st.caption("Add yourself and anyone else (family, a dog walker) with the hours they're free each day.")
    for person in owner.caregivers:
        windows = ", ".join(f"{s}-{e}" for s, e in person.availability) or "no hours set"
        st.write(f"**{person.name}**: {windows}")

    with st.form("add_caregiver", clear_on_submit=True):
        cg_name = st.text_input("Name")
        c1, c2 = st.columns(2)
        cg_start = c1.time_input("Free from", value=time(9, 0), key="cg_start")
        cg_end = c2.time_input("Free until", value=time(17, 0), key="cg_end")
        if st.form_submit_button("Add person / hours"):
            try:
                if not cg_name.strip():
                    raise ValueError("Please enter a name")
                person = owner.get_caregiver(cg_name)
                if person is None:  # new person
                    person = owner.add_caregiver(Caregiver(cg_name.strip()))
                person.add_window(hhmm(cg_start), hhmm(cg_end))  # existing person: add another window
                autosave()
                st.success(f"Saved hours for {person.name}")
                st.rerun()
            except ValueError as error:
                st.error(str(error))

    st.header("💾 Data")
    if st.button("Save now"):
        autosave()
        st.success(f"Saved to {DATA_FILE}")
    if st.button("Reset everything"):
        st.session_state.owner = new_owner(owner.name)
        if os.path.exists(DATA_FILE):
            os.remove(DATA_FILE)
        st.rerun()

# --------------------------------------------------------------------------- #
# Pets
# --------------------------------------------------------------------------- #

st.subheader("🐶 Your pets")
if owner.pets:
    st.table(
        [
            {
                "Name": p.name,
                "Species": p.species,
                "Age": p.age,
                "Notes": p.notes or "—",
                "Pending tasks": len(p.get_tasks(include_completed=False)),
            }
            for p in owner.pets
        ]
    )
else:
    st.info("No pets yet. Add your first pet below.")

with st.form("add_pet", clear_on_submit=True):
    p1, p2, p3 = st.columns([2, 2, 1])
    pet_name = p1.text_input("Pet name")
    species = p2.selectbox("Species", ["dog", "cat", "rabbit", "bird", "other"])
    age = p3.number_input("Age", min_value=0, max_value=40, value=1)
    pet_notes = st.text_input("Notes (optional)")
    if st.form_submit_button("➕ Add pet"):
        if not pet_name.strip():
            st.error("Please enter a pet name.")
        else:
            try:
                owner.add_pet(Pet(pet_name.strip(), species, int(age), pet_notes.strip()))
                autosave()
                st.success(f"Added {pet_name.strip()}!")
                st.rerun()
            except ValueError as error:
                st.error(str(error))

st.divider()

# --------------------------------------------------------------------------- #
# Schedule a task
# --------------------------------------------------------------------------- #

st.subheader("📝 Schedule a task")
if not owner.pets:
    st.info("Add a pet first, then you can schedule tasks for it.")
else:
    caregiver_choices = ["Unassigned"] + [c.name for c in owner.caregivers]
    with st.form("add_task", clear_on_submit=False):
        t1, t2, t3 = st.columns(3)
        task_pet = t1.selectbox("Pet", [p.name for p in owner.pets])
        task_category = t2.selectbox("Activity", CATEGORIES, format_func=lambda c: f"{CATEGORY_EMOJI[c]} {c}")
        task_desc = t3.text_input("Description", value="Morning walk")

        t4, t5, t6, t7 = st.columns(4)
        task_date = t4.date_input("Date", value=date.today())
        task_time = t5.time_input("Start time", value=time(8, 0))
        task_duration = t6.number_input("Duration (min)", min_value=1, max_value=480, value=30)
        task_priority = t7.selectbox("Priority", PRIORITIES, index=1)

        t8, t9 = st.columns(2)
        task_frequency = t8.selectbox("Repeats", FREQUENCIES)
        task_who = t9.selectbox("Who will do it?", caregiver_choices)

        if st.form_submit_button("Add task"):
            try:
                task = Task(
                    description=task_desc.strip() or task_category.title(),
                    due_time=hhmm(task_time),
                    duration_mins=int(task_duration),
                    frequency=task_frequency,
                    priority=task_priority,
                    category=task_category,
                    due_date=task_date,
                    assigned_to=None if task_who == "Unassigned" else task_who,
                )
                warnings = scheduler.schedule_task(task_pet, task)  # Phase 3 step 3: UI -> logic layer
                autosave()
                st.success(f"Added '{task.description}' for {task_pet} at {task.due_time}.")
                for warning in warnings:  # conflicts are shown, never blocking
                    st.warning(warning)
            except (ValueError, KeyError) as error:
                st.error(str(error))

st.divider()

# --------------------------------------------------------------------------- #
# Availability tools
# --------------------------------------------------------------------------- #

st.subheader("🕒 Is someone available?")
a1, a2, a3 = st.columns(3)
q_date = a1.date_input("Day", value=date.today(), key="q_date")
q_time = a2.time_input("Time", value=time(8, 0), key="q_time")
q_duration = a3.number_input("Duration (min)", min_value=5, max_value=480, value=30, key="q_duration")

if st.button("Who is free then?"):
    people = scheduler.available_caregivers(q_date, hhmm(q_time), int(q_duration))
    if people:
        st.success(f"Available {hhmm(q_time)} for {int(q_duration)} min: {', '.join(people)}")
    else:
        st.warning("Nobody is free at that time (outside their hours, or already booked).")

n1, n2 = st.columns(2)
slot_pet = n1.selectbox("For pet (optional)", ["Any"] + [p.name for p in owner.pets], key="slot_pet")
slot_person = n2.selectbox("With person (optional)", ["Anyone"] + [c.name for c in owner.caregivers], key="slot_person")
if st.button("Find next open slot"):
    slot = scheduler.find_next_available_slot(
        q_date,
        int(q_duration),
        caregiver_name=None if slot_person == "Anyone" else slot_person,
        pet_name=None if slot_pet == "Any" else slot_pet,
    )
    if slot:
        st.success(f"Next open {int(q_duration)}-minute slot on {q_date}: **{slot[0]}** with **{slot[1]}**")
    else:
        st.warning("No open slot that day. Try a shorter duration, another day, or add more availability.")

st.divider()

# --------------------------------------------------------------------------- #
# The schedule (sorted / filtered / conflicts / completing tasks)
# --------------------------------------------------------------------------- #

st.subheader("📅 Schedule")
f1, f2, f3, f4 = st.columns(4)
view_day = f1.date_input("Day", value=date.today(), key="view_day")
pet_filter = f2.selectbox("Pet", ["All pets"] + [p.name for p in owner.pets], key="pet_filter")
status_filter = f3.selectbox("Status", ["All", "To do", "Done"], key="status_filter")
category_filter = f4.selectbox("Activity", ["All"] + list(CATEGORIES), key="category_filter")

day_tasks = scheduler.filter_tasks(
    tasks=scheduler.get_schedule_for_day(view_day),
    pet_name=None if pet_filter == "All pets" else pet_filter,
    completed={"All": None, "To do": False, "Done": True}[status_filter],
    category=None if category_filter == "All" else category_filter,
)

conflicts = scheduler.detect_conflicts(view_day)
if conflicts:
    st.error(f"{len(conflicts)} scheduling conflict(s) on {view_day}. Move one of the tasks below:")
    for warning in conflicts:
        st.warning(warning)
elif scheduler.get_schedule_for_day(view_day):
    st.success("No conflicts: everything fits.")

tab_time, tab_priority, tab_why = st.tabs(["⏰ By time", "🔴 By priority", "💡 Why this plan?"])
with tab_time:
    if day_tasks:
        st.table(task_rows(scheduler.sort_by_time(day_tasks)))
    else:
        st.info("No tasks match for this day and filter.")
with tab_priority:
    if day_tasks:
        st.table(task_rows(scheduler.sort_by_priority(day_tasks)))
    else:
        st.info("No tasks match for this day and filter.")
with tab_why:
    explanation = scheduler.explain_schedule(view_day)
    if explanation:
        for line in explanation:
            st.write("• " + line)
    else:
        st.info("Nothing pending this day.")

pending = [t for t in day_tasks if not t.is_completed]
if pending:
    st.markdown("**Mark a task done** (daily/weekly tasks automatically create the next one):")
    for task in scheduler.sort_by_time(pending):
        label = f"✅ {task.due_time} {task.pet_name}: {task.description}"
        if st.button(label, key=f"done_{task.task_id}"):
            follow_up = scheduler.mark_task_complete(task.task_id)
            autosave()
            if follow_up:
                st.toast(f"Next '{follow_up.description}' scheduled for {follow_up.due_date}")
            st.rerun()
