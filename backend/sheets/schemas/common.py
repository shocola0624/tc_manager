from enum import Enum
from typing import Final


class Role(str, Enum):
    ADMIN = "admin"
    OFFICER = "officer"
    MEMBER = "member"


class Category(str, Enum):
    DRIPPER = "dripper"
    GRINDER = "grinder"
    SCALE = "scale"
    KETTLE = "kettle"
    POT = "pot"
    SCOOP = "scoop"
    THERMOMETER = "thermometer"
    SERVER = "server"
    OTHER = "other"


class Storage(str, Enum):
    CLUBROOM = "clubroom"
    OWNER = "owner"
    OTHER = "other"


class AttendanceStatus(str, Enum):
    ATTENDING = "attending"
    ABSENT = "absent"
    UNDECIDED = "undecided"


class AssignmentAction(str, Enum):
    ADD = "add"
    REMOVE = "remove"


class TaskStatus(str, Enum):
    TODO = "todo"
    DOING = "doing"
    DONE = "done"


# items.owner_id / assignments.assignee_id で「個人ではなくサークル所有」を表す特別値。
# users シートには対応する行が存在しない。
CIRCLE_OWNER_ID: Final[str] = "CIRCLE"
