from datetime import time

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator


class RuleCreate(BaseModel):
    """A weekly window, in the business's LOCAL time.

    Examples:
      Mon 09:00-17:00            {"day_of_week": 0, "start_time": "09:00", "end_time": "17:00"}
      Fri 20:00-02:00 (overnight){"day_of_week": 4, "start_time": "20:00", "end_time": "02:00"}
      Sat open 24 hours          {"day_of_week": 5, "is_all_day": true}
    """

    day_of_week: int = Field(ge=0, le=6, description="0 = Monday ... 6 = Sunday")
    start_time: time | None = None
    end_time: time | None = None
    is_all_day: bool = False

    @model_validator(mode="after")
    def check_shape(self):
        if self.is_all_day:
            if self.start_time is not None or self.end_time is not None:
                raise ValueError("All-day rules must not have start_time or end_time")
        else:
            if self.start_time is None or self.end_time is None:
                raise ValueError(
                    "start_time and end_time are required unless is_all_day is true"
                )
            if self.start_time == self.end_time:
                raise ValueError(
                    "start_time and end_time must differ (use is_all_day for 24 hours)"
                )

        for value in (self.start_time, self.end_time):
            if value is not None and (
                value.second or value.microsecond or value.tzinfo is not None
            ):
                raise ValueError(
                    "Times must be whole minutes with no timezone: "
                    "they are the business's local wall-clock time"
                )
        return self


class RuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    business_id: int
    day_of_week: int
    start_time: time | None
    end_time: time | None
    is_all_day: bool

    @computed_field
    @property
    def crosses_midnight(self) -> bool:
        return (
            not self.is_all_day
            and self.start_time is not None
            and self.end_time is not None
            and self.end_time < self.start_time
        )
