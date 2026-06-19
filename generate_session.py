import asyncio
import sys

try:
    from hydrogram import Client
except ImportError:
    print("Error: The 'hydrogram' package is not installed.")
    print("Please install it locally by running: pip install hydrogram tgcrypto")
    sys.exit(1)

async def generate():
    print("=" * 60)
    print("            Telegram Session String Generator")
    print("=" * 60)
    print("To get your API_ID and API_HASH, visit: https://my.telegram.org/")
    print("-" * 60)
    
    try:
        api_id_input = input("Enter your API_ID: ").strip()
        if not api_id_input:
            print("Error: API_ID cannot be empty.")
            return
        api_id = int(api_id_input)
        
        api_hash = input("Enter your API_HASH: ").strip()
        if not api_hash:
            print("Error: API_HASH cannot be empty.")
            return
            
    except ValueError:
        print("Error: API_ID must be an integer.")
        return
    except KeyboardInterrupt:
        print("\nCancelled.")
        return

    print("\nStarting Telegram Client...")
    print("You will be prompted to enter your phone number (including country code, e.g., +1234567890)")
    print("and then the verification code sent to your Telegram app.")
    print("-" * 60)
    
    try:
        # Create an in-memory client
        async with Client(":memory:", api_id=api_id, api_hash=api_hash, in_memory=True) as app:
            session_str = await app.export_session_string()
            print("\n" + "=" * 60)
            print("SUCCESS! HERE IS YOUR SESSION STRING:")
            print("=" * 60)
            print(session_str)
            print("=" * 60)
            print("IMPORTANT SAFETY WARNING:")
            print("This session string grants full access to your Telegram account.")
            print("Never share it. If leaked, terminate the session in Telegram Settings -> Devices.")
            print("-" * 60)
            print("Copy the entire string above and set it as an environment variable")
            print("named 'SESSION_STRING' on Vercel.")
            print("=" * 60 + "\n")
    except Exception as e:
        print(f"\nAn error occurred: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(generate())
    except KeyboardInterrupt:
        print("\nSession generation cancelled.")
