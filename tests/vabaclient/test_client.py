from datetime import date, datetime
from unittest import mock
from unittest.mock import AsyncMock

import pytest

from vabaclient.client import AvailableReservations, NotAuthorizedError, \
    Reservation, ReservationNotFound, TimeSlotNotAvailableError, VabaClient, \
    WrongCredentialsError
from pytest_httpx import HTTPXMock


@pytest.mark.parametrize(
    ("available_times", "expected"),
    [
        (
            [], []
        ),
        (
                {
                    '08:00': 0,
                    '09:00': 1,
                    '17:00': 10,
                    '17:20': 0,
                    '23:20': 5
                },
                [
                    AvailableReservations(timestamp=datetime(2025, 1, 2, 9, 0), count=1),
                    AvailableReservations(timestamp=datetime(2025, 1, 2, 17, 0), count=10),
                    AvailableReservations(timestamp=datetime(2025, 1, 2, 23, 20), count=5),
                ]
        ),
    ]
)
@pytest.mark.asyncio
async def test_get_available_times(available_times, expected, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://wellness.vs.sparkleapp.sparkle.plus/proxy.php"
            "?language=en"
            "&apikey=43816A1657EC4FCB6E953B5BA3EEEen"
            "&modul=sparkleTicketingOnline"
            "&action=getPossibleUhrzeiten"
            "&file=ajaxResponder.php",
        method="POST",
        match_content=b"datum=2025-01-02"
                      b"&bereich="
                      b"&Artikel_ID=2948"
                      b"&anzahlPersonen=1",
        json={
            'data': {
                'success': True,
                'geoeffnetVon': '08:00',
                'geoeffnetBis': '00:00',
                'singleBlock': False,
                'gesamtFrei': {
                    '08:00': 0,
                    '09:00': 50,
                    '17:00': 27,
                    '17:20': 27,
                    '23:20': 0,
                },
                'uhrzeiten': available_times
            },
        }
    )

    client = VabaClient("user", "password")

    d = date(2025, 1, 2)

    available_times = await client.get_available_reservations(d)

    assert available_times == expected


@pytest.mark.parametrize(
    ("reservations", "expected"),
    [
        (
            '''
                <p>There are currently no treatments booked for you.</p>
                <div style="clear:both"></div>
            ''',
            []
        ),
        (
            """
                <hr>
                <h3>Juni 2025</h3>
                <li class="anwendungswrap" id="TicketingTermine_ID_100500">
                    <span aria-hidden="true" class="spkl-datum kalender-style-datum">
                        <span class="dayname">Sa</span>
                        <span class="day">21</span>
                        <span class="month">Juni</span>
                        <span class="year">2025</span>
                    </span>
                    <div class="anwendungscontent">
                        <div class="terminHeading">
                            <span class="artikel">reservation   03.02.2025 from 09:00    to 09:20   for Sobaka Ulybaka</span><br>
                            <span class="uhrzeit">Montag, 03.02.2025, <span class="spkl-secondaryTextColor">
                                <span class="Uhrzeit">09:00</span>
                            </span>
                        </div>
                        <div></div>
                    </div>
                    <div class="anwendungszusatzinfo">
                        <div class="buttons" style="flex-grow: 1;">
                            <button type="button" data-spkl-click="userTicketingTermine.showMoveTicketingTerminDialog(2316842)">Re-schedule</button>
                            <button type="button" data-spkl-click="userTicketingTermine.showVoucher(2316842)">Show ticket</button>
                            <button type="button" data-spkl-click="userTicketingTermine.showCode(2316842)">Show code</button>
                        </div>
                        <div class="anmerkungen" style="align-self: flex-end;"></div>
                    </div>
                </li>
                <div style="clear:both"></div>
            """,
            [
                Reservation(id=100500, timestamp=datetime(2025, 2, 3, 9, 0))
            ]
        )
    ]
)
@pytest.mark.asyncio
async def test_get_active_reservations(reservations, expected, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url='https://wellness.vs.sparkleapp.sparkle.plus/proxy.php'
            '?key=ABCDEFGHIJKLMNOPQRSTUVWXYZ'
            '&language=en'
            '&apikey=43816A1657EC4FCB6E953B5BA3EEEen'
            '&modul=sparkleTicketingOnline'
            '&file=userTermine.php',
        text=reservations)

    client = VabaClient("test_user", "test_password")

    login_mock = AsyncMock(return_value="ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    client._get_login_token = login_mock

    reservations = await client.get_active_reservations()

    login_mock.assert_called_once()

    assert reservations == expected


@pytest.mark.asyncio
async def test_get_active_reservations_not_authorized(httpx_mock: HTTPXMock):
    client = VabaClient("test_user", "test_password")

    httpx_mock.add_response(text='')
    httpx_mock.add_response(text='')

    login_mock = AsyncMock(return_value="ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    client._get_login_token = login_mock

    with pytest.raises(NotAuthorizedError):
        await client.get_active_reservations()


@pytest.mark.asyncio
async def test_update_reservation_time(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://wellness.vs.sparkleapp.sparkle.plus/proxy.php"
            "?key=ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            "&language=en"
            "&apikey=43816A1657EC4FCB6E953B5BA3EEEen"
            "&modul=sparkleTicketingOnline"
            "&file=ajaxResponder.php%3Faction%3DmoveTicket",
        method="POST",
        match_content=b"bereich="
                      b"&modul=sparkleTicketingOnline"
                      b"&Termine_ID=100500"
                      b"&Datum=2025-03-04"
                      b"&Uhrzeit=12%3A40",
        json={'success': True, 'data': ''}
    )

    client = VabaClient("test_user", "test_password")

    login_mock = AsyncMock(return_value="ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    client._get_login_token = login_mock

    await client.update_reservation_time(100500, datetime(2025, 3, 4, 12, 40))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (
            {'success': False, 'message': "Keine Rechte zum verschieben."},
            ReservationNotFound()
        ),
        (
            {'success': False},
            Exception("Can't update reservation")
        ),
        (
            {'success': True,
             'data': "Ausgewählter Termin nicht mehr frei verfügbar."},
            TimeSlotNotAvailableError()
        ),
        (
            {'success': True, 'data': "Something went wrong"},
            Exception("Can't update reservation")
        ),
    ]
)
async def test_update_reservation_time_fails(response, expected, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        method="POST",
        json=response
    )

    client = VabaClient("test_user", "test_password")

    login_mock = AsyncMock(return_value="ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    client._get_login_token = login_mock

    with pytest.raises(type(expected), match=str(expected)):
        await client.update_reservation_time(100500, datetime(2025, 3, 4, 12, 40))


@pytest.mark.asyncio
async def test_update_reservation_unauthorized(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        method="POST",
        status_code=500
    )

    httpx_mock.add_response(
        method="POST",
        status_code=500
    )

    client = VabaClient("test_user", "test_password")

    login_mock = AsyncMock(return_value="ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    client._get_login_token = login_mock

    with pytest.raises(NotAuthorizedError):
        await client.update_reservation_time(100500, datetime(2025, 3, 4, 12, 40))

    assert login_mock.call_count == 2


@pytest.mark.asyncio
async def test_login(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url='https://wellness.vs.sparkleapp.sparkle.plus/proxy.php'
            '?key=ABCDEFGHIJKLMNOPQRSTUVWXYZ'
            '&language=en'
            '&apikey=43816A1657EC4FCB6E953B5BA3EEEen'
            '&modul=sparkleTicketingOnline'
            '&file=ajaxResponder.php%3Faction%3Dlogin',
        match_content=b"username=test_user&userpass=test_password",
        json={'success': True, 'data': ''}
    )

    client = VabaClient("test_user", "test_password")

    def choice_firsts(population, k):
        return population[:k]

    with mock.patch('random.choices', choice_firsts):
        await client._get_login_token()


@pytest.mark.asyncio
async def test_login_keep_token(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        json={'success': True, 'data': ''}
    )

    client = VabaClient("test_user", "test_password")

    assert client._token is None

    token_1 = await client._get_login_token()
    token_2 = await client._get_login_token()

    assert token_1 == token_2


@pytest.mark.asyncio
async def test_login_failed_credentials(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        json={'success': False, 'message': '''
<span class="warning">Please check your details. Username and/or password are incorrect. If you forgot your password, click this link.</span>
<div style="text-align:center;">
    <a href="#!lostpass">Set password</a>
</div>
'''})

    client = VabaClient("test_user", "test_password")

    with pytest.raises(WrongCredentialsError):
        await client._get_login_token()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("message", "expected"),
    [
        (None, "Can't login"),
        ("Something is wrong", "Something is wrong"),
    ]
)
async def test_login_failed_unknown(message, expected, httpx_mock: HTTPXMock):
    response = {'success': False}

    if message is not None:
        response['message'] = message

    httpx_mock.add_response(
        json=response
    )

    client = VabaClient("test_user", "test_password")

    with pytest.raises(Exception, match=expected):
        await client._get_login_token()
