"""
Test script for chat_service.py UUID fixes
Tests that the chat service works correctly with UUID-only schema
"""

from database.chat_service import ChatService
from database.db_connection import DatabaseConnection

def test_chat_service():
    """Test basic chat service functionality"""
    print("=" * 60)
    print("Testing ChatService with UUID-only schema")
    print("=" * 60)

    # Initialize service
    chat_service = ChatService()

    # Test 1: Create a chat conversation for a patient
    print("\n[Test 1] Creating a test chat conversation...")

    # Get a test patient UUID
    db = DatabaseConnection()
    patient_query = "SELECT Patient_UUID FROM patient WHERE Deleted = 0 LIMIT 1"
    patient_result = db.execute_one(patient_query, ())

    if not patient_result:
        print("ERROR: No patient found in database. Please add a test patient first.")
        return False

    patient_uuid = patient_result['Patient_UUID']
    print(f"  Using patient UUID: {patient_uuid}")

    # Create chat conversation
    chat_uuid = chat_service.create_chat_for_patient(
        patient_id=patient_uuid,
        title="UUID Test Conversation",
        conversation_type="general",
        ai_agent="agent_1"
    )

    if not chat_uuid:
        print("  ERROR: Failed to create chat conversation")
        return False

    print(f"  SUCCESS: Created chat with UUID: {chat_uuid}")

    # Test 2: Save a message
    print("\n[Test 2] Saving a test message...")
    message_uuid = chat_service.save_message(
        chat_id=chat_uuid,
        message_content="This is a test message after UUID migration",
        message_type="user",
        sender_info="test_user"
    )

    if not message_uuid:
        print("  ERROR: Failed to save message")
        return False

    print(f"  SUCCESS: Saved message with UUID: {message_uuid}")

    # Test 3: Get chat messages
    print("\n[Test 3] Retrieving chat messages...")
    messages = chat_service.get_chat_messages(chat_id=chat_uuid)

    if not messages or len(messages) == 0:
        print("  ERROR: Failed to retrieve messages")
        return False

    print(f"  SUCCESS: Retrieved {len(messages)} message(s)")
    for msg in messages:
        print(f"    - Message UUID: {msg['Message_UUID']}")
        print(f"      Content: {msg['Message_Content'][:50]}...")

    # Test 4: Get chat by ID
    print("\n[Test 4] Getting chat by UUID...")
    chat_info = chat_service.get_chat_by_id(chat_uuid)

    if not chat_info:
        print("  ERROR: Failed to get chat info")
        return False

    print(f"  SUCCESS: Retrieved chat info")
    print(f"    - Title: {chat_info.get('Title')}")
    print(f"    - Total Messages: {chat_info.get('Total_Messages')}")
    print(f"    - Status: {chat_info.get('Status')}")

    # Test 5: Update chat title
    print("\n[Test 5] Updating chat title...")
    success = chat_service.update_chat_title(chat_uuid, "Updated UUID Test Conversation")

    if not success:
        print("  ERROR: Failed to update chat title")
        return False

    print("  SUCCESS: Chat title updated")

    # Test 6: Get chat statistics
    print("\n[Test 6] Getting chat statistics...")
    stats = chat_service.get_chat_statistics(chat_uuid)

    if not stats:
        print("  ERROR: Failed to get chat statistics")
        return False

    print(f"  SUCCESS: Retrieved chat statistics")
    print(f"    - Total messages: {stats.get('total_messages')}")
    print(f"    - User messages: {stats.get('user_messages')}")
    print(f"    - AI messages: {stats.get('ai_messages')}")

    # Cleanup: Delete test chat
    print("\n[Cleanup] Deleting test chat...")
    success = chat_service.delete_chat(chat_uuid)

    if not success:
        print("  WARNING: Failed to delete test chat")
    else:
        print("  SUCCESS: Test chat deleted")

    print("\n" + "=" * 60)
    print("All tests passed!")
    print("=" * 60)

    return True


if __name__ == "__main__":
    try:
        test_chat_service()
    except Exception as e:
        print(f"\nERROR: Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
