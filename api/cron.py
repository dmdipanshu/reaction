from http.server import BaseHTTPRequestHandler
import json
import os
import asyncio
import random
import time
from datetime import datetime, timezone
from hydrogram import Client
from hydrogram.enums import ChatType

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        from urllib.parse import urlparse
        parsed_path = urlparse(self.path)
        
        # 1. Handle non-cron requests (e.g. /, /favicon.ico)
        if parsed_path.path != "/api/cron":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "active"}).encode("utf-8"))
            return

        # 2. Verify Authorization Header (if CRON_SECRET is set)
        cron_secret = os.getenv("CRON_SECRET")
        if cron_secret:
            # Case-insensitive header lookup (handles standard dict, HTTPMessage, etc.)
            auth_header = next((v for k, v in self.headers.items() if k.lower() == "authorization"), None)
            
            # Safe debug logging to Vercel console
            masked_secret = f"{cron_secret[:3]}...{cron_secret[-3:]}" if len(cron_secret) > 6 else "***"
            masked_header = f"{auth_header[:15]}...{auth_header[-3:]}" if auth_header and len(auth_header) > 18 else ("Present" if auth_header else "None")
            print(f"[DEBUG] CRON_SECRET: {masked_secret} (len: {len(cron_secret)})")
            print(f"[DEBUG] Authorization Header: {masked_header}")
            
            if not auth_header or auth_header != f"Bearer {cron_secret}":
                self.send_response(401)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Unauthorized"}).encode("utf-8"))
                return

        # 2. Run the async execution
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            status, response_data = loop.run_until_complete(self.run_reactions())
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode("utf-8"))
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
        finally:
            loop.close()

    async def run_reactions(self):
        # Fetch environment variables
        api_id = os.getenv("API_ID")
        api_hash = os.getenv("API_HASH")
        session_string = os.getenv("SESSION_STRING")
        preferred_reactions_str = os.getenv("PREFERRED_REACTIONS", "👍,🔥,❤️,🎉,👏,😎")

        if not api_id or not api_hash or not session_string:
            return 400, {"error": "Missing required environment variables: API_ID, API_HASH, or SESSION_STRING."}

        try:
            api_id = int(api_id)
        except ValueError:
            return 400, {"error": "API_ID must be an integer."}

        preferred_reactions = [e.strip() for e in preferred_reactions_str.split(",") if e.strip()]
        if not preferred_reactions:
            preferred_reactions = ["👍"]

        start_time = time.time()
        reactions_added = 0
        groups_processed = 0
        skipped_messages = 0

        print("Initializing Telegram client...")
        # Start client in-memory
        app = Client(
            "auto_reaction_session",
            api_id=api_id,
            api_hash=api_hash,
            session_string=session_string,
            in_memory=True
        )

        try:
            await app.start()
            print("Telegram client connected.")

            now = datetime.now(timezone.utc)
            # Scan dialogs (ordered by last message date, most recent first)
            async for dialog in app.get_dialogs():
                # Vercel Hobby timeout is 10s. Keep buffer of 2s.
                if time.time() - start_time > 8.0:
                    print("Approaching Vercel execution timeout, stopping gracefully.")
                    break

                if dialog.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
                    continue

                # Check if group has been active within the last 35 minutes
                if dialog.top_message and dialog.top_message.date:
                    msg_date = dialog.top_message.date
                    if msg_date.tzinfo is None:
                        msg_date = msg_date.replace(tzinfo=timezone.utc)
                    
                    elapsed = (now - msg_date).total_seconds()
                    # 35 minutes = 2100 seconds
                    if elapsed > 2100:
                        # Since dialogs are ordered by date descending, any subsequent dialog will be even older.
                        print(f"Skipping group {dialog.chat.title} (inactive for {elapsed/60:.1f} minutes). Stopping scan.")
                        break

                groups_processed += 1
                print(f"Processing group: {dialog.chat.title} (ID: {dialog.chat.id})")

                # Get last 5 messages
                try:
                    async for message in app.get_chat_history(chat_id=dialog.chat.id, limit=5):
                        # Vercel timeout check
                        if time.time() - start_time > 8.0:
                            break

                        if message.service:
                            continue

                        # Check if we already reacted
                        has_reacted = False
                        if message.reactions:
                            reactions_list = getattr(message.reactions, "reactions", [])
                            if not reactions_list:
                                try:
                                    reactions_list = list(message.reactions)
                                except Exception:
                                    reactions_list = []
                            for r in reactions_list:
                                if getattr(r, "chosen", False) or getattr(r, "chosen_order", None) is not None:
                                    has_reacted = True
                                    break

                        if has_reacted:
                            skipped_messages += 1
                            continue

                        # Choose a random reaction
                        emoji = random.choice(preferred_reactions)
                        try:
                            await message.react(emoji)
                            reactions_added += 1
                            print(f"  -> Reacted {emoji} to message {message.id}")
                            # Small delay to prevent flood waits
                            await asyncio.sleep(0.2)
                        except Exception as react_err:
                            print(f"  -> Failed to react to message {message.id}: {react_err}")

                except Exception as history_err:
                    print(f"Failed to fetch history for group {dialog.chat.title}: {history_err}")

            await app.stop()
            print("Telegram client disconnected.")

        except Exception as client_err:
            print(f"Telegram client error: {client_err}")
            return 500, {"error": f"Telegram client error: {str(client_err)}"}

        duration = time.time() - start_time
        return 200, {
            "status": "success",
            "groups_processed": groups_processed,
            "reactions_added": reactions_added,
            "already_reacted_skipped": skipped_messages,
            "duration_seconds": round(duration, 2)
        }
