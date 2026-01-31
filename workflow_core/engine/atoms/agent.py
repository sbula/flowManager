# Copyright 2026 Steve Bula @ pitBula
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import Optional

def query(prompt: str, mock_response: Optional[str] = None) -> str:
    """
    Executes a query against the AI Agent.
    For V7 Implementation, this is a wrapper that prefers 'mock_response' if provided.
    In production, this would call the actual LLM API.
    """
    if mock_response:
        return mock_response.strip()
    
    # Placeholder for real LLM call
    # TODO: Integrate with real Agent API
    return "Agent Output (Mock)"

def run(args, context):
    prompt_text = args.get("prompt")
    mock = args.get("mock_response")
    
    if not prompt_text:
        raise ValueError("Agent Atom: Missing 'prompt' argument")
        
    result = query(prompt_text, mock)
    return {"response": result}
