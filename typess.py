from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, TypedDict, Optional

#### Enums
# Типи параметрів фільтра
class FiltrOption(Enum):
    BERUF = "beruf"
    BRANCH = "branch"
    AVAILABILITY = "arbeitszeit"
    PUBLISHED = "veroeffentlichtseit"
    TYPEOFFER = "angebotsart"

# Створення Enum для зайнятості
class Availability(Enum):
    FULL_TIME = "vz"

# Створення Enum для часових проміжків
class TimeSlot(Enum):
    TODAY = "0"
    YESTERDAY = "1"
    WEEK1 = "7"
    WEEK2 = "14"
    WEEK4 = "28"

# Тип позиції вакансії
class TypeOffer(Enum):
    WORK = "1"

# Статус роботи парсера
class ScraperStatus(Enum):
    WORKING = 'work'
    STOPED = 'stop'

#### Types
# Створення типу для параметрів, який буде включати зайнятість та часовий проміжок
@dataclass
class JobParams:
    branch: List[str] = None
    beruf: List[str] = None
    availability: List[Availability] = None
    time_slot: TimeSlot = None
    type_offer: TypeOffer = TypeOffer.WORK.value
