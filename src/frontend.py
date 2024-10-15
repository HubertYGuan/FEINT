from fastapi import Request
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from nicegui import app, ui
import auth
from auth import ErrorCode
from dotenv import load_dotenv
import os

load_dotenv(dotenv_path="../.env")
BACKEND_URL = os.getenv("BACKEND_URL")
FRONTEND_URL = os.getenv("FRONTEND_URL")
FRONTEND_HOST = os.getenv("FRONTEND_HOST")
FRONTEND_PORT = os.getenv("FRONTEND_PORT")
STORAGE_SECRET = os.getenv("STORAGE_SECRET")


async def call_api(url: str, method: str = "GET"):
    response = await ui.run_javascript(
        f"""
            async function fetchData() {{
            try {{
                const response = await fetch("{BACKEND_URL}{url}",
                {{credentials: "include",
                headers: {{
                        "Accept": "application/json",
                        "Content-Type": "application/json"
                    }},
                    method: "{method}"
                    }});
                if (!response.ok) {{
                    return false;
                    }}
                const data = await response.json();
                return data;
            }} catch {{
                return false;
            }}
            }}
            return await fetchData();
            """
    )
    return response


# Middleware redirects back to login when not authenticated
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        if not app.storage.user.get("authenticated", False):
            # store where the user was trying to go
            if not request.url.path.startswith(
                ("/_nicegui", "/register", "/login", "/auth")
            ):
                app.storage.user["referrer_path"] = request.url.path
                return RedirectResponse("/login")
        return await call_next(request)


app.add_middleware(AuthMiddleware)


@ui.page("/")
async def main_page():
    def logout():
        app.storage.user.clear()
        ui.navigate.to("/login")

    ui.label(f'Welcome {app.storage.user.get("username", "ERROR")}')
    ui.button("Logout", on_click=logout)
    if not app.storage.user.get("otp_enabled", False):
        ui.button("Enable OTP", on_click=lambda: ui.navigate.to("/otp/enable"))
    else:
        ui.button("Disable OTP", on_click=lambda: ui.navigate.to("/otp/disable"))


@ui.page("/login")
async def login_page():
    username = ""
    password = ""

    async def login_failure():
        ui.notify("Login failed")

    async def attempt_login():
        if not username or not password:
            return
        result = await call_api(
            f"/auth/login?username={username.value}&password={password.value}"
        )
        if result:
            response = auth.Login_Response(**result)
            if (
                response.status == ErrorCode.OTP_REQUIRED
                or response.status == ErrorCode.INVALID_OTP
            ):
                app.storage.user["otp_enabled"] = True
                app.storage.user["username"] = username.value
                ui.navigate.to("/login/otp")
            else:
                print(response.status)
                print(response.status == ErrorCode.INVALID_OTP)
                if await call_api("/auth/login/token"):
                    current_user = await call_api("/auth/token/verify")
                    app.storage.user["authenticated"] = True
                    app.storage.user["otp_enabled"] = current_user["otp_enabled"]
                    app.storage.user["username"] = username.value
                    ui.navigate.to(app.storage.user.get("referrer_path", "/"))
                else:
                    await login_failure()
        else:
            await login_failure()

    ui.label("Login")
    ui.label("Username")
    username = ui.input("Username").on("keydown.enter", attempt_login)
    ui.label("Password")
    password = ui.input("Password", password=True, password_toggle_button=True).on(
        "keydown.enter", attempt_login
    )
    ui.button("Login", on_click=attempt_login)
    ui.button("Register", on_click=lambda: ui.navigate.to("/register"))


@ui.page("/login/otp")
async def otp_page():
    otp = ui.input()

    async def otp_failure():
        ui.notify("OTP failed")

    async def attempt_otp():
        if not otp.value:
            await otp_failure()
            return
        result = await call_api(f"/auth/login/otp?otp={otp.value}")
        if result:
            if await call_api("/auth/login/token"):
                current_user = await call_api("/auth/token/verify")
                app.storage.user["authenticated"] = True
                app.storage.user["otp_enabled"] = current_user["otp_enabled"]
                app.storage.user["username"] = current_user["username"]
                ui.navigate.to(app.storage.user.get("referrer_path", "/"))
            else:
                await otp_failure()
        else:
            await otp_failure()

    ui.label("Enter the one-time password from your authenticator app")
    otp = ui.input("OTP").on("keydown.enter", attempt_otp)
    ui.button("Submit", on_click=attempt_otp)


@ui.page("/register")
def register_page():
    username = ""
    password = ""

    async def register_failure():
        ui.notify("Registration failed")

    async def attempt_register():
        if not username or not password:
            return
        response: str = await call_api(
            f"/auth/register?username={username.value}&password={password.value}",
            method="POST",
        )
        print(f"response: {response}")
        if response:
            ui.navigate.to("/register/success")
        else:
            await register_failure()

    ui.label("Register")
    ui.label("Username")
    username = ui.input("Username").on("keydown.enter", attempt_register)
    ui.label("Password")
    password = ui.input("Password", password=True, password_toggle_button=True).on(
        "keydown.enter", attempt_register
    )
    ui.button("Register", on_click=attempt_register)
    ui.button("Login", on_click=lambda: ui.navigate.to("/login"))


@ui.page("/register/success")
def register_success():
    ui.label("Registration successful\nPlease login.")
    ui.button("Login", on_click=lambda: ui.navigate.to("/login"))


@ui.page("/otp/enable")
async def otp_register():
    if app.storage.user.get("otp_enabled", False):
        ui.label("OTP is already enabled")
        ui.button("Login", on_click=lambda: ui.navigate.to("/"))
        return
    else:
        ui.label("Please scan the QR code with your authenticator app")
        ui.image(f"{BACKEND_URL}/auth/otp/generate").style(
            "max-width: 300px; max-height: 300px;"
        )
        ui.label(
            "Once you have scanned the QR code, enter the one-time password from your authenticator app:"
        )

    otp = ""

    async def attempt_enable_otp():
        response: str = await call_api("/auth/otp/enable", method="PUT")
        if response:
            if await call_api(f"/auth/login/otp?otp={otp.value}&enabling_otp=True"):
                app.storage.user["otp_enabled"] = True
                ui.notify("OTP enabled")
                ui.navigate.to("/")
                return
        await call_api("/auth/otp/disable", method="PUT")
        ui.notify("OTP failed")

    otp = ui.input("OTP").on("keydown.enter", attempt_enable_otp)
    ui.button("Submit", on_click=attempt_enable_otp)


@ui.page("/otp/disable")
async def otp_disable():
    if not app.storage.user.get("otp_enabled", False):
        ui.label("OTP is already disabled")
        ui.button("Login", on_click=lambda: ui.navigate.to("/"))
    else:
        ui.label(
            "Please confirm you want to disable OTP by entering the one-time password from your authenticator app:"
        )
        otp = ""

        async def attempt_disable_otp():
            if await call_api(f"/auth/login/otp?otp={otp.value}&enabling_otp=True"):
                if not await call_api("/auth/otp/disable", method="PUT"):
                    ui.notify("OTP failed")
                    return
                app.storage.user["otp_enabled"] = False
                ui.notify("OTP disabled")
                ui.navigate.to("/")
                return
            ui.notify("OTP failed")

        otp = ui.input("OTP").on("keydown.enter", attempt_disable_otp)
        ui.button("Submit", on_click=attempt_disable_otp)


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        storage_secret=STORAGE_SECRET,
        host="0.0.0.0",
        port=int(FRONTEND_PORT),
    )
