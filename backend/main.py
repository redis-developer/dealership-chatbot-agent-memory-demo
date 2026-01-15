from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from langchain_openai import ChatOpenAI
from orchestrator import handle_turn, delete_all_sessions, build_workflow
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
    state: Optional[dict] = None  # Include state information

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
    # Require user_id from UI - no fallback to prevent memory association issues
    if not chat_request.user_id:
        logger.error("user_id is required but was not provided in the request")
        raise HTTPException(status_code=400, detail="user_id is required")
    
    user_id = chat_request.user_id
    # Generate session_id if not provided (session can be new)
    session_id = chat_request.session_id or f"session_{uuid.uuid4().hex[:16]}"
    
    logger.info(f"Received chat request - Session: {session_id}, User: {user_id}, Message: {chat_request.message[:100]}...")
    
    try:
        # handle_turn now returns both response and journey (from state with conversation context)
        response, journey = handle_turn(session_id, user_id, chat_request.message)
        logger.info(f"Successfully processed chat request - Session: {session_id}")
        return ChatResponse(response=response, session_id=session_id, state=journey)
    except Exception as e:
        logger.error(f"Error processing chat request - Session: {session_id}, Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")


@app.get("/")
def root():
    """Health check endpoint."""
    return {"status": "ok", "message": "AutoEmporium Chatbot API is running"}

@app.get("/journey/{session_id}")
def get_journey(session_id: str, user_id: str):
    """Get the current customer journey from checkpoint state.
    
    The checkpoint state already contains conversation context retrieved by 
    retrieve_conversation_context during workflow execution.
    """
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    
    try:
        thread_id = session_id or f"user_{user_id or 'unknown'}"
        empty_journey = {
            "body": None,
            "seats_min": None,
            "fuel": None,
            "brand": None,
            "model": None,
            "stage": None,
            "test_drive_completed": False
        }
        
        graph = build_workflow()
        config = {"configurable": {"thread_id": thread_id}}
        checkpoint = graph.get_state(config)
        
        if checkpoint and checkpoint.values:
            state = checkpoint.values
            # State already has conversation_context from retrieve_conversation_context
            journey = {
                "body": state.get("body"),
                "seats_min": state.get("seats_min"),
                "fuel": state.get("fuel"),
                "brand": state.get("brand"),
                "model": state.get("model"),
                "stage": state.get("stage"),
                "test_drive_completed": state.get("test_drive_completed", False)
            }
            logger.debug(f"Retrieved customer journey from checkpoint - User: {user_id}, Brand: {journey['brand']}, Model: {journey['model']}, Stage: {journey['stage']}")
            return {"state": journey}
        else:
            logger.debug(f"No checkpoint found for thread_id: {thread_id}")
            return {"state": empty_journey}
    except Exception as e:
        logger.error(f"Error getting customer journey - Session: {session_id}, Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting customer journey: {str(e)}")


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

