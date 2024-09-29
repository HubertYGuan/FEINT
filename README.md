
# FEINT

FastAPI & ESP Interface and Notification Transponder

A web app for users to receive notifications (through Google Calendar) from devices running ESP-IDF (currently testing only ESP-32). In the future, the app will allow remote interfacing with a device.

The is centered around a REST API made with FastAPI that allows users to register and login with 2FA (currently multi-user functionality is limited) as well as query databases used in the notifications (currently including Todo list and notification history tables).
## Tech Stack

**Frontend:** Nicegui

**Backend:** FastAPI, Google Calendar API

**Server:** Uvicorn

**DB:** SQLite3, SQLAlchemy

**MCU:** ESP-IDF
## Roadmap

- Finish adding ESP-IDF client integration

- Add full support for multiple concurrent users, possibly switching to PostgreSQL or MySQL

- Implement web to MCU interfacing
## Run Locally

Ensure you have the following dependencies installed:
1. Docker
1. Dev Containers extension/manager (Optional)
1. Google Account
\
Clone the project

```bash
  git clone https://github.com/HubertYGuan/FEINT/
```
\
`cd FEINT` and create a file `.env`. This environment file must have the variables:
1. `SUPER_SECRET_KEY`: The key used to encode and decode JWTs.
1. `BACKEND_URL` 
1. `BACKEND_HOST`
1. `BACKEND_PORT`
1. `FRONTEND_URL`
1. `FRONTEND_HOST`
1. `FRONTEND_PORT`
1. `STORAGE_SECRET`: The key used to encrypt Nicegui storage data.
\
Set up a Google Cloud project with Google Calendar permissions ([guide](https://developers.google.com/workspace/guides/get-started)). Move the generated `credentials.json` inside `src`.

You can either (1.) use the dev container to run the web app and make changes or (2.) run the project with docker-compose.

1. If you run the dev container, the app files are in `/app`. You can edit them and the backend and frontend will automatically reload.
2. Simply use the docker-compose to launch a container and automatically run

```bash
  docker-compose up
```
## Deployment

If you want to deploy, you just have to run the docker compose and port forward your frontend port. However, I am using university-managed wifi so I'll likely have to resort to a cloud provider.
