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
from agent_memory_client import create_memory_client, MemoryAPIClient, MemoryClientConfig
from agent_memory_client.models import WorkingMemory, MemoryMessage, ClientMemoryRecord, MemoryTypeEnum
import asyncio

load_dotenv()

# Configure logger for orchestrator
logger = logging.getLogger(__name__)

class State(TypedDict):
    # User input
    request: str
    user_id: Optional[str]  # User identifier for working memory
    session_id: Optional[str]  # Session identifier for working memory
    
    # Slots (extracted information)
    budget_max: Optional[float]
    seats_min: Optional[int]
    fuel: Optional[str]  # "gas", "electric", "hybrid", etc.
    body: Optional[str]  # "sedan", "suv", "truck", etc.
    transmission_ban: Annotated[List[str], operator.add]  # List of banned transmission types
    brand: Optional[str]
    model: Optional[str]
    test_drive_completed: Optional[bool]  # Track if test drive is completed
    
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

# Initialize Agent Memory Client for working memory
memory_server_url = os.getenv("MEMORY_SERVER_URL", "http://localhost:8000")
memory_client = None

# Note: create_memory_client is async, so we'll create it lazily when needed
# For now, we'll use the sync initialization pattern
try:
    config = MemoryClientConfig(base_url=memory_server_url)
    memory_client = MemoryAPIClient(config=config)
    logger.info(f"Agent Memory Client initialized successfully - Server: {memory_server_url}")
except Exception as e:
    logger.warning(f"Failed to initialize Agent Memory Client: {str(e)}. Working memory will not be available.")
    memory_client = None

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
        "test_drive_completed": state.get("test_drive_completed", False),
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
- test_drive_completed: Boolean - set to true if user mentions they completed the test drive, scheduled a test drive, confirmed test drive date, or said they're ready to proceed after test drive. Extract from phrases like "test drive done", "completed test drive", "test drive was great", "ready to buy", "let's proceed", "I've driven it"

Note: Convert Indian number formats - "lakh" = 100000, "crore" = 10000000. "50 lakh" = 5000000, "1.5 crore" = 15000000. This is a luxury showroom, so budgets are typically in higher ranges (30 lakh+).

Return JSON format:
{{
  "budget_max": <number or null>,
  "seats_min": <integer or null>,
  "fuel": <string or null>,
  "body": <string or null>,
  "transmission_ban": <array of strings or empty array>,
  "brand": <string or null>,
  "model": <string or null>,
  "test_drive_completed": <boolean or null>
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
        
        # Handle test_drive_completed
        if extracted_slots.get("test_drive_completed") is not None:
            updated_slots["test_drive_completed"] = bool(extracted_slots["test_drive_completed"])
        elif existing_slots.get("test_drive_completed") is not None:
            updated_slots["test_drive_completed"] = existing_slots["test_drive_completed"]
        
        logger.info(f"Parsed slots - Budget: {updated_slots.get('budget_max')}, Seats: {updated_slots.get('seats_min')}, Fuel: {updated_slots.get('fuel')}, Body: {updated_slots.get('body')}, Brand: {updated_slots.get('brand')}, Model: {updated_slots.get('model')}, Test Drive: {updated_slots.get('test_drive_completed')}")
        
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
        
        clarification_prompt = f"""You are a professional sales consultant at a premium luxury car showroom in India. Generate a single, refined, and sophisticated question in Indian English to ask the customer about their {slot_descriptions.get(next_slot_to_ask, next_slot_to_ask)} preference for purchasing a luxury car.
        
Context: They're looking to buy a luxury/premium car and we need to know their {next_slot_to_ask}.
Current known preferences: Budget: {state.get('budget_max')} INR, Body: {state.get('body')}, Seats: {state.get('seats_min')}, Fuel: {state.get('fuel')}, Brand: {state.get('brand')}, Model: {state.get('model')}

Guidelines:
- Use refined Indian English appropriate for a luxury showroom
- Use premium terminology (e.g., "luxury sedan", "premium SUV", "high-end")
- For budget questions, mention "lakh" or "crore" as appropriate (luxury cars typically 30 lakh+)
- Maintain a sophisticated yet warm tone
- Keep it concise and professional
- Keep it conversational - NO formal email greetings like "Dear Customer" or "Dear [Customer]"
- NO formal closings like "Warm regards", "Best regards", "[Your Name]", "Sales Consultant at [Showroom Name]", or any signatures

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
- Reference luxury features: "premium interiors", "advanced technology", "superior craftsmanship", "exclusive", "bespoke"
- Use terms like "on-road price", "ex-showroom", "mileage" (not "fuel economy")
- Mention luxury services: "test drive", "personalized consultation", "exclusive showroom visit", "customization options"
- Keep it conversational and chat-like - NO formal email greetings like "Dear Customer" or "Dear [Customer]"
- NO formal closings like "Warm regards", "Best regards", "[Your Name]", "Sales Consultant at [Showroom Name]", or any signatures
- Write as if you're chatting directly with the customer, not writing an email

Provide a sophisticated response that:
1. Provides relevant information or recommendations about luxury vehicles based on what they've shared (consider Indian luxury car market context)
2. Highlights premium features, craftsmanship, and exclusivity when relevant
3. Suggests a clear next step (e.g., test drive, showroom visit, detailed consultation)

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

# Node 4: suggest_test_drive - suggest test drive dates when model is decided
def suggest_test_drive(state: State) -> State:
    logger.info("Node: suggest_test_drive - Suggesting test drive dates")
    
    model = state.get("model")
    brand = state.get("brand")
    
    if not model:
        logger.warning("No model selected, cannot suggest test drive")
        return {
            "response": "I'd be happy to arrange a test drive once you've selected a model. Which vehicle are you interested in?",
            "rationale": "No model selected for test drive",
            "next_step": "Select a model"
        }
    
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
    
    test_drive_prompt = f"""You are an elegant sales consultant at a premium luxury car showroom in India chatting with a customer. The customer has decided on the {brand} {model}. 

Generate a warm, professional chat message suggesting a test drive with the following available dates: {date_options}.

Guidelines:
- Use refined Indian English
- Be enthusiastic but professional
- Mention the specific model: {brand} {model}
- Present the dates in a friendly way
- Suggest they can choose a convenient time
- Mention that you can arrange a personalized test drive experience
- Keep it conversational and chat-like - NO formal email greetings like "Dear Customer" or "Dear [Customer]"
- NO formal closings like "Warm regards", "Best regards", "[Your Name]", "Sales Consultant at [Showroom Name]", or any signatures
- Write as if you're chatting directly with the customer

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

# Node 5: suggest_financing - suggest financing options when test drive is completed
def suggest_financing(state: State) -> State:
    logger.info("Node: suggest_financing - Suggesting financing options")
    
    model = state.get("model")
    brand = state.get("brand")
    budget_max = state.get("budget_max")
    test_drive_completed = state.get("test_drive_completed", False)
    
    if not test_drive_completed:
        logger.warning("Test drive not completed, cannot suggest financing")
        return {
            "response": "I'd be happy to discuss financing options once you've completed the test drive. Have you scheduled your test drive yet?",
            "rationale": "Test drive not completed",
            "next_step": "Complete test drive"
        }
    
    if not model or not budget_max:
        logger.warning("Missing model or budget, cannot calculate financing")
        return {
            "response": "I'd be happy to discuss financing options. Could you please confirm the model and budget you're interested in?",
            "rationale": "Missing model or budget for financing",
            "next_step": "Provide model and budget details"
        }
    
    logger.info(f"Test drive completed - Suggesting financing options for {brand} {model}")
    
    # Calculate financing options
    # Typical financing: 10-20% down payment, 3-7 years tenure, 8-12% interest rate
    down_payment_10 = budget_max * 0.10
    down_payment_20 = budget_max * 0.20
    loan_amount_10 = budget_max - down_payment_10
    loan_amount_20 = budget_max - down_payment_20
    
    # Format in Indian currency
    def format_currency(amount):
        if amount >= 10000000:
            return f"₹{amount/10000000:.2f} crore"
        elif amount >= 100000:
            return f"₹{amount/100000:.2f} lakh"
        else:
            return f"₹{amount:,.0f}"
    
    financing_prompt = f"""You are a sales consultant at a premium luxury car showroom in India chatting with a customer. The customer has completed the test drive for the {brand} {model} and is ready to discuss financing.

Vehicle: {brand} {model}
On-road price: {format_currency(budget_max)}

Financing options:
- Down Payment: {format_currency(down_payment_10)} (10%) or {format_currency(down_payment_20)} (20%)
- Loan Amount: {format_currency(loan_amount_10)} (with 10% down) or {format_currency(loan_amount_20)} (with 20% down)
- Tenure: 3, 5, or 7 years
- Interest Rate: Starting from 8.5% per annum
- Processing Fee: Waived
- Special: Zero down payment option available (subject to eligibility)

Generate a SHORT, conversational chat message (2-3 sentences max) presenting these financing options.

Guidelines:
- Keep it brief and chat-like, NOT a formal email or letter
- Use conversational Indian English
- Be friendly and enthusiastic
- NO formal greetings like "Dear Customer", "Dear [Customer]", or any email-style greetings
- NO formal closings like "Warm regards", "Best regards", "[Your Name]", "Sales Consultant at [Showroom Name]", or any signatures
- Just present the key options naturally in a chat format
- End with a question to engage the customer
- Write as if you're chatting directly with the customer

Return ONLY the message text, nothing else. Keep it under 100 words."""
    
    try:
        response_obj = llm.invoke(financing_prompt)
        financing_message = response_obj.content.strip()
        
        # Remove quotes if LLM adds them
        if financing_message.startswith('"') and financing_message.endswith('"'):
            financing_message = financing_message[1:-1]
        if financing_message.startswith("'") and financing_message.endswith("'"):
            financing_message = financing_message[1:-1]
        
        logger.info(f"Generated financing suggestion for {brand} {model}")
        
        return {
            "stage": "financing",
            "response": financing_message,
            "rationale": f"Test drive completed for {brand} {model}, suggesting financing options",
            "next_step": "Discuss financing details"
        }
    except Exception as e:
        logger.error(f"Error generating financing suggestion: {str(e)}", exc_info=True)
        # Fallback message
        fallback_message = f"Great! Hope you enjoyed the test drive of the {brand} {model}. We have flexible financing options - you can choose between 10% or 20% down payment, with interest rates starting from 8.5% and tenure options of 3, 5, or 7 years. We also have a zero down payment option for eligible customers. Which option interests you?"
        return {
            "stage": "financing",
            "response": fallback_message,
            "rationale": "Test drive completed, suggesting financing (fallback)",
            "next_step": "Discuss financing details"
        }

# Node 6: advance_stage - update procedural stage
def advance_stage(state: State) -> State:
    logger.info("Node: advance_stage - Updating procedural stage")
    
    current_stage = state.get("stage")
    
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

# Node 7: save_to_working_memory - save conversation history to agent memory server
def save_to_working_memory(state: State) -> State:
    """Save conversation history to agent memory server working memory.
    
    This allows the memory server to automatically extract memories in the background.
    Saves both user_id and session_id for inter-session memory support.
    """
    if not memory_client:
        logger.debug("Memory client not available, skipping working memory save")
        return {}
    
    try:
        user_message = state.get("request", "")
        assistant_response = state.get("response", "")
        user_id = state.get("user_id")
        session_id = state.get("session_id")
        
        if not user_message or not assistant_response:
            logger.debug("No messages to save to working memory")
            return {}
        
        if not user_id or not session_id:
            logger.warning("user_id or session_id not available, cannot save to working memory")
            return {}
        
        # Create messages to append
        messages_to_append = [
            MemoryMessage(role="user", content=user_message),
            MemoryMessage(role="assistant", content=assistant_response)
        ]
        
        # Helper function to run async code
        def run_async(coro):
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If loop is already running, skip for now
                    logger.debug("Event loop already running, skipping working memory save")
                    return None
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            return loop.run_until_complete(coro)
        
        # Append messages to working memory using the convenience method
        async def append_messages():
            result = await memory_client.append_messages_to_working_memory(
                session_id=session_id,
                messages=messages_to_append,
                user_id=user_id
            )
            logger.info(f"Saved conversation turn to working memory - Session: {session_id}, User: {user_id}")
            return result
        
        result = run_async(append_messages())
        if result:
            logger.debug(f"Working memory updated successfully for session {session_id}")
        
        # Store important stage information as long-term memory
        current_stage = state.get("stage")
        test_drive_completed = state.get("test_drive_completed", False)
        brand = state.get("brand", "Unknown")
        model = state.get("model", "Unknown")
        
        # Track important stage transitions and milestones
        stage_memories_to_store = []
        
        if current_stage == "test_drive":
            # Test drive has been scheduled
            stage_memory_text = f"Customer is at test drive stage for {brand} {model}. Test drive has been scheduled."
            stage_memories_to_store.append(ClientMemoryRecord(
                text=stage_memory_text,
                user_id=user_id,
                session_id=session_id,
                memory_type=MemoryTypeEnum.EPISODIC,
                topics=["car_purchase", "stage", "test_drive", "scheduled"],
                entities=[brand, model] if brand != "Unknown" else []
            ))
        
        if test_drive_completed:
            # Test drive has been completed
            test_drive_memory_text = f"Customer completed test drive for {brand} {model}."
            stage_memories_to_store.append(ClientMemoryRecord(
                text=test_drive_memory_text,
                user_id=user_id,
                session_id=session_id,
                memory_type=MemoryTypeEnum.EPISODIC,
                topics=["car_purchase", "stage", "test_drive", "completed"],
                entities=[brand, model] if brand != "Unknown" else []
            ))
        
        if current_stage == "financing":
            # Customer is at financing stage
            financing_memory_text = f"Customer is at financing stage for {brand} {model}."
            if test_drive_completed:
                financing_memory_text = f"Customer completed test drive for {brand} {model} and is now at financing stage."
            stage_memories_to_store.append(ClientMemoryRecord(
                text=financing_memory_text,
                user_id=user_id,
                session_id=session_id,
                memory_type=MemoryTypeEnum.EPISODIC,
                topics=["car_purchase", "stage", "financing"],
                entities=[brand, model] if brand != "Unknown" else []
            ))
        
        # Store all stage memories
        if stage_memories_to_store:
            async def save_stage_memories():
                result = await memory_client.create_long_term_memory(stage_memories_to_store)
                logger.info(f"Stored {len(stage_memories_to_store)} stage memory/memories for user {user_id}")
                return result
            
            stage_result = run_async(save_stage_memories())
            if stage_result:
                logger.debug(f"Stage memories stored successfully for user {user_id}")
        
    except Exception as e:
        logger.warning(f"Error saving to working memory: {str(e)}", exc_info=True)
    
    return {}

def route_after_respond(state: State) -> str:
    """Route after respond based on ensure_readiness decision.
    
    If need_clarification is True: loop back to parse_slots to continue asking questions.
    If test drive is completed: advance to financing suggestion.
    If model is decided: advance to test drive suggestion.
    Otherwise: advance to next stage.
    """
    need_clarification = state.get("need_clarification", False)
    model = state.get("model")
    current_stage = state.get("stage")
    test_drive_completed = state.get("test_drive_completed", False)
    
    if need_clarification:
        # ensure_readiness determined we need clarification
        # respond node asked a question - loop back to parse_slots to continue
        # Note: This will wait for user's next message in the next turn
        logger.debug("Looping back to parse_slots (clarification needed)")
        return END  # End this turn, user will respond, then next turn goes through parse_slots again
    elif test_drive_completed and current_stage == "test_drive":
        # Test drive is completed, advance to financing
        logger.debug("Test drive completed - Advancing to financing suggestion")
        return "suggest_financing"
    elif model and current_stage != "test_drive" and current_stage != "financing":
        # Model is decided and we haven't suggested test drive yet
        # Advance to suggest test drive dates
        logger.debug(f"Model {model} decided - Advancing to test drive suggestion")
        return "suggest_test_drive"
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
    workflow.add_node("suggest_test_drive", suggest_test_drive)
    workflow.add_node("suggest_financing", suggest_financing)
    workflow.add_node("advance_stage", advance_stage)
    workflow.add_node("save_to_working_memory", save_to_working_memory)
    
    # Define the flow
    workflow.set_entry_point("parse_slots")
    workflow.add_edge("parse_slots", "ensure_readiness")
    workflow.add_edge("ensure_readiness", "respond")
    workflow.add_conditional_edges(
        "respond",
        route_after_respond,
        {
            "suggest_test_drive": "suggest_test_drive",
            "suggest_financing": "suggest_financing",
            "advance_stage": "advance_stage",
            END: "save_to_working_memory"
        }
    )
    
    # All nodes route to save_to_working_memory before ending
    # This ensures conversation history is saved after every turn
    workflow.add_edge("suggest_test_drive", "save_to_working_memory")
    workflow.add_edge("suggest_financing", "save_to_working_memory")
    workflow.add_edge("advance_stage", "save_to_working_memory")
    workflow.add_edge("save_to_working_memory", END)
    
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
                "user_id": user_id,  # Pass user_id for working memory
                "session_id": session_id,  # Pass session_id for working memory
                "budget_max": existing_state.get("budget_max"),
                "seats_min": existing_state.get("seats_min"),
                "fuel": existing_state.get("fuel"),
                "body": existing_state.get("body"),
                "transmission_ban": existing_state.get("transmission_ban", []),
                "brand": existing_state.get("brand"),
                "model": existing_state.get("model"),
                "test_drive_completed": existing_state.get("test_drive_completed"),
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
                "user_id": user_id,  # Pass user_id for working memory
                "session_id": session_id,  # Pass session_id for working memory
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
                "test_drive_completed": None,
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
    """Delete all Redis checkpoint entries and long-term memories.
    
    WARNING: This will delete ALL session states and long-term memories. Use with caution.
    
    Returns:
        bool: True if deletion was successful, False otherwise
    """
    if not redis_uri:
        logger.warning("Cannot delete all sessions: Redis URI not configured")
        return False
    
    try:
        logger.warning("Deleting ALL Redis checkpoint entries and long-term memories - this action cannot be undone")
        
        # Create a Redis client directly from the connection string
        redis_client = redis.from_url(redis_uri, decode_responses=False)
        
        total_deleted = 0
        
        # Delete all keys matching the checkpoint pattern
        # RedisSaver typically uses keys with "checkpoint:" prefix
        checkpoint_patterns = ["checkpoint:*", "checkpoint_*", "langgraph:*", "thread:*"]
        
        for pattern in checkpoint_patterns:
            deleted_count = 0
            cursor = 0
            
            while True:
                cursor, keys = redis_client.scan(cursor, match=pattern, count=100)
                if keys:
                    # Delete all matching keys
                    deleted = redis_client.delete(*keys)
                    deleted_count += deleted
                if cursor == 0:
                    break
            
            if deleted_count > 0:
                logger.info(f"Deleted {deleted_count} checkpoint entries matching pattern: {pattern}")
                total_deleted += deleted_count
        
        # Delete long-term memory keys from agent memory server
        # Long-term memory keys start with "memory*"
        memory_pattern = "memory*"
        memory_deleted_count = 0
        cursor = 0
        
        while True:
            cursor, keys = redis_client.scan(cursor, match=memory_pattern, count=100)
            if keys:
                deleted = redis_client.delete(*keys)
                memory_deleted_count += deleted
            if cursor == 0:
                break
        
        if memory_deleted_count > 0:
            logger.info(f"Deleted {memory_deleted_count} long-term memory entries from Redis")
            total_deleted += memory_deleted_count
        
        if total_deleted > 0:
            logger.info(f"Total deleted: {total_deleted} entries (checkpoints + long-term memories)")
        else:
            logger.info("No entries found to delete")
        
        redis_client.close()
        return True
            
    except Exception as e:
        logger.error(f"Error deleting all session data: {str(e)}", exc_info=True)
        return False


