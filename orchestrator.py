from langchain_openai import ChatOpenAI
from typing_extensions import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.redis import RedisSaver
from dotenv import load_dotenv
import os
import logging
from typing import List, Optional
import operator
import json
import re
import redis
from datetime import datetime, timedelta

load_dotenv()

# Configure logger for orchestrator
logger = logging.getLogger(__name__)

class State(TypedDict):
    # User input
    request: str
    
    # Slots (extracted information)
    budget_max: Optional[float]
    seats_min: Optional[int]
    fuel: Optional[str]  # "gas", "electric", "hybrid", etc.
    body: Optional[str]  # "sedan", "suv", "truck", etc.
    transmission_ban: Annotated[List[str], operator.add]  # List of banned transmission types
    brand: Optional[str]
    model: Optional[str]
    
    # Readiness check
    need_clarification: bool
    missing_slots: Optional[dict]  # Temporary field to pass missing slots info
    
    # Procedural stage
    stage: Optional[str]  # needs_analysis | shortlist | test_drive | financing | etc.
    
    # Response generation
    response: Optional[str]
    rationale: Optional[str]
    next_step: Optional[str]


# Initialize Redis checkpointer for state persistence
redis_uri = os.getenv("REDIS_URL") or os.getenv("REDIS_URI")
checkpointer = None
checkpointer_cm = None  # Keep reference to context manager

if not redis_uri:
    logger.warning("REDIS_URL or REDIS_URI not found in environment variables. State persistence will not work.")
else:
    try:
        # Use context manager to call setup() for initialization
        # This initializes the Redis indices needed for checkpoints
        # Following the pattern from: https://github.com/redis-developer/langgraph-apps-with-redis
        with RedisSaver.from_conn_string(redis_uri) as temp_checkpointer:
            temp_checkpointer.setup()
            logger.info("Redis checkpointer indices initialized successfully")
        
        # Create checkpointer context manager and enter it to get the actual checkpointer object
        # We need to keep the context manager open for the lifetime of the application
        # so we store both the context manager and the entered checkpointer
        checkpointer_cm = RedisSaver.from_conn_string(redis_uri)
        checkpointer = checkpointer_cm.__enter__()
        logger.info("Redis checkpointer initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Redis checkpointer: {str(e)}", exc_info=True)
        checkpointer = None
        checkpointer_cm = None

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

# Node 1: parse_slots - extract/merge slots from user message
def parse_slots(state: State) -> State:
    logger.info("Node: parse_slots - Extracting and merging slots")
    
    user_message = state.get("request", "")
    existing_slots = {
        "budget_max": state.get("budget_max"),
        "seats_min": state.get("seats_min"),
        "fuel": state.get("fuel"),
        "body": state.get("body"),
        "transmission_ban": state.get("transmission_ban", []),
        "brand": state.get("brand"),
        "model": state.get("model"),
    }
    
    # Create prompt for slot extraction
    extraction_prompt = f"""Extract luxury car purchase preferences from the following user message from an Indian customer at a premium luxury car showroom. 
Return ONLY a valid JSON object with the extracted values. If a value is not mentioned, use null.

User message: "{user_message}"

Current known preferences: {json.dumps(existing_slots, default=str)}

Extract the following slots (all amounts are in Indian Rupees - INR):
- budget_max: Maximum budget as a number in INR (e.g., 5000000, 15000000, 50000000, 100000000). Extract from phrases like "under 50 lakh", "max ₹1.5 crore", "budget of 1 crore", "around 2 crore rupees", "upto 75L", "within 80 lakh budget", "50 lakh to 1 crore"
- seats_min: Minimum number of seats as an integer (e.g., 4, 5, 7). Extract from phrases like "seats 5", "at least 7 seats", "5-seater", "need 7 seater"
- fuel: Fuel type as lowercase string - one of: "petrol", "diesel", "electric", "hybrid", "plug-in hybrid". Extract from phrases like "petrol car", "diesel vehicle", "electric", "hybrid", "EV"
- body: Body type as lowercase string - one of: "sedan", "suv", "coupe", "convertible", "wagon", "sports car". Extract from phrases like "luxury sedan", "premium SUV", "sports car", "coupe", "convertible"
- transmission_ban: List of transmission types the user does NOT want (e.g., ["manual"]). Extract from phrases like "no manual", "don't want manual", "avoid manual", "only automatic"
- brand: Luxury car brand as string (e.g., "Mercedes-Benz", "BMW", "Audi", "Jaguar", "Land Rover", "Volvo", "Lexus", "Porsche", "Bentley", "Rolls-Royce", "Maserati", "Range Rover"). Extract brand names mentioned
- model: Luxury car model as string (e.g., "S-Class", "5 Series", "A6", "XF", "Discovery", "XC90", "ES", "Cayenne", "Continental", "Ghost", "Ghibli", "Evoque"). Extract model names mentioned

Note: Convert Indian number formats - "lakh" = 100000, "crore" = 10000000. "50 lakh" = 5000000, "1.5 crore" = 15000000. This is a luxury showroom, so budgets are typically in higher ranges (30 lakh+).

Return JSON format:
{{
  "budget_max": <number or null>,
  "seats_min": <integer or null>,
  "fuel": <string or null>,
  "body": <string or null>,
  "transmission_ban": <array of strings or empty array>,
  "brand": <string or null>,
  "model": <string or null>
}}

Only return the JSON object, no other text."""

    try:
        # Get LLM response
        response = llm.invoke(extraction_prompt)
        response_text = response.content.strip()
        
        # Extract JSON from response (in case LLM adds extra text)
        # Try to find JSON object boundaries
        start_idx = response_text.find('{')
        if start_idx != -1:
            # Find matching closing brace
            brace_count = 0
            end_idx = start_idx
            for i in range(start_idx, len(response_text)):
                if response_text[i] == '{':
                    brace_count += 1
                elif response_text[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = i + 1
                        break
            if end_idx > start_idx:
                response_text = response_text[start_idx:end_idx]
        
        # Parse JSON
        extracted_slots = json.loads(response_text)
        logger.debug(f"Extracted slots: {extracted_slots}")
        
        # Merge with existing slots (only update non-null values)
        updated_slots = {}
        
        if extracted_slots.get("budget_max") is not None:
            updated_slots["budget_max"] = float(extracted_slots["budget_max"])
        elif existing_slots["budget_max"] is not None:
            updated_slots["budget_max"] = existing_slots["budget_max"]
        
        if extracted_slots.get("seats_min") is not None:
            updated_slots["seats_min"] = int(extracted_slots["seats_min"])
        elif existing_slots["seats_min"] is not None:
            updated_slots["seats_min"] = existing_slots["seats_min"]
        
        if extracted_slots.get("fuel") is not None:
            updated_slots["fuel"] = extracted_slots["fuel"].lower()
        elif existing_slots["fuel"] is not None:
            updated_slots["fuel"] = existing_slots["fuel"]
        
        if extracted_slots.get("body") is not None:
            updated_slots["body"] = extracted_slots["body"].lower()
        elif existing_slots["body"] is not None:
            updated_slots["body"] = existing_slots["body"]
        
        # Merge transmission_ban lists
        new_bans = extracted_slots.get("transmission_ban", [])
        if isinstance(new_bans, list) and len(new_bans) > 0:
            updated_slots["transmission_ban"] = [t.lower() for t in new_bans if t]
        elif existing_slots["transmission_ban"]:
            updated_slots["transmission_ban"] = existing_slots["transmission_ban"]
        
        if extracted_slots.get("brand") is not None:
            updated_slots["brand"] = extracted_slots["brand"]
        elif existing_slots["brand"] is not None:
            updated_slots["brand"] = existing_slots["brand"]
        
        if extracted_slots.get("model") is not None:
            updated_slots["model"] = extracted_slots["model"]
        elif existing_slots["model"] is not None:
            updated_slots["model"] = existing_slots["model"]
        
        logger.info(f"Parsed slots - Budget: {updated_slots.get('budget_max')}, Seats: {updated_slots.get('seats_min')}, Fuel: {updated_slots.get('fuel')}, Body: {updated_slots.get('body')}, Brand: {updated_slots.get('brand')}, Model: {updated_slots.get('model')}")
        
        return updated_slots
        
    except json.JSONDecodeError as e:
        response_preview = response_text[:200] if 'response_text' in locals() else "N/A"
        logger.warning(f"Failed to parse JSON from LLM response: {response_preview}... Error: {str(e)}")
        return {}
    except Exception as e:
        logger.error(f"Error in parse_slots: {str(e)}", exc_info=True)
        return {}

# Node 2: ensure_readiness - check if required slots are missing
def ensure_readiness(state: State) -> State:
    logger.info("Node: ensure_readiness - Checking if required slots are present")
    
    # Define required slots for car purchase
    required_slots = {
        "budget_max": state.get("budget_max"),
        "body": state.get("body"),
    }
    
    # Optional but helpful slots
    optional_slots = {
        "seats_min": state.get("seats_min"),
        "fuel": state.get("fuel"),
    }
    
    # Check which required slots are missing
    missing_required = [slot for slot, value in required_slots.items() if value is None]
    
    # Determine if clarification is needed
    need_clarification = len(missing_required) > 0
    
    # Store missing slots info for the respond node
    missing_slots_info = {
        "required": missing_required,
        "optional": [slot for slot, value in optional_slots.items() if value is None]
    }
    
    logger.info(f"Readiness check - Need clarification: {need_clarification}, Missing required: {missing_required}")
    
    return {
        "need_clarification": need_clarification,
        "missing_slots": missing_slots_info  # Store in a temporary field (we'll use it in respond)
    }

# Node 3: respond - generate response based on readiness
def respond(state: State) -> State:
    logger.info("Node: respond - Generating response")
    
    need_clarification = state.get("need_clarification", False)
    missing_slots_info = state.get("missing_slots", {})
    missing_required = missing_slots_info.get("required", [])
    
    if need_clarification:
        # Ask one crisp clarification question about the most important missing slot
        # Priority: budget_max > body > seats_min > fuel
        
        slot_priority = ["budget_max", "body", "seats_min", "fuel"]
        next_slot_to_ask = None
        
        # First, try to find a missing required slot in priority order
        for slot in slot_priority:
            if slot in missing_required:
                next_slot_to_ask = slot
                break
        
        # If no required slot found, check optional slots
        if not next_slot_to_ask:
            missing_optional = missing_slots_info.get("optional", [])
            for slot in slot_priority:
                if slot in missing_optional:
                    next_slot_to_ask = slot
                    break
        
        # Fallback: use first missing required slot, or first optional, or default to budget
        if not next_slot_to_ask:
            if missing_required:
                next_slot_to_ask = missing_required[0]
            elif missing_slots_info.get("optional", []):
                next_slot_to_ask = missing_slots_info["optional"][0]
            else:
                next_slot_to_ask = "budget_max"  # Default fallback
        
        # Generate a crisp clarification question
        clarification_prompts = {
            "budget_max": "What's your maximum budget for the car?",
            "body": "What type of luxury vehicle are you looking for? (e.g., sedan, SUV, coupe, convertible)",
            "seats_min": "How many seats do you need?",
            "fuel": "What fuel type do you prefer? (petrol, diesel, electric, hybrid)"
        }
        
        # Use LLM to generate a more natural clarification question for Indian luxury car showroom
        slot_descriptions = {
            "budget_max": "maximum budget in Indian Rupees (INR) for a luxury car. Use terms like 'lakh' or 'crore'. For example, '50 lakh', '1 crore', '₹1.5 crore'. Typical luxury car budgets range from 30 lakh to several crores",
            "body": "type of luxury vehicle (sedan, SUV, coupe, convertible, sports car, etc.)",
            "seats_min": "number of seats needed",
            "fuel": "fuel type preference (petrol, diesel, electric, hybrid, plug-in hybrid)"
        }
        
        clarification_prompt = f"""You are an elegant and professional sales consultant at a premium luxury car showroom in India. Generate a single, refined, and sophisticated question in Indian English to ask the customer about their {slot_descriptions.get(next_slot_to_ask, next_slot_to_ask)} preference for purchasing a luxury car.
        
Context: They're looking to buy a luxury/premium car and we need to know their {next_slot_to_ask}.
Current known preferences: Budget: {state.get('budget_max')} INR, Body: {state.get('body')}, Seats: {state.get('seats_min')}, Fuel: {state.get('fuel')}, Brand: {state.get('brand')}, Model: {state.get('model')}

Guidelines:
- Use refined Indian English appropriate for a luxury showroom
- Be professional, elegant, and respectful (addressing them as "sir" or "madam" if natural)
- Use premium terminology (e.g., "luxury sedan", "premium SUV", "high-end")
- For budget questions, mention "lakh" or "crore" as appropriate (luxury cars typically 30 lakh+)
- Maintain a sophisticated yet warm tone
- Keep it concise and professional

Return ONLY the question, nothing else. Do not add quotes."""
        
        try:
            response_obj = llm.invoke(clarification_prompt)
            clarification_question = response_obj.content.strip()
            
            # Remove quotes if LLM adds them
            if clarification_question.startswith('"') and clarification_question.endswith('"'):
                clarification_question = clarification_question[1:-1]
            if clarification_question.startswith("'") and clarification_question.endswith("'"):
                clarification_question = clarification_question[1:-1]
            
            logger.info(f"Generated clarification question for {next_slot_to_ask}: {clarification_question}")
            
            return {
                "response": clarification_question,
                "rationale": f"Need to clarify {next_slot_to_ask} to proceed",
                "next_step": None
            }
        except Exception as e:
            logger.error(f"Error generating clarification question: {str(e)}", exc_info=True)
            # Fallback to simple question
            fallback_question = clarification_prompts.get(next_slot_to_ask, "Could you provide more details about your preferences?")
            return {
                "response": fallback_question,
                "rationale": f"Need to clarify {next_slot_to_ask} to proceed",
                "next_step": None
            }
    else:
        # Generate answer from LLM's knowledge with rationale and next step
        user_message = state.get("request", "")
        extracted_slots = {
            "budget_max": state.get("budget_max"),
            "seats_min": state.get("seats_min"),
            "fuel": state.get("fuel"),
            "body": state.get("body"),
            "transmission_ban": state.get("transmission_ban", []),
            "brand": state.get("brand"),
            "model": state.get("model"),
        }
        
        # Format budget string in Indian format (lakhs/crores)
        budget_str = "Not specified"
        if extracted_slots['budget_max']:
            budget_value = extracted_slots['budget_max']
            if budget_value >= 10000000:  # 1 crore or more
                budget_str = f"₹{budget_value/10000000:.1f} crore"
            elif budget_value >= 100000:  # 1 lakh or more
                budget_str = f"₹{budget_value/100000:.1f} lakh"
            else:
                budget_str = f"₹{budget_value:,.0f}"
        
        response_prompt = f"""You are an elegant and professional sales consultant at a premium luxury car showroom in India, helping a discerning Indian customer purchase a luxury vehicle. Use refined Indian English, Indian currency (INR/₹), and premium terminology appropriate for a luxury showroom.

Customer's message: "{user_message}"

Customer's preferences so far:
- Budget: {budget_str}
- Body type: {extracted_slots['body'] or 'Not specified'}
- Seats: {extracted_slots['seats_min'] or 'Not specified'}
- Fuel type: {extracted_slots['fuel'] or 'Not specified'}
- Brand: {extracted_slots['brand'] or 'Not specified'}
- Model: {extracted_slots['model'] or 'Not specified'}
- Avoid transmissions: {', '.join(extracted_slots['transmission_ban']) if extracted_slots['transmission_ban'] else 'None'}

Current stage: {state.get('stage', 'needs_analysis')}

Guidelines for your response:
- Use Indian English appropriate for a luxury showroom (e.g., "petrol" not "gas", "lakh" not "hundred thousand")
- Use Indian currency format (₹ and lakhs/crores where appropriate)
- Be professional and respectful
- Reference luxury/premium car brands available in India: Mercedes-Benz, BMW, Audi, Jaguar, Land Rover, Range Rover, Volvo, Lexus, Porsche, Bentley, Rolls-Royce, Maserati, etc.
- Use premium terminology: "luxury sedan", "premium SUV", "high-end", "prestigious", "sophisticated", "refined"
- Reference luxury features: "premium interiors", "advanced technology", "superior craftsmanship", "exclusive", "bespoke"
- Use terms like "on-road price", "ex-showroom", "mileage" (not "fuel economy")
- Mention luxury services: "test drive", "personalized consultation", "exclusive showroom visit", "customization options"

Provide a sophisticated response that:
1. Provides relevant information or recommendations about luxury vehicles based on what they've shared (consider Indian luxury car market context)
2. Highlights premium features, craftsmanship, and exclusivity when relevant
4. Suggests a clear next step (e.g., test drive, showroom visit, detailed consultation)

Format your response as JSON:
{{
  "response": "<your response to the customer>",
  "rationale": "<brief reason for this response>",
  "next_step": "<suggested next step>"
}}

Only return the JSON object, no other text."""
        
        try:
            response_obj = llm.invoke(response_prompt)
            response_text = response_obj.content.strip()
            
            # Extract JSON from response
            start_idx = response_text.find('{')
            if start_idx != -1:
                brace_count = 0
                end_idx = start_idx
                for i in range(start_idx, len(response_text)):
                    if response_text[i] == '{':
                        brace_count += 1
                    elif response_text[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            end_idx = i + 1
                            break
                if end_idx > start_idx:
                    response_text = response_text[start_idx:end_idx]
            
            response_data = json.loads(response_text)
            
            logger.info(f"Generated response - Rationale: {response_data.get('rationale', 'N/A')[:50]}..., Next step: {response_data.get('next_step', 'N/A')[:50]}...")
            
            return {
                "response": response_data.get("response", "I'm here to help you find the perfect car!"),
                "rationale": response_data.get("rationale", ""),
                "next_step": response_data.get("next_step", "")
            }
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON from LLM response: {response_text[:200] if 'response_text' in locals() else 'N/A'}... Error: {str(e)}")
            # Fallback response
            return {
                "response": "I understand you're looking for a luxury vehicle. Let me help you find the perfect premium car that matches your discerning taste and requirements!",
                "rationale": "Generated fallback response",
                "next_step": "Continue gathering preferences"
            }
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}", exc_info=True)
            return {
                "response": "I'm here to assist you in finding the perfect luxury car! Please share your preferences, and I'll provide personalized recommendations from our premium collection.",
                "rationale": "Error occurred, using fallback",
                "next_step": "Continue conversation"
            }

# Node 4: advance_stage - update procedural stage and suggest test drive
def advance_stage(state: State) -> State:
    logger.info("Node: advance_stage - Updating procedural stage")
    
    current_stage = state.get("stage")
    model = state.get("model")
    brand = state.get("brand")
    
    # If model is decided and we haven't suggested test drive yet, suggest test drive date
    if model and current_stage != "test_drive":
        logger.info(f"Model decided: {brand} {model} - Suggesting test drive date")
        
        # Generate test drive date suggestion
        # Suggest dates: today + 2 days, today + 3 days, today + 5 days
        today = datetime.now()
        suggested_dates = [
            (today + timedelta(days=2)).strftime("%d %B %Y"),  # Day after tomorrow
            (today + timedelta(days=3)).strftime("%d %B %Y"),  # 3 days from now
            (today + timedelta(days=5)).strftime("%d %B %Y"),  # 5 days from now
        ]
        
        # Format dates in Indian style
        date_options = ", ".join([f"{date}" for date in suggested_dates])
        
        test_drive_prompt = f"""You are an elegant sales consultant at a premium luxury car showroom in India. The customer has decided on the {brand} {model}. 

Generate a warm, professional message suggesting a test drive with the following available dates: {date_options}.

Guidelines:
- Use refined Indian English
- Be enthusiastic but professional
- Mention the specific model: {brand} {model}
- Present the dates in a friendly way
- Suggest they can choose a convenient time
- Mention that you can arrange a personalized test drive experience

Return ONLY the message text, nothing else. Make it conversational and warm."""
        
        try:
            response_obj = llm.invoke(test_drive_prompt)
            test_drive_message = response_obj.content.strip()
            
            # Remove quotes if LLM adds them
            if test_drive_message.startswith('"') and test_drive_message.endswith('"'):
                test_drive_message = test_drive_message[1:-1]
            if test_drive_message.startswith("'") and test_drive_message.endswith("'"):
                test_drive_message = test_drive_message[1:-1]
            
            logger.info(f"Generated test drive suggestion for {brand} {model}")
            
            return {
                "stage": "test_drive",
                "response": test_drive_message,
                "rationale": f"Customer decided on {brand} {model}, suggesting test drive dates",
                "next_step": "Schedule test drive"
            }
        except Exception as e:
            logger.error(f"Error generating test drive suggestion: {str(e)}", exc_info=True)
            # Fallback message
            fallback_message = f"Excellent choice! The {brand} {model} is a remarkable vehicle. I'd be delighted to arrange a test drive for you. We have availability on {date_options}. Which date works best for you?"
            return {
                "stage": "test_drive",
                "response": fallback_message,
                "rationale": "Model decided, suggesting test drive (fallback)",
                "next_step": "Schedule test drive"
            }
    else:
        # Update stage to next logical step
        if not current_stage:
            new_stage = "needs_analysis"
        elif current_stage == "needs_analysis":
            new_stage = "shortlist"
        else:
            new_stage = current_stage
        
        logger.info(f"Advancing stage from {current_stage} to {new_stage}")
        return {
            "stage": new_stage
        }

def route_after_respond(state: State) -> str:
    """Route after respond based on ensure_readiness decision.
    
    If need_clarification is True: loop back to parse_slots to continue asking questions.
    If need_clarification is False: we have all required slots, so advance to next stage.
    If model is decided: advance to test drive suggestion stage.
    """
    need_clarification = state.get("need_clarification", False)
    model = state.get("model")
    current_stage = state.get("stage")
    
    if need_clarification:
        # ensure_readiness determined we need clarification
        # respond node asked a question - loop back to parse_slots to continue
        # Note: This will wait for user's next message in the next turn
        logger.debug("Looping back to parse_slots (clarification needed)")
        return END  # End this turn, user will respond, then next turn goes through parse_slots again
    elif model and current_stage != "test_drive":
        # Model is decided and we haven't suggested test drive yet
        # Advance to suggest test drive dates
        logger.debug(f"Model {model} decided - Advancing to test drive suggestion")
        return "advance_stage"
    else:
        # ensure_readiness determined we're ready (all required slots filled)
        # respond node provided recommendations - advance to next stage
        logger.debug("Advancing to next stage (all required slots filled)")
        return "advance_stage"

def build_workflow():
    workflow = StateGraph(State)
    
    # Add all nodes
    workflow.add_node("parse_slots", parse_slots)
    workflow.add_node("ensure_readiness", ensure_readiness)
    workflow.add_node("respond", respond)
    workflow.add_node("advance_stage", advance_stage)
    
    # Define the flow
    workflow.set_entry_point("parse_slots")
    workflow.add_edge("parse_slots", "ensure_readiness")
    workflow.add_edge("ensure_readiness", "respond")
    workflow.add_conditional_edges(
        "respond",
        route_after_respond,
        {
            "advance_stage": "advance_stage",
            END: END
        }
    )
    
    workflow.set_finish_point("advance_stage")
    
    # Compile with checkpointer if available
    # Note: LangGraph's compile() accepts the checkpointer directly
    if checkpointer:
        compiled_graph = workflow.compile(checkpointer=checkpointer)
        logger.debug("Workflow compiled successfully with Redis checkpointer")
    else:
        compiled_graph = workflow.compile()
        logger.warning("Workflow compiled without checkpointer - state will not persist")
    
    return compiled_graph



def handle_turn(session_id: str, user_id: str, message: str) -> str:
    logger.info(f"Handling turn - Session: {session_id}, User: {user_id}, Message length: {len(message)}")
    
    # Use session_id as thread_id for Redis checkpointer
    # If session_id is None or empty, use a default
    thread_id = session_id or f"user_{user_id or 'unknown'}"
    
    try:
        graph = build_workflow()
        logger.debug(f"Workflow built, invoking with thread_id: {thread_id}")
        
        # Use config with thread_id for state persistence
        config = {"configurable": {"thread_id": thread_id}}
        
        # Get existing state from checkpointer if available
        existing_state = None
        if checkpointer:
            try:
                # Try to get the current state for this thread
                checkpoint = graph.get_state(config)
                if checkpoint and checkpoint.values:
                    existing_state = checkpoint.values
                    logger.debug(f"Restored state for thread_id: {thread_id} - Budget: {existing_state.get('budget_max')}, Body: {existing_state.get('body')}")
            except Exception as e:
                logger.debug(f"No existing state found for thread_id: {thread_id} (this is normal for new sessions)")
        
        # Initialize state - merge with existing state if available
        if existing_state:
            # Merge existing state with new request
            initial_state: State = {
                "request": message,  # New user message
                "budget_max": existing_state.get("budget_max"),
                "seats_min": existing_state.get("seats_min"),
                "fuel": existing_state.get("fuel"),
                "body": existing_state.get("body"),
                "transmission_ban": existing_state.get("transmission_ban", []),
                "brand": existing_state.get("brand"),
                "model": existing_state.get("model"),
                "need_clarification": False,  # Reset for new turn
                "missing_slots": None,  # Reset temporary field
                "stage": existing_state.get("stage"),  # Preserve stage
                "response": None,  # Reset for new turn
                "rationale": None,  # Reset for new turn
                "next_step": None,  # Reset for new turn
            }
        else:
            # Initialize new state for this session
            initial_state: State = {
                "request": message,
                "budget_max": None,
                "seats_min": None,
                "fuel": None,
                "body": None,
                "transmission_ban": [],
                "brand": None,
                "model": None,
                "need_clarification": False,
                "missing_slots": None,
                "stage": None,
                "response": None,
                "rationale": None,
                "next_step": None,
            }
            logger.debug(f"Created new state for thread_id: {thread_id}")
        
        # Invoke the graph - checkpointer is already compiled into the graph
        # The config with thread_id ensures state is persisted per session
        final_state = graph.invoke(initial_state, config=config)
        
        response = final_state.get("response", "I'm processing your request.")
        logger.info(f"Turn completed - Session: {session_id}, Response length: {len(response) if response else 0}")
        logger.debug(f"State persisted for thread_id: {thread_id} - Budget: {final_state.get('budget_max')}, Body: {final_state.get('body')}")
        return response
    except Exception as e:
        logger.error(f"Error in handle_turn - Session: {session_id}, Error: {str(e)}", exc_info=True)
        raise


def delete_all_sessions() -> bool:
    """Delete all Redis checkpoint entries.
    
    WARNING: This will delete ALL session states. Use with caution.
    
    Returns:
        bool: True if deletion was successful, False otherwise
    """
    if not redis_uri:
        logger.warning("Cannot delete all sessions: Redis URI not configured")
        return False
    
    try:
        logger.warning("Deleting ALL Redis checkpoint entries - this action cannot be undone")
        
        # Create a Redis client directly from the connection string
        redis_client = redis.from_url(redis_uri, decode_responses=False)
        
        # Delete all keys matching the checkpoint pattern
        # RedisSaver typically uses keys with "checkpoint:" prefix
        pattern = "checkpoint:*"
        
        # Use SCAN instead of KEYS for better performance
        deleted_count = 0
        cursor = 0
        
        while True:
            cursor, keys = redis_client.scan(cursor, match=pattern, count=100)
            if keys:
                # Delete all matching keys
                # Keys are already bytes from scan, so we can delete them directly
                deleted = redis_client.delete(*keys)
                deleted_count += deleted
            if cursor == 0:
                break
        
        # Also try to delete keys with other possible patterns
        # Some RedisSaver implementations might use different prefixes
        additional_patterns = ["checkpoint_*", "langgraph:*", "thread:*"]
        for pattern in additional_patterns:
            cursor = 0
            while True:
                cursor, keys = redis_client.scan(cursor, match=pattern, count=100)
                if keys:
                    deleted = redis_client.delete(*keys)
                    deleted_count += deleted
                if cursor == 0:
                    break
        
        if deleted_count > 0:
            logger.info(f"Deleted {deleted_count} checkpoint entries from Redis")
        else:
            logger.info("No checkpoint entries found to delete")
        
        redis_client.close()
        return True
            
    except Exception as e:
        logger.error(f"Error deleting all sessions: {str(e)}", exc_info=True)
        return False


