import datetime
import random
import string
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

API_URL = "https://wellness.vs.sparkleapp.sparkle.plus/proxy.php"
API_KEY = "43816A1657EC4FCB6E953B5BA3EEEen"  # public key


@dataclass
class Reservation:
    id: int
    timestamp: datetime.datetime


@dataclass
class AvailableReservations:
    timestamp: datetime.datetime
    count: int


def auth(method):
    async def wrapper(self, *args, **kwargs):
        if self._token is None:
            self._token = await self._get_login_token()

        try:
            return await method(self, *args, **kwargs)
        except NotAuthorizedError:
            self._token = None
            self._token = await self._get_login_token()
            return await method(self, *args, **kwargs)

    return wrapper


class VabaClient:

    def __init__(self, username, password):
        self._username = username
        self._password = password

        self._token = None

    @staticmethod
    async def get_available_times(dt: datetime.date) -> list[
        AvailableReservations]:
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

        if not data["data"]["uhrzeiten"]:
            return []

        for time, count in data["data"]["uhrzeiten"].items():
            if count == 0:
                continue

            h, m = map(int, time.split(":"))
            appointment = datetime.datetime(dt.year, dt.month, dt.day, h, m)
            appointments.append(AvailableReservations(
                timestamp=appointment,
                count=count
            ))

        return appointments

    @auth
    async def get_active_appointments(self) -> list[Reservation]:
        client = httpx.AsyncClient()

        response = await client.get(
            API_URL,
            params={
                "key": self._token,
                "language": "en",
                "apikey": API_KEY,
                "modul": "sparkleTicketingOnline",
                "file": "userTermine.php",
            })

        if response.text == '':
            raise NotAuthorizedError()

        soup = BeautifulSoup(response.text, "html.parser")
        times = []

        for appointment in soup.select(".anwendungswrap"):
            termin_id = int(appointment["id"].split("_")[2])

            _, date, time = map(str.strip,
                                appointment.select_one(".uhrzeit").text.split(
                                    ","))

            ts = datetime.datetime.strptime(f"{date} {time}", "%d.%m.%Y %H:%M")

            times.append(Reservation(
                id=termin_id,
                timestamp=ts
            ))

            times.sort(key=lambda x: x.timestamp)

        return times

    @auth
    async def update_appointment_time(self, appointment_id, timestamp):
        date = timestamp.strftime("%Y-%m-%d")
        time = timestamp.strftime("%H:%M")

        client = httpx.AsyncClient()

        response = await client.post(
            API_URL,
            params={
                "key": self._token,
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

        if response.status_code == 500:
            raise NotAuthorizedError()

        response = response.json()

        if not response.get("success"):
            message = response.get("message", "Can't update appointment")
            if message == "Keine Rechte zum verschieben.":
                raise ReservationNotFound()

            raise Exception("Can't update appointment")
        else:
            if response["data"] == "Ausgewählter Termin nicht mehr frei verfügbar.":
                raise TimeSlotNotAvailableError()
            if response["data"] == "":
                return

        raise Exception("Can't update appointment")

    async def _get_login_token(self):
        if self._token is not None:
            return self._token

        token = "".join(
            random.choices(string.ascii_uppercase + string.digits, k=26))

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
            message = response.json().get("message", "Can't login")

            if "Username and/or password are incorrect" in message:
                raise WrongCredentialsError()
            else:
                raise Exception(message)

        self._token = token
        return token


class NotAuthorizedError(Exception):
    pass


class WrongCredentialsError(Exception):
    pass


class ReservationNotFound(Exception):
    pass


class TimeSlotNotAvailableError(Exception):
    pass

