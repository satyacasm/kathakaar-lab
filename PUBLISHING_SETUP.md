# Publishing setup: YouTube and Instagram (one time)

Some steps happen in your browser, under your own accounts. Claude can't do these for you. Nothing here costs money.
Never paste a token, secret or JSON file's contents into the Claude chat. Files go into `~/kathakaar-lab/secrets/`
(the folder is chmod 700, and the scripts set each file to chmod 600).

## A. YouTube (about 15 minutes)

1. Go to **console.cloud.google.com** and sign in with the Google account that owns the Kathakaar channel.
   Create a project named "kathakaar-publisher".
2. **APIs & Services → Library →** "YouTube Data API v3" **→ Enable.**
3. **Google Auth Platform → Branding / Audience** (older consoles call this "OAuth consent screen"):
   - App name: Kathakaar Publisher. Add your email for support and as the developer contact.
   - Audience: **External.**
   - Under Test users, add your own Google account.
   - Then click **Publish app** ("In production"). Without this, the login expires every 7 days.
     Google will show "unverified app" when you sign in. That's expected for a personal tool, and it's still safe
     because the app is your own.
4. **Clients → Create client → Application type: Desktop app** → name it "kathakaar-cli" → Create →
   **Download JSON.**
5. Move the file into place. In this Claude session, type:
   `! mv ~/Downloads/client_secret_*.json ~/kathakaar-lab/secrets/youtube_client.json && chmod 600 ~/kathakaar-lab/secrets/youtube_client.json`
6. Connect the channel:
   `! ~/kathakaar-lab/pipeline/youtube_publish.py setup`
   A browser tab opens. Pick the channel's account, click **Advanced → Go to Kathakaar Publisher (unsafe)**,
   allow access, then close the tab. The terminal then prints the channel name.
7. **Remove the private-only lock (optional but needed for one-step publishing).** Uploads from a new, unaudited API
   project are locked to private, so until this passes you switch each video to Public in Studio yourself (one click).
   Apply through the **YouTube API Services Audit and Quota Extension form**
   (support.google.com/youtube/contact/yt_api_form). It's free and takes days to weeks.

## B. Instagram (about 20 minutes)

1. The Instagram account must be **Professional** (Creator or Business):
   Instagram app → Settings → Account type and tools → Switch to professional account.
2. Go to **developers.facebook.com** → My Apps → **Create app** → use case "Manage messaging & content on Instagram"
   → create it.
3. In the app: **Instagram → API setup with Instagram login.**
   - Under "Generate access tokens", **Add account** and log in as the Kathakaar Instagram account.
     If asked, accept the tester invite in Instagram (Settings → Website permissions → Apps and websites → Tester invites).
   - Make sure the permissions include `instagram_business_basic` and `instagram_business_content_publish`.
   - **Generate token** and copy it. Also copy the **Instagram app secret** (App settings → Basic, or shown on the same
     page).
4. In **Terminal.app** (not in Claude, because the input is hidden), run:
   `~/kathakaar-lab/pipeline/instagram_publish.py setup`
   Paste the token, then the app secret. It saves a 60-day token and prints the account it will post to.
5. Check it any time with `! ~/kathakaar-lab/pipeline/instagram_publish.py check`. Renew before 60 days with
   `refresh`.

The app can stay in **Development** mode: an app in development can still post to the accounts that have a role on it,
which here is your own account.

## How publishing works afterwards
Only after you say **"publish"** for an episode, Claude runs:
- `pipeline/youtube_publish.py publish <episode> --yes-publish [--privacy public] [--publish-at <time>]`
- `pipeline/instagram_publish.py publish <episode> --yes-publish`

Both log the post IDs and links into `episode.json`. A `--dry-run` shows exactly what would go up, without uploading.
