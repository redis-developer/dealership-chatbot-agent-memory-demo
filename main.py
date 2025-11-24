from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from langchain_openai import ChatOpenAI
from orchestrator import handle_turn, delete_all_sessions
from fastapi.middleware.cors import CORSMiddleware
import os
import logging
import uuid

# Configure logging
import os
log_dir = 'logs'
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'chatbot.log')),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)



class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    session_id: str

EXPECTED_COLS = [
    "Company Names",
    "Cars Names",
    "Engines",
    "CC/Battery Capacity",
    "HorsePower",
    "Total Speed",
    "Performance(0 - 100 )KM/H",
    "Cars Prices",
    "Fuel Types",
    "Seats",
    "Torque",
]



app = FastAPI(title = "AutoEmporium Chatbot", description="Chatbot for AutoEmporium")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/chat")
def chat_request_handler(chat_request: ChatRequest) -> ChatResponse:
    # Generate IDs if not provided
    session_id = chat_request.session_id or f"session_{uuid.uuid4().hex[:16]}"
    user_id = chat_request.user_id or f"user_{uuid.uuid4().hex[:16]}"
    
    logger.info(f"Received chat request - Session: {session_id}, User: {user_id}, Message: {chat_request.message[:100]}...")
    
    try:
        # Always pass the generated IDs to handle_turn
        response = handle_turn(session_id, user_id, chat_request.message)
        logger.info(f"Successfully processed chat request - Session: {session_id}")
        return ChatResponse(response=response, session_id=session_id)
    except Exception as e:
        logger.error(f"Error processing chat request - Session: {session_id}, Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")


@app.get("/")
def root():
    """Health check endpoint."""
    return {"status": "ok", "message": "AutoEmporium Chatbot API is running"}


class DeleteSessionResponse(BaseModel):
    success: bool
    message: str


@app.delete("/sessions/all")
def delete_all_sessions_endpoint() -> DeleteSessionResponse:
    """Delete ALL Redis checkpoint entries.
    
    WARNING: This will delete ALL session states. Use with extreme caution.
    
    Returns:
        DeleteSessionResponse: Success status and message
    """
    logger.warning("Delete ALL sessions request received")
    
    try:
        success = delete_all_sessions()
        if success:
            return DeleteSessionResponse(
                success=True,
                message="All sessions deleted successfully"
            )
        else:
            return DeleteSessionResponse(
                success=False,
                message="Failed to delete all sessions"
            )
    except Exception as e:
        logger.error(f"Error deleting all sessions: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error deleting all sessions: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    
    logger.info("Starting AutoEmporium Chatbot API Server...")
    logger.info("API will be available at http://localhost:8001")
    logger.info("Frontend should connect to http://localhost:8001/chat")
    uvicorn.run(app, host="0.0.0.0", port=8001, log_config=None)
  
