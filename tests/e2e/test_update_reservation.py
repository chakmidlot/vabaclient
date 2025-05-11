import os
from datetime import date, timedelta

import pytest
from dotenv import load_dotenv

from vabaclient.client import VabaClient


load_dotenv()

@pytest.mark.asyncio
@pytest.mark.e2e
async def test_get_move_reservation():
    username = os.environ["VABALI_USERNAME"]
    password = os.environ["VABALI_PASSWORD"]

    client = VabaClient(username, password)

    old_reservations = await client.get_active_reservations()
    assert len(old_reservations) == 1
    old_reservation = old_reservations[0]

    # reservations in one month on Saturday
    d = date.today() + timedelta(days=30)
    target_date = d + timedelta(days=(12 - d.weekday()))
    reservations = await client.get_available_reservations(target_date)

    # choose a new reservation
    new_timestamp = None
    for reservation in reservations:
        if new_timestamp != old_reservation.timestamp:
            new_timestamp = reservation.timestamp
            break

    await client.update_reservation_time(old_reservations[0].id, new_timestamp)

    new_reservations = await client.get_active_reservations()
    assert len(new_reservations) == 1
    assert new_reservations[0].id == old_reservations[0].id
    assert new_reservations[0].timestamp == new_timestamp
