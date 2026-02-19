import logging
import traceback

# Configure logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Function to simulate your ChatService send_message functionality with error catching
async def send_message(conversation_id: str, user_message: str, db) -> dict:
    try:
        # Simulate the actual logic of sending a message
        logger.debug(f"Received conversation_id: {conversation_id} and message: {user_message}")

        # Simulate loading conversation from the database
        result = await db.execute(f"SELECT * FROM core.conversations WHERE id = '{conversation_id}'")
        conversation = result.scalar_one_or_none()

        if not conversation:
            logger.error(f"Conversation not found: {conversation_id}")
            raise ValueError(f"Conversation not found: {conversation_id}")

        # Simulate loading conversation messages
        result = await db.execute(f"SELECT * FROM core.conversation_messages WHERE conversation_id = '{conversation_id}'")
        messages = result.scalars().all()

        logger.debug(f"Loaded {len(messages)} messages for conversation {conversation_id}")

        # Simulate other parts of the logic...
        # Simulate saving the user's message
        logger.debug(f"Saving user message: {user_message}")

        # Example of where things could fail (e.g., database query for AI response, LangGraph processing, etc.)
        if user_message == "fail":
            raise Exception("Simulated failure in LangGraph response")

        # Normally return response
        response = {"conversation_id": conversation_id, "response": "AI response"}
        return response

    except Exception as e:
        logger.error(f"Error occurred while processing message: {user_message}")
        logger.error(f"Exception: {str(e)}")
        logger.error("Stack trace:")
        logger.error(traceback.format_exc())  # This logs the full stack trace of the error
        
        # Optionally, return a standardized error response
        return {"error": "Internal server error", "details": str(e)}

# Example of how you can call the send_message function
async def main():
    # Simulate db session (replace with your actual db session)
    db = None  # Replace with your actual db connection/session

    # Call the send_message function
    result = await send_message("36f24d11-9816-483e-a2a9-8b9966a4cab1", "Hello, what services do you offer?", db)
    
    if "error" in result:
        logger.error(f"Failed to process message: {result['details']}")
    else:
        logger.debug(f"Message processed successfully: {result['response']}")

# Run the script (this should be run within an event loop in your application)
import asyncio
asyncio.run(main())
