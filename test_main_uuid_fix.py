"""
Test script to verify main.py UUID fixes
Tests the chat history API endpoint
"""

import requests
import sys

def test_chat_history_api():
    """Test the chat history API endpoint"""
    print("=" * 60)
    print("Testing Chat History API with UUID fixes")
    print("=" * 60)

    # Test getting chat history by phone number
    phone_number = "13900000001"
    url = f"http://localhost:8000/api/chat/history/phone/{phone_number}"

    print(f"\n[Test] Getting chat history for phone: {phone_number}")
    print(f"URL: {url}")

    try:
        response = requests.get(url, timeout=10)
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"\nSUCCESS: Retrieved chat history")
            print(f"  - Success: {data.get('success')}")
            print(f"  - Phone: {data.get('phone_number')}")
            print(f"  - Patient UUID: {data.get('patient_uuid')}")
            print(f"  - Chat count: {data.get('count')}")

            if data.get('chats'):
                print(f"\n  Sample chat:")
                chat = data['chats'][0]
                print(f"    - Chat UUID: {chat.get('Chat_UUID')}")
                print(f"    - Title: {chat.get('Title')}")
                print(f"    - Status: {chat.get('Status')}")
                print(f"    - Total Messages: {chat.get('Total_Messages')}")

            return True
        elif response.status_code == 500:
            print(f"\nERROR: Server error (500)")
            print(f"Response: {response.text}")
            return False
        else:
            print(f"\nERROR: Unexpected status code")
            print(f"Response: {response.text}")
            return False

    except requests.exceptions.ConnectionError:
        print("\nERROR: Cannot connect to server")
        print("Please make sure the FastAPI server is running:")
        print("  python main.py")
        return False
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n" + "=" * 60)

if __name__ == "__main__":
    success = test_chat_history_api()
    sys.exit(0 if success else 1)
