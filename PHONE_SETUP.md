# Using GREAT MEGA on your phone

How it works: the website and your bots run on your **laptop**. Your phone is a remote control
for it. The laptop must be on, awake, and GREAT MEGA must be running.
(Set the laptop's sleep setting to "never" while the bots are active.)

## Step 0: set a password (once)

Open GREAT MEGA on the laptop > **Settings > Security > Set password** (8+ characters).
Without a password, the site refuses every device except the laptop itself.
Forgot it? On the laptop run `py set_password.py` in this folder.

## Option A: same Wi-Fi (simplest)

1. On the laptop, double-click **Start for Phone (Wi-Fi).bat** (or run `py app.py --lan`).
2. Windows Firewall will ask about Python. Allow it on **Private networks**.
3. The window prints an address like `http://192.168.1.20:5000`. Type it into your phone's browser
   (phone on the same Wi-Fi). Log in with your password.
4. Make it an app:
   - **iPhone (Safari):** Share > Add to Home Screen. It opens full screen like an app.
   - **Android (Chrome):** menu (three dots) > Add to Home screen.

Limits: works only on that Wi-Fi, and the connection is not encrypted (plain http). That is
fine on a home network you trust. Do not use this on public or shared Wi-Fi.
If the phone cannot connect: same Wi-Fi? firewall allowed? "Guest" Wi-Fi networks often block
devices from talking to each other.

## Option B: from anywhere, private and encrypted (recommended): Tailscale

Tailscale makes a private network between your own devices only. Nothing is exposed to the internet.

1. Install **Tailscale** on the laptop and on the phone, and sign in with the same account (free for personal use).
2. In the Tailscale admin console (login.tailscale.com) > **DNS**: turn on **MagicDNS** and **HTTPS Certificates**.
3. Start GREAT MEGA on the laptop as usual (`py app.py`, or the Start GREAT MEGA.bat launcher).
4. In PowerShell on the laptop, run:

       tailscale serve --bg 5000

   (If the app was started with the launcher on port 8765, use 8765 instead of 5000.
   Tailscale's command options change between versions. If it errors, run `tailscale serve --help`.)
5. Tailscale prints an address like `https://laptop-name.your-tailnet.ts.net`. Open it on your phone and log in.
6. Install it: **Android (Chrome):** menu > **Install app**. **iPhone (Safari):** Share > Add to Home Screen.
   Because this address is HTTPS, Android gives you the full installable app.

I could not test the Tailscale steps here, so treat them as a guide and check Tailscale's own documentation if a step differs.

## Never do this

Do not "port forward" your router to the laptop or put the site on the open internet in its
current form. Use Tailscale (Option B) instead.

## Troubleshooting

| What you see | Meaning |
|---|---|
| "This site is not password protected..." (403) | Set the password first (Step 0) |
| "Can't reach the server" | Laptop asleep or off, or GREAT MEGA not running |
| Login says too many attempts | 5 wrong tries lock the login for 60 seconds |
| Changed the password | Every other device is signed out; log in again |
