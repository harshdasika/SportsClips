from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import UUID4, BaseModel


class VideoStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Highlight(BaseModel):
    start_time: float
    end_time: float
    excitement_score: float


# Used when creating a new video
class CreateVideo(BaseModel):
    raw_url: str
    status: VideoStatus = VideoStatus.PENDING


# The complete video object (used for responses)
class Video(CreateVideo):
    id: UUID4
    highlight_url: Optional[str] = None
    highlights: List[Highlight] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
