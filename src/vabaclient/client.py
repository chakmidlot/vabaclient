import datetime
import random
import string
from typing import TypedDict

import httpx
from bs4 import BeautifulSoup

API_URL = "https://wellness.vs.sparkleapp.sparkle.plus/proxy.php"
API_KEY = "43816A1657EC4FCB6E953B5BA3EEEen"  # public key


class Reservation(TypedDict):
    id: int
    timestamp: datetime.datetime

class AvailableReservations(TypedDict):
    timestamp: datetime.datetime
    count: int


class VabaClient:

    def __init__(self, username, password):
        self._username = username
        self._password = password

    async def get_available_times(self, dt: datetime.date) -> list[AvailableReservations]:
        client = httpx.AsyncClient()
        response = await client.post(
            API_URL,
            params={
                "language": "en",
                "apikey": API_KEY,
                "modul": "sparkleTicketingOnline",
                "file": "ajaxResponder.php",
                "action": "getPossibleUhrzeiten"
            },
            data={
                "datum": dt.strftime("%Y-%m-%d"),
                "bereich": "",
                "Artikel_ID": "2948",
                "anzahlPersonen": "1"
            }
        )

        response.raise_for_status()

        data = response.json()

        appointments = []

        for time, count in data["data"]["uhrzeiten"].items():
            if count == 0:
                continue

            h, m = map(int, time.split(":"))
            appointment = datetime.datetime(dt.year, dt.month, dt.day, h, m)
            appointments.append({
                "timestamp": appointment,
                "count": count
            })

        return appointments

    async def get_active_appointments(self) -> list[Reservation]:
        token = await self._get_login_token()

        client = httpx.AsyncClient()

        response = await client.get(
            API_URL,
            params={
                "key": token,
                "language": "en",
                "apikey": API_KEY,
                "modul": "sparkleTicketingOnline",
                "file": "userTermine.php",
            })

        soup = BeautifulSoup(response.text, "html.parser")
        times = []

        for appointment in soup.select(".anwendungswrap"):
            termin_id = int(appointment["id"].split("_")[2])

            _, date, time = map(str.strip, appointment.select_one(".uhrzeit").text.split(","))

            ts = datetime.datetime.strptime(f"{date} {time}", "%d.%m.%Y %H:%M")

            times.append({
                "id": termin_id,
                "timestamp": ts
            })

            times.sort(key=lambda x: x["timestamp"])

        return times

    async def _get_login_token(self):
        token = "".join(random.choices(string.ascii_uppercase + string.digits, k=26))

        client = httpx.AsyncClient()
        response = await client.post(
            API_URL,
            params={
                "key": token,
                "language": "en",
                "apikey": API_KEY,
                "modul": "sparkleTicketingOnline",
                "file": "ajaxResponder.php?action=login",
            },
            data={
                "username": self._username,
                "userpass": self._password
            },
        )

        response.raise_for_status()

        if not response.json()["success"]:
            raise Exception("Can't login")

        return token

    async def update_appointment_time(self, appointment_id, timestamp):
        token = await self._get_login_token()

        date = timestamp.strftime("%Y-%m-%d")
        time = timestamp.strftime("%H:%M")

        client = httpx.AsyncClient()

        response = await client.post(
            API_URL,
            params={
                "key": token,
                "language": "en",
                "apikey": API_KEY,
                "modul": "sparkleTicketingOnline",
                "file": "ajaxResponder.php?action=moveTicket",
            },
            data={
                "bereich": "",
                "modul": "sparkleTicketingOnline",
                "Termine_ID": appointment_id,
                "Datum": date,
                "Uhrzeit": time,
            }
        )

        if not response.json()["success"]:
            raise Exception("Can't update appointment")
