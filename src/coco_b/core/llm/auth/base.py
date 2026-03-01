# =============================================================================
'''
    File Name : base.py
    
    Description : Base OAuth utilities shared across providers.
                  This module contains OAuthCallbackHandler for HTTP handling
                  of OAuth redirects, PKCE code verifier/challenge generation,
                  and base functions for OAuth flows.
    
    Modifying it on 2026-02-07
    
    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
    
    Project : mr_bot - Persistent Memory AI Chatbot
    
    License : Open Source - Safe Open Community Project
    
    Mission : Making AI Useful for Everyone
'''
# =============================================================================

# =============================================================================
# Import Section
# =============================================================================

import base64
import hashlib
import secrets
import time
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional, Tuple
from urllib.parse import urlencode, parse_qs, urlparse

import requests


# =============================================================================
'''
    OAuthCallbackHandler : HTTP handler for OAuth redirect callbacks.
                           Handles the OAuth callback by extracting the
                           authorization code from the redirect URL and
                           displaying a success/error page to the user.
'''
# =============================================================================

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    # =========================================================================
    # =========================================================================
    # Function log_message -> str to None (suppresses default HTTP logging)
    # =========================================================================
    # =========================================================================
    def log_message(self, format, *args):
        """Suppress default HTTP logging."""
        pass

    # =========================================================================
    # =========================================================================
    # Function do_GET -> None to None (handles OAuth callback GET request)
    # =========================================================================
    # =========================================================================
    def do_GET(self):
        """Handle the OAuth callback GET request."""
        print(f"[OAuth] Received callback: {self.path}")
        query = parse_qs(urlparse(self.path).query)

        # ==================================
        # Verify state parameter if expected
        # ==================================
        if hasattr(self.server, 'expected_state') and self.server.expected_state:
            received_state = query.get("state", [None])[0]
            # ==================================
            if received_state != self.server.expected_state:
                print(f"[OAuth] State mismatch! Expected: {self.server.expected_state[:20]}..., Got: {received_state[:20] if received_state else 'None'}...")
                self.server.auth_code = None
                self.server.error = "State mismatch - possible CSRF attack"
                self._send_error_response(self.server.error)
                return

        # ==================================
        if "code" in query:
            print("[OAuth] Authorization code received!")
            self.server.auth_code = query["code"][0]
            self.server.error = None
            self._send_success_response()
        # ==================================
        elif "error" in query:
            error_msg = query.get("error_description", query["error"])[0]
            print(f"[OAuth] Error received: {error_msg}")
            self.server.auth_code = None
            self.server.error = error_msg
            self._send_error_response(self.server.error)
        else:
            print(f"[OAuth] Unexpected callback, no code or error in: {query}")
            self.server.auth_code = None
            self.server.error = "No authorization code received"
            self._send_error_response(self.server.error)

    # =========================================================================
    # =========================================================================
    # Function _send_success_response -> None to None (sends success HTML page)
    # =========================================================================
    # =========================================================================
    def _send_success_response(self):
        """Send success HTML page to browser."""
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        html = """
<!DOCTYPE html>
<html>
<head>
    <title>Login Successful</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        .container {
            text-align: center;
            background: white;
            padding: 3rem;
            border-radius: 1rem;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }
        .checkmark {
            font-size: 4rem;
            margin-bottom: 1rem;
        }
        h2 { color: #333; margin-bottom: 0.5rem; }
        p { color: #666; }
    </style>
</head>
<body>
    <div class="container">
        <div class="checkmark">✓</div>
        <h2>Login Successful!</h2>
        <p>You can close this window and return to the terminal.</p>
    </div>
</body>
</html>
"""
        self.wfile.write(html.encode("utf-8"))

    # =========================================================================
    # =========================================================================
    # Function _send_error_response -> str to None (sends error HTML page)
    # =========================================================================
    # =========================================================================
    def _send_error_response(self, error: str):
        """Send error HTML page to browser."""
        self.send_response(400)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Login Failed</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #ff6b6b 0%, #ee5a5a 100%);
        }}
        .container {{
            text-align: center;
            background: white;
            padding: 3rem;
            border-radius: 1rem;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }}
        .error-icon {{
            font-size: 4rem;
            margin-bottom: 1rem;
        }}
        h2 {{ color: #333; margin-bottom: 0.5rem; }}
        p {{ color: #666; }}
        .error-msg {{ color: #d63031; font-family: monospace; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="error-icon">✗</div>
        <h2>Login Failed</h2>
        <p class="error-msg">{error}</p>
        <p>Please try again.</p>
    </div>
</body>
</html>
"""
        self.wfile.write(html.encode("utf-8"))


# =============================================================================
# =========================================================================
# Function generate_pkce -> None to Tuple[str, str] (PKCE verifier/challenge)
# =========================================================================
# =============================================================================

def generate_pkce() -> Tuple[str, str]:
    """
    Generate PKCE code verifier and challenge.

    PKCE (Proof Key for Code Exchange) is used to secure the OAuth flow
    for public clients that can't securely store a client secret.

    Returns:
        Tuple of (verifier, challenge_b64)
    """
    verifier = secrets.token_urlsafe(32)
    challenge = hashlib.sha256(verifier.encode()).digest()
    challenge_b64 = base64.urlsafe_b64encode(challenge).rstrip(b"=").decode()
    return verifier, challenge_b64


# =============================================================================
# =========================================================================
# Function find_available_port -> int, int to int (finds available local port)
# =========================================================================
# =============================================================================

def find_available_port(start_port: int = 8085, max_tries: int = 100) -> int:
    """Find an available port starting from start_port."""
    import socket
    # ==================================
    for port in range(start_port, start_port + max_tries):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('localhost', port))
                return port
        except OSError:
            continue
    raise Exception(f"Could not find available port in range {start_port}-{start_port + max_tries}")


# =============================================================================
# =========================================================================
# Function run_oauth_flow -> multiple params to dict (OAuth 2.0 auth code flow)
# =========================================================================
# =============================================================================

def run_oauth_flow(
    auth_url: str,
    token_url: str,
    redirect_uri: str,
    client_id: str,
    scopes: list,
    client_secret: Optional[str] = None,
    port: int = 0,  # 0 = auto-find available port
    extra_auth_params: Optional[dict] = None,
    extra_token_params: Optional[dict] = None,
    provider_name: str = "OAuth",
) -> dict:
    """
    Run a standard OAuth 2.0 authorization code flow with PKCE.

    This is a generic OAuth flow that can be used by any provider.

    Args:
        auth_url: Authorization endpoint URL
        token_url: Token endpoint URL
        redirect_uri: Redirect URI for callback
        client_id: OAuth client ID
        scopes: List of OAuth scopes to request
        client_secret: OAuth client secret (optional)
        port: Port for callback server
        extra_auth_params: Extra parameters for auth request
        extra_token_params: Extra parameters for token request
        provider_name: Name for display messages

    Returns:
        dict with access_token, refresh_token, expires_at

    Raises:
        Exception: If OAuth flow fails
    """
    verifier, challenge = generate_pkce()

    # Generate state parameter for CSRF protection
    state = secrets.token_urlsafe(32)

    # Build authorization URL
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": " ".join(scopes),
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
    }

    # Add extra auth params if provided
    # ==================================
    if extra_auth_params:
        params.update(extra_auth_params)

    # Start callback server FIRST (before opening browser)
    import socket
    import subprocess
    import sys

    # Find available port if not specified or if port=0
    # ==================================
    if port == 0:
        actual_port = find_available_port()
    else:
        actual_port = port

    # Update redirect_uri with actual port
    # Replace port in redirect_uri if it contains a port placeholder
    # ==================================
    if "{port}" in redirect_uri:
        actual_redirect_uri = redirect_uri.replace("{port}", str(actual_port))
    # ==================================
    elif redirect_uri.startswith("http://localhost:"):
        # Replace existing port in redirect_uri
        import re
        actual_redirect_uri = re.sub(r'http://localhost:\d+', f'http://localhost:{actual_port}', redirect_uri)
    else:
        actual_redirect_uri = redirect_uri

    # Update params with actual redirect_uri
    params["redirect_uri"] = actual_redirect_uri

    full_auth_url = f"{auth_url}?{urlencode(params)}"

    # Try to free the port if it's in use (from previous failed attempts)
    # =========================================================================
    # =========================================================================
    # Function free_port_safe -> int to bool (safely frees a port without shell commands)
    # =========================================================================
    # =========================================================================
    def free_port_safe(port: int) -> bool:
        """
        Safely kill any process using the specified port without shell commands
        
        Uses psutil for cross-platform process management. Prevents command injection
        vulnerabilities that exist with shell-based approaches using lsof and kill.
        
        Args:
            port: The port number to free
            
        Returns:
            bool: True if a process was terminated or port is free, False on error
            
        Security Note:
            This function avoids shell command injection by using psutil's native
            process management APIs instead of executing shell commands.
        """
        # ==================================
        # Validate port number is in valid range
        # ==================================
        if not isinstance(port, int) or port < 1 or port > 65535:
            return False
        
        # ==================================
        # Attempt to import psutil for safe process management
        # ==================================
        try:
            import psutil
        except ImportError:
            # psutil not available, cannot safely free port
            return False
        
        # ==================================
        # Track if we killed any process
        # ==================================
        killed = False
        
        try:
            # ==================================
            # Iterate through all network connections
            # ==================================
            for conn in psutil.net_connections():
                # ==================================
                # Check if this connection uses our target port
                # ==================================
                if conn.laddr and conn.laddr.port == port and conn.pid:
                    try:
                        # ==================================
                        # Get the process and terminate it
                        # ==================================
                        proc = psutil.Process(conn.pid)
                        proc.terminate()
                        
                        # ==================================
                        # Wait briefly for graceful termination
                        # ==================================
                        try:
                            proc.wait(timeout=2)
                        # ==================================
                        # Force kill if graceful termination fails
                        # ==================================
                        except psutil.TimeoutExpired:
                            proc.kill()
                            
                        killed = True
                        
                    # ==================================
                    # Process may have already exited
                    # ==================================
                    except psutil.NoSuchProcess:
                        killed = True
                    # ==================================
                    # Permission denied - cannot kill this process
                    # ==================================
                    except psutil.AccessDenied:
                        pass
                        
        # ==================================
        # Handle any unexpected errors
        # ==================================
        except Exception:
            return False
            
        return True

    # Create server with socket reuse
    try:
        server = HTTPServer(("localhost", actual_port), OAuthCallbackHandler)
        server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    except OSError as e:
        # ==================================
        if "Address already in use" in str(e) or e.errno == 48:
            # Try to free the port
            print(f"Port {actual_port} is in use, attempting to free it...")
            free_port_safe(actual_port)
            time.sleep(0.5)
            try:
                server = HTTPServer(("localhost", actual_port), OAuthCallbackHandler)
                server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            except OSError:
                raise Exception(
                    f"Port {actual_port} is still in use. "
                    f"Please close other applications using this port and try again."
                )
        else:
            raise

    server.auth_code = None
    server.error = None
    server.expected_state = state  # For CSRF verification
    server.timeout = 300  # 5 minute timeout

    # Now open browser (server is ready to receive callback)
    print(f"\nOpening browser for {provider_name} login...")
    print(f"If browser doesn't open, visit:\n{full_auth_url}\n")
    webbrowser.open(full_auth_url)

    print(f"Waiting for login callback on port {actual_port}...")
    try:
        server.handle_request()  # Wait for single callback
    finally:
        server.server_close()  # Clean up the socket

    # ==================================
    if server.error:
        raise Exception(f"OAuth error: {server.error}")

    # ==================================
    if not server.auth_code:
        raise Exception("No authorization code received")

    # Exchange code for tokens
    # Anthropic requires JSON format with state parameter included
    token_data = {
        "grant_type": "authorization_code",
        "code": server.auth_code,
        "state": state,  # Include state in token exchange
        "client_id": client_id,
        "redirect_uri": actual_redirect_uri,
        "code_verifier": verifier,
    }

    # ==================================
    if client_secret:
        token_data["client_secret"] = client_secret

    # Add extra token params if provided
    # ==================================
    if extra_token_params:
        token_data.update(extra_token_params)

    print(f"[OAuth] Exchanging code for tokens at {token_url}...")
    print(f"[OAuth] Token data:")
    for k, v in token_data.items():
        # ==================================
        if k in ("code", "code_verifier", "state"):
            print(f"  {k}: {str(v)[:20]}...")
        # ==================================
        elif k == "client_secret":
            print(f"  {k}: ***hidden***")
        else:
            print(f"  {k}: {v}")

    # Try JSON format first (Anthropic requires this)
    print(f"[OAuth] Trying JSON format...")
    headers = {"Content-Type": "application/json"}
    resp = requests.post(token_url, json=token_data, headers=headers, timeout=30)
    print(f"[OAuth] Response: {resp.status_code}")

    # If JSON fails, try form-encoded (standard OAuth2)
    # ==================================
    if not resp.ok:
        print(f"[OAuth] JSON failed, trying form-encoded...")
        resp = requests.post(token_url, data=token_data, timeout=30)
        print(f"[OAuth] Response: {resp.status_code}")

    # ==================================
    if not resp.ok:
        print(f"[OAuth] Token response body: {resp.text[:500]}")

    # ==================================
    if not resp.ok:
        error_data = {}
        # ==================================
        if resp.headers.get("content-type", "").startswith("application/json"):
            try:
                error_data = resp.json()
            except Exception:
                pass
        error_msg = error_data.get("error_description", error_data.get("error", resp.text))
        raise Exception(f"Token exchange failed: {error_msg}")

    tokens = resp.json()
    print(f"[OAuth] Tokens received! Access token: {tokens.get('access_token', 'N/A')[:20]}...")

    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens.get("refresh_token"),
        "expires_at": time.time() + tokens.get("expires_in", 3600) - 300,  # 5 min buffer
    }


# =============================================================================
# =========================================================================
# Function refresh_access_token -> multiple params to dict (refresh token)
# =========================================================================
# =============================================================================

def refresh_access_token(
    token_url: str,
    client_id: str,
    refresh_token: str,
    client_secret: Optional[str] = None,
) -> dict:
    """
    Refresh an access token using a refresh token.

    Args:
        token_url: Token endpoint URL
        client_id: OAuth client ID
        refresh_token: The refresh token
        client_secret: OAuth client secret (optional)

    Returns:
        dict with new access_token and expires_at

    Raises:
        Exception: If refresh fails
    """
    data = {
        "client_id": client_id,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    # ==================================
    if client_secret:
        data["client_secret"] = client_secret

    # Try JSON format first (Anthropic requires this)
    headers = {"Content-Type": "application/json"}
    resp = requests.post(token_url, json=data, headers=headers, timeout=30)

    # If JSON fails, try form-encoded
    # ==================================
    if not resp.ok:
        resp = requests.post(token_url, data=data, timeout=30)

    # ==================================
    if not resp.ok:
        error_data = {}
        # ==================================
        if resp.headers.get("content-type", "").startswith("application/json"):
            try:
                error_data = resp.json()
            except Exception:
                pass
        error_msg = error_data.get("error_description", error_data.get("error", resp.text))
        raise Exception(f"Token refresh failed: {error_msg}")

    tokens = resp.json()

    # Anthropic may return a new refresh token
    new_refresh_token = tokens.get("refresh_token", refresh_token)

    return {
        "access_token": tokens["access_token"],
        "refresh_token": new_refresh_token,
        "expires_at": time.time() + tokens.get("expires_in", 3600) - 300,
    }


# =============================================================================
# End of File - mr_bot OAuth Base Utilities
# =============================================================================
