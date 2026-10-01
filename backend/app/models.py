from datetime import date
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import BaseModel, ConfigDict, Field, field_validator

Domain = Literal[
    "physical", "mental", "financial", "productivity", "social", "learning"
]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PersonalDetails(Model):
    display_name: str = Field(default="", max_length=80)
    age: int | None = Field(default=None, ge=1, le=120)
    phone: str = Field(default="", max_length=30, pattern=r"^[0-9+().\- ]*$")
    city: str = Field(default="", max_length=100)
    country: str = Field(default="", max_length=100)
    occupation: str = Field(default="", max_length=150)
    education: str = Field(default="", max_length=200)
    about: str = Field(default="", max_length=1000)
    interests: str = Field(default="", max_length=300)
    strengths: str = Field(default="", max_length=500)
    challenges: str = Field(default="", max_length=500)
    routine: str = Field(default="", max_length=500)

    @field_validator("display_name")
    @classmethod
    def name_length(cls, value):
        if value and len(value) < 2:
            raise ValueError("Use at least two characters for your name")
        return value


class PersonalUpdate(Model):
    personal: PersonalDetails
    aspiration: str = Field(default="", max_length=500)


class Profile(Model):
    personal: PersonalDetails = Field(default_factory=PersonalDetails)
    timezone: str = "Asia/Kolkata"
    currency: Literal["INR", "USD", "EUR", "GBP"] = "INR"
    daily_minutes: int = Field(default=45, ge=5, le=240)
    priorities: list[Domain] = Field(
        default_factory=lambda: ["productivity", "physical", "financial"],
        min_length=1,
        max_length=6,
    )
    aspiration: str = Field(default="", max_length=500)
    reminder_hour: int = Field(default=19, ge=0, le=23)
    reminders: bool = True

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Use a valid IANA timezone")
        return value

    @field_validator("priorities")
    @classmethod
    def unique(cls, value):
        return list(dict.fromkeys(value))


class Register(Model):
    name: str = Field(min_length=2, max_length=80)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=10, max_length=128)

    @field_validator("email")
    @classmethod
    def email_valid(cls, value):
        value = value.lower()
        if (
            value.count("@") != 1
            or "." not in value.split("@")[-1]
            or any(c.isspace() for c in value)
        ):
            raise ValueError("Enter a valid email address")
        return value


class Login(Model):
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)


class Checkin(Model):
    day: date | None = None
    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    movement_minutes: int | None = Field(default=None, ge=0, le=600)
    mood: int | None = Field(default=None, ge=1, le=5)
    energy: int | None = Field(default=None, ge=1, le=5)
    stress: int | None = Field(default=None, ge=1, le=5)
    focus: int | None = Field(default=None, ge=1, le=5)
    planned_tasks: int | None = Field(default=None, ge=0, le=100)
    completed_tasks: int | None = Field(default=None, ge=0, le=100)
    reflection: str = Field(default="", max_length=1500)


class Goal(Model):
    title: str = Field(min_length=2, max_length=150)
    domain: Domain
    target_date: date
    next_step: str = Field(min_length=2, max_length=250)
    progress: int = Field(default=0, ge=0, le=100)


class Progress(Model):
    progress: int = Field(ge=0, le=100)


class Habit(Model):
    title: str = Field(min_length=2, max_length=120)
    domain: Domain


class HabitLog(Model):
    complete: bool = True


class Transaction(Model):
    day: date
    kind: Literal["income", "expense"]
    amount_cents: int = Field(gt=0, le=100000000000)
    category: str = Field(min_length=1, max_length=60)
    note: str = Field(default="", max_length=250)


class Budget(Model):
    category: str = Field(min_length=1, max_length=60)
    amount_cents: int = Field(ge=0, le=100000000000)


class ActionUpdate(Model):
    status: Literal["pending", "done", "skipped"]
    helpful: bool | None = None


class Experiment(Model):
    title: str = Field(min_length=2, max_length=150)
    option_a: str = Field(min_length=2, max_length=100)
    option_b: str = Field(min_length=2, max_length=100)
    days: int = Field(default=14, ge=6, le=28)


class ExperimentLog(Model):
    focus: int = Field(ge=1, le=5)
    completed: bool
    minutes: int = Field(ge=1, le=480)
    note: str = Field(default="", max_length=500)


class Scenario(Model):
    focus_sessions: int = Field(default=0, ge=0, le=14)
    minutes_per_session: int = Field(default=25, ge=5, le=120)
    expense_reduction_cents: int = Field(default=0, ge=0, le=100000000000)


class Feedback(Model):
    rating: int = Field(ge=1, le=5)
    message: str = Field(default="", max_length=2000)


class DeleteAccount(Model):
    password: str = Field(max_length=128)
