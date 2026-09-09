import sys
from datetime import datetime, timezone, timedelta
sys.path.insert(0, '.')
from agentsblog.config import Settings
from agentsblog.utils.time import is_quiet_hours, local_now

s = Settings()
# 21:09:24 UTC = 00:09:24 MSK (next day)
event_utc = datetime(2026, 9, 7, 21, 9, 24, tzinfo=timezone.utc)
event_msk = event_utc + timedelta(hours=3)
print(f'Event UTC: {event_utc}')
print(f'Event MSK: {event_msk}, hour={event_msk.hour}')
print(f'is_quiet_hours(MSK): {is_quiet_hours(event_msk, start_hour=s.quiet_hours_start, end_hour=s.quiet_hours_end)}')

# Actual current
now_msk = local_now(s.tz_offset)
print(f'\nActual now MSK: {now_msk}')
print(f'is_quiet_hours(now): {is_quiet_hours(now_msk, start_hour=s.quiet_hours_start, end_hour=s.quiet_hours_end)}')
