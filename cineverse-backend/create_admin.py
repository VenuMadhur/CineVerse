#!/usr/bin/env python3
"""
create_admin.py — CineVerse Billing Platform

A local developer CLI tool that replaces the manual SQL step previously
documented in the README:

    UPDATE users SET is_superuser = true WHERE email='...';

This is NOT an API endpoint and does not change any backend route,
schema, or authentication flow. It reuses the exact same building
blocks the API itself uses:

  - app.core.database.SessionLocal   (the existing session factory)
  - app.models.user.User             (the existing User model)
  - app.repositories.user_repository.UserRepository.get_by_email
  - app.services.auth_service.AuthService.register
      -> which itself reuses app.core.security.hash_password,
         so this script never hashes a password itself and never
         duplicates authentication logic.
  - app.schemas.auth.UserRegister    (the exact same input validation
         POST /auth/register enforces: real email format, full_name
         1-200 chars, password 8-128 chars)

Usage (run from the project root, e.g. `billing-platform/`):

    python create_admin.py

Behavior:
  - If no account exists for the given email: prompts for Full Name
    and Password, creates the account via the existing registration
    path, then promotes it to admin.
  - If an account already exists for the given email: promotes it to
    admin in place. The existing password is never touched.
"""
import getpass
import sys

from pydantic import ValidationError

from app.core.database import SessionLocal
from app.exceptions.custom_exceptions import ConflictException
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import UserRegister
from app.services.auth_service import AuthService


def prompt_non_empty(label: str) -> str:
    while True:
        value = input(f"{label}: ").strip()
        if value:
            return value
        print(f"  {label} cannot be empty. Please try again.")


def prompt_password() -> str:
    """
    Uses getpass (standard library) so the password is never echoed to
    the terminal or left sitting in shell history -- a real security
    consideration for a script that handles a plaintext password, even
    a local developer-only one.
    """
    while True:
        value = getpass.getpass("Password: ")
        if len(value) >= 8:
            return value
        print("  Password must be at least 8 characters (matches the API's own rule). Please try again.")


def promote_existing_user(db, user: User) -> None:
    if user.is_superuser:
        print(f"\n'{user.email}' is already an administrator. Nothing to do.")
        return

    # Only ever flips this one flag -- the existing hashed_password is
    # never read, written, or otherwise touched here.
    user.is_superuser = True
    db.commit()
    print(f"\nSuccess: '{user.email}' has been promoted to administrator.")


def create_new_admin(db, email: str) -> None:
    print(f"\nNo account found for '{email}'. Let's create one.")
    full_name = prompt_non_empty("Full Name")
    password = prompt_password()

    # Same validation the real POST /auth/register enforces (real email
    # format, name length, password length) -- rejects bad input before
    # ever touching the database.
    payload = UserRegister(email=email, full_name=full_name, password=password, country="US")

    # AuthService.register() is the *only* place this script creates a
    # user: it hashes the password via the existing hash_password(),
    # persists the User row, records the standard USER_REGISTERED audit
    # event, and commits -- exactly what happens for a normal signup.
    # This script adds nothing to that path except the is_superuser flip
    # below.
    user = AuthService(db).register(payload, is_superuser=True)
    print(f"\nSuccess: admin account created for '{user.email}'.")


def main() -> None:
    print("=== CineVerse Billing Platform: Create / Promote Admin ===\n")
    email = prompt_non_empty("Email").strip().lower()

    db = SessionLocal()
    try:
        existing_user = UserRepository(db).get_by_email(email)
        if existing_user is not None:
            promote_existing_user(db, existing_user)
        else:
            create_new_admin(db, email)
    except ValidationError as exc:
        db.rollback()
        print("\nFailed: the provided details are invalid.")
        for error in exc.errors():
            field = error["loc"][-1]
            print(f"  - {field}: {error['msg']}")
        sys.exit(1)
    except ConflictException as exc:
        # Defensive only -- the existence check above already routes
        # around this in the normal case; this only fires on a genuine
        # race (e.g. the account was created by something else between
        # the check and the insert).
        db.rollback()
        print(f"\nFailed: {exc}")
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001 -- top-level CLI guard, intentional
        db.rollback()
        print(f"\nFailed: an unexpected error occurred: {exc}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
