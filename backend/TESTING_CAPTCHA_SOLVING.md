# Testing CAPTCHA Solving Feature

## Prerequisites

### Local Development (Windows)

1. **Install Playwright:**
   ```powershell
   cd C:\temp\AI\AI_blog_app\backend
   pip install playwright
   playwright install chromium
   ```

2. **Verify Installation:**
   ```powershell
   python -c "from playwright.sync_api import sync_playwright; print('Playwright installed successfully')"
   ```

### AWS Elastic Beanstalk

**Note:** Playwright requires a display server (X11) for visible browser mode. On EC2, you have two options:

1. **Use headless mode** (modify code)
2. **Use manual cookie upload** (recommended for EB)

For now, we'll test locally first, then provide EB instructions.

---

## Local Testing (Windows)

### Step 1: Start Django Server

```powershell
cd C:\temp\AI\AI_blog_app\backend
python manage.py runserver
```

### Step 2: Open Browser

Navigate to: `http://127.0.0.1:8000/`

### Step 3: Login or Sign Up

1. Click "Sign Up" if you don't have an account
2. Or click "Login" if you already have one

### Step 4: Trigger Bot Detection

To test CAPTCHA solving, you need a YouTube URL that triggers bot detection. Try these methods:

#### Method A: Use a Video That Often Triggers Bot Detection

Some videos are more likely to trigger bot detection. Try:
- New videos
- Videos with restricted access
- Videos from channels with strict policies

**Test URL examples:**
```
https://www.youtube.com/watch?v=skMzCAga-dg
https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

#### Method B: Force Bot Detection (for testing)

1. Clear any existing cookies:
   ```powershell
   # Delete cookie file if it exists
   Remove-Item "C:\temp\AI\AI_blog_app\backend\cookies\youtube_cookies.txt" -ErrorAction SilentlyContinue
   ```

2. Remove environment variable:
   ```powershell
   $env:YTDLP_COOKIES_PATH = ""
   ```

3. Try generating a blog - YouTube may detect it as a bot

### Step 5: Test CAPTCHA Solving Flow

1. **Enter YouTube URL** in the input field
2. **Click "Generate Blog"**
3. **Wait for bot detection** - You should see:
   - A modal popup saying "Verify You Are Human"
   - Instructions on how to solve
   - A button "Verify You Are Human"

4. **Click "Verify You Are Human"**
   - A browser window should open automatically
   - Navigate to the YouTube video page
   - If CAPTCHA appears, solve it:
     - Click "I'm not a robot" checkbox
     - Solve any puzzles/images
     - Wait for verification to complete

5. **Wait for automatic capture**
   - The modal should show "✓ Verification successful!"
   - Cookies are saved automatically
   - Blog generation retries automatically

6. **Verify cookies were saved:**
   ```powershell
   # Check if cookie file was created
   Test-Path "C:\temp\AI\AI_blog_app\backend\cookies\youtube_cookies.txt"
   
   # View cookie file (first few lines)
   Get-Content "C:\temp\AI\AI_blog_app\backend\cookies\youtube_cookies.txt" -Head 10
   ```

### Step 6: Test Retry After Solving

1. After CAPTCHA is solved and cookies saved
2. Try generating another blog from a different YouTube URL
3. It should work without showing CAPTCHA again (cookies are reused)

### Troubleshooting Local Testing

#### Browser Doesn't Open

**Error:** "Playwright not installed" or browser doesn't launch

**Solution:**
```powershell
# Reinstall Playwright
pip uninstall playwright
pip install playwright
playwright install chromium

# Verify installation
python -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); print('OK')"
```

#### CAPTCHA Modal Doesn't Appear

**Check:**
1. Open browser console (F12)
2. Look for JavaScript errors
3. Check if `bot_detection: true` is in the response

**Debug:**
```javascript
// In browser console, check response
console.log('Response:', data);
```

#### Cookies Not Saved

**Check:**
1. Verify `backend/cookies/` directory exists:
   ```powershell
   Test-Path "C:\temp\AI\AI_blog_app\backend\cookies"
   ```

2. Create directory if missing:
   ```powershell
   New-Item -ItemType Directory -Path "C:\temp\AI\AI_blog_app\backend\cookies" -Force
   ```

3. Check Django logs for errors:
   ```powershell
   Get-Content "C:\temp\AI\AI_blog_app\backend\django.log" -Tail 50
   ```

---

## Testing on AWS Elastic Beanstalk (EC2)

### Option 1: Manual Cookie Upload (Recommended)

Since Playwright requires a display server on EC2, use manual cookie upload:

#### Step 1: Export Cookies from Your Browser

**Chrome/Edge:**
1. Install extension: "Get cookies.txt LOCALLY" or "Cookie-Editor"
2. Go to YouTube and solve CAPTCHA manually
3. Export cookies in Netscape format
4. Save as `youtube_cookies.txt`

**Firefox:**
1. Install extension: "cookies.txt"
2. Go to YouTube and solve CAPTCHA manually
3. Export cookies
4. Save as `youtube_cookies.txt`

#### Step 2: Upload Cookies to S3

```powershell
# Upload to S3 bucket
aws s3 cp "C:\temp\AI\secret keys\youtube_cookies.txt" s3://elasticbeanstalk-ap-south-1-130236498315/yt_cookie.txt
```

#### Step 3: Set Environment Variables

```powershell
cd C:\temp\AI\AI_blog_app\backend
eb setenv YTDLP_COOKIES_S3_BUCKET=elasticbeanstalk-ap-south-1-130236498315
eb setenv YTDLP_COOKIES_S3_KEY=yt_cookie.txt
eb setenv YTDLP_COOKIES_PATH=/var/app/current/cookies.txt
```

#### Step 4: Deploy

```powershell
eb deploy
```

#### Step 5: Test on EB

1. Open your EB URL: `http://<your-env>.elasticbeanstalk.com/`
2. Try generating a blog
3. If bot detection occurs, cookies from S3 should be used automatically

### Option 2: Use Headless Browser (Advanced)

If you want to use Playwright on EC2, you need to:

1. **Install Xvfb (virtual display):**
   ```yaml
   # Add to .ebextensions/08_xvfb.config
   packages:
     yum:
       xorg-x11-server-Xvfb: []
   ```

2. **Modify captcha_solver.py** to use headless mode:
   ```python
   # Change headless=False to headless=True
   self.browser = self.playwright.chromium.launch(
       headless=True,  # Headless mode
       args=['--no-sandbox', '--disable-setuid-sandbox']
   )
   ```

3. **Use screenshots** to show CAPTCHA to user via web interface

**Note:** This is more complex and not recommended for production.

---

## Test Checklist

### Local Testing ✅

- [ ] Playwright installed and working
- [ ] Django server running
- [ ] Can trigger bot detection
- [ ] CAPTCHA modal appears
- [ ] Browser window opens
- [ ] Can solve CAPTCHA
- [ ] Cookies are saved
- [ ] Blog generation retries automatically
- [ ] Subsequent requests use saved cookies

### EC2 Testing ✅

- [ ] Cookies uploaded to S3
- [ ] Environment variables set
- [ ] Application deployed
- [ ] Cookies downloaded on instance
- [ ] Blog generation works with cookies
- [ ] Bot detection bypassed

---

## Expected Behavior

### First Time (No Cookies)

1. User enters YouTube URL
2. Clicks "Generate Blog"
3. YouTube detects bot → Returns error
4. Modal appears: "Verify You Are Human"
5. User clicks "Verify You Are Human"
6. Browser opens → User solves CAPTCHA
7. Cookies saved → Blog generation retries
8. Success! Blog generated

### Subsequent Times (With Cookies)

1. User enters YouTube URL
2. Clicks "Generate Blog"
3. Cookies used automatically
4. No CAPTCHA needed
5. Blog generated directly

---

## Debugging Commands

### Check Playwright Installation
```powershell
python -c "from playwright.sync_api import sync_playwright; print('OK')"
```

### Check Cookie File
```powershell
Get-Content "C:\temp\AI\AI_blog_app\backend\cookies\youtube_cookies.txt" | Select-Object -First 5
```

### Check Environment Variables
```powershell
$env:YTDLP_COOKIES_PATH
```

### View Django Logs
```powershell
Get-Content "C:\temp\AI\AI_blog_app\backend\django.log" -Tail 100
```

### Test CAPTCHA Solver Directly
```powershell
cd C:\temp\AI\AI_blog_app\backend
python -c "from config.captcha_solver import solve_youtube_captcha; result = solve_youtube_captcha('https://www.youtube.com/watch?v=skMzCAga-dg'); print(result)"
```

---

## Common Issues

### Issue: "Playwright not installed"

**Solution:**
```powershell
pip install playwright
playwright install chromium
```

### Issue: "Browser doesn't open"

**Check:**
- Antivirus blocking browser launch
- Windows Defender blocking
- Permissions issue

**Solution:**
- Add exception in antivirus
- Run PowerShell as Administrator
- Check Windows Event Viewer for errors

### Issue: "Cookies not saved"

**Check:**
- Directory permissions
- Disk space
- File path correct

**Solution:**
```powershell
# Create directory with proper permissions
New-Item -ItemType Directory -Path "C:\temp\AI\AI_blog_app\backend\cookies" -Force
```

### Issue: "CAPTCHA solved but blog still fails"

**Check:**
- Cookies format (must be Netscape format)
- Cookie expiration
- Cookie domain matches YouTube

**Solution:**
- Verify cookie file format
- Re-export cookies if expired
- Check cookie domain is `.youtube.com` or `youtube.com`

---

## Next Steps

After successful local testing:

1. **Deploy to EB** with manual cookie upload method
2. **Test on production** URL
3. **Monitor logs** for any issues
4. **Update cookies** periodically (they expire)

For questions or issues, check:
- `CAPTCHA_SOLVING_GUIDE.md` - Full documentation
- Django logs: `backend/django.log`
- Browser console (F12) for frontend errors
