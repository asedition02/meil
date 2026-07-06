"""Takvim kaynakları: Apple iCloud (CalDAV) ve Google/genel ICS beslemeleri."""
import datetime as dt

import caldav
import icalendar
import recurring_ical_events
import requests

ICLOUD_CALDAV_URL = "https://caldav.icloud.com/"


class CalendarError(Exception):
    pass


def _to_local_naive(value) -> tuple[str, bool]:
    """DTSTART/DTEND değerini (ISO metin, tüm_gün_mü) olarak döndürür."""
    if isinstance(value, dt.datetime):
        if value.tzinfo is not None:
            value = value.astimezone().replace(tzinfo=None)
        return value.isoformat(timespec="minutes"), False
    if isinstance(value, dt.date):
        return dt.datetime.combine(value, dt.time.min).isoformat(timespec="minutes"), True
    return str(value), False


def _vevent_to_dict(comp) -> dict | None:
    start_prop = comp.get("DTSTART")
    if start_prop is None:
        return None
    start, all_day = _to_local_naive(start_prop.dt)
    end_prop = comp.get("DTEND") or comp.get("DUE")
    if end_prop is not None:
        end, _ = _to_local_naive(end_prop.dt)
    else:
        end = start
    return {
        "uid": str(comp.get("UID", "")),
        "title": str(comp.get("SUMMARY", "(başlıksız)")),
        "start": start,
        "end": end,
        "all_day": all_day,
        "location": str(comp.get("LOCATION", "")) or None,
        "notes": None,
    }


# ---- Apple iCloud (CalDAV) ----

def _dav_client(username: str, password: str, url: str = ICLOUD_CALDAV_URL) -> caldav.DAVClient:
    return caldav.DAVClient(url=url, username=username, password=password)


def discover_icloud(username: str, password: str) -> list[dict]:
    """iCloud hesabındaki takvimleri bulur: [{name, url}]."""
    try:
        client = _dav_client(username, password)
        principal = client.principal()
        calendars = []
        for cal in principal.calendars():
            try:
                name = cal.name or "Takvim"
            except Exception:
                name = "Takvim"
            calendars.append({"name": str(name), "url": str(cal.url)})
        if not calendars:
            raise CalendarError("Bu iCloud hesabında takvim bulunamadı.")
        return calendars
    except caldav.lib.error.AuthorizationError as e:
        raise CalendarError(
            "iCloud girişi reddedildi. Apple Kimliğiniz ve appleid.apple.com adresinden "
            "oluşturacağınız UYGULAMA ŞİFRESİ gerekir (normal Apple şifreniz çalışmaz)."
        ) from e
    except CalendarError:
        raise
    except Exception as e:
        raise CalendarError(f"iCloud'a bağlanılamadı: {e}") from e


def fetch_caldav_events(cal_row: dict, start: dt.datetime, end: dt.datetime) -> list[dict]:
    """Tek bir CalDAV takviminden etkinlikleri çeker (tekrarlar açılmış olarak)."""
    try:
        client = _dav_client(cal_row["username"], cal_row["password"], cal_row["url"])
        cal = caldav.Calendar(client=client, url=cal_row["url"])
        found = cal.search(start=start, end=end, event=True, expand=True)
    except Exception as e:
        raise CalendarError(f"{cal_row['name']}: etkinlikler alınamadı: {e}") from e
    events = []
    for item in found:
        try:
            ev = _vevent_to_dict(item.icalendar_component)
            if ev:
                events.append(ev)
        except Exception:
            continue
    return events


def create_caldav_event(cal_row: dict, title: str, start: dt.datetime, end: dt.datetime,
                        location: str | None = None, notes: str | None = None) -> str:
    """CalDAV takvimine (iCloud) etkinlik yazar; UID döner."""
    try:
        client = _dav_client(cal_row["username"], cal_row["password"], cal_row["url"])
        cal = caldav.Calendar(client=client, url=cal_row["url"])
        kwargs = {"dtstart": start, "dtend": end, "summary": title}
        if location:
            kwargs["location"] = location
        if notes:
            kwargs["description"] = notes
        event = cal.save_event(**kwargs)
        try:
            return str(event.icalendar_component.get("UID", ""))
        except Exception:
            return ""
    except Exception as e:
        raise CalendarError(f"Etkinlik takvime yazılamadı: {e}") from e


# ---- ICS / webcal beslemeleri (Google gizli adresi dahil) ----

def _normalize_ics_url(url: str) -> str:
    url = url.strip()
    if url.startswith("webcal://"):
        url = "https://" + url[len("webcal://"):]
    return url


def fetch_ics_events(url: str, start: dt.datetime, end: dt.datetime) -> list[dict]:
    url = _normalize_ics_url(url)
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        cal = icalendar.Calendar.from_ical(resp.content)
    except Exception as e:
        raise CalendarError(f"ICS takvimi okunamadı: {e}") from e
    events = []
    try:
        occurrences = recurring_ical_events.of(cal).between(start, end)
    except Exception as e:
        raise CalendarError(f"ICS etkinlikleri çözümlenemedi: {e}") from e
    for comp in occurrences:
        ev = _vevent_to_dict(comp)
        if ev:
            events.append(ev)
    return events


def test_ics(url: str):
    """ICS adresini doğrular (indirme + çözümleme)."""
    now = dt.datetime.now()
    fetch_ics_events(url, now - dt.timedelta(days=7), now + dt.timedelta(days=30))


# ---- Ortak eşitleme ----

def fetch_events(cal_row: dict, start: dt.datetime, end: dt.datetime) -> list[dict]:
    if cal_row["type"] == "icloud":
        return fetch_caldav_events(cal_row, start, end)
    if cal_row["type"] == "ics":
        return fetch_ics_events(cal_row["url"], start, end)
    return []
