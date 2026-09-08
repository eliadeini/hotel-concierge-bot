from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class HotelRegionTag(Base):
    __tablename__ = "hotel_region_tag"
    __table_args__ = (
        UniqueConstraint("hotel_settings_id", "tag", name="uq_hotel_region_tag"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    hotel_settings_id: Mapped[int] = mapped_column(
        ForeignKey("hotel_settings.id", ondelete="CASCADE"), index=True
    )
    tag: Mapped[str] = mapped_column(String(64), index=True)

    hotel: Mapped["HotelSettings"] = relationship(back_populates="region_tags")  # noqa: F821