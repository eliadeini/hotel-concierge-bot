from pathlib import Path


def read_hotel_skill(path: str | None) -> str | None:
    """Reads a hotel's free-text skill file (tone/branding instructions and
    the WhatsApp onboarding greeting — see HotelSettings.hotel_skill_path).

    Read fresh on every call, same as the region knowledge files — no
    caching. Returns None if no path is set or the file doesn't exist, so
    callers fall back to the generic defaults.
    """
    if not path:
        return None
    file_path = Path(path)
    if not file_path.is_file():
        return None
    text = file_path.read_text(encoding="utf-8").strip()
    return text or None