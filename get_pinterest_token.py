import os
import urllib.parse
import requests
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

PORT = 8080
REDIRECT_URI = f"http://localhost:{PORT}/callback"
creds = {}

class OAuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global creds
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path
        
        if path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            html = """
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 500px; margin: 50px auto; padding: 30px; text-align: center; border: 1px solid #ddd; border-radius: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);">
                <h2 style="color: #E60023;">Pinterest OAuth Setup</h2>
                <p style="color: #666; margin-bottom: 25px;">Enter your App details from the Pinterest Developer portal to securely generate your permanent token.</p>
                <form action="/start" method="GET">
                    <input type="text" name="app_id" placeholder="App ID" required style="padding: 12px; width: 100%; margin-bottom: 15px; border: 1px solid #ccc; border-radius: 5px; box-sizing: border-box;" /><br/>
                    <input type="password" name="app_secret" placeholder="App Secret" required style="padding: 12px; width: 100%; margin-bottom: 25px; border: 1px solid #ccc; border-radius: 5px; box-sizing: border-box;" /><br/>
                    <button type="submit" style="padding: 14px 20px; width: 100%; background: #E60023; color: white; border: none; border-radius: 5px; font-weight: bold; font-size: 16px; cursor: pointer;">Connect Pinterest Account</button>
                </form>
            </body>
            </html>
            """
            self.wfile.write(html.encode('utf-8'))
            
        elif path == "/start":
            query = urllib.parse.parse_qs(parsed_path.query)
            app_id = query.get("app_id", [""])[0].strip()
            app_secret = query.get("app_secret", [""])[0].strip()
            creds['app_id'] = app_id
            creds['app_secret'] = app_secret
            
            auth_url = f"https://www.pinterest.com/oauth/?client_id={app_id}&redirect_uri={urllib.parse.quote(REDIRECT_URI)}&response_type=code&scope=boards:read,pins:read,pins:write"
            
            self.send_response(302)
            self.send_header("Location", auth_url)
            self.end_headers()
            
        elif path == "/callback":
            query = urllib.parse.parse_qs(parsed_path.query)
            code = query.get("code", [""])[0]
            
            if not code:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"No code provided.")
                return
                
            # Exchange code for token
            token_url = "https://api.pinterest.com/v5/oauth/token"
            auth_str = f"{creds['app_id']}:{creds['app_secret']}"
            import base64
            b64_auth = base64.b64encode(auth_str.encode()).decode()
            
            headers = {
                "Authorization": f"Basic {b64_auth}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            data = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI
            }
            
            resp = requests.post(token_url, headers=headers, data=data)
            
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            
            if resp.status_code == 200:
                tokens = resp.json()
                refresh = tokens.get("refresh_token")
                access = tokens.get("access_token")
                
                html = f"""
                <html>
                <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 30px; text-align: center; border: 1px solid #ddd; border-radius: 10px;">
                    <h1 style="color: #E60023;">Success! 🎉</h1>
                    <p style="font-size: 16px;">Your permanent refresh token has been successfully generated!</p>
                    <p style="color: #666;">I have securely transmitted it back to your AI assistant. You can now close this window and return to the chat.</p>
                </body>
                </html>
                """
                print("\n" + "="*50)
                print("SUCCESS: REFRESH TOKEN ACQUIRED!")
                print(f"PINTEREST_REFRESH_TOKEN: {refresh}")
                print(f"PINTEREST_APP_ID: {creds['app_id']}")
                print(f"PINTEREST_APP_SECRET: {creds['app_secret']}")
                print("="*50 + "\n")
                
                # Shutdown server after 1 second so response can be sent
                threading.Timer(1.0, self.server.shutdown).start()
                
            else:
                html = f"<html><body><h2>Error {resp.status_code}</h2><p>{resp.text}</p><p>Please check your App ID and Secret, and ensure http://localhost:8080/callback is added to your Redirect URIs.</p></body></html>"
                print("Error getting token:", resp.text)
                threading.Timer(1.0, self.server.shutdown).start()
                
            self.wfile.write(html.encode('utf-8'))

def run():
    server_address = ('', PORT)
    httpd = HTTPServer(server_address, OAuthHandler)
    print(f"Server started at http://localhost:{PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    print("Server stopped.")

if __name__ == "__main__":
    run()
