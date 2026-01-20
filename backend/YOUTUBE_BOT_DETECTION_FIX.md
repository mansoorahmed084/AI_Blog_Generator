# YouTube Bot Detection Fix

## Problem
**Error**: `Sign in to confirm you're not a bot. Use --cookies-from-browser or --cookies for the authentication.`

**Cause**: YouTube is blocking yt-dlp requests because they appear to come from a bot/server.

## Solution Applied

Updated `blog_generator.py` to include:
1. **User Agent**: Set to Chrome browser user agent string
2. **Android Client**: Use Android player client (less strict bot detection)

### Changes Made:
- Added `user_agent` to yt-dlp options
- Added `extractor_args` with Android client preference
- Applied to both `get_video_info()` and `download_audio()` methods

## Testing

Try generating a blog post again. The YouTube bot detection should be bypassed.

## If Issue Persists

If YouTube still blocks requests, try these alternatives:

### Option 1: Use Cookies (Most Reliable)
1. Export YouTube cookies from your browser
2. Save cookies file or set it as base64 in EB environment variables
3. Configure `yt-dlp` to use cookies via env vars

#### Export cookies (Chrome/Edge)
1. Install the extension **"Get cookies.txt LOCALLY"** or **"cookies.txt"**.
2. Go to `youtube.com` and ensure you are logged in.
3. Export cookies for YouTube and save as `cookies.txt`.

#### Local usage
Set the cookie file path:
```powershell
$env:YTDLP_COOKIES_PATH="C:\path\to\cookies.txt"
```

#### EB usage (automatic)
1. Base64 encode your `cookies.txt`:
```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("C:\path\to\cookies.txt"))
```
2. Set EB environment variable:
```powershell
eb setenv YTDLP_COOKIES_B64="<base64 string>"
```
3. Deploy:
```powershell
eb deploy
```

EB will create `/var/app/current/cookies.txt` automatically during deploy.

### Option 2: Try Different Client
Update `extractor_args` to use different clients:

```python
'extractor_args': {
    'youtube': {
        'player_client': ['ios', 'android', 'web'],  # Try iOS first
    }
}
```

### Option 3: Use YouTube API (Paid)
For production, consider using YouTube Data API v3 (requires API key, has quotas).

## Current Status

✅ **Fix Deployed**: User agent and Android client configured
🔄 **Testing**: Try generating a blog post now

## Monitoring

Check logs if it still fails:
```bash
eb logs
Get-Content .elasticbeanstalk\logs\latest\*\var\log\web.stdout.log | Select-String -Pattern "youtube|bot|error"
```
