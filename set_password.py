"""Set (or remove) the site password.

    py set_password.py            set or change the password
    py set_password.py --remove   remove it (site then only answers this computer)

Takes effect immediately; no need to restart the server. Changing the password logs out
every phone and browser that was signed in.
"""
import getpass
import sys

import auth


def main():
    if "--remove" in sys.argv:
        auth.clear_password()
        print("Password removed. The site now only accepts requests from this computer.")
        return

    print(f"Choose a password for GREAT MEGA (at least {auth.MIN_PASSWORD_LEN} characters).")
    print("Nothing is shown while you type; that is normal.")
    first = getpass.getpass("New password: ")
    second = getpass.getpass("Repeat password: ")
    if first != second:
        print("The two passwords do not match. Nothing was changed.")
        sys.exit(1)
    try:
        auth.set_password(first)
    except ValueError as err:
        print(err)
        sys.exit(1)
    print("Password saved. Your phone can now log in.")


if __name__ == "__main__":
    main()
