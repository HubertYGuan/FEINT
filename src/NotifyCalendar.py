import datetime
import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/calendar"]

def notify(todo_list: list[str]):
  """Shows basic usage of the Google Calendar API.
  Prints the start and name of the next 10 events on the user's calendar.
  """
  creds = None
  # The file token.json stores the user's access and refresh tokens, and is
  # created automatically when the authorization flow completes for the first
  # time.
  if os.path.exists("token.json"):
    creds = Credentials.from_authorized_user_file("token.json", SCOPES)
  # If there are no (valid) credentials available, let the user log in.
  if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
      creds.refresh(Request())
    else:
      flow = InstalledAppFlow.from_client_secrets_file(
          "credentials.json", SCOPES
      )
      creds = flow.run_local_server(port=0)
    # Save the credentials for the next run
    with open("token.json", "w") as token:
      token.write(creds.to_json())

  try:
    service = build("calendar", "v3", credentials=creds)
    # The calendar doesn't notify properly bruh

    # Call the Calendar API
    now = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10, seconds=1)).isoformat()
    later = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=16.9)).isoformat()
    Description = '\n'.join(str(item) for item in todo_list)
    print("Creating event...")
    event = {
    'summary': 'TODO List:',
    'location': 'Department of Gnome Studies, Santa Barbara, CA 93117, USA',
    'description': Description,
    'start': {
      'dateTime': now,
      'timeZone': 'UTC',
    },
    'end': {
      'dateTime': later,
      'timeZone': 'UTC',
    },
    'reminders': {
      'useDefault': False,
      'overrides': [
        {'method': 'email', 'minutes': 24 * 60},
        {'method': 'popup', 'minutes': 10},
      ],
    },
    }

    event = service.events().insert(calendarId='primary', body=event).execute()
    print("Event created: %s" % (event.get('htmlLink')))
  except HttpError as error:
    print(f"An error occurred: {error}")
