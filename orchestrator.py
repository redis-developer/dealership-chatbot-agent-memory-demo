from langchain_openai import ChatOpenAI
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from dotenv import load_dotenv
import os
import logging

load_dotenv()

# Configure logger for orchestrator
logger = logging.getLogger(__name__)

class State(TypedDict):
    request: str
    response: str
    

# Initialize LLM
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    logger.warning("OPENAI_API_KEY not found in environment variables")

llm = ChatOpenAI(
    model="gpt-3.5-turbo",
    temperature=0.3,
    openai_api_key=openai_api_key
)

logger.info("LLM initialized with model: gpt-3.5-turbo")

def get_response_from_llm(state: State) -> str:
    request = state["request"]
    logger.debug(f"Processing LLM request: {request[:100]}...")
    
    try:
        response = llm.invoke(request)
        logger.debug(f"LLM response received: {response.content[:100]}...")
        return {"response": response.content}
    except Exception as e:
        logger.error(f"Error invoking LLM: {str(e)}", exc_info=True)
        raise

def build_workflow():
    workflow = StateGraph(State)
    workflow.add_node("get_response_from_llm", get_response_from_llm)
    workflow.set_entry_point("get_response_from_llm")
    workflow.set_finish_point("get_response_from_llm")
    compiled_graph = workflow.compile()
    logger.debug("Workflow compiled successfully")
    return compiled_graph



def handle_turn(session_id: str, user_id: str, message: str) -> str:
    logger.info(f"Handling turn - Session: {session_id}, User: {user_id}, Message length: {len(message)}")
    
    # Initialize state with the message
    initial_state: State = {
        "request": message,
        "response": ""
    }
    
    try:
        graph = build_workflow()
        logger.debug(f"Workflow built, invoking with session: {session_id}")
        final_state = graph.invoke(initial_state)
        response = final_state["response"]
        logger.info(f"Turn completed - Session: {session_id}, Response length: {len(response)}")
        return response
    except Exception as e:
        logger.error(f"Error in handle_turn - Session: {session_id}, Error: {str(e)}", exc_info=True)
        raise
