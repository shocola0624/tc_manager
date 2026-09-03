from pydantic import BaseModel, Field


class BudgetItemCreateRequest(BaseModel):
    activity_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    amount_jpy: int
