# Videoflix Backend

REST API for **Videoflix**, a small video streaming platform. Users register with email
activation, log in with JWT stored in HttpOnly cookies and stream videos via HLS in
480p, 720p and 1080p. Uploaded videos are converted in the background with FFmpeg.

This repository contains the backend only. The frontend is provided by the
Developer Akademie and runs separately (see [Frontend](#frontend)).

## Contents

- [Tech stack](#tech-stack)
- [Requirements](#requirements)
- [Quickstart](#quickstart)
- [Frontend](#frontend)
- [Uploading videos](#uploading-videos)
- [Emails](#emails)
- [Environment variables](#environment-variables)
- [API endpoints](#api-endpoints)
- [Project structure](#project-structure)
- [Notes on the Docker setup](#notes-on-the-docker-setup)
- [Troubleshooting](#troubleshooting)

## Tech stack

- Python 3.12, Django, Django REST Framework
- JWT authentication with [SimpleJWT](https://django-rest-framework-simplejwt.readthedocs.io/) (tokens in HttpOnly cookies, refresh token rotation and blacklist)
- PostgreSQL as database
- Redis as cache and as message broker for [django-rq](https://github.com/rq/django-rq)
- FFmpeg for the HLS conversion and the thumbnails
- Gunicorn and WhiteNoise
- Docker and Docker Compose

## Requirements

- [Docker Desktop](https://docs.docker.com/get-docker/) (includes Docker Compose)
- [Git](https://git-scm.com/downloads)
- For the frontend: VS Code with the **Live Server** extension, or another static file server on port 5500

Python, PostgreSQL, Redis and FFmpeg do **not** need to be installed locally. Everything runs inside the containers.

## Quickstart

**1. Clone the repository**

```bash
git clone https://github.com/Infamous2k9/videoflix-backend.git
cd videoflix-backend
```

**2. Create the `.env` file**

```bash
cp .env.template .env
```

Replace at least the following values in `.env`:

| Variable             | What to enter                     |
| -------------------- | --------------------------------- |
| `SECRET_KEY`         | a long random string              |
| `JWT_SIGNING_KEY`    | a second, different random string |
| `DB_PASSWORD`        | any password for the database     |
| `DJANGO_SUPERUSER_*` | login data for the Django admin   |

Generate the two keys with:

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(50))'
```

Without further changes, emails are printed to the Docker log instead of being sent.
See [Emails](#emails) to send real emails.

**3. Build and start the containers**

```bash
docker compose up --build
```

On the first start the containers wait for PostgreSQL, run the migrations, collect the static
files and create the superuser from the `.env`. The backend is ready when the log shows
`Listening at: http://0.0.0.0:8000` and `Listening on high,default,low`.

**4. Open the admin**

[http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/), log in with `DJANGO_SUPERUSER_USERNAME` and `DJANGO_SUPERUSER_PASSWORD`.

**Stop the containers** with `Ctrl + C` or `docker compose down`.
`docker compose down -v` also deletes all data (database, uploaded videos).

## Frontend

1. Clone the [Videoflix frontend](https://github.com/Developer-Akademie-Backendkurs/project.Videoflix).
2. Open the **frontend folder itself** in VS Code (the folder that contains `index.html`).
3. Right-click `index.html` and choose **Open with Live Server**.

The frontend must run on **`http://127.0.0.1:5500`**:

- Use `127.0.0.1`, not `localhost`. The frontend calls the API at `http://127.0.0.1:8000/api/`. For the browser, `localhost` and `127.0.0.1` are different sites, and the auth cookies would not be sent.
- Use port `5500`. CORS only allows this origin, and the links in the emails point to it. If Live Server picks port 5501, port 5500 is still in use by another Live Server instance.

To use a different address, change `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` and `FRONTEND_BASE_URL` in `.env`.

## Uploading videos

Videos are uploaded in the Django admin under **App_Video → Videos**:

1. Enter title, description and category, and choose a video file (e.g. `.mp4`).
2. After saving, a background job converts the video. The status changes from
   **Pending** to **Processing** to **Ready** (or **Failed**).
3. Only videos with status **Ready** appear in the API and the frontend.

The conversion creates an HLS stream for each resolution (480p, 720p, 1080p) and a thumbnail.
Depending on the length of the video this can take a few minutes. Progress is visible in the
Docker log and in the admin under **Django RQ**.

Deleting a video in the admin also deletes the original file, the thumbnail and all HLS files.

Files are stored in the Docker volume `videoflix_media`, not in the project folder:

```bash
docker compose exec web ls -R media/
```

## Emails

Videoflix sends two emails: the account activation after registration and the password reset link.
Both are sent as HTML emails with a plain text fallback by a background job in the `high` queue.

**Development (default):** `EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend` prints
the emails to the Docker log. The log shows the raw email, so `=` appears as `=3D` and long
lines end with `=` and continue on the next line. Remove both to get the working link.

**Real emails with Gmail:**

1. Turn on 2-Step Verification for your Google account.
2. Create an app password at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).
3. Set in `.env`:

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
EMAIL_HOST_USER=your.address@gmail.com
EMAIL_HOST_PASSWORD=your16characterapppassword
DEFAULT_FROM_EMAIL=Videoflix <your.address@gmail.com>
```

4. Recreate the containers with `docker compose down` and `docker compose up`.

Activation and password reset links are valid for 24 hours (`PASSWORD_RESET_TIMEOUT`).

## Environment variables

All variables are read from `.env`. Changes take effect after `docker compose down` and `docker compose up`.

**Provided by the Developer Akademie setup** (do not rename):

| Variable                                  | Description                                    | Example                        |
| ----------------------------------------- | ---------------------------------------------- | ------------------------------ |
| `DJANGO_SUPERUSER_USERNAME`               | Username of the admin account created on start | `admin`                        |
| `DJANGO_SUPERUSER_PASSWORD`               | Password of the admin account                  | `adminpassword`                |
| `DJANGO_SUPERUSER_EMAIL`                  | Email of the admin account                     | `admin@example.com`            |
| `SECRET_KEY`                              | Django secret key                              | random string                  |
| `DEBUG`                                   | Debug mode, must be `False` in production      | `True`                         |
| `ALLOWED_HOSTS`                           | Hosts Django answers to                        | `localhost,127.0.0.1`          |
| `CSRF_TRUSTED_ORIGINS`                    | Trusted origins for CSRF                       | `http://127.0.0.1:5500`        |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD`     | PostgreSQL database, user and password         | `videoflix_db`                 |
| `DB_HOST` / `DB_PORT`                     | PostgreSQL host and port                       | `db` / `5432`                  |
| `REDIS_HOST` / `REDIS_PORT` / `REDIS_DB`  | Redis connection of the job queues             | `redis` / `6379` / `0`         |
| `REDIS_LOCATION`                          | Redis URL of the cache                         | `redis://redis:6379/1`         |
| `EMAIL_HOST` / `EMAIL_PORT`               | SMTP server and port                           | `smtp.gmail.com` / `587`       |
| `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | SMTP login                                     |                                |
| `EMAIL_USE_TLS` / `EMAIL_USE_SSL`         | Encryption of the SMTP connection              | `True` / `False`               |
| `DEFAULT_FROM_EMAIL`                      | Sender of all emails                           | `Videoflix <info@example.com>` |

**Additional variables:**

| Variable                 | Description                                                      | Example                                                     |
| ------------------------ | ---------------------------------------------------------------- | ----------------------------------------------------------- |
| `EMAIL_BACKEND`          | Console backend for development, SMTP backend for real emails    | `django.core.mail.backends.console.EmailBackend`            |
| `CORS_ALLOWED_ORIGINS`   | Origins allowed to call the API with cookies                     | `http://127.0.0.1:5500`                                     |
| `FRONTEND_BASE_URL`      | Base URL of the frontend, used for the links in the emails       | `http://127.0.0.1:5500`                                     |
| `AUTH_ACTIVATION_PATH`   | Frontend page of the activation link                             | `/pages/auth/activate.html?uid={uid}&token={token}`         |
| `PASSWORD_RESET_PATH`    | Frontend page of the password reset link                         | `/pages/auth/confirm_password.html?uid={uid}&token={token}` |
| `PASSWORD_RESET_TIMEOUT` | Validity of activation and reset links in seconds                | `86400`                                                     |
| `JWT_SIGNING_KEY`        | Separate key for signing the JWT                                 | random string                                               |
| `AUTH_COOKIE_SECURE`     | Send auth cookies over HTTPS only, `False` for local HTTP        | `False`                                                     |
| `USE_X_FORWARDED_PROTO`  | Trust the `X-Forwarded-Proto` header behind a reverse proxy      | `False`                                                     |
| `GUNICORN_CMD_ARGS`      | Extra Gunicorn options (see [Notes](#notes-on-the-docker-setup)) | `--workers 2 --threads 4 --timeout 120`                     |

## API endpoints

All endpoints are below `/api/`. Authentication uses the HttpOnly cookies `access_token` and
`refresh_token`, which are set by the login. Requests from the browser must be sent with
credentials (`fetch(..., { credentials: "include" })`).

**Authentication**

| Method | Endpoint                                  | Description                                              | Auth           |
| ------ | ----------------------------------------- | -------------------------------------------------------- | -------------- |
| POST   | `/api/register/`                          | Create an inactive account and send the activation email | –              |
| GET    | `/api/activate/<uidb64>/<token>/`         | Activate the account                                     | –              |
| POST   | `/api/login/`                             | Log in with email and password, sets both cookies        | –              |
| POST   | `/api/logout/`                            | Blacklist the refresh token and delete both cookies      | refresh cookie |
| POST   | `/api/token/refresh/`                     | Issue a new access token (and refresh token)             | refresh cookie |
| POST   | `/api/password_reset/`                    | Send the password reset email                            | –              |
| POST   | `/api/password_confirm/<uidb64>/<token>/` | Set a new password                                       | –              |

**Video**

| Method | Endpoint                                        | Description                                          | Auth          |
| ------ | ----------------------------------------------- | ---------------------------------------------------- | ------------- |
| GET    | `/api/video/`                                   | List all converted videos, newest first              | access cookie |
| GET    | `/api/video/<movie_id>/<resolution>/index.m3u8` | HLS playlist of a video in `480p`, `720p` or `1080p` | access cookie |
| GET    | `/api/video/<movie_id>/<resolution>/<segment>/` | One HLS segment, e.g. `000.ts`                       | access cookie |

Error messages of registration, login and password reset are kept generic on purpose,
so the API does not reveal whether an email address is registered.

The access token is valid for 30 minutes, the refresh token for 7 days.
Each refresh returns a new refresh token and blacklists the old one.

## Project structure

```
.
├── app_auth/                 # Registration, activation, login, logout, password reset
│   ├── api/                  # Serializers, views, URLs, authentication, tokens, helpers
│   ├── static/app_auth/      # Logo embedded in the emails
│   └── templates/app_auth/emails/
├── app_video/                # Video model, admin, conversion
│   ├── api/                  # Serializers, views, URLs
│   ├── signals.py            # Starts the conversion, deletes files
│   ├── tasks.py              # Background job for the RQ worker
│   └── utils.py              # FFmpeg commands and file helpers
├── core/                     # Settings and central URL configuration
├── backend.Dockerfile
├── backend.entrypoint.sh
├── docker-compose.yml
├── .env.template
└── requirements.txt
```

## Notes on the Docker setup

The Docker files are provided by the Developer Akademie. Differences from the original setup:

- **`backend.entrypoint.sh`** starts the RQ worker for three queues instead of one
  (`rqworker high default low`). Emails use `high`, the video
  conversion uses `low`, so emails are never delayed by a long conversion.
- **`GUNICORN_CMD_ARGS`** in `.env` gives Gunicorn several workers and threads and a longer
  timeout. With the default single worker, an idle connection opened in advance by the browser
  can block all requests, and large video uploads exceed the 30 second timeout.
- **Settings** read the environment with [django-environ](https://django-environ.readthedocs.io/).
  All variable names of the original setup are kept.
- **Media files** (thumbnails) are served by Django only with `DEBUG=True`. In production a web
  server such as Nginx should serve `/media/`.

## Troubleshooting

**`exec ./backend.entrypoint.sh: permission denied`**
The file is not executable:

```bash
chmod +x backend.entrypoint.sh
```

**`exec ./backend.entrypoint.sh: no such file or directory`**
The file has Windows line endings. Save it with **LF** line endings (VS Code: bottom right, `CRLF` → `LF`).

**The backend keeps logging `PostgreSQL ist nicht erreichbar`**
The database container did not start. Check `docker compose logs db`. If the volume contains
data of an older PostgreSQL version, remove it (this deletes all data):

```bash
docker compose down -v
docker compose up --build
```

**The frontend loads without styles, or the login does not keep the user logged in**
The frontend is not served from `http://127.0.0.1:5500/` (see [Frontend](#frontend)).

**A video stays on "Failed"**
Check the Docker log for the error of the conversion job. Delete the video in the admin and upload it again.

**Changes to a background job have no effect**
The RQ worker does not reload code automatically. Restart it with `docker compose restart web`.

## Credits

The frontend and the Docker setup were provided by the [Developer Akademie](https://developerakademie.com/).
