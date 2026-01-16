import os
import time
import requests


def load_api_key():
    key_path = r"C:\temp\AI\secret keys\assemblyAI_key.txt"
    if os.path.exists(key_path):
        with open(key_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    return os.environ.get("ASSEMBLYAI_API_KEY", "").strip()


def main():
    api_key = load_api_key()
    if not api_key:
        print("AssemblyAI API key not found.")
        return

    audio_path = input("Enter path to audio file (wav/mp3/m4a): ").strip('"').strip()
    if not os.path.exists(audio_path):
        print(f"File not found: {audio_path}")
        return

    session = requests.Session()
    headers = {"authorization": api_key}

    print("Uploading audio...")
    with open(audio_path, "rb") as f:
        upload_resp = session.post(
            "https://api.assemblyai.com/v2/upload",
            headers=headers,
            files={"file": f},
            timeout=60,
        )
    if not upload_resp.ok:
        print("Upload failed:", upload_resp.status_code, upload_resp.text[:500])
        return
    try:
        upload_url = upload_resp.json().get("upload_url")
    except ValueError:
        print("Upload returned non-JSON:", upload_resp.text[:500])
        return
    if not upload_url:
        print("Upload missing upload_url")
        return

    print("Starting transcription...")
    transcript_resp = session.post(
        "https://api.assemblyai.com/v2/transcript",
        headers=headers,
        json={"audio_url": upload_url},
        timeout=20,
    )
    if not transcript_resp.ok:
        print("Transcript request failed:", transcript_resp.status_code, transcript_resp.text[:500])
        return
    try:
        transcript_id = transcript_resp.json().get("id")
    except ValueError:
        print("Transcript request returned non-JSON:", transcript_resp.text[:500])
        return
    if not transcript_id:
        print("Transcript request missing id")
        return

    print("Polling...")
    status_url = f"https://api.assemblyai.com/v2/transcript/{transcript_id}"
    while True:
        status_resp = session.get(status_url, headers=headers, timeout=20)
        if not status_resp.ok:
            print("Status poll failed:", status_resp.status_code, status_resp.text[:500])
            return
        try:
            data = status_resp.json()
        except ValueError:
            print("Status poll returned non-JSON:", status_resp.text[:500])
            return

        status = data.get("status")
        if status == "completed":
            text = data.get("text", "")
            print("\n=== TRANSCRIPT ===\n")
            print(text[:2000])
            print("\n=== END (truncated to 2000 chars) ===")
            return
        if status == "error":
            print("Transcription error:", data.get("error"))
            return

        time.sleep(3)


if __name__ == "__main__":
    main()
