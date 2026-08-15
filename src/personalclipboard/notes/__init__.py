"""Meeting and playback notes saved to the desktop."""

from personalclipboard.notes.library import RecordInfo, list_records, load_record
from personalclipboard.notes.meeting import MeetingNotes, desktop_directory, meeting_filename

__all__ = [
    "MeetingNotes",
    "RecordInfo",
    "desktop_directory",
    "list_records",
    "load_record",
    "meeting_filename",
]
