from typing import List, Optional

from pydantic import BaseModel, Field


class AnnouncementIn(BaseModel):
    description: str = Field(..., max_length=800)
    price: Optional[str] = Field(default="", max_length=130)
    price_in_description: bool = False
    contact_info: Optional[str] = Field(default="", max_length=200)
    photo_file_ids: List[str] = Field(default_factory=list)


class AnnouncementOut(BaseModel):
    id: int
    description: str
    price: str
    price_in_description: bool = False
    contact_info: Optional[str] = None
    photo_file_ids: List[str]
    is_published: bool
    post_link: Optional[str] = None
    published_at: Optional[str] = None
    is_updated: bool = False
