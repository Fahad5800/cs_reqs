"""Stony Brook AMS BS major audit, current undergraduate requirements.

Source: https://www.stonybrook.edu/ams/academics/undergraduate/

Input records have the same fields as the CSE checker's Taken tuple. Credits
must be earned credits after institutional repeat and credit-exclusion rules.
"""

from collections import namedtuple
from itertools import combinations, product

# Each course taken by a student, matching the CSE checker's format
Taken = namedtuple("Taken", ["id", "credits", "grade", "when", "where"])

# 1. Grade & Course Helper Functions
# English: "All courses taken to satisfy requirements 1, 2, and 3 above must be
# taken for a letter grade and passed with a grade of C or higher."

C_OR_HIGHER = {"A", "A-", "B+", "B", "B-", "C+", "C"}

# Req 4 accepts verified WRTD registration or completed WRTD coursework.
WRTD_EXAMPLES = {"AMS 300", "AMS 488"}
PASSING_GRADES = C_OR_HIGHER | {"C-", "D+", "D", "P", "S"}

def get_course_number(course_id):
    """Extract the number from a course ID like 'AMS 301' -> 301."""
    parts = course_id.split()
    return int(parts[1]) if len(parts) == 2 and parts[1].isdigit() else -1

def is_ams_301_or_above(course_id):
    """Check if a course is an AMS course numbered 301 or higher."""
    return course_id.startswith("AMS ") and get_course_number(course_id) >= 301

def is_typical_non_ams_math(course_id):
    """English 3(d): Typical non-AMS upper-division mathematically oriented courses:
      ECO 321, ECO 348, CSE 302+ (excluding 312), and MAT 310+.
      """
    num = get_course_number(course_id)
    if course_id in {"ECO 321", "ECO 348"}:
      return True
    if course_id.startswith("CSE ") and num >= 302 and num != 312:
      return True
    if course_id.startswith("MAT ") and num >= 310:
      return True
    return False

# --- 2. Requirement Course Sets (Directly from the Bulletin) ---

CALC_SEQUENCES = [
    {"AMS 151", "AMS 161"},
    {"MAT 125", "MAT 126", "MAT 127"},
    {"MAT 131", "MAT 132"}
]

LINEAR_ALGEBRA_OPTIONS = {"AMS 210", "MAT 211"}
CALC_III_OPTIONS = {"AMS 261", "MAT 203"}

DEFAULT_COMPUTING = {"AMS 325", "CSE 101", "CSE 114", "ESG 111"}

REQ_3A_OPTIONS = {"AMS 301"}
REQ_3B_OPTIONS = {"AMS 310", "AMS 311"}
REQ_3C_OPTIONS = {"AMS 315", "AMS 361", "MAT 303"}

RESTRICTED_AMS = {"AMS 475", "AMS 476", "AMS 487", "AMS 488"}

# --- 3. Step-by-Step Requirement Checkers ---

def check_calc(passed_ids):
    """Req 1a: Must complete one full calculus sequence."""
    for sequence in CALC_SEQUENCES:
      if sequence <= passed_ids:  # '<=' checks if every course in sequence is in passed_ids
        return True, sorted(sequence)
    return False, ["Need AMS 151+161, MAT 125+126+127, or MAT 131+132"]

def check_either_or(options, passed_ids, missing_msg):
    """Helper for any rule saying 'Either X or Y must be taken'."""
    for course in sorted(options):
      if course in passed_ids:
        return True, [course]
    return False, [missing_msg]

def _elective_witness(passed, excluded, approved, minimum):
    """Find whole-course credits that meet the minimum within the six-credit cap."""
    unrestricted = []
    restricted = []
    for course, credits in sorted(passed.items()):
        if course in excluded or credits <= 0:
            continue
        if is_ams_301_or_above(course) and course not in RESTRICTED_AMS:
            unrestricted.append(course)
        elif credits <= 6 and (course in RESTRICTED_AMS or course in approved):
            restricted.append(course)

    shortfall = minimum - sum(passed[course] for course in unrestricted)
    if shortfall <= 0:
        return unrestricted

    # Even taking the full restricted allowance would leave a shortfall.
    if shortfall > 6 or sum(passed[course] for course in restricted) < shortfall:
        return None

    # The smallest restricted course bounds how many courses can fit in the cap.
    max_courses = min(len(restricted), int(6 // min(passed[course] for course in restricted)))
    for size in range(1, max_courses + 1):
        for selection in combinations(restricted, size):
            credits = sum(passed[course] for course in selection)
            if shortfall <= credits <= 6:
                return unrestricted + list(selection)
    return None


CORE_OPTIONS = {
    "3(a)": REQ_3A_OPTIONS,
    "3(b)": REQ_3B_OPTIONS,
    "3(c)": REQ_3C_OPTIONS,
}


def find_allocation(credits_by_id, computing_choices, core_choices, approved_electives):
    """Try one course per slot, then look for enough unused elective credits."""
    for computing_course, *core in product(computing_choices, *core_choices):
        if computing_course in core:
            continue
        core_credits = sum(credits_by_id[course] for course in core)
        needed_credits = max(18, 27 - core_credits)
        electives = _elective_witness(
            credits_by_id, {computing_course, *core}, approved_electives, needed_credits
        )
        if electives is not None:
            return computing_course, core, electives
    return None


def check_req3_and_computing(credits_by_id, approved_computing=(), approved_electives=()):
    """Apply the working assumption that computing and section 3 use distinct courses."""
    passed_ids = set(credits_by_id)
    computing_options = DEFAULT_COMPUTING | set(approved_computing)
    results = {
        "computing": check_either_or(computing_options, passed_ids, "Need one approved computing course"),
    }
    for clause, options in CORE_OPTIONS.items():
        results[clause] = check_either_or(options, passed_ids, "Need " + " or ".join(sorted(options)))

    # A missing computing course should still allow an independent section 3 check.
    computing_choices = sorted(computing_options & passed_ids) or [None]
    core_choices = [sorted(options & passed_ids) for options in CORE_OPTIONS.values()]
    approved = {
        course for course in approved_electives
        if not course.startswith("AMS ") and get_course_number(course) >= 300
    }
    allocation = find_allocation(credits_by_id, computing_choices, core_choices, approved)
    if allocation is not None:
        computing_course, core, electives = allocation
        if computing_course is not None:
            results["computing"] = True, [computing_course]
        for clause, course in zip(CORE_OPTIONS, core):
            results[clause] = True, [course]
        results["3(d)"] = True, sorted(electives)
        return results

    messages = ["Need 18 additional eligible credits and 27 total, with at most 6 restricted elective credits"]
    pending = {course for course in passed_ids if is_typical_non_ams_math(course)} - approved
    if pending:
        provisional = find_allocation(credits_by_id, computing_choices, core_choices, approved | pending)
        if provisional is not None:
            needed = sorted(pending.intersection(provisional[2]))
            messages.append("Needs AMS elective approval: " + ", ".join(needed))
    results["3(d)"] = False, messages
    return results


def check_writing(taken_courses, approved_wrtd=(), registered_wrtd=()):
    """Req 4: Upper-Division Writing Requirement (WRTD), e.g., AMS 300."""
    wrtd_options = WRTD_EXAMPLES | set(approved_wrtd)
    passed_wrtd = {
        c.id for c in taken_courses
        if c.id in wrtd_options and c.grade in PASSING_GRADES
    }
    matched = sorted(passed_wrtd | (wrtd_options & set(registered_wrtd)))

    if matched:
      return True, [matched[0]]
    return False, ["Need WRTD course (e.g., AMS 300)"]

# --- 4. Main Audit Entry Point ---
def degree_reqs(taken, *, approved_computing=(), approved_electives=(), wrtd_courses=(),
                wrtd_registrations=()):
    """Check all AMS BS major requirements and return (satisfied, witness) pairs."""
    taken = tuple(taken)
    credits_by_id = {}
    for course in taken:
        if course.grade in C_OR_HIGHER and course.credits >= 0:
            credits_by_id[course.id] = max(credits_by_id.get(course.id, 0), course.credits)
    passed_ids = set(credits_by_id)

    checked = {}
    checked["calc"] = check_calc(passed_ids)
    checked["alg"] = check_either_or(LINEAR_ALGEBRA_OPTIONS, passed_ids, "Need AMS 210 or MAT 211")
    checked["calc_iii"] = check_either_or(CALC_III_OPTIONS, passed_ids, "Need AMS 261 or MAT 203")
    checked.update(check_req3_and_computing(credits_by_id, approved_computing, approved_electives))
    checked["writing"] = check_writing(taken, wrtd_courses, wrtd_registrations)
    checked["degree"] = all(status for status, _ in checked.values()), []
    return checked
