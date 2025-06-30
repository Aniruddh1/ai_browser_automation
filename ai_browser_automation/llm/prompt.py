"""Prompt builders for LLM interactions - matches TypeScript implementation."""

from typing import Optional, Dict, List
from ..types import LLMMessage


def build_user_instructions_string(user_provided_instructions: Optional[str] = None) -> str:
    """
    Build user instructions string to append to prompts.
    Matches TypeScript's buildUserInstructionsString.
    """
    if not user_provided_instructions:
        return ""
    
    return f"""

# Custom Instructions Provided by the User
    
Please keep the user's instructions in mind when performing actions. If the user's instructions are not relevant to the current task, ignore them.

User Instructions:
{user_provided_instructions}"""


def build_extract_system_prompt(
    is_using_print_extracted_data_tool: bool = False,
    user_provided_instructions: Optional[str] = None
) -> LLMMessage:
    """
    Build system prompt for extraction.
    Matches TypeScript's buildExtractSystemPrompt.
    """
    base_content = """You are extracting content on behalf of a user.
  If a user asks you to extract a 'list' of information, or 'all' information, 
  YOU MUST EXTRACT ALL OF THE INFORMATION THAT THE USER REQUESTS.
   
  You will be given:
1. An instruction
2. """
    
    content_detail = "A list of DOM elements to extract from."
    
    instructions = """Print the exact text from the DOM elements with all symbols, characters, and endlines as is.
Print null or an empty string if no new information is found.""".strip()
    
    tool_instructions = """ONLY print the content using the print_extracted_data tool provided.
ONLY print the content using the print_extracted_data tool provided.""".strip() if is_using_print_extracted_data_tool else ""
    
    additional_instructions = ("If a user is attempting to extract links or URLs, you MUST respond with ONLY the IDs of the link elements. \n"
                             "Do not attempt to extract links directly from the text unless absolutely necessary. ")
    
    user_instructions = build_user_instructions_string(user_provided_instructions)
    
    # Combine all parts and normalize whitespace
    parts = [base_content + content_detail, instructions]
    if tool_instructions:
        parts.append(tool_instructions)
    if additional_instructions:
        parts.append(additional_instructions)
    if user_instructions:
        parts.append(user_instructions)
    
    content = "\n\n".join(parts)
    # Normalize whitespace (matching TypeScript's .replace(/\s+/g, " "))
    import re
    content = re.sub(r'\s+', ' ', content)
    
    return LLMMessage(role="system", content=content)


def build_extract_user_prompt(
    instruction: str,
    dom_elements: str,
    is_using_print_extracted_data_tool: bool = False
) -> LLMMessage:
    """
    Build user prompt for extraction.
    Matches TypeScript's buildExtractUserPrompt.
    """
    content = f"""Instruction: {instruction}
DOM: {dom_elements}"""
    
    if is_using_print_extracted_data_tool:
        content += """
ONLY print the content using the print_extracted_data tool provided.
ONLY print the content using the print_extracted_data tool provided."""
    
    return LLMMessage(role="user", content=content)


def build_metadata_system_prompt() -> LLMMessage:
    """
    Build system prompt for metadata evaluation.
    Matches TypeScript's buildMetadataSystemPrompt.
    """
    metadata_system_prompt = """You are an AI assistant tasked with evaluating the progress and completion status of an extraction task.
Analyze the extraction response and determine if the task is completed or if more information is needed.
Strictly abide by the following criteria:
1. Once the instruction has been satisfied by the current extraction response, ALWAYS set completion status to true and stop processing, regardless of remaining chunks.
2. Only set completion status to false if BOTH of these conditions are true:
   - The instruction has not been satisfied yet
   - There are still chunks left to process (chunksTotal > chunksSeen)"""
    
    return LLMMessage(role="system", content=metadata_system_prompt)


def build_metadata_prompt(
    instruction: str,
    extraction_response: object,
    chunks_seen: int,
    chunks_total: int
) -> LLMMessage:
    """
    Build user prompt for metadata evaluation.
    Matches TypeScript's buildMetadataPrompt.
    """
    import json
    
    content = f"""Instruction: {instruction}
Extracted content: {json.dumps(extraction_response, indent=2)}
chunksSeen: {chunks_seen}
chunksTotal: {chunks_total}"""
    
    return LLMMessage(role="user", content=content)


def build_observe_system_prompt(user_provided_instructions: Optional[str] = None) -> LLMMessage:
    """
    Build system prompt for observation.
    Matches TypeScript's buildObserveSystemPrompt.
    """
    observe_system_prompt = """
You are helping the user automate the browser by finding elements based on what the user wants to observe in the page.

You will be given:
1. a instruction of elements to observe
2. a hierarchical accessibility tree showing the semantic structure of the page. The tree is a hybrid of the DOM and the accessibility tree.

Return an array of elements that match the instruction if they exist, otherwise return an empty array."""
    
    # Normalize whitespace
    import re
    content = re.sub(r'\s+', ' ', observe_system_prompt)
    
    # Add user instructions if provided
    parts = [content]
    user_instructions = build_user_instructions_string(user_provided_instructions)
    if user_instructions:
        parts.append(user_instructions)
    
    return LLMMessage(
        role="system",
        content="\n\n".join(parts)
    )


def build_observe_user_message(instruction: str, dom_elements: str) -> LLMMessage:
    """
    Build user message for observation.
    Matches TypeScript's buildObserveUserMessage.
    """
    content = f"""instruction: {instruction}
Accessibility Tree: \n{dom_elements}"""
    
    return LLMMessage(role="user", content=content)


def build_act_observe_prompt(
    action: str,
    supported_actions: List[str],
    variables: Optional[Dict[str, str]] = None
) -> str:
    """
    Build the instruction for the observeAct method to find the most relevant element for an action.
    Matches TypeScript's buildActObservePrompt.
    """
    # Base instruction
    instruction = f"""Find the most relevant element to perform an action on given the following action: {action}. 
  Provide an action for this element such as {', '.join(supported_actions)}, or any other playwright locator method. Remember that to users, buttons and links look the same in most cases.
  If the action is completely unrelated to a potential action to be taken on the page, return an empty array. 
  ONLY return one action. If multiple actions are relevant, return the most relevant one. 
  If the user is asking to scroll to a position on the page, e.g., 'halfway' or 0.75, etc, you must return the argument formatted as the correct percentage, e.g., '50%' or '75%', etc.
  If the user is asking to scroll to the next chunk/previous chunk, choose the nextChunk/prevChunk method. No arguments are required here.
  If the action implies a key press, e.g., 'press enter', 'press a', 'press space', etc., always choose the press method with the appropriate key as argument — e.g. 'a', 'Enter', 'Space'. Do not choose a click action on an on-screen keyboard. Capitalize the first character like 'Enter', 'Tab', 'Escape' only for special keys."""
    
    # Add variable names (not values) to the instruction if any
    if variables and len(variables) > 0:
        variable_names = ', '.join(f'%{key}%' for key in variables.keys())
        variables_prompt = f"The following variables are available to use in the action: {variable_names}. Fill the argument variables with the variable name."
        instruction += f" {variables_prompt}"
    
    return instruction


def build_operator_system_prompt(goal: str) -> LLMMessage:
    """
    Build system prompt for operator/agent.
    Matches TypeScript's buildOperatorSystemPrompt.
    """
    content = f"""You are a general-purpose agent whose job is to accomplish the user's goal across multiple model calls by running actions on the page.

You will be given a goal and a list of steps that have been taken so far. Your job is to determine if either the user's goal has been completed or if there are still steps that need to be taken.

# Your current goal
{goal}

# Important guidelines
1. Break down complex actions into individual atomic steps
2. For `act` commands, use only one action at a time, such as:
   - Single click on a specific element
   - Type into a single input field
   - Select a single option
3. Avoid combining multiple actions in one instruction
4. If multiple actions are needed, they should be separate steps"""
    
    return LLMMessage(role="system", content=content)