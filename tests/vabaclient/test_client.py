import os
from datetime import date, datetime, timedelta

from dotenv import load_dotenv
import pytest

from vabaclient.client import VabaClient

load_dotenv()


@pytest.mark.asyncio
async def test_get_available_times():
    client = VabaClient("user", "password")

    next_saturday = date.today() + timedelta(days=(12 - date.today().weekday()))

    available_times = await client.get_available_times(next_saturday)

    # we don't know the values
    assert len(available_times) > 0
    assert all(x["timestamp"].date() == next_saturday for x in available_times)
    assert all(isinstance(x["count"], int) for x in available_times)


@pytest.mark.asyncio
async def test_get_active_appointments():
    username = os.environ["VABALI_USERNAME"]
    password = os.environ["VABALI_PASSWORD"]
    appointment_id = int(os.environ["VABALI_E2E_APPOINTMENT_ID"])

    client = VabaClient(username, password)

    appointments = await client.get_active_appointments()

    assert len(appointments) == 1
    assert appointments[0]["id"] == appointment_id
    assert isinstance(appointments[0]["timestamp"], datetime)


@pytest.mark.asyncio
async def test_get_move_appointment():
    username = os.environ["VABALI_USERNAME"]
    password = os.environ["VABALI_PASSWORD"]

    client = VabaClient(username, password)

    old_appointments = await client.get_active_appointments()
    assert len(old_appointments) == 1
    old_appointment = old_appointments[0]

    # appointments in one month on Saturday
    d = date.today() + timedelta(days=30)
    target_date = d + timedelta(days=(12 - d.weekday()))
    appointments = await client.get_available_times(target_date)

    # choose a new appointment
    new_timestamp = None
    for appointment in appointments:
        if new_timestamp != old_appointment["timestamp"]:
            new_timestamp = appointment["timestamp"]
            break

    await client.update_appointment_time(old_appointments[0]["id"], new_timestamp)

    new_appointments = await client.get_active_appointments()
    assert len(new_appointments) == 1
    assert new_appointments[0]["id"] == old_appointments[0]["id"]
    assert new_appointments[0]["timestamp"] == new_timestamp
