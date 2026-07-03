from typing import List, Optional

from pydantic import BaseModel, Field


class AnnouncementIn(BaseModel):
    description: str = Field(..., max_length=800)
    price: Optional[str] = Field(default="", max_length=130)
    price_in_description: bool = False
    contact_info: Optional[str] = Field(default="", max_length=200)
    photo_file_ids: List[str] = Field(default_factory=list)
    ad_type: Optional[str] = Field(default="fixed")
    start_price: Optional[int] = None
    min_step: Optional[int] = None
    buyout_price: Optional[int] = None
    auction_duration_hours: Optional[int] = None
    currency: Optional[str] = None


class AnnouncementOut(BaseModel):
    id: int
    description: str
    price: str
    price_in_description: bool = False
    contact_info: Optional[str] = None
    photo_file_ids: List[str]
    is_published: bool
    post_link: Optional[str] = None
    comments_count: int = 0
    published_at: Optional[str] = None
    updated_at: Optional[str] = None
    is_updated: bool = False
    is_reserved: bool = False
    ad_type: str = "fixed"
    auction_status: Optional[str] = None
    start_price: Optional[int] = None
    current_price: Optional[int] = None
    min_step: Optional[int] = None
    buyout_price: Optional[int] = None
    auction_end_at: Optional[str] = None
    winner_username: Optional[str] = None
    bids_count: int = 0


class BidIn(BaseModel):
    amount: int = Field(..., gt=0)
