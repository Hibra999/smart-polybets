from datetime import datetime, timezone

from core import timez


def test_pdc_is_fixed_utc_minus_5():
    # Cancún no tiene DST: -5 en invierno y en verano.
    for month in (1, 7):
        dt = datetime(2026, month, 15, 18, 0, tzinfo=timezone.utc)
        assert timez.to_local(dt).utcoffset().total_seconds() == -5 * 3600


def test_et_has_dst():
    # ET es UTC-4 en verano (EDT) y UTC-5 en invierno (EST).
    assert timez.to_et(datetime(2026, 7, 15, 18, tzinfo=timezone.utc)).utcoffset().total_seconds() == -4 * 3600
    assert timez.to_et(datetime(2026, 1, 15, 18, tzinfo=timezone.utc)).utcoffset().total_seconds() == -5 * 3600


def test_fmt_same_date():
    # 2026-06-30 19:00 UTC -> 14:00 PDC / 15:00 ET (mismo día)
    s = timez.fmt_local_et(datetime(2026, 6, 30, 19, 0, tzinfo=timezone.utc))
    assert s == "2026-06-30 14:00 PDC / 15:00 ET"


def test_fmt_cross_midnight_shows_et_date():
    # 2026-06-30 02:00 UTC -> 21:00 PDC (jun 29) / 22:00 ET (jun 29): fechas iguales entre local y ET
    s = timez.fmt_local_et(datetime(2026, 6, 30, 2, 0, tzinfo=timezone.utc))
    assert s == "2026-06-29 21:00 PDC / 22:00 ET"


def test_accepts_iso_string():
    assert "PDC" in timez.fmt_local_et("2026-06-30T19:00:00+00:00")


def test_fmt_short():
    # 2026-06-30 19:00 UTC -> 14:00 PDC / 15:00 ET
    assert timez.fmt_local_et_short(datetime(2026, 6, 30, 19, tzinfo=timezone.utc)) == "06-30 14:00/15:00"
    assert timez.fmt_local_et_short(None) == "—"
