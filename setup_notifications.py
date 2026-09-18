"""Genera secretos locales de Web Push sin imprimir sus valores en la consola."""

import base64
import secrets
from pathlib import Path

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from dotenv import dotenv_values
from py_vapid import Vapid01

ENV_PATH = Path(__file__).resolve().parent / ".env"


def base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def generate_vapid_keys() -> tuple[str, str]:
    vapid = Vapid01()
    vapid.generate_keys()
    private_value = vapid.private_key.private_numbers().private_value.to_bytes(32, "big")
    public_value = vapid.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    return base64url(public_value), base64url(private_value)


def configure() -> list[str]:
    current = dotenv_values(ENV_PATH) if ENV_PATH.exists() else {}
    additions = {}
    if not current.get("VAPID_PUBLIC_KEY") or not current.get("VAPID_PRIVATE_KEY"):
        public_key, private_key = generate_vapid_keys()
        additions["VAPID_PUBLIC_KEY"] = public_key
        additions["VAPID_PRIVATE_KEY"] = private_key
    if not current.get("VAPID_SUBJECT"):
        additions["VAPID_SUBJECT"] = "mailto:admin@picarico.app"
    if not current.get("CRON_SECRET"):
        additions["CRON_SECRET"] = secrets.token_urlsafe(32)
    if not current.get("APP_TIMEZONE"):
        additions["APP_TIMEZONE"] = "America/Bogota"

    if additions:
        with ENV_PATH.open("a", encoding="utf-8") as env_file:
            if ENV_PATH.stat().st_size:
                env_file.write("\n")
            for key, value in additions.items():
                env_file.write(f"{key}={value}\n")
    return list(additions)


if __name__ == "__main__":
    created = configure()
    print("NOTIFICATION_CONFIG_OK", created or "already configured")
