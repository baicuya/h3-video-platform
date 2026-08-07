from __future__ import annotations

import argparse
import asyncio
import getpass
import sys

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.user import User
from app.schemas.auth import validate_password, validate_username


async def create_admin() -> int:
    async with SessionLocal() as db:
        existing_admin = await db.scalar(select(User.id).where(User.role == "admin"))
        if existing_admin:
            print("系统已存在管理员；不会覆盖或自动创建新的默认管理员。")
            return 1
        username = input("username: ").strip()
        display_name = input("display_name: ").strip()
        password = getpass.getpass("password: ")
        confirmation = getpass.getpass("confirm password: ")
        try:
            validate_username(username)
            validate_password(password)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        if not display_name:
            print("display_name 不能为空", file=sys.stderr)
            return 2
        if password != confirmation:
            print("两次输入的密码不一致", file=sys.stderr)
            return 2
        user = User(
            username=username,
            display_name=display_name,
            password_hash=hash_password(password),
            role="admin",
            is_active=True,
            must_change_password=False,
            created_by=None,
        )
        db.add(user)
        await db.commit()
        print(f"管理员 {username} 创建成功。")
        return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("create-admin")
    args = parser.parse_args()
    if args.command == "create-admin":
        raise SystemExit(asyncio.run(create_admin()))


if __name__ == "__main__":
    main()
