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

## Common Issues

- **YouTube bot detection**: If YouTube blocks downloads, see `backend\YOUTUBE_BOT_DETECTION_FIX.md`.
- **FFmpeg missing**: For local audio conversion, install FFmpeg (see `backend\INSTALL_FFMPEG.md`).
- **API keys**: For free APIs, see `backend\FREE_API_SETUP.md`.

