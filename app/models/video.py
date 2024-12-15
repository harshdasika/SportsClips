import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy import Float, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from app.database import Base
from app.schemas.video import VideoStatus


class Video(Base):
    __tablename__ = "videos"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    raw_url = Column(String)
    highlight_url = Column(String, nullable=True)
    status = Column(SQLAlchemyEnum(VideoStatus))
    file_signature = Column(String, index=True)
    highlights = Column(JSONB, default=list)  # Store array of highlights
