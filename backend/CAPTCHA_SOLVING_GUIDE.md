# YouTube CAPTCHA Solving Guide

## Overview

When YouTube detects automated access (bot detection), the app now provides an interactive CAPTCHA solving feature. A browser window opens where you can solve the CAPTCHA, and cookies are automatically captured and saved for future requests.

## How It Works

1. **Detection**: When YouTube triggers bot detection, the app detects it automatically
2. **Modal Popup**: A modal appears asking you to solve the CAPTCHA
3. **Browser Opens**: Clicking "Open Browser to Solve CAPTCHA" launches a visible browser window
4. **Solve CAPTCHA**: Solve the CAPTCHA in the browser window (click "I'm not a robot", solve puzzles, etc.)
5. **Auto-Capture**: Once solved, cookies are automatically captured and saved
6. **Retry**: The blog generation automatically retries with the new cookies

## Installation

### For Local Development (Windows)

1. Install Playwright:
   ```powershell
   pip install playwright
   playwright install chromium
   ```

2. The browser will open automatically when CAPTCHA solving is needed.

### For AWS Elastic Beanstalk

**Note**: Playwright requires a display server (X11) to run in visible mode. On EB, you have two options:

#### Option 1: Use Headless Mode with Screenshots (Recommended)

Modify `captcha_solver.py` to use headless mode and show screenshots to users via the web interface.

#### Option 2: Manual Cookie Upload

If Playwright is not available on EB, users can:
1. Solve CAPTCHA manually in their browser
2. Export cookies using a browser extension
3. Upload cookies via the web interface (to be implemented)

## Usage

1. **Generate Blog**: Try to generate a blog from a YouTube URL
2. **Bot Detection**: If YouTube detects a bot, a modal appears
3. **Solve CAPTCHA**: Click "Open Browser to Solve CAPTCHA"
4. **Wait**: A browser window opens - solve the CAPTCHA when it appears
5. **Automatic Retry**: Once solved, cookies are saved and blog generation retries automatically

## Technical Details

### Files Modified

- `config/captcha_solver.py`: Playwright-based CAPTCHA solver
- `config/blog_generator.py`: Bot detection error handling
- `config/views.py`: CAPTCHA solving endpoint
- `templates/index.html`: CAPTCHA modal UI

### Cookie Storage

Cookies are saved in Netscape format to:
- **Local**: `backend/cookies/youtube_cookies.txt`
- **Environment Variable**: `YTDLP_COOKIES_PATH` is set automatically

### Error Handling

- If Playwright is not installed, the modal shows an error message
- If CAPTCHA solving times out (5 minutes), an error is shown
- If cookies cannot be captured, an error is shown

## Troubleshooting

### Browser Doesn't Open

- **Check Playwright Installation**: Run `playwright install chromium`
- **Check Permissions**: Ensure the app has permission to launch browsers
- **Windows**: Some antivirus software may block browser launches

### CAPTCHA Not Detected

- The solver waits for common CAPTCHA indicators
- If CAPTCHA appears but isn't detected, try solving it manually and the cookies will still be captured when the video page loads

### Cookies Not Saved

- Check file permissions in `backend/cookies/` directory
- Check Django logs for errors
- Ensure `YTDLP_COOKIES_PATH` environment variable is set correctly

## Future Improvements

1. **Headless Mode Support**: For servers without display (EB)
2. **Cookie Upload UI**: Manual cookie upload interface
3. **Cookie Management**: View/edit/delete saved cookies
4. **Multiple Cookie Sets**: Support for multiple YouTube accounts
