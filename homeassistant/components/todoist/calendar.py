"""Support for Todoist task management (https://todoist.com)."""
from datetime import datetime, timedelta
import logging

from todoist.api import TodoistAPI
import voluptuous as vol

from homeassistant.components.calendar import PLATFORM_SCHEMA, CalendarEventDevice
from homeassistant.const import CONF_ID, CONF_NAME, CONF_TOKEN
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.template import DATE_STR_FORMAT
from homeassistant.util import dt

from .const import (
    ALL_DAY,
    ALL_TASKS,
    CHECKED,
    COMPLETED,
    CONF_EXTRA_PROJECTS,
    CONF_PROJECT_DUE_DATE,
    CONF_PROJECT_LABEL_WHITELIST,
    CONF_PROJECT_WHITELIST,
    CONTENT,
    DATETIME,
    DESCRIPTION,
    DOMAIN,
    DUE,
    DUE_DATE,
    DUE_DATE_LANG,
    DUE_DATE_STRING,
    DUE_DATE_VALID_LANGS,
    DUE_TODAY,
    DUE_TOMORROW,
    DUE_NEXT7DAYS,
    TASK_DUE_FORMATTED,
    RECURRING_STATE,
    END,
    ID,
    LABELS,
    NAME,
    OVERDUE,
    PRIORITY,
    PARENT_ID,
    PARENT_SUMMARY,
    PROJECT_ID,
    PROJECT_COLOUR,
    PROJECT_NAME,
    PROJECT_ORDER,
    PROJECTS,
    SERVICE_NEW_TASK,
    START,
    SUMMARY,
    TASKS,
    DAYSWITCHER,
    MONTHSWITCHER,
)

_LOGGER = logging.getLogger(__name__)

NEW_TASK_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONTENT): cv.string,
        vol.Optional(PROJECT_NAME, default="inbox"): vol.All(cv.string, vol.Lower),
        vol.Optional(LABELS): cv.ensure_list_csv,
        vol.Optional(PRIORITY): vol.All(vol.Coerce(int), vol.Range(min=1, max=4)),
        vol.Exclusive(DUE_DATE_STRING, "due_date"): cv.string,
        vol.Optional(DUE_DATE_LANG): vol.All(cv.string, vol.In(DUE_DATE_VALID_LANGS)),
        vol.Exclusive(DUE_DATE, "due_date"): cv.string,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_TOKEN): cv.string,
        vol.Optional(CONF_EXTRA_PROJECTS, default=[]): vol.All(
            cv.ensure_list,
            vol.Schema(
                [
                    vol.Schema(
                        {
                            vol.Required(CONF_NAME): cv.string,
                            vol.Optional(CONF_PROJECT_DUE_DATE): vol.Coerce(int),
                            vol.Optional(CONF_PROJECT_WHITELIST, default=[]): vol.All(
                                cv.ensure_list, [vol.All(cv.string, vol.Lower)]
                            ),
                            vol.Optional(
                                CONF_PROJECT_LABEL_WHITELIST, default=[]
                            ): vol.All(cv.ensure_list, [vol.All(cv.string, vol.Lower)]),
                        }
                    )
                ]
            ),
        ),
    }
)

SCAN_INTERVAL = timedelta(minutes=1)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Todoist platform."""
    token = config.get(CONF_TOKEN)

    # Look up IDs based on (lowercase) names.
    project_id_lookup = {}
    label_id_lookup = {}
    
#   for recuresive lookup of project names we need to keep a list of items
#   project id as key, and dict entry of ProjectName and Parentid
    recursive_proj_name_lookup = {}

    api = TodoistAPI(token)
    api.sync()
    # Setup devices:
    # Grab all projects.
    #_LOGGER.warning("Projects before: %s", len(api.state[PROJECTS]))
    #_LOGGER.warning("All Projects before: %s", api.state[PROJECTS])
    
    projects = sort_projects(api.state[PROJECTS], None)
    #projects = api.state[PROJECTS]
    #_LOGGER.warning("Projects after: %s", len(projects))
    #_LOGGER.warning("All Projects after: %s", projects)
    # Grab all labels
    labels = api.state[LABELS]
    
    # Add all Todoist-defined projects.
    project_devices = []
    for project in projects:
        # Project is an object, not a dict!
        # Because of that, we convert what we need to a dict.
    #    _LOGGER.warning("todoist1 ParentID: %s", project[PARENT_ID])
        project_data = {CONF_NAME: project[NAME], 
                        CONF_ID: project[ID],
                        PROJECT_COLOUR: project[PROJECT_COLOUR],
                        PARENT_SUMMARY: calc_parent_summary(recursive_proj_name_lookup, project[PARENT_ID]),
                       }
    #    _LOGGER.warning("todoist2 PARENT_SUMMARY: %s", project_data[PARENT_SUMMARY])
        project_devices.append(TodoistProjectDevice(hass, project_data, labels, api) )
        # Cache the names so we can easily look up name->ID.
        project_id_lookup[project[NAME].lower()] = project[ID]
        recursive_proj_name_lookup[project[ID]] = {CONF_NAME: project[NAME], PARENT_ID: project[PARENT_ID]}
    #    _LOGGER.warning("todoist3 project key for recursive fields: %s", project[ID])    
    #    _LOGGER.warning("todoist4 values for recursive fields: %s", recursive_proj_name_lookup[project[ID]])
    # Cache all label names
    for label in labels:
        label_id_lookup[label[NAME].lower()] = label[ID]

    # Check config for more projects.
    extra_projects = config[CONF_EXTRA_PROJECTS]
    for project in extra_projects:
        # Special filter: By date
        project_due_date = project.get(CONF_PROJECT_DUE_DATE)

        # Special filter: By label
        project_label_filter = project[CONF_PROJECT_LABEL_WHITELIST]

        # Special filter: By name
        # Names must be converted into IDs.
        project_name_filter = project[CONF_PROJECT_WHITELIST]
        project_id_filter = [
            project_id_lookup[project_name.lower()]
            for project_name in project_name_filter
        ]

        # Create the custom project and add it to the devices array.
        project_devices.append(
            TodoistProjectDevice(
                hass,
                project,
                labels,
                api,
                project_due_date,
                project_label_filter,
                project_id_filter,
            )
        )

    add_entities(project_devices)

    def handle_new_task(call):
        """Call when a user creates a new Todoist Task from Home Assistant."""
        project_name = call.data[PROJECT_NAME]
        project_id = project_id_lookup[project_name]

        # Create the task
        item = api.items.add(call.data[CONTENT], project_id=project_id)

        if LABELS in call.data:
            task_labels = call.data[LABELS]
            label_ids = [label_id_lookup[label.lower()] for label in task_labels]
            item.update(labels=label_ids)

        if PRIORITY in call.data:
            item.update(priority=call.data[PRIORITY])

        _due: dict = {}
        if DUE_DATE_STRING in call.data:
            _due["string"] = call.data[DUE_DATE_STRING]

        if DUE_DATE_LANG in call.data:
            _due["lang"] = call.data[DUE_DATE_LANG]

        if DUE_DATE in call.data:
            due_date = dt.parse_datetime(call.data[DUE_DATE])
            if due_date is None:
                due = dt.parse_date(call.data[DUE_DATE])
                due_date = datetime(due.year, due.month, due.day)
            # Format it in the manner Todoist expects
            due_date = dt.as_utc(due_date)
            date_format = "%Y-%m-%dT%H:%M"
            due_date = datetime.strftime(due_date, date_format)
            _due["date"] = due_date

        if _due:
            item.update(due=_due)

        # Commit changes
        api.commit()
        _LOGGER.debug("Created Todoist task: %s", call.data[CONTENT])

    hass.services.register(
        DOMAIN, SERVICE_NEW_TASK, handle_new_task, schema=NEW_TASK_SERVICE_SCHEMA
    )

def sort_projects(pProjects, pParentID):
    """Recursively sort projects to create tree structure with correct position."""
    retlist = []
    for project in pProjects:
        if project[PARENT_ID] == pParentID:
            #_LOGGER.warning("pprojects length in sort loop: %s", len(pProjects))
            #_LOGGER.warning("current project before remove: %s", project)
            projlist = []
            projlist.append(project)
            #pProjects.remove(project)
            #_LOGGER.warning("current project after remove: %s", project)

            projlist.extend(sort_projects(pProjects, project[ID]))
            # find position to projlist into retlist.
            #_LOGGER.warning("Projlist tree: %s", projlist)
            i = 0
            for retproject in retlist:
                if (retproject[PARENT_ID]  == pParentID) and (retproject[PROJECT_ORDER] > project[PROJECT_ORDER]):
                    break    
                i += 1
            retlist[i:i] = projlist
    return retlist

def _parse_due_date(data: dict) -> datetime:
    """Parse the due date dict into a datetime object."""
    # Add time information to date only strings.
    if len(data["date"]) == 10:
        data["date"] += "T00:00:00"
    # If there is no timezone provided, use UTC.
    if data["timezone"] is None:
        data["date"] += "Z"
    return dt.parse_datetime(data["date"])

def calc_parent_summary(pProjectList, pParentID):
    """Recursively calculates project summary"""
    if pParentID in pProjectList:
        retValue = calc_parent_summary(pProjectList,pProjectList[pParentID][PARENT_ID])
        if retValue != "":
            retValue += "➡" 
        retValue += pProjectList[pParentID][CONF_NAME] 
        return retValue  
    else:
        return ""

def parse_addtime_tosummary(pAllday, pTime: datetime):
    """check if time is needed and returns formatted"""
    if pAllday: 
        return ""
    retValue = " "    
    # add hours
    amPM = ""
    if pTime.time().hour > 12 :
        retValue += str(pTime.time().hour - 12)
        amPM = "PM"
    else :
        retValue += str(pTime.time().hour)
        amPM = "AM"
    # add and format minutes if not 0
    if pTime.time().minute > 0 : 
        retValue += ":"+ format(pTime.time().minute, '02') + " "
    # now handle AM/PM
    retValue += amPM
    return retValue
class TodoistProjectDevice(CalendarEventDevice):
    """A device for getting the next Task from a Todoist Project."""

    def __init__(
        self,
        hass,
        data,
        labels,
        token,
        latest_task_due_date=None,
        whitelisted_labels=None,
        whitelisted_projects=None,
    ):
        """Create the Todoist Calendar Event Device."""
        self.data = TodoistProjectData(
            data,
            labels,
            token,
            latest_task_due_date,
            whitelisted_labels,
            whitelisted_projects,
        )
     #   self._cal_data = {}
        self._name = data[CONF_NAME]
        self._project_colour = data[PROJECT_COLOUR]
        self._parent_summary = data[PARENT_SUMMARY]
      #  _LOGGER.warning("todoist5 device data[parent_summary]: %s", data[PARENT_SUMMARY])
      #  _LOGGER.warning("todoist6 device _parent_summary: %s", self._parent_summary)

    @property
    def event(self):
        """Return the next upcoming event."""
        return self.data.event

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    def update(self):
        """Update all Todoist Calendars."""
        self.data.update()
        # Set Todoist-specific data that can't easily be grabbed
        # self._cal_data[ALL_TASKS] = [
        #    task[SUMMARY] for task in self.data.all_project_tasks
        #]

    async def async_get_events(self, hass, start_date, end_date):
        """Get all events in a specific time frame."""
        self.update(self)
        # _LOGGER.warning("get events called!on todoist")
        
        return await self.data.async_get_events(hass, start_date, end_date)

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        if self.data.event is None:
            # No tasks, we don't REALLY need to show anything.
            return {
                PROJECT_COLOUR: self._project_colour,
                PARENT_SUMMARY: self._parent_summary,
            }
        return {
            DUE_TODAY: self.data.event[DUE_TODAY],
            OVERDUE: self.data.event[OVERDUE],
          #  ALL_TASKS: self._cal_data[ALL_TASKS],
            ALL_TASKS: self.data.all_project_tasks,
            PRIORITY: self.data.event[PRIORITY],
            LABELS: self.data.event[LABELS],
            PROJECT_COLOUR: self._project_colour,
            PARENT_SUMMARY: self._parent_summary,
        }


class TodoistProjectData:
    """
    Class used by the Task Device service object to hold all Todoist Tasks.

    This is analogous to the GoogleCalendarData found in the Google Calendar
    component.

    Takes an object with a 'name' field and optionally an 'id' field (either
    user-defined or from the Todoist API), a Todoist API token, and an optional
    integer specifying the latest number of days from now a task can be due (7
    means everything due in the next week, 0 means today, etc.).

    This object has an exposed 'event' property (used by the Calendar platform
    to determine the next calendar event) and an exposed 'update' method (used
    by the Calendar platform to poll for new calendar events).

    The 'event' is a representation of a Todoist Task, with defined parameters
    of 'due_today' (is the task due today?), 'all_day' (does the task have a
    due date?), 'task_labels' (all labels assigned to the task), 'message'
    (the content of the task, e.g. 'Fetch Mail'), 'description' (a URL pointing
    to the task on the Todoist website), 'end_time' (what time the event is
    due), 'start_time' (what time this event was last updated), 'overdue' (is
    the task past its due date?), 'priority' (1-4, how important the task is,
    with 4 being the most important), and 'all_tasks' (all tasks in this
    project, sorted by how important they are).

    'offset_reached', 'location', and 'friendly_name' are defined by the
    platform itself, but are not used by this component at all.

    The 'update' method polls the Todoist API for new projects/tasks, as well
    as any updates to current projects/tasks. This occurs every SCAN_INTERVAL minutes.
    """

    def __init__(
        self,
        project_data,
        labels,
        api,
        latest_task_due_date=None,
        whitelisted_labels=None,
        whitelisted_projects=None,
    ):
        """Initialize a Todoist Project."""
        self.event = None

        self._api = api
        self._name = project_data[CONF_NAME]
        # If no ID is defined, fetch all tasks.
        self._id = project_data.get(CONF_ID)

        # All labels the user has defined, for easy lookup.
        self._labels = labels
        # Not tracked: order, indent, comment_count.

        self.all_project_tasks = []

        # The latest date a task can be due (for making lists of everything
        # due today, or everything due in the next week, for example).
        if latest_task_due_date is not None:
            self._latest_due_date = dt.utcnow() + timedelta(days=latest_task_due_date)
        else:
            self._latest_due_date = None

        # Only tasks with one of these labels will be included.
        if whitelisted_labels is not None:
            self._label_whitelist = whitelisted_labels
        else:
            self._label_whitelist = []

        # This project includes only projects with these names.
        if whitelisted_projects is not None:
            self._project_id_whitelist = whitelisted_projects
        else:
            self._project_id_whitelist = []

    def create_todoist_task(self, data):
        """
        Create a dictionary based on a Task passed from the Todoist API.

        Will return 'None' if the task is to be filtered out.
        """
        task = {}
        # Fields are required to be in all returned task objects.
        task[CONF_ID] = data[CONF_ID]
        task[SUMMARY] = data[CONTENT]
        task[COMPLETED] = data[CHECKED] == 1
        task[PRIORITY] = data[PRIORITY]
        task[DESCRIPTION] = "https://todoist.com/showTask?id={}".format(data[ID])
        if data[PARENT_ID] is not None:
            task[PARENT_ID] = data[PARENT_ID]
        # All task Labels (optional parameter).
        task[LABELS] = [
            label[NAME].lower() for label in self._labels if label[ID] in data[LABELS]
        ]

        if self._label_whitelist and (
            not any(label in task[LABELS] for label in self._label_whitelist)
        ):
            # We're not on the whitelist, return invalid task.
            return None

        # Due dates (optional parameter).
        # The due date is the END date -- the task cannot be completed
        # past this time.
        # That means that the START date is the earliest time one can
        # complete the task.
        # Generally speaking, that means right now.
        task[START] = dt.utcnow()
        if data[DUE] is not None:
            dueDateDict = data[DUE]
            # add task recurring
            task[RECURRING_STATE] = dueDateDict[RECURRING_STATE]

            # check if all day event or if we have a valid time
            if len(dueDateDict["date"]) == 10:
                task[ALL_DAY] = True
            else :
                task[ALL_DAY] = False
            task[END] = _parse_due_date(dueDateDict)
            if self._latest_due_date is not None and (
                task[END] > self._latest_due_date
            ):
                # This task is out of range of our due date;
                # it shouldn't be counted.
                return None

            task[DUE_TODAY] = task[END].date() == datetime.today().date()
            task[DUE_TOMORROW] = task[END].date() == (datetime.today() + timedelta(days=1)).date()
            task[DUE_NEXT7DAYS] = ((task[END].date() > datetime.today().date()) and (task[END].date() <= (datetime.today() + timedelta(days=7)).date()))
            
            # Special case: Task is overdue.
            if (task[END].date() < task[START].date()): # if it was due on a previous day then overdue always.
                task[OVERDUE] = True

            elif ((task[END] <= task[START]) and (task[ALL_DAY] == False)): # else if on today only overdue if not all day and time missed
                task[OVERDUE] = True
                # Set end time to the current time plus 1 hour.
                # We're pretty much guaranteed to update within that 1 hour,
                # so it should be fine.
                #PH - I want the end date to remain task[END] = task[START] + timedelta(hours=1)
            else:
                task[OVERDUE] = False

            #case to create formatted text
            if task[OVERDUE]:
                if task[DUE_TODAY]:
                    #if show today but as red if we missed it today
                    task[TASK_DUE_FORMATTED] = "Today" + parse_addtime_tosummary(task[ALL_DAY],task[END])
                elif (task[END].date() == (datetime.today() - timedelta(days=1)).date()):
                    #if yesterday
                    task[TASK_DUE_FORMATTED] = "Yesterday" + parse_addtime_tosummary(task[ALL_DAY],task[END])
                else:
                     #if less than a year old then display short date otherwise display iso date
                    formattedDate = ""
                    if (task[END].date() >= (datetime.today() - timedelta(days=365)).date()) :
                        formattedDate = str(task[END].day) + " " + MONTHSWITCHER.get(task[END].month)
                    else: 
                        formattedDate = task[END].date().isoformat()
                    task[TASK_DUE_FORMATTED] = formattedDate + parse_addtime_tosummary(task[ALL_DAY],task[END])
            elif task[DUE_TODAY]:
                task[TASK_DUE_FORMATTED] = "Today" + parse_addtime_tosummary(task[ALL_DAY],task[END])
            elif task[DUE_TOMORROW]:
                task[TASK_DUE_FORMATTED] = "Tomorrow" + parse_addtime_tosummary(task[ALL_DAY],task[END])
            elif task[DUE_NEXT7DAYS]:
                task[TASK_DUE_FORMATTED] = DAYSWITCHER.get(task[END].isoweekday()) + parse_addtime_tosummary(task[ALL_DAY],task[END])
            else:
                #default future if less than a year old then display short date otherwise display iso date
                formattedDatefuture = ""
                if (task[END].date() <= (datetime.today() + timedelta(days=365)).date()) :
                    formattedDatefuture = str(task[END].day) + " " + MONTHSWITCHER.get(task[END].month)
                else: 
                    formattedDatefuture = task[END].date().isoformat()
                task[TASK_DUE_FORMATTED] = formattedDatefuture + parse_addtime_tosummary(task[ALL_DAY],task[END])
        else:
            # If we ask for everything due before a certain date, don't count
            # things which have no due dates.
            if self._latest_due_date is not None:
                return None

            # Define values for tasks without due dates
            task[END] = None
            task[DUE_DATE] = None
            task[ALL_DAY] = True
            task[DUE_TODAY] = False
            task[OVERDUE] = False
            task[RECURRING_STATE] = False

        return task

    @staticmethod
    def select_best_task(project_tasks):
        """
        Search through a list of events for the "best" event to select.

        The "best" event is determined by the following criteria:
          * A proposed event must not be completed
          * A proposed event must have an end date (otherwise we go with
            the event at index 0, selected above)
          * A proposed event must be on the same day or earlier as our
            current event
          * If a proposed event is an earlier day than what we have so
            far, select it
          * If a proposed event is on the same day as our current event
            and the proposed event has a higher priority than our current
            event, select it
          * If a proposed event is on the same day as our current event,
            has the same priority as our current event, but is due earlier
            in the day, select it
        """
        # Start at the end of the list, so if tasks don't have a due date
        # the newest ones are the most important.

        event = project_tasks[-1]

        for proposed_event in project_tasks:
            if event == proposed_event:
                continue

            if proposed_event[COMPLETED]:
                # Event is complete!
                continue

            if proposed_event[END] is None:
                # No end time:
                if event[END] is None and (proposed_event[PRIORITY] < event[PRIORITY]):
                    # They also have no end time,
                    # but we have a higher priority.
                    event = proposed_event
                continue

            if event[END] is None:
                # We have an end time, they do not.
                event = proposed_event
                continue

            if proposed_event[END].date() > event[END].date():
                # Event is too late.
                continue

            if proposed_event[END].date() < event[END].date():
                # Event is earlier than current, select it.
                event = proposed_event
                continue

            if proposed_event[PRIORITY] > event[PRIORITY]:
                # Proposed event has a higher priority.
                event = proposed_event
                continue

            if proposed_event[PRIORITY] == event[PRIORITY] and (
                proposed_event[END] < event[END]
            ):
                event = proposed_event
                continue

        return event

    async def async_get_events(self, hass, start_date, end_date):
        """Get all tasks in a specific time frame."""
        if self._id is None:
            project_task_data = [
                task
                for task in self._api.state[TASKS]
                if not self._project_id_whitelist
                or task[PROJECT_ID] in self._project_id_whitelist
            ]
        else:
            project_data = await hass.async_add_executor_job(
                self._api.projects.get_data, self._id
            )
            project_task_data = project_data[TASKS]

        events = []
        for task in project_task_data:
            if task["due"] is None:
                continue
            due_date = _parse_due_date(task["due"])
            if start_date < due_date < end_date:
                if due_date.hour == 0 and due_date.minute == 0:
                    # If the due date has no time data, return just the date so that it
                    # will render correctly as an all day event on a calendar.
                    due_date_value = due_date.strftime("%Y-%m-%d")
                else:
                    due_date_value = due_date.isoformat()
                event = {
                    "uid": task["id"],
                    "title": task["content"],
                    "start": due_date_value,
                    "end": due_date_value,
                    "allDay": True,
                    "summary": task["content"],
                }
                events.append(event)
        return events

    def update(self):
        """Get the latest data."""
        if self._id is None:
            self._api.reset_state()
            self._api.sync()
            project_task_data = [
                task
                for task in self._api.state[TASKS]
                if not self._project_id_whitelist
                or task[PROJECT_ID] in self._project_id_whitelist
            ]
        else:
            project_task_data = self._api.projects.get_data(self._id)[TASKS]

        # If we have no data, we can just return right away.
        if not project_task_data:
            _LOGGER.debug("No data for %s", self._name)
            self.event = None
            return

        # Keep an updated list of all tasks in this project.
        project_tasks = []

        for task in project_task_data:
            todoist_task = self.create_todoist_task(task)
            if todoist_task is not None:
                # A None task means it is invalid for this project
                project_tasks.append(todoist_task)

        if not project_tasks:
            # We had no valid tasks
            _LOGGER.debug("No valid tasks for %s", self._name)
            self.event = None
            return

        # Make sure the task collection is reset to prevent an
        # infinite collection repeating the same tasks
        self.all_project_tasks.clear()

        # Organize the best tasks (so users can see all the tasks
        # they have, organized)
        #while project_tasks:
        #    best_task = self.select_best_task(project_tasks)
        #    _LOGGER.debug("Found Todoist Task: %s", best_task[SUMMARY])
        #    project_tasks.remove(best_task)
        #    self.all_project_tasks.append(best_task)
        
        #self.event = self.all_project_tasks[0]
        
        #PH - for now let us keep the standard ordering until we can deel with subtrees.
        self.all_project_tasks = project_tasks  
        self.event = project_tasks[-1] #//self.select_best_task(project_tasks)

        # Convert datetime to a string again
        if self.event is not None:
            if self.event[START] is not None:
                self.event[START] = {
                    DATETIME: self.event[START].strftime(DATE_STR_FORMAT)
                }
            if self.event[END] is not None:
                self.event[END] = {DATETIME: self.event[END].strftime(DATE_STR_FORMAT)}
            else:
                # Home Assistant gets cranky if a calendar event never ends
                # Let's set our "due date" to tomorrow
                self.event[END] = {
                    DATETIME: (datetime.utcnow() + timedelta(days=1)).strftime(
                        DATE_STR_FORMAT
                    )
                }
        _LOGGER.debug("Updated %s", self._name)
