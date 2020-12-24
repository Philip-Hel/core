"""Constants for the Todoist component."""
CONF_EXTRA_PROJECTS = "custom_projects"
CONF_PROJECT_DUE_DATE = "due_date_days"
CONF_PROJECT_LABEL_WHITELIST = "labels"
CONF_PROJECT_WHITELIST = "include_projects"

# Calendar Platform: Does this calendar event last all day?
ALL_DAY = "all_day"
# Attribute: All tasks in this project
ALL_TASKS = "all_tasks"
# Todoist API: "Completed" flag -- 1 if complete, else 0
CHECKED = "checked"
# Attribute: Is this task complete?
COMPLETED = "completed"
# Todoist API: What is this task about?
# Service Call: What is this task about?
CONTENT = "content"
# Calendar Platform: Get a calendar event's description
DESCRIPTION = "description"
# Calendar Platform: Used in the '_get_date()' method
DATETIME = "dateTime"
DUE = "due"
# Service Call: When is this task due (in natural language)?
DUE_DATE_STRING = "due_date_string"
# Service Call: The language of DUE_DATE_STRING
DUE_DATE_LANG = "due_date_lang"
# Service Call: The available options of DUE_DATE_LANG
DUE_DATE_VALID_LANGS = [
    "en",
    "da",
    "pl",
    "zh",
    "ko",
    "de",
    "pt",
    "ja",
    "it",
    "fr",
    "sv",
    "ru",
    "es",
    "nl",
]
# Attribute: When is this task due?
# Service Call: When is this task due?
DUE_DATE = "due_date"
# Attribute: Is this task due today?
DUE_TODAY = "due_today"
# Attribute: Is this task due tomorrow?
DUE_TOMORROW = "due_tomorrow"
# Attribute: Was this task due yesterday?
DUE_NEXT7DAYS = "due_next7days"
# Attribute: Was this task due yesterday?
TASK_DUE_FORMATTED = "due_formatted"
# Calendar Platform: When a calendar event ends
END = "end"
# Todoist API: Look up a Project/Label/Task ID
ID = "id"
# Todoist API: Fetch all labels
# Service Call: What are the labels attached to this task?
LABELS = "labels"
# Todoist API: "Name" value
NAME = "name"
# Attribute: Is this task overdue?
OVERDUE = "overdue"
# Todoist API: Get a project's parent id if available
PARENT_ID="parent_id"
# Attribute: What is this project's parents?
PARENT_SUMMARY="parent_summary"
# Attribute: What is this task's priority?
# Todoist API: Get a task's priority
# Service Call: What is this task's priority?
PRIORITY = "priority"
# Attribute: What is the colour id for the project?
PROJECT_COLOUR = "color"
# Todoist API: Look up the Project ID a Task belongs to
PROJECT_ID = "project_id"
# Todoist API: Look up the Project Child Order a Project belongs to
PROJECT_ORDER = "child_order"
# Service Call: What Project do you want a Task added to?
PROJECT_NAME = "project"
# Todoist API: Fetch all Projects
PROJECTS = "projects"
# Attribute: Is this a recurring task?
# Todoist API: Get a task's recurrence
RECURRING_STATE = "is_recurring"
# Calendar Platform: When does a calendar event start?
START = "start"
# Calendar Platform: What is the next calendar event about?
SUMMARY = "summary"
# Todoist API: Fetch all Tasks
TASKS = "items"

DOMAIN = "todoist"

SERVICE_NEW_TASK = "new_task"

DAYSWITCHER = {
    1: "Monday",
    2: "Tuesday",
    3: "Wednesday",
    4: "Thursday",
    5: "Friday",
    6: "Saturday",
    7: "Sunday"
}

MONTHSWITCHER = {
    1: "Jan",
    2: "Feb",
    3: "Mar",
    4: "Apr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Aug",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dec"
}