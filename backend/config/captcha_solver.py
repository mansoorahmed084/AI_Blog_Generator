"""
CAPTCHA Solver for YouTube Bot Detection
Uses Playwright to open a browser window where users can solve CAPTCHA challenges.
"""
import os
import json
import logging
import tempfile
from typing import Optional, Dict, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Try to import Playwright
try:
    from playwright.sync_api import sync_playwright, Browser, Page
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    except ImportError:
        PlaywrightTimeoutError = Exception
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    PlaywrightTimeoutError = Exception
    logger.warning("Playwright not installed. Install with: pip install playwright && playwright install chromium")


class YouTubeCaptchaSolver:
    """Solve YouTube CAPTCHA challenges using Playwright browser automation"""
    
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.page = None
        self.cookies_saved = False
        
    def _is_bot_detection_error(self, error_message: str) -> bool:
        """Check if error message indicates bot detection"""
        bot_indicators = [
            "Sign in to confirm you're not a bot",
            "bot detection",
            "verify you're not a robot",
            "captcha",
            "challenge",
        ]
        error_lower = error_message.lower()
        return any(indicator in error_lower for indicator in bot_indicators)
    
    def solve_captcha_interactive(self, youtube_url: str, timeout: int = 300) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Open a browser window for user to solve CAPTCHA interactively.
        
        Args:
            youtube_url: YouTube video URL
            timeout: Maximum time to wait for user to solve (seconds)
            
        Returns:
            Tuple of (success, cookie_file_path, error_message)
        """
        if not PLAYWRIGHT_AVAILABLE:
            return False, None, "Playwright is not installed. Please install it: pip install playwright && playwright install chromium"
        
        try:
            # Start Playwright
            self.playwright = sync_playwright().start()
            
            # Launch browser in visible mode (non-headless) so user can interact
            logger.info("Launching browser for CAPTCHA solving...")
            self.browser = self.playwright.chromium.launch(
                headless=False,  # Visible browser so user can solve CAPTCHA
                args=['--disable-blink-features=AutomationControlled']  # Hide automation
            )
            
            # Create a new page
            context = self.browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            self.page = context.new_page()
            
            # Navigate to YouTube video
            logger.info(f"Navigating to {youtube_url}...")
            self.page.goto(youtube_url, wait_until='networkidle', timeout=60000)
            
            # Wait for user to solve CAPTCHA
            logger.info("Waiting for user to solve CAPTCHA...")
            logger.info("Please solve the CAPTCHA in the browser window that opened.")
            
            # Check for CAPTCHA/challenge page
            captcha_detected = False
            try:
                # Look for common CAPTCHA indicators
                captcha_selectors = [
                    'iframe[src*="recaptcha"]',
                    'div[id*="captcha"]',
                    'div[class*="captcha"]',
                    'button:has-text("I\'m not a robot")',
                ]
                
                for selector in captcha_selectors:
                    try:
                        element = self.page.wait_for_selector(selector, timeout=5000)
                        if element:
                            captcha_detected = True
                            logger.info("CAPTCHA detected! Please solve it in the browser.")
                            break
                    except:
                        continue
            except:
                pass
            
            # Wait for user to solve (check if page navigated away from CAPTCHA)
            # We'll wait for the video page to load or timeout
            try:
                # Wait for video player or main content
                self.page.wait_for_selector('div#player, ytd-watch-flexy, #movie_player', timeout=timeout * 1000)
                logger.info("CAPTCHA appears to be solved (video page loaded)")
            except PlaywrightTimeoutError:
                logger.warning(f"Timeout waiting for CAPTCHA solution ({timeout}s)")
                # Check if still on CAPTCHA page
                current_url = self.page.url
                if 'captcha' in current_url.lower() or 'challenge' in current_url.lower():
                    return False, None, f"CAPTCHA not solved within {timeout} seconds. Please try again."
            
            # Get cookies after solving
            cookies = context.cookies()
            
            if not cookies:
                return False, None, "No cookies found after solving CAPTCHA. Please try again."
            
            # Save cookies to Netscape format file
            cookie_file = self._save_cookies_netscape(cookies, youtube_url)
            
            logger.info(f"Successfully captured {len(cookies)} cookies after CAPTCHA solution")
            
            return True, cookie_file, None
            
        except Exception as e:
            error_msg = f"Error during CAPTCHA solving: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, None, error_msg
        
        finally:
            # Don't close browser immediately - let user see the result
            # Browser will be closed when solver is destroyed
            pass
    
    def _save_cookies_netscape(self, cookies: list, youtube_url: str) -> str:
        """Save cookies in Netscape format for yt-dlp"""
        from datetime import datetime
        
        # Create temporary cookie file
        temp_dir = tempfile.gettempdir()
        cookie_file = os.path.join(temp_dir, f'youtube_cookies_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt')
        
        # Parse domain from URL
        parsed = urlparse(youtube_url)
        domain = parsed.netloc.replace('www.', '')
        
        # Write Netscape format
        with open(cookie_file, 'w', encoding='utf-8') as f:
            f.write("# Netscape HTTP Cookie File\n")
            f.write(f"# Generated by YouTube CAPTCHA Solver\n")
            f.write(f"# Domain: {domain}\n")
            f.write(f"# Generated: {datetime.now().isoformat()}\n\n")
            
            for cookie in cookies:
                # Netscape format: domain, domain_flag, path, secure, expiration, name, value
                domain_flag = 'TRUE' if cookie.get('domain', '').startswith('.') else 'FALSE'
                domain_val = cookie.get('domain', domain).lstrip('.')
                path = cookie.get('path', '/')
                secure = 'TRUE' if cookie.get('secure', False) else 'FALSE'
                expiration = cookie.get('expires', 0)
                if expiration == 0:
                    expiration = '0'  # Session cookie
                else:
                    expiration = str(int(expiration))
                
                name = cookie.get('name', '')
                value = cookie.get('value', '')
                
                line = '\t'.join([
                    domain_val,
                    domain_flag,
                    path,
                    secure,
                    expiration,
                    name,
                    value
                ])
                f.write(line + '\n')
        
        logger.info(f"Saved {len(cookies)} cookies to {cookie_file}")
        return cookie_file
    
    def close(self):
        """Close browser and cleanup"""
        try:
            if self.page:
                self.page.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except Exception as e:
            logger.warning(f"Error closing browser: {e}")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def solve_youtube_captcha(youtube_url: str, timeout: int = 300) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Convenience function to solve YouTube CAPTCHA.
    
    Returns:
        Tuple of (success, cookie_file_path, error_message)
    """
    solver = YouTubeCaptchaSolver()
    try:
        return solver.solve_captcha_interactive(youtube_url, timeout)
    finally:
        solver.close()
