"""
YouTube Video Transcription and Blog Generation Module
"""
import os
import tempfile
import re
import logging
from typing import Dict, Optional
from urllib.parse import urlparse, parse_qs

# Set up logging
logger = logging.getLogger(__name__)

# Import required packages with error handling
try:
    import yt_dlp
except ImportError:
    yt_dlp = None
    print("Warning: yt-dlp not installed. Install with: pip install yt-dlp")

try:
    from google.cloud import speech
    from google.oauth2 import service_account
except ImportError:
    speech = None
    service_account = None
    print("Warning: google-cloud-speech not installed. Install with: pip install google-cloud-speech")

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None
    print("Warning: openai not installed. Install with: pip install openai")

# Free alternatives
# Whisper import - will be imported dynamically when needed
# This avoids import errors at module load time
whisper_module_available = False
try:
    import whisper
    if hasattr(whisper, 'load_model'):
        whisper_module_available = True
except:
    whisper_module_available = False

try:
    import requests
except ImportError:
    requests = None
    print("Warning: requests not installed. Install with: pip install requests")

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound, VideoUnavailable
    YOUTUBE_TRANSCRIPT_AVAILABLE = True
except ImportError:
    YouTubeTranscriptApi = None
    TranscriptsDisabled = None
    NoTranscriptFound = None
    VideoUnavailable = None
    YOUTUBE_TRANSCRIPT_AVAILABLE = False
    print("Warning: youtube-transcript-api not installed. Install with: pip install youtube-transcript-api")

try:
    import google.genai as genai
except ImportError:
    try:
        # Fallback to deprecated package
        import google.generativeai as genai
    except ImportError:
        genai = None
        print("Warning: google-genai not installed. Install with: pip install google-genai (for Gemini)")

# Import CAPTCHA solver
try:
    from config.captcha_solver import YouTubeCaptchaSolver, solve_youtube_captcha
    CAPTCHA_SOLVER_AVAILABLE = True
except ImportError:
    CAPTCHA_SOLVER_AVAILABLE = False
    logger.warning("CAPTCHA solver not available")


class BotDetectionError(Exception):
    """Raised when YouTube bot detection is triggered"""
    def __init__(self, message: str, youtube_url: str):
        super().__init__(message)
        self.youtube_url = youtube_url


class YouTubeBlogGenerator:
    """Generate blog posts from YouTube videos"""
    
    def __init__(self):
        """Initialize with API credentials from environment variables"""
        # OpenAI API key for blog generation (optional - paid)
        self.openai_api_key = os.environ.get('OPENAI_API_KEY', '')
        
        # Google Cloud Speech-to-Text credentials (optional - paid)
        self.google_credentials_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', '')
        
        # FREE APIs - Groq (free tier, very fast)
        # Try to read from file first (local development), then environment variable (production)
        self.groq_api_key = ''
        
        # Check for file-based key (Windows local development)
        groq_key_file = r'C:\temp\AI\secret keys\groq_api_key.txt'
        if os.path.exists(groq_key_file):
            try:
                with open(groq_key_file, 'r', encoding='utf-8') as f:
                    self.groq_api_key = f.read().strip()
                logger.info(f"Groq API key loaded from file: {groq_key_file}")
            except Exception as e:
                logger.warning(f"Could not read Groq API key from file: {e}")
        
        # Fallback to environment variable (works on EC2/cloud)
        if not self.groq_api_key:
            self.groq_api_key = os.environ.get('GROQ_API_KEY', '')
            if self.groq_api_key:
                logger.info("Groq API key loaded from environment variable")
        
        # FREE APIs - Google Gemini (free tier)
        self.gemini_api_key = os.environ.get('GEMINI_API_KEY', '')
        
        # FREE APIs - AssemblyAI (free tier: 5 hours/month)
        # Try to read from file first (local development), then environment variable (production)
        self.assemblyai_api_key = ''
        
        # Check for file-based key (Windows local development)
        assemblyai_key_file = r'C:\temp\AI\secret keys\assemblyAI_key.txt'
        if os.path.exists(assemblyai_key_file):
            try:
                with open(assemblyai_key_file, 'r', encoding='utf-8') as f:
                    raw_key = f.read().strip()
                if '=' in raw_key:
                    raw_key = raw_key.split('=', 1)[1].strip()
                if raw_key.startswith('"') and raw_key.endswith('"'):
                    raw_key = raw_key[1:-1]
                self.assemblyai_api_key = raw_key.strip()
                logger.info(f"AssemblyAI API key loaded from file: {assemblyai_key_file}")
            except Exception as e:
                logger.warning(f"Could not read AssemblyAI API key from file: {e}")
        
        # Fallback to environment variable (works on EC2/cloud)
        if not self.assemblyai_api_key:
            raw_env_key = os.environ.get('ASSEMBLYAI_API_KEY', '')
            if raw_env_key:
                if '=' in raw_env_key:
                    raw_env_key = raw_env_key.split('=', 1)[1].strip()
                if raw_env_key.startswith('"') and raw_env_key.endswith('"'):
                    raw_env_key = raw_env_key[1:-1]
                self.assemblyai_api_key = raw_env_key.strip()
                logger.info("AssemblyAI API key loaded from environment variable")
        
        # FREE APIs - Deepgram (free tier available)
        self.deepgram_api_key = os.environ.get('DEEPGRAM_API_KEY', '')

        # Transcription provider selection
        # Options: "auto" (default), "whisper", "assemblyai", "deepgram"
        self.transcription_provider = os.environ.get('TRANSCRIPTION_PROVIDER', 'auto').strip().lower()
        if self.transcription_provider not in {'auto', 'whisper', 'assemblyai', 'deepgram'}:
            logger.warning(
                "Invalid TRANSCRIPTION_PROVIDER '%s'. Falling back to 'auto'.",
                self.transcription_provider,
            )
            self.transcription_provider = 'auto'
        
        # Initialize OpenAI client if API key is available
        self.openai_client = None
        if self.openai_api_key and OpenAI:
            try:
                self.openai_client = OpenAI(api_key=self.openai_api_key)
            except Exception as e:
                print(f"Warning: Could not initialize OpenAI client: {e}")
        
        # Initialize Groq client (FREE alternative)
        self.groq_client = None
        if self.groq_api_key and OpenAI:  # Groq uses OpenAI-compatible API
            try:
                self.groq_client = OpenAI(
                    api_key=self.groq_api_key,
                    base_url="https://api.groq.com/openai/v1"
                )
            except Exception as e:
                print(f"Warning: Could not initialize Groq client: {e}")
        
        # Initialize Gemini client (FREE alternative)
        self.gemini_client = None
        if self.gemini_api_key and genai:
            try:
                # Try new API first
                if hasattr(genai, 'Client'):
                    self.gemini_client = genai.Client(api_key=self.gemini_api_key)
                else:
                    # Fallback to deprecated API
                    genai.configure(api_key=self.gemini_api_key)
                    self.gemini_client = genai.GenerativeModel('gemini-pro')
            except Exception as e:
                print(f"Warning: Could not initialize Gemini client: {e}")
        
        # Initialize Google Speech client if credentials are available
        self.speech_client = None
        if self.google_credentials_path and os.path.exists(self.google_credentials_path) and speech and service_account:
            try:
                credentials = service_account.Credentials.from_service_account_file(
                    self.google_credentials_path
                )
                self.speech_client = speech.SpeechClient(credentials=credentials)
            except Exception as e:
                print(f"Warning: Could not initialize Google Speech client: {e}")
    
    def extract_video_id(self, youtube_url: str) -> Optional[str]:
        """Extract video ID from YouTube URL"""
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com\/watch\?.*v=([a-zA-Z0-9_-]{11})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, youtube_url)
            if match:
                return match.group(1)
        return None

    def _get_yt_dlp_cookiefile(self) -> tuple[Optional[str], bool]:
        """Return cookie file path and whether it should be deleted after use."""
        cookie_path = os.environ.get('YTDLP_COOKIES_PATH', '').strip()
        if cookie_path:
            if os.path.exists(cookie_path):
                file_size = os.path.getsize(cookie_path)
                logger.info(f"Using yt-dlp cookies from file path: {cookie_path} (size: {file_size} bytes)")
                return cookie_path, False
            else:
                logger.warning(f"YTDLP_COOKIES_PATH set to {cookie_path} but file does not exist!")
        else:
            logger.debug("YTDLP_COOKIES_PATH not set")

        cookies_b64 = os.environ.get('YTDLP_COOKIES_B64', '').strip()
        if cookies_b64:
            import base64
            try:
                content = base64.b64decode(cookies_b64).decode('utf-8')
                temp_dir = tempfile.mkdtemp()
                temp_cookie_path = os.path.join(temp_dir, 'yt_cookies.txt')
                with open(temp_cookie_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                logger.info("Using yt-dlp cookies from base64 env var.")
                return temp_cookie_path, True
            except Exception as e:
                logger.warning(f"Failed to decode YTDLP_COOKIES_B64: {e}")

        return None, False
    
    def get_video_info(self, youtube_url: str) -> Dict[str, str]:
        """Get video information (title, channel, duration) from YouTube"""
        if not yt_dlp:
            print("Error: yt-dlp is not installed. Please install it with: pip install yt-dlp")
            return {}
        
        video_id = self.extract_video_id(youtube_url)
        if not video_id:
            return {}
        
        cookiefile, delete_cookie = self._get_yt_dlp_cookiefile()
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                # Bypass YouTube bot detection
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'web'],  # Use Android client (less bot detection)
                    }
                },
            }
            if cookiefile:
                ydl_opts['cookiefile'] = cookiefile
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=False)
                
                return {
                    'title': info.get('title', ''),
                    'channel': info.get('uploader', ''),
                    'duration': self._format_duration(info.get('duration', 0)),
                    'description': info.get('description', '')[:500],  # First 500 chars
                }
        except Exception as e:
            error_msg = str(e)
            # Check if this is a bot detection error
            if 'Sign in to confirm you\'re not a bot' in error_msg or 'bot' in error_msg.lower():
                logger.warning(f"Bot detection triggered: {error_msg}")
                raise BotDetectionError(f"YouTube bot detection triggered: {error_msg}", youtube_url)
            print(f"Error getting video info: {e}")
            return {}
        finally:
            if cookiefile and delete_cookie:
                try:
                    os.remove(cookiefile)
                except Exception:
                    pass
    
    def _format_duration(self, seconds: int) -> str:
        """Format duration in seconds to MM:SS or HH:MM:SS"""
        if not seconds:
            return "0:00"
        
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"
    
    def get_youtube_transcript(self, youtube_url: str) -> Optional[str]:
        """
        Fetch transcript directly from YouTube using youtube-transcript-api.
        This avoids bot detection and cookie issues - works like youtube-transcript.io!
        Returns the transcript text or None if not available.
        """
        if not YOUTUBE_TRANSCRIPT_AVAILABLE or not YouTubeTranscriptApi:
            logger.warning("youtube-transcript-api not available. Install with: pip install youtube-transcript-api")
            return None
        
        video_id = self.extract_video_id(youtube_url)
        if not video_id:
            logger.error(f"Could not extract video ID from URL: {youtube_url}")
            return None
        
        try:
            logger.info(f"Fetching YouTube transcript directly for video ID: {video_id}")
            # Create instance and fetch transcript
            api = YouTubeTranscriptApi()
            transcript = api.fetch(
                video_id,
                languages=['en', 'en-US', 'en-GB']  # Try English variants first
            )
            
            # Combine all transcript entries into a single text
            # transcript is iterable and contains snippets with .text attribute
            transcript_text = ' '.join([snippet.text for snippet in transcript])
            logger.info(f"Successfully fetched YouTube transcript ({len(transcript)} entries, {len(transcript_text)} chars)")
            return transcript_text
            
        except TranscriptsDisabled:
            logger.warning(f"Transcripts are disabled for video {video_id}")
            return None
        except NoTranscriptFound:
            logger.warning(f"No transcript found for video {video_id}. Video may not have auto-generated transcripts.")
            return None
        except VideoUnavailable:
            logger.error(f"Video {video_id} is unavailable")
            return None
        except Exception as e:
            logger.error(f"Error fetching YouTube transcript: {e}")
            return None
    
    def download_audio(self, youtube_url: str) -> Optional[str]:
        """Download audio from YouTube video and return temporary file path"""
        if not yt_dlp:
            print("Error: yt-dlp is not installed. Please install it with: pip install yt-dlp")
            return None
        cookiefile, delete_cookie = self._get_yt_dlp_cookiefile()
        try:
            # Create temporary directory for audio
            temp_dir = tempfile.mkdtemp()
            temp_filename = 'audio'
            
            # Check if FFmpeg is available
            import shutil
            import subprocess
            
            # Try multiple methods to find FFmpeg and ffprobe
            ffmpeg_available = False
            ffmpeg_path = None
            ffprobe_path = None
            
            # Method 1: Check PATH
            ffmpeg_path = shutil.which('ffmpeg')
            ffprobe_path = shutil.which('ffprobe')
            if ffmpeg_path and ffprobe_path:
                ffmpeg_available = True
                logger.info(f"FFmpeg found in PATH: {ffmpeg_path}")
            else:
                # Method 2: Check common installation locations on Windows
                common_paths = [
                    r'C:\ffmpeg\bin\ffmpeg.exe',
                    r'C:\Program Files\ffmpeg\bin\ffmpeg.exe',
                    r'C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe',
                    os.path.expanduser(r'~\ffmpeg\bin\ffmpeg.exe'),
                    r'C:\tools\ffmpeg\bin\ffmpeg.exe',
                    # WinGet Links location (common for WinGet installations)
                    os.path.expanduser(r'~\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe'),
                ]
                
                # Also search WindowsApps (Windows Store apps that bundle FFmpeg)
                try:
                    import glob
                    windowsapps_pattern = r'C:\Program Files\WindowsApps\*\*\*\ffmpeg.exe'
                    windowsapps_matches = glob.glob(windowsapps_pattern)
                    if windowsapps_matches:
                        common_paths.extend(windowsapps_matches[:3])  # Limit to first 3 matches
                except:
                    pass
                
                for path in common_paths:
                    if os.path.exists(path):
                        # Check if ffprobe exists in the same directory
                        probe_path = path.replace('ffmpeg.exe', 'ffprobe.exe')
                        if os.path.exists(probe_path):
                            ffmpeg_path = path
                            ffprobe_path = probe_path
                            ffmpeg_available = True
                            logger.info(f"FFmpeg found at: {ffmpeg_path}")
                            logger.info(f"FFprobe found at: {ffprobe_path}")
                            break
                        # Also check bin directory
                        bin_dir = os.path.dirname(path)
                        probe_path2 = os.path.join(bin_dir, 'ffprobe.exe')
                        if os.path.exists(probe_path2):
                            ffmpeg_path = path
                            ffprobe_path = probe_path2
                            ffmpeg_available = True
                            logger.info(f"FFmpeg found at: {ffmpeg_path}")
                            logger.info(f"FFprobe found at: {ffprobe_path}")
                            break
            
            if not ffmpeg_available:
                logger.warning("FFmpeg/ffprobe not found. Audio will be downloaded in original format.")
                logger.warning("To enable WAV conversion, install FFmpeg: choco install ffmpeg OR winget install ffmpeg")
            
            # Redirect stdout/stderr to avoid Windows encoding issues in Django
            import sys
            
            # Create a null output stream for yt-dlp
            class NullWriter:
                def write(self, s):
                    pass
                def flush(self):
                    pass
                def isatty(self):
                    return False
            
            null_writer = NullWriter()
            
            # Prepare yt-dlp options
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(temp_dir, f'{temp_filename}.%(ext)s'),
                'quiet': True,  # Suppress output to avoid Windows encoding issues
                'no_warnings': True,
                'noprogress': True,
                # Bypass YouTube bot detection
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'web'],  # Use Android client (less bot detection)
                    }
                },
            }
            if cookiefile:
                ydl_opts['cookiefile'] = cookiefile
            
            # If FFmpeg is available, add post-processing and location
            if ffmpeg_available and ffmpeg_path and ffprobe_path:
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'wav',
                    'preferredquality': '192',
                }]
                
                # Set FFmpeg location (yt-dlp needs the directory containing ffmpeg.exe and ffprobe.exe)
                ffmpeg_dir = os.path.dirname(ffmpeg_path)
                ydl_opts['ffmpeg_location'] = ffmpeg_dir
                logger.info(f"Using FFmpeg from directory: {ffmpeg_dir}")
                logger.info(f"  FFmpeg: {ffmpeg_path}")
                logger.info(f"  FFprobe: {ffprobe_path}")
            elif ffmpeg_available and shutil.which('ffmpeg') and shutil.which('ffprobe'):
                # FFmpeg is in PATH
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'wav',
                    'preferredquality': '192',
                }]
                logger.info("Using FFmpeg from PATH")
            else:
                # FFmpeg not available, download without conversion
                logger.info("FFmpeg/ffprobe not available, downloading in original format")
            
            # Temporarily redirect stdout/stderr to avoid Windows encoding errors
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            try:
                sys.stdout = null_writer
                sys.stderr = null_writer
                
                logger.info(f"Downloading audio to: {temp_dir}")
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([youtube_url])
            finally:
                # Restore stdout/stderr
                sys.stdout = old_stdout
                sys.stderr = old_stderr
            
            # Find the downloaded file
            audio_file = None
            base_path = os.path.join(temp_dir, temp_filename)
            
            # Check for various possible extensions (WAV first if FFmpeg was used)
            extensions = ['.wav', '.webm', '.m4a', '.mp3', '.opus', '.ogg']
            for ext in extensions:
                test_path = base_path + ext
                if os.path.exists(test_path):
                    audio_file = test_path
                    print(f"Found audio file: {audio_file}")
                    break
            
            # If not found, search in temp directory
            if not audio_file:
                for file in os.listdir(temp_dir):
                    file_path = os.path.join(temp_dir, file)
                    if os.path.isfile(file_path) and file.startswith(temp_filename):
                        audio_file = file_path
                        print(f"Found audio file (alternative): {audio_file}")
                        break
            
            if not audio_file or not os.path.exists(audio_file):
                print(f"Error: Could not find downloaded audio file in {temp_dir}")
                if os.path.exists(temp_dir):
                    print(f"Files in directory: {os.listdir(temp_dir)}")
                else:
                    print("Directory not found")
                return None
            
            return audio_file
            
        except Exception as e:
            error_msg = str(e)
            # Check if this is a bot detection error
            if 'Sign in to confirm you\'re not a bot' in error_msg or 'bot' in error_msg.lower():
                logger.warning(f"Bot detection triggered during audio download: {error_msg}")
                raise BotDetectionError(f"YouTube bot detection triggered: {error_msg}", youtube_url)
            
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"Exception in download_audio: {str(e)}\n{error_trace}")
            print(f"Error downloading audio: {e}")
            traceback.print_exc()
            return None
        finally:
            if cookiefile and delete_cookie:
                try:
                    os.remove(cookiefile)
                except Exception:
                    pass
    
    def transcribe_audio(self, audio_file_path: str) -> Optional[str]:
        """Transcribe audio file using Google Speech-to-Text"""
        if not self.speech_client or not speech:
            return None
        
        try:
            # Read audio file
            with open(audio_file_path, 'rb') as audio_file:
                content = audio_file.read()
            
            # Configure recognition
            audio = speech.RecognitionAudio(content=content)
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                language_code='en-US',
                enable_automatic_punctuation=True,
                enable_word_time_offsets=False,
            )
            
            # Perform transcription
            response = self.speech_client.recognize(config=config, audio=audio)
            
            # Combine all transcripts
            transcript = ' '.join([result.alternatives[0].transcript 
                                  for result in response.results])
            
            return transcript
            
        except Exception as e:
            print(f"Error transcribing audio: {e}")
            return None
    
    def transcribe_audio_local_whisper(self, audio_file_path: str) -> Optional[str]:
        """Transcribe audio using LOCAL Whisper (100% FREE, no API needed)"""
        # Try to import whisper dynamically
        try:
            import whisper as whisper_module
            if not hasattr(whisper_module, 'load_model'):
                logger.error("Whisper module doesn't have load_model function")
                return None
        except ImportError:
            logger.warning("Whisper not available. Install with: pip install openai-whisper")
            return None
        except Exception as e:
            logger.error(f"Error importing Whisper: {e}")
            return None
        
        try:
            # Whisper uses FFmpeg internally via subprocess
            # We need to ensure FFmpeg is accessible to Whisper
            import os
            import shutil
            
            # Find FFmpeg for Whisper
            ffmpeg_for_whisper = None
            
            # Check PATH first
            ffmpeg_path = shutil.which('ffmpeg')
            if ffmpeg_path:
                ffmpeg_for_whisper = ffmpeg_path
                logger.info(f"Whisper will use FFmpeg from PATH: {ffmpeg_for_whisper}")
            else:
                # Check common locations (same as download_audio uses)
                common_paths = [
                    r'C:\ffmpeg\bin\ffmpeg.exe',
                    r'C:\Program Files\ffmpeg\bin\ffmpeg.exe',
                    r'C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe',
                    os.path.expanduser(r'~\ffmpeg\bin\ffmpeg.exe'),
                    r'C:\tools\ffmpeg\bin\ffmpeg.exe',
                    os.path.expanduser(r'~\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe'),
                ]
                
                # Also check WindowsApps
                try:
                    import glob
                    windowsapps_pattern = r'C:\Program Files\WindowsApps\*\*\*\ffmpeg.exe'
                    windowsapps_matches = glob.glob(windowsapps_pattern)
                    if windowsapps_matches:
                        common_paths.extend(windowsapps_matches[:3])
                except:
                    pass
                
                for path in common_paths:
                    if os.path.exists(path):
                        ffmpeg_for_whisper = path
                        ffmpeg_dir = os.path.dirname(path)
                        # Add FFmpeg directory to PATH for this process
                        current_path = os.environ.get('PATH', '')
                        if ffmpeg_dir not in current_path:
                            os.environ['PATH'] = ffmpeg_dir + os.pathsep + current_path
                            logger.info(f"Added FFmpeg directory to PATH for Whisper: {ffmpeg_dir}")
                        break
            
            if not ffmpeg_for_whisper:
                logger.error("FFmpeg not found for Whisper. Whisper requires FFmpeg to load audio files.")
                return None
            
            logger.info("Loading Whisper model (first time may take a moment)...")
            # Use 'base' model for good balance of speed and accuracy
            # Options: tiny (~75MB), base (~150MB), small (~500MB), medium (~1.5GB), large (~3GB)
            model = whisper_module.load_model("base")
            logger.info("Transcribing audio with local Whisper...")
            result = model.transcribe(audio_file_path, language="en")
            transcript_text = result.get("text", "")
            if transcript_text:
                logger.info(f"Whisper transcription completed. Length: {len(transcript_text)} characters")
            else:
                logger.warning("Whisper returned empty transcript")
            return transcript_text
        except FileNotFoundError as e:
            # This usually means FFmpeg wasn't found by Whisper's subprocess
            logger.error(f"FFmpeg not found for Whisper: {e}")
            logger.error("Whisper requires FFmpeg to be accessible via subprocess.")
            logger.error("Try restarting Django server after FFmpeg is added to system PATH")
            return None
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"Error transcribing with local Whisper: {str(e)}\n{error_trace}")
            return None
    
    def transcribe_audio_whisper_api(self, audio_file_path: str) -> Optional[str]:
        """Transcribe audio using OpenAI Whisper API (paid)"""
        if not self.openai_client:
            return None
        
        try:
            with open(audio_file_path, 'rb') as audio_file:
                transcript = self.openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="en"
                )
                return transcript.text
        except Exception as e:
            print(f"Error transcribing with Whisper API: {e}")
            return None
    
    def transcribe_audio_assemblyai(self, audio_file_path: str) -> Optional[str]:
        """Transcribe audio using AssemblyAI (FREE tier: 5 hours/month)"""
        if not self.assemblyai_api_key or not requests:
            return None
        
        try:
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry

            session = requests.Session()
            retries = Retry(
                total=3,
                backoff_factor=0.5,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["POST", "GET"],
            )
            adapter = HTTPAdapter(max_retries=retries)
            session.mount("https://", adapter)
            session.mount("http://", adapter)

            # Upload audio file
            upload_url = "https://api.assemblyai.com/v2/upload"
            headers = {
                "authorization": self.assemblyai_api_key,
                "content-type": "application/octet-stream",
            }
            
            with open(audio_file_path, 'rb') as audio_file:
                response = session.post(
                    upload_url,
                    headers=headers,
                    data=audio_file,
                    timeout=60,
                )
                if not response.ok:
                    logger.error(
                        "AssemblyAI upload failed: status=%s body=%s",
                        response.status_code,
                        response.text[:500],
                    )
                    return None
                try:
                    upload_url_response = response.json().get('upload_url')
                except ValueError:
                    logger.error(
                        "AssemblyAI upload returned non-JSON response: %s",
                        response.text[:500],
                    )
                    return None
            
            if not upload_url_response:
                logger.error("AssemblyAI upload missing upload_url.")
                return None
            
            # Start transcription
            transcript_url = "https://api.assemblyai.com/v2/transcript"
            transcript_response = session.post(
                transcript_url,
                json={"audio_url": upload_url_response},
                headers=headers,
                timeout=20,
            )
            if not transcript_response.ok:
                logger.error(
                    "AssemblyAI transcript request failed: status=%s body=%s",
                    transcript_response.status_code,
                    transcript_response.text[:500],
                )
                return None
            try:
                transcript_id = transcript_response.json().get('id')
            except ValueError:
                logger.error(
                    "AssemblyAI transcript request returned non-JSON response: %s",
                    transcript_response.text[:500],
                )
                return None
            if not transcript_id:
                logger.error("AssemblyAI transcript request missing id.")
                return None
            
            # Poll for completion
            while True:
                status_response = session.get(
                    f"{transcript_url}/{transcript_id}",
                    headers=headers,
                    timeout=20,
                )
                if not status_response.ok:
                    logger.error(
                        "AssemblyAI status poll failed: status=%s body=%s",
                        status_response.status_code,
                        status_response.text[:500],
                    )
                    return None
                try:
                    status = status_response.json().get('status')
                except ValueError:
                    logger.error(
                        "AssemblyAI status poll returned non-JSON response: %s",
                        status_response.text[:500],
                    )
                    return None
                
                if status == 'completed':
                    return status_response.json().get('text')
                elif status == 'error':
                    return None
                # Wait before polling again
                import time
                time.sleep(1)
                
        except Exception as e:
            print(f"Error transcribing with AssemblyAI: {e}")
            return None
    
    def transcribe_audio_deepgram(self, audio_file_path: str) -> Optional[str]:
        """Transcribe audio using Deepgram (FREE tier available)"""
        if not self.deepgram_api_key or not requests:
            return None
        
        try:
            url = "https://api.deepgram.com/v1/listen"
            headers = {
                "Authorization": f"Token {self.deepgram_api_key}",
            }
            
            with open(audio_file_path, 'rb') as audio_file:
                response = requests.post(url, headers=headers, files={"audio": audio_file})
                result = response.json()
                return result.get('results', {}).get('channels', [{}])[0].get('alternatives', [{}])[0].get('transcript', '')
        except Exception as e:
            print(f"Error transcribing with Deepgram: {e}")
            return None
    
    def generate_blog_post(self, transcript: str, video_info: Dict[str, str]) -> Dict[str, str]:
        """Generate blog post from transcript - tries free APIs first, then paid"""
        # Create prompt for blog generation
        prompt = f"""You are a professional blog writer. Create a well-structured, engaging blog post based on the following video transcript.

Video Title: {video_info.get('title', 'Unknown')}
Video Channel: {video_info.get('channel', 'Unknown')}

Transcript:
{transcript[:12000]}  # Limit transcript length

Please create:
1. A compelling title (max 100 characters)
2. A brief description/summary (2-3 sentences, max 200 characters)
3. A well-structured blog post with:
   - An engaging introduction
   - Clear sections with headings
   - Key points and insights
   - A conclusion

Format the response as:
TITLE: [title]
DESCRIPTION: [description]
CONTENT:
[blog post content with proper formatting, headings, paragraphs, and structure]

Make it engaging, informative, and suitable for a blog audience."""

        system_prompt = "You are a professional blog writer who creates engaging, well-structured blog posts from video transcripts."
        
        # Try FREE Groq API first (very fast, free tier)
        if self.groq_client:
            # Try models in order of preference (newest first, with fallbacks)
            groq_models = [
                "llama-3.3-70b-versatile",  # Latest model
                "llama-3.1-8b-instant",     # Fast alternative
                "mixtral-8x7b-32768",       # Alternative option
            ]
            
            for model_name in groq_models:
                try:
                    print(f"Generating blog post with Groq (FREE) using {model_name}...")
                    response = self.groq_client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt}
                        ],
                        max_tokens=3500,
                        temperature=0.7,
                    )
                    blog_text = response.choices[0].message.content or ""
                    finish_reason = getattr(response.choices[0], "finish_reason", None)
                    if finish_reason == "length":
                        continuation = self._continue_blog_post(
                            client=self.groq_client,
                            model=model_name,
                            system_prompt=system_prompt,
                            partial_text=blog_text,
                        )
                        blog_text = self._append_continuation(blog_text, continuation)
                    return self._parse_blog_response(blog_text, video_info)
                except Exception as e:
                    error_msg = str(e)
                    # If model is decommissioned or not found, try next model
                    if "decommissioned" in error_msg.lower() or "not found" in error_msg.lower() or "invalid" in error_msg.lower():
                        print(f"Groq model {model_name} not available: {e}, trying next model...")
                        continue
                    else:
                        # Other errors (rate limit, etc.) - try next option entirely
                        print(f"Groq API error: {e}, trying next option...")
                        break
        
        # Try FREE Gemini API
        if self.gemini_client:
            try:
                print("Generating blog post with Google Gemini (FREE)...")
                # Handle both new and old API
                if hasattr(self.gemini_client, 'models'):
                    # New API
                    model = self.gemini_client.models.generate_content(
                        model='gemini-pro',
                        contents=prompt
                    )
                    blog_text = model.text
                else:
                    # Old API
                    response = self.gemini_client.generate_content(prompt)
                    blog_text = response.text
                return self._parse_blog_response(blog_text, video_info)
            except Exception as e:
                print(f"Gemini API error: {e}, trying next option...")
        
        # Try OpenAI (paid, but better quality)
        if self.openai_client:
            try:
                print("Generating blog post with OpenAI...")
                response = self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=3500,
                    temperature=0.7,
                )
                blog_text = response.choices[0].message.content or ""
                finish_reason = getattr(response.choices[0], "finish_reason", None)
                if finish_reason == "length":
                    continuation = self._continue_blog_post(
                        client=self.openai_client,
                        model="gpt-3.5-turbo",
                        system_prompt=system_prompt,
                        partial_text=blog_text,
                    )
                    blog_text = self._append_continuation(blog_text, continuation)
                return self._parse_blog_response(blog_text, video_info)
            except Exception as e:
                print(f"OpenAI API error: {e}")
        
        # Fallback: return transcript as content
        return {
            'title': video_info.get('title', 'Blog Post'),
            'description': 'A blog post generated from a YouTube video.',
            'content': transcript if transcript else 'Content generation requires an API key. Please set up Groq, Gemini, or OpenAI API.',
        }
    
    def _parse_blog_response(self, blog_text: str, video_info: Dict[str, str]) -> Dict[str, str]:
        """Parse blog generation response"""
        title_match = re.search(r'TITLE:\s*(.+?)(?:\n|DESCRIPTION:)', blog_text, re.IGNORECASE)
        desc_match = re.search(r'DESCRIPTION:\s*(.+?)(?:\n|CONTENT:)', blog_text, re.IGNORECASE)
        content_match = re.search(r'CONTENT:\s*(.+?)$', blog_text, re.IGNORECASE | re.DOTALL)
        
        title = title_match.group(1).strip() if title_match else video_info.get('title', 'Blog Post')
        description = desc_match.group(1).strip() if desc_match else 'A blog post generated from a YouTube video.'
        content = content_match.group(1).strip() if content_match else blog_text
        
        return {
            'title': title,
            'description': description,
            'content': content,
        }

    def _continue_blog_post(self, client, model: str, system_prompt: str, partial_text: str) -> Optional[str]:
        """Request a continuation when the model output was cut off."""
        try:
            continuation_prompt = (
                "The response was cut off. Continue ONLY the blog post content from the last sentence. "
                "Do NOT repeat the title or description. Continue in the same style.\n\n"
                "Partial response:\n"
                f"{partial_text}\n\n"
                "CONTINUATION:"
            )
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": continuation_prompt},
                ],
                max_tokens=1500,
                temperature=0.7,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.warning(f"Continuation generation failed: {e}")
            return None

    def _append_continuation(self, blog_text: str, continuation: Optional[str]) -> str:
        """Append continuation text if present."""
        if not continuation:
            return blog_text
        return f"{blog_text}\n{continuation.strip()}"
    
    def process_youtube_video(self, youtube_url: str) -> Dict[str, any]:
        """Complete pipeline: Get transcript and generate blog post"""
        result = {
            'success': False,
            'error': None,
            'video_info': {},
            'transcript': None,
            'blog_post': {},
        }
        
        try:
            # Step 1: Get video information
            print("Fetching video information...")
            video_info = self.get_video_info(youtube_url)
            result['video_info'] = video_info
            
            if not video_info:
                result['error'] = 'Could not fetch video information. Please check the URL.'
                return result
            
            # Step 2: Try to get transcript directly from YouTube (FASTEST, NO COOKIES NEEDED!)
            print("Fetching transcript directly from YouTube...")
            transcript = self.get_youtube_transcript(youtube_url)
            
            # Step 3: If direct transcript failed, fall back to audio download + transcription
            audio_file = None
            if not transcript:
                logger.info("Direct transcript not available, falling back to audio download + transcription")
                print("Downloading audio...")
                audio_file = self.download_audio(youtube_url)
                
                if not audio_file:
                    error_msg = 'Could not download audio from video. Check Django logs for details.'
                    logger.error(f"Audio download failed for URL: {youtube_url}")
                    result['error'] = error_msg
                    return result
                
                try:
                    # Step 3: Transcribe audio
                    logger.info("Transcribing audio... provider=%s", self.transcription_provider)

                    if self.transcription_provider == 'whisper':
                        logger.info("Using local Whisper (forced)...")
                        transcript = self.transcribe_audio_local_whisper(audio_file)
                    elif self.transcription_provider == 'assemblyai':
                        logger.info("Using AssemblyAI (forced)...")
                        transcript = self.transcribe_audio_assemblyai(audio_file)
                    elif self.transcription_provider == 'deepgram':
                        logger.info("Using Deepgram (forced)...")
                        transcript = self.transcribe_audio_deepgram(audio_file)
                    else:
                        # auto: try free options in order
                        try:
                            logger.info("Trying local Whisper (FREE, no API needed)...")
                            transcript = self.transcribe_audio_local_whisper(audio_file)
                            if transcript:
                                logger.info("Whisper transcription successful. Length: %s characters", len(transcript))
                            else:
                                logger.warning("Whisper transcription returned empty result")
                        except Exception as e:
                            logger.error(f"Error trying Whisper: {e}", exc_info=True)

                        if not transcript and self.assemblyai_api_key:
                            print("Trying AssemblyAI (FREE tier)...")
                            transcript = self.transcribe_audio_assemblyai(audio_file)

                        if not transcript and self.deepgram_api_key:
                            print("Trying Deepgram (FREE tier)...")
                            transcript = self.transcribe_audio_deepgram(audio_file)
                    
                    # Priority 4: Google Speech-to-Text (paid, but first 60 min/month free)
                    if not transcript and self.speech_client:
                        print("Trying Google Speech-to-Text...")
                        transcript = self.transcribe_audio(audio_file)
                    
                    # Priority 5: OpenAI Whisper API (paid)
                    if not transcript and self.openai_client:
                        print("Trying OpenAI Whisper API...")
                        transcript = self.transcribe_audio_whisper_api(audio_file)
                finally:
                    # Clean up temporary audio file
                    if audio_file and os.path.exists(audio_file):
                        try:
                            os.unlink(audio_file)
                        except:
                            pass
            
            # Step 4: Check if we have a transcript
            if not transcript:
                result['error'] = 'Could not get transcript. Video may not have auto-generated transcripts, or transcription services are unavailable.'
                return result
            
            result['transcript'] = transcript
            
            # Step 5: Generate blog post
            print("Generating blog post...")
            blog_post = self.generate_blog_post(transcript, video_info)
            result['blog_post'] = blog_post
            
            result['success'] = True
            
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            error_msg = f'Error processing video: {str(e)}'
            logger.error(f"Exception in process_youtube_video: {error_msg}\n{error_trace}")
            result['error'] = error_msg
            print(f"Error: {e}")
        
        return result


# Convenience function for Django views
def generate_blog_from_youtube(youtube_url: str) -> Dict[str, any]:
    """Convenience function to generate blog from YouTube URL"""
    generator = YouTubeBlogGenerator()
    return generator.process_youtube_video(youtube_url)
