"""
Views for the AI Blog Generator application
"""
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .models import BlogPost
from .blog_generator import generate_blog_from_youtube
import os
import shutil

# Try to import CAPTCHA solver (may not be available)
try:
    from .blog_generator import BotDetectionError
    from .captcha_solver import solve_youtube_captcha, CAPTCHA_SOLVER_AVAILABLE
except ImportError:
    BotDetectionError = Exception  # Fallback
    CAPTCHA_SOLVER_AVAILABLE = False
    def solve_youtube_captcha(*args, **kwargs):
        return False, None, "CAPTCHA solver not available"

# Set up logging
logger = logging.getLogger(__name__)


def index(request):
    """Serve the main index.html page"""
    return render(request, 'index.html')


def login_view(request):
    """Handle login page display and authentication"""
    # Redirect if already logged in
    if request.user.is_authenticated:
        return redirect('index')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        if username and password:
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back, {username}!')
                return redirect('index')
            else:
                messages.error(request, 'Invalid username or password.')
        else:
            messages.error(request, 'Please fill in all fields.')
    
    return render(request, 'login.html')


def logout_view(request):
    """Handle user logout"""
    # Clear all existing messages before logout by consuming them
    list(messages.get_messages(request))  # Consume all existing messages
    
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('login')


def signup_view(request):
    """Handle signup page display and user registration"""
    # Redirect if already logged in
    if request.user.is_authenticated:
        return redirect('index')
    
    errors = {}
    form_data = {}
    
    if request.method == 'POST':
        # Get form data
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        repeat_password = request.POST.get('repeatPassword', '')
        
        # Store form data to repopulate form on error
        form_data = {
            'username': username,
            'email': email,
        }
        
        # Validation
        if not username:
            errors['username'] = 'Username is required.'
        elif len(username) < 3:
            errors['username'] = 'Username must be at least 3 characters long.'
        elif User.objects.filter(username=username).exists():
            errors['username'] = 'Username already exists. Please choose another.'
        
        if not email:
            errors['email'] = 'Email is required.'
        elif '@' not in email or '.' not in email:
            errors['email'] = 'Please enter a valid email address.'
        elif User.objects.filter(email=email).exists():
            errors['email'] = 'Email already registered. Please use another email.'
        
        if not password:
            errors['password'] = 'Password is required.'
        elif len(password) < 6:
            errors['password'] = 'Password must be at least 6 characters long.'
        
        if not repeat_password:
            errors['repeatPassword'] = 'Please confirm your password.'
        elif password != repeat_password:
            errors['repeatPassword'] = 'Passwords do not match.'
        
        # If no errors, create user and log them in
        if not errors:
            try:
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password
                )
                # Automatically log in the user
                login(request, user)
                messages.success(request, f'Account created successfully! Welcome, {username}!')
                return redirect('index')
            except Exception as e:
                errors['general'] = f'An error occurred during registration: {str(e)}'
    
    # Render template with errors and form data
    context = {
        'errors': errors,
        'form_data': form_data,
    }
    return render(request, 'signup.html', context)


@login_required
def all_blog_posts(request):
    """Display all blog posts for the logged-in user"""
    blog_posts = BlogPost.objects.filter(author=request.user)
    context = {
        'blog_posts': blog_posts,
    }
    return render(request, 'all_blog_posts.html', context)


@login_required
def blog_details(request, blog_id=None):
    """Display details of a specific blog post"""
    if blog_id:
        blog_post = get_object_or_404(BlogPost, id=blog_id, author=request.user)
    else:
        # For demo purposes, get the first blog post if no ID provided
        blog_post = BlogPost.objects.filter(author=request.user).first()
        if not blog_post:
            messages.info(request, 'No blog posts found. Create your first blog post!')
            return redirect('index')
    
    context = {
        'blog_post': blog_post,
    }
    return render(request, 'blog-details.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def edit_blog(request, blog_id):
    """Edit a blog post owned by the logged-in user"""
    blog_post = get_object_or_404(BlogPost, id=blog_id, author=request.user)
    errors = {}

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        content = request.POST.get('content', '').strip()
        category = request.POST.get('category', '').strip() or blog_post.category

        if not title:
            errors['title'] = 'Title is required.'
        if not description:
            errors['description'] = 'Description is required.'
        if not content:
            errors['content'] = 'Content is required.'

        if not errors:
            blog_post.title = title
            blog_post.description = description
            blog_post.content = content
            blog_post.category = category
            blog_post.save(update_fields=['title', 'description', 'content', 'category', 'updated_at'])
            messages.success(request, 'Blog post updated successfully.')
            return redirect('blog_details', blog_id=blog_post.id)

    context = {
        'blog_post': blog_post,
        'errors': errors,
    }
    return render(request, 'edit-blog.html', context)


@login_required
@require_http_methods(["POST"])
def delete_blog(request, blog_id):
    """Delete a blog post owned by the logged-in user"""
    blog_post = get_object_or_404(BlogPost, id=blog_id, author=request.user)
    blog_post.delete()
    messages.success(request, 'Blog post deleted successfully.')
    return redirect('all_blog_posts')


@require_http_methods(["POST"])
def generate_blog(request):
    """Generate blog post from YouTube URL"""
    # Check if user is authenticated
    if not request.user.is_authenticated:
        # For AJAX requests, return JSON error instead of redirecting
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'error': 'Please log in to generate blog posts.',
                'login_required': True,
                'login_url': '/login/?next=/generate-blog/'
            }, status=401)
        # For regular form submissions, redirect to login
        return redirect('/login/?next=/generate-blog/')
    
    youtube_url = request.POST.get('youtube_url', '').strip()
    
    if not youtube_url:
        return JsonResponse({
            'success': False,
            'error': 'Please provide a YouTube URL.'
        }, status=400)
    
    # Validate YouTube URL format
    if 'youtube.com' not in youtube_url and 'youtu.be' not in youtube_url:
        return JsonResponse({
            'success': False,
            'error': 'Please provide a valid YouTube URL.'
        }, status=400)
    
    try:
        # Generate blog post
        logger.info(f"Starting blog generation for URL: {youtube_url}")
        result = generate_blog_from_youtube(youtube_url)
        
        logger.info(f"Blog generation result: success={result.get('success')}, error={result.get('error')}")
        
        if not result['success']:
            error_msg = result.get('error', 'Failed to generate blog post.')
            logger.error(f"Blog generation failed: {error_msg}")
            return JsonResponse({
                'success': False,
                'error': error_msg
            }, status=500)
        
        # Check if blog_post data exists
        blog_post_data = result.get('blog_post', {})
        if not blog_post_data or not blog_post_data.get('title'):
            error_msg = 'Blog post generation failed. Please check your API keys (Groq/Gemini/OpenAI).'
            logger.error(f"Blog post data missing: {result}")
            return JsonResponse({
                'success': False,
                'error': error_msg
            }, status=500)
        
        # Save blog post to database
        blog_post = BlogPost.objects.create(
            title=blog_post_data.get('title', 'Untitled Blog Post'),
            description=blog_post_data.get('description', ''),
            content=blog_post_data.get('content', ''),
            youtube_url=youtube_url,
            youtube_title=result.get('video_info', {}).get('title', ''),
            youtube_channel=result.get('video_info', {}).get('channel', ''),
            youtube_duration=result.get('video_info', {}).get('duration', ''),
            author=request.user,
            category='Technology',  # Default category, can be made dynamic
        )
        
        return JsonResponse({
            'success': True,
            'blog_id': blog_post.id,
            'message': 'Blog post generated successfully!',
            'redirect_url': f'/blog-details/{blog_post.id}/'
        })
    
    except BotDetectionError as e:
        # YouTube bot detection triggered - need user to solve CAPTCHA
        logger.warning(f"Bot detection error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e),
            'bot_detection': True,
            'youtube_url': e.youtube_url,
            'captcha_solver_available': CAPTCHA_SOLVER_AVAILABLE,
            'message': 'YouTube detected automated access. Please solve the CAPTCHA to continue.'
        }, status=403)
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Exception in generate_blog view: {str(e)}\n{error_trace}")
        return JsonResponse({
            'success': False,
            'error': f'An error occurred: {str(e)}'
        }, status=500)


@login_required
def solve_captcha(request):
    """Handle CAPTCHA solving request"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST method required'}, status=405)
    
    youtube_url = request.POST.get('youtube_url', '').strip()
    if not youtube_url:
        return JsonResponse({'success': False, 'error': 'YouTube URL required'}, status=400)
    
    if not CAPTCHA_SOLVER_AVAILABLE:
        return JsonResponse({
            'success': False,
            'error': 'CAPTCHA solver not available. Please install Playwright: pip install playwright && playwright install chromium'
        }, status=503)
    
    try:
        logger.info(f"Starting CAPTCHA solving for URL: {youtube_url}")
        success, cookie_file, error_msg = solve_youtube_captcha(youtube_url, timeout=300)
        
        if success and cookie_file:
            # Copy cookie file to persistent location
            persistent_cookie_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'cookies')
            os.makedirs(persistent_cookie_dir, exist_ok=True)
            persistent_cookie_file = os.path.join(persistent_cookie_dir, 'youtube_cookies.txt')
            
            shutil.copy2(cookie_file, persistent_cookie_file)
            logger.info(f"Cookies saved to {persistent_cookie_file}")
            
            # Set environment variable for yt-dlp to use
            os.environ['YTDLP_COOKIES_PATH'] = persistent_cookie_file
            
            return JsonResponse({
                'success': True,
                'message': 'CAPTCHA solved successfully! Cookies saved. Please try generating the blog again.',
                'cookie_file': persistent_cookie_file
            })
        else:
            return JsonResponse({
                'success': False,
                'error': error_msg or 'Failed to solve CAPTCHA'
            }, status=500)
    
    except Exception as e:
        logger.error(f"Error solving CAPTCHA: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Error solving CAPTCHA: {str(e)}'
        }, status=500)


@login_required
def test_blog_generator(request):
    """Debug endpoint to test blog generator from Django context"""
    import shutil
    import subprocess
    
    diagnostics = {
        'ffmpeg_in_path': shutil.which('ffmpeg') is not None,
        'ffmpeg_path': shutil.which('ffmpeg'),
        'yt_dlp_available': False,
        'whisper_available': False,
        'test_url': 'https://www.youtube.com/watch?v=skMzCAga-dg',
    }
    
    # Check yt-dlp
    try:
        import yt_dlp
        diagnostics['yt_dlp_available'] = True
        diagnostics['yt_dlp_version'] = yt_dlp.version.__version__
    except ImportError:
        pass
    
    # Check whisper
    try:
        import whisper
        diagnostics['whisper_available'] = True
    except ImportError:
        pass
    
    # Test FFmpeg
    if diagnostics['ffmpeg_path']:
        try:
            result = subprocess.run([diagnostics['ffmpeg_path'], '-version'], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=5)
            diagnostics['ffmpeg_version'] = result.stdout.split('\n')[0] if result.stdout else 'Unknown'
        except:
            diagnostics['ffmpeg_version'] = 'Error checking version'
    
    # Try a simple download test
    if request.GET.get('test') == 'download':
        try:
            from .blog_generator import YouTubeBlogGenerator
            generator = YouTubeBlogGenerator()
            test_url = diagnostics['test_url']
            logger.info(f"Testing download for: {test_url}")
            audio_file = generator.download_audio(test_url)
            diagnostics['download_test'] = {
                'success': audio_file is not None,
                'audio_file': audio_file if audio_file else None,
            }
        except Exception as e:
            diagnostics['download_test'] = {
                'success': False,
                'error': str(e),
            }
            logger.error(f"Download test failed: {e}", exc_info=True)
    
    return JsonResponse(diagnostics, json_dumps_params={'indent': 2})
