from pyrogram import Client

from pathlib import Path
import sys


def main() -> None:
    api_id = input("Telegram API ID: ").strip()
    api_hash = input("Telegram API Hash: ").strip()
    if not api_id or not api_hash:
        raise SystemExit("API ID and API Hash are required.")

    print("\nسيتم فتح تسجيل دخول للحساب المساعد.")
    print("استخدم حساباً مخصصاً للبوت، وليس حسابك الرئيسي إذا أمكن.\n")
    app = Client(
        "lybot-session-generator",
        api_id=int(api_id),
        api_hash=api_hash,
        workdir=str(Path(__file__).resolve().parent),
    )
    with app:
        session = app.export_session_string()
    print("\nTELEGRAM_USER_SESSION=")
    print(session)
    print("\nضع القيمة في Secrets فقط ولا ترفعها إلى GitHub.")


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    main()