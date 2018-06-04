from __future__ import print_function
from apiclient.discovery import build
from httplib2 import Http
from oauth2client import file, client, tools
from datetime import datetime, timedelta, date
import pytz
import os
import click
from enum import Enum, auto
import socket
import json
from dateutil import parser

BASE_PATH = os.path.abspath(os.path.dirname(__file__))
SCOPES = 'https://www.googleapis.com/auth/calendar.readonly'

# ここを変える
CRED1 = "cred1.json"
CRED2 = "cred2.json"
CALENDAE_ID_1 = "id1"
CALENDAR_ID_2_1 = "id2-1"
CALENDAR_ID_2_2 = "id2-2"


class Date_expression(Enum):
    今日 = auto()
    明日 = auto()
    明後日 = auto()
    今週 = auto()
    来週 = auto()


def get_credentials(cred_file_name):
    store = file.Storage(BASE_PATH + '/' + cred_file_name)
    creds = store.get()
    if not creds or creds.invalid:
        flow = client.flow_from_clientsecrets(
            BASE_PATH + '/client_secret.json', SCOPES)
        creds = tools.run_flow(flow, store)
    return creds


def get_week_beginning_datetime(datetime):
    until_weekend = 7 - datetime.isoweekday()
    until_week_beginning = until_weekend + 1
    return datetime + timedelta(days=until_week_beginning)


def to_zero_oclock(datetime):
    return datetime.replace(hour=0, minute=0, second=0, microsecond=0)


def get_events_by_span(service, calendar_id, from_time, to_time):
    events_result = service.events().list(
        calendarId=calendar_id,
        timeMin=from_time,
        timeMax=to_time,
        maxResults=10,
        singleEvents=True,
        orderBy='startTime').execute()

    return events_result.get('items', [])


def get_events(service, calendar_id, date_expression):
    tz_jp = pytz.timezone('Asia/Tokyo')

    from_date_str = None
    to_date_str = None

    if date_expression is Date_expression.今日:
        from_datetime = to_zero_oclock(tz_jp.normalize(datetime.now(pytz.utc)))
        to_date_str = (from_datetime + timedelta(days=1)).isoformat()
        from_date_str = from_datetime.isoformat()
    elif date_expression is Date_expression.明日:
        from_datetime = to_zero_oclock(tz_jp.normalize(
            datetime.now(pytz.utc)) + timedelta(days=1))
        to_date_str = (from_datetime + timedelta(days=1)).isoformat()
        from_date_str = from_datetime.isoformat()
    elif date_expression is Date_expression.明後日:
        from_datetime = to_zero_oclock(tz_jp.normalize(
            datetime.now(pytz.utc)) + timedelta(days=2))
        to_date_str = (from_datetime + timedelta(days=1)).isoformat()
        from_date_str = from_datetime.isoformat()
    elif date_expression is Date_expression.今週:
        from_datetime = to_zero_oclock(tz_jp.normalize(datetime.now(pytz.utc)))
        to_date_str = get_week_beginning_datetime(from_datetime).isoformat()
        from_date_str = from_datetime.isoformat()
    elif date_expression is Date_expression.来週:
        from_datetime = to_zero_oclock(get_week_beginning_datetime(
            tz_jp.normalize(datetime.now(pytz.utc))))
        to_date_str = get_week_beginning_datetime(from_datetime).isoformat()
        from_date_str = from_datetime.isoformat()

    return get_events_by_span(service, calendar_id, from_date_str, to_date_str)


# 開始日を昇順で並び替える
def event_compare(a, b):
    x_date_str = a["start"].get('dateTime', a['start'].get('date'))
    x_datetime = parser.parse(x_date_str, ignoretz=True)
    y_date_str = b["start"].get('dateTime', b['start'].get('date'))
    y_datetime = parser.parse(y_date_str, ignoretz=True)

    if x_datetime > y_datetime:
        return 1
    elif x_datetime < y_datetime:
        return -1
    else:
        return 0


def cmp_to_key(mycmp):
    'Convert a cmp= function into a key= function'
    class K:
        def __init__(self, obj, *args):
            self.obj = obj

        def __lt__(self, other):
            return mycmp(self.obj, other.obj) < 0

        def __gt__(self, other):
            return mycmp(self.obj, other.obj) > 0

        def __eq__(self, other):
            return mycmp(self.obj, other.obj) == 0

        def __le__(self, other):
            return mycmp(self.obj, other.obj) <= 0

        def __ge__(self, other):
            return mycmp(self.obj, other.obj) >= 0

        def __ne__(self, other):
            return mycmp(self.obj, other.obj) != 0
    return K


@click.command()
@click.option("--date_expression_str", "-d", default="今日",
              help="optins : 今日, 明日, 明後日, 今週, 来週, X月Y日")
def main(date_expression_str):
    date_expression = Date_expression[date_expression_str]

    creds = get_credentials(CRED1)
    service = build('calendar', 'v3', http=creds.authorize(Http()))
    events = get_events(service, CALENDAE_ID_1, date_expression)

    creds = get_credentials(CRED2)
    service = build('calendar', 'v3', http=creds.authorize(Http()))
    events.extend(get_events(service, CALENDAR_ID_2_1, date_expression))
    events.extend(get_events(service, CALENDAR_ID_2_2, date_expression))

    events = sorted(events, key=cmp_to_key(event_compare))

    if not events:
        print(date_expression.name + "の予定はありません")
        return

    weekday = ["月", "火", "水", "木", "金", "土", "日"]
    if date_expression in [Date_expression.今日, Date_expression.明日, Date_expression.明後日]:
        specified_datetime = parser.parse(
            events[0]["start"].get("dateTime", events[0]["start"].get("date")))
        print(
            f"{date_expression.name}、{specified_datetime.month}月{specified_datetime.day}日、{weekday[specified_datetime.weekday()]}曜日")
        for event in events:
            if "dateTime" in event["start"]:
                datetime = parser.parse(event["start"]["dateTime"])
                print(
                    f"{datetime.hour}時{f'{datetime.minute}分' if datetime.minute > 0 else ''}、{event['summary']}")
            elif "date" in event["start"]:
                print(event["summary"])
            else:
                raise Exception()
    else:
        pre_date = None
        for event in events:
            t_date = parser.parse(event["start"].get(
                "dateTime", event["start"].get("date")), ignoretz=True).date()
            if not pre_date or t_date > pre_date:
                print(
                    f"{t_date.month}月{t_date.day}日、{weekday[t_date.weekday()]}曜日")
                pre_date = t_date

            if "dateTime" in event["start"]:
                datetime = parser.parse(event["start"]["dateTime"])
                print(
                    f"{datetime.hour}時{f'{datetime.minute}分' if datetime.minute > 0 else ''}、{event['summary']}")
            elif "date" in event["start"]:
                print(event["summary"])
            else:
                raise Exception()


if __name__ == "__main__":
    main()
