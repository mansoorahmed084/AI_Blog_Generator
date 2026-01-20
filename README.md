# AI Blog Generator (Django)

Generate blog posts from YouTube URLs using transcription + LLMs.

## Run Locally (Windows PowerShell)

1. Create and activate a virtual environment:
   ```powershell
   cd C:\temp\AI\AI_blog_app
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. Install dependencies:
   ```powershell
   pip install -r .\backend\requirements.txt
   ```

3. Run migrations:
   ```powershell
   cd .\backend
   python manage.py migrate
   ```

4. Start the server:
   ```powershell
   python manage.py runserver
   ```

5. Open the app in your browser:
   - `http://127.0.0.1:8000/`

## Test in the Browser (Local)

1. Sign up for a new account.
2. Log in.
3. Paste a YouTube URL on the home page.
4. Click "Generate Blog" and wait for the result.
5. You should be redirected to the blog details page if successful.

## Edit and Delete Blogs

- **Edit**: Open a blog (from **My Blog Posts** or **Blog Details**) and click **Edit**. Update title/description/content/category, then **Save Changes**.
- **Delete**: From **My Blog Posts** or **Blog Details**, click **Delete** and confirm the prompt. The post is removed and you are redirected back to **My Blog Posts**.

## Transcription Provider Switch (Local vs EB)

You can force the transcription provider with an environment variable:

```powershell
# Options: auto (default), whisper, assemblyai, deepgram
$env:TRANSCRIPTION_PROVIDER = "assemblyai"
```

Examples:

- **Local Whisper** (free, local CPU):
  ```powershell
  $env:TRANSCRIPTION_PROVIDER = "whisper"
  ```
- **AssemblyAI** (recommended for EB):
  ```powershell
  $env:TRANSCRIPTION_PROVIDER = "assemblyai"
  ```

Restart `runserver` after changing the variable.

If you see an error popup, check `backend\django.log` and the terminal output.

## Test in the Browser (AWS Elastic Beanstalk)

1. Deploy latest code:
   ```powershell
   cd C:\temp\AI\AI_blog_app\backend
   eb deploy
   ```

2. Open your EB URL in the browser (example):
   - `http://<your-env>.elasticbeanstalk.com/`

3. Repeat the same steps as local testing (sign up, log in, generate blog).

To fetch logs from EB:
```powershell
cd C:\temp\AI\AI_blog_app\backend
eb logs
```

## How It Works

The app uses a **smart two-step approach** to get video transcripts:

1. **Direct YouTube Transcript API** (preferred, fastest):
   - Fetches transcripts directly from YouTube (like [youtube-transcript.io](https://www.youtube-transcript.io/))
   - **No cookies needed** - avoids bot detection entirely!
   - Works for videos with auto-generated or manual transcripts
   - Instant results (no audio download required)

2. **Audio Download + Transcription** (fallback):
   - If direct transcript isn't available, downloads audio using `yt-dlp`
   - Transcribes using free APIs (AssemblyAI, Deepgram) or local Whisper
   - Requires cookies for bot detection bypass (see `YOUTUBE_BOT_DETECTION_FIX.md`)

## CAPTCHA Solving (Bot Detection)

When YouTube detects automated access, the app provides interactive CAPTCHA solving:

1. **Modal appears** asking to verify you're human
2. **Browser opens** automatically (Playwright)
3. **Solve CAPTCHA** in the browser window
4. **Cookies captured** automatically
5. **Blog generation retries** with saved cookies

**Testing:** See `backend\TESTING_CAPTCHA_SOLVING.md` for detailed local and EC2 testing instructions.

**Installation (Local):**
```powershell
pip install playwright
playwright install chromium
```

## Common Issues

- **YouTube bot detection**: The app now tries direct transcript API first (no cookies needed!). If that fails and audio download is needed, see `backend\YOUTUBE_BOT_DETECTION_FIX.md` or use the CAPTCHA solving feature.
- **CAPTCHA solving**: See `backend\TESTING_CAPTCHA_SOLVING.md` for testing instructions.
- **No transcript available**: Some videos don't have transcripts. The app will automatically fall back to audio download + transcription.
- **FFmpeg missing**: For local audio conversion, install FFmpeg (see `backend\INSTALL_FFMPEG.md`).
- **API keys**: For free APIs, see `backend\FREE_API_SETUP.md`.

