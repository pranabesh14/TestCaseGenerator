import os
from typing import List, Dict, Optional
import requests
import json

class LLMHandler:
    """Handler for LLM interactions with security boundaries"""
    
    def __init__(self, model_name: str = "llama3", api_endpoint: str = None):
        """
        Initialize LLM handler
        
        Args:
            model_name: Name of the Llama model to use
            api_endpoint: API endpoint for the LLM (e.g., Ollama)
        """
        self.model_name = model_name
        self.api_endpoint = api_endpoint or os.getenv("LLM_API_ENDPOINT", "http://localhost:11434/api/generate")
        
        # System prompt with strict boundaries
        self.system_prompt = """You are a specialized AI assistant for test case generation ONLY. 

YOUR SOLE PURPOSE: Generate unit tests, regression tests, and functional tests for code.

STRICT BOUNDARIES:
- You can ONLY discuss and help with: test case generation, testing strategies, code analysis for testing purposes, test coverage, and testing best practices.
- You CANNOT: write production code (only test code), discuss non-testing topics, answer general questions, or perform any other tasks.
- If asked about anything unrelated to test generation, respond: "I can only assist with generating test cases. Please ask questions related to test case generation, code analysis, or testing strategies."

CAPABILITIES:
- Analyze code structure and logic
- Generate unit tests with assertions
- Create regression tests for changed code
- Design functional tests for features
- Suggest edge cases and boundary conditions
- Provide test coverage recommendations

Always generate test cases that are:
- Clear and well-documented
- Follow testing best practices
- Include proper assertions
- Cover edge cases
- Are maintainable and readable"""

    def _make_request(self, prompt: str, context: str = "") -> str:
        """Make request to LLM API with security checks"""
        
        # Combine system prompt with context and user prompt
        full_prompt = f"{self.system_prompt}\n\n"
        
        if context:
            full_prompt += f"CONTEXT:\n{context}\n\n"
        
        full_prompt += f"USER REQUEST:\n{prompt}\n\nRESPONSE:"
        
        # Retry logic
        max_retries = 3
        retry_delay = 2  # seconds
        
        for attempt in range(max_retries):
            try:
                # Example for Ollama API
                payload = {
                    "model": self.model_name,
                    "prompt": full_prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "top_p": 0.9,
                        "max_tokens": 1000,  # Reduced from 2000 for faster response
                        "num_predict": 1000,  # Ollama-specific: limit prediction length
                        "num_ctx": 2048      # Ollama-specific: context window
                    }
                }
                
                response = requests.post(
                    self.api_endpoint,
                    json=payload,
                    timeout=180  # Increased timeout to 3 minutes
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return result.get('response', '')
                else:
                    error_msg = f"API returned status code {response.status_code}"
                    if attempt < max_retries - 1:
                        print(f"Attempt {attempt + 1} failed: {error_msg}. Retrying in {retry_delay}s...")
                        import time
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                        continue
                    return f"Error: {error_msg}"
                    
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    print(f"Attempt {attempt + 1} timed out. Retrying with longer timeout...")
                    import time
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                return "Error: Request timed out after multiple attempts. Try using a smaller model (llama3:8b or llama3.2:3b) or reduce the code size."
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"Attempt {attempt + 1} failed: {str(e)}. Retrying...")
                    import time
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                return f"Error communicating with LLM: {str(e)}"
        
        return "Error: Max retries exceeded"
    
    def generate_unit_tests(self, code: str, file_name: str, context: Dict) -> List[Dict]:
        """Generate unit tests for given code"""
        
        # Limit code size to prevent timeouts
        max_code_length = 2000  # Reduced from 3000
        code_snippet = code[:max_code_length]
        if len(code) > max_code_length:
            code_snippet += "\n... (truncated for brevity)"
        
        prompt = f"""Generate comprehensive unit tests for the following code from {file_name}.

CODE:
```
{code_snippet}
```

REQUIREMENTS:
1. Generate 5-10 unit tests covering different functions/methods
2. Include edge cases and boundary conditions
3. Use proper test naming conventions
4. Include assertions for expected behavior
5. Format each test as a complete, runnable test case

Return the tests in this JSON format:
[
  {{
    "name": "test_function_name_scenario",
    "description": "What this test validates",
    "code": "complete test code",
    "target": "function/method being tested"
  }}
]"""
        
        response = self._make_request(prompt, json.dumps(context, indent=2)[:1000])  # Limit context too
        return self._parse_test_response(response, "Unit Test")
    
    def generate_regression_tests(self, old_code: str, new_code: str, changes: Dict) -> List[Dict]:
        """Generate regression tests for code changes"""
        
        prompt = f"""Generate regression tests to ensure code changes don't break existing functionality.

OLD CODE:
```
{old_code[:2000]}
```

NEW CODE:
```
{new_code[:2000]}
```

DETECTED CHANGES:
{json.dumps(changes, indent=2)}

REQUIREMENTS:
1. Focus on areas affected by changes
2. Test that existing functionality still works
3. Validate new behavior introduced by changes
4. Include tests for integration points
5. Generate 3-7 regression tests

Return tests in JSON format as before."""
        
        response = self._make_request(prompt)
        return self._parse_test_response(response, "Regression Test")
    
    def generate_functional_tests(self, code: str, module_info: Dict) -> List[Dict]:
        """Generate functional tests for entire module"""
        
        prompt = f"""Generate functional tests for the following module.

MODULE INFORMATION:
{json.dumps(module_info, indent=2)}

CODE SAMPLE:
```
{code[:2000]}
```

REQUIREMENTS:
1. Test end-to-end functionality
2. Focus on user-facing features
3. Test integration between components
4. Include happy path and error scenarios
5. Generate 3-5 comprehensive functional tests

Return tests in JSON format."""
        
        response = self._make_request(prompt)
        return self._parse_test_response(response, "Functional Test")
    
    def _parse_test_response(self, response: str, test_type: str) -> List[Dict]:
        """Parse LLM response into structured test cases"""
        
        if not response or response.startswith("Error:"):
            # Return empty list if error response
            return []
        
        try:
            # Try to extract JSON from response
            start_idx = response.find('[')
            end_idx = response.rfind(']') + 1
            
            if start_idx != -1 and end_idx > start_idx:
                json_str = response[start_idx:end_idx]
                tests = json.loads(json_str)
                
                # Validate and fix test structure
                valid_tests = []
                for i, test in enumerate(tests):
                    if isinstance(test, dict):
                        # Ensure required keys exist
                        valid_test = {
                            'name': test.get('name', f'{test_type.lower().replace(" ", "_")}_{i+1}'),
                            'description': test.get('description', 'Test case'),
                            'code': test.get('code', '# No code generated'),
                            'type': test_type,
                            'target': test.get('target', 'general')
                        }
                        valid_tests.append(valid_test)
                
                if valid_tests:
                    return valid_tests
            
            # If no valid JSON found, try to parse as plain text test
            return self._parse_plain_text_tests(response, test_type)
                
        except json.JSONDecodeError:
            # If JSON parsing fails, try plain text parsing
            return self._parse_plain_text_tests(response, test_type)
        except Exception as e:
            print(f"Error parsing test response: {e}")
            return self._parse_plain_text_tests(response, test_type)
    
    def _parse_plain_text_tests(self, response: str, test_type: str) -> List[Dict]:
        """Parse plain text response into test cases"""
        
        # Look for code blocks
        import re
        code_blocks = re.findall(r'```(?:python)?\n(.*?)```', response, re.DOTALL)
        
        if code_blocks:
            tests = []
            for i, code in enumerate(code_blocks, 1):
                tests.append({
                    'name': f'{test_type.lower().replace(" ", "_")}_{i}',
                    'description': f'Generated {test_type}',
                    'code': code.strip(),
                    'type': test_type,
                    'target': 'general'
                })
            return tests
        
        # If no code blocks, treat entire response as test code
        if response and len(response) > 10:
            return [{
                'name': f'{test_type.lower().replace(" ", "_")}_1',
                'description': f'Generated {test_type}',
                'code': response.strip(),
                'type': test_type,
                'target': 'general'
            }]
        
        # Return empty list if nothing could be parsed
        return []
    
    def generate_chat_response(self, user_message: str, context: str, chat_history: List[Dict]) -> str:
        """Generate response for chat interface"""
        
        # Build conversation history
        history_text = "\n".join([
            f"{msg['role'].upper()}: {msg['content']}"
            for msg in chat_history[-5:]  # Last 5 messages
        ])
        
        prompt = f"""Previous conversation:
{history_text}

Current question: {user_message}

Provide a helpful response focused on test case generation. If the question is not about testing, politely redirect."""
        
        return self._make_request(prompt, context)
    
    def validate_code_for_testing(self, code: str) -> Dict:
        """Validate if code is suitable for test generation"""
        
        prompt = f"""Analyze this code and determine:
1. Programming language
2. Main functions/methods/classes
3. Complexity level
4. Testability (easy/medium/hard)
5. Recommended test types

CODE:
```
{code[:2000]}
```

Return as JSON:
{{
  "language": "...",
  "components": ["..."],
  "complexity": "...",
  "testability": "...",
  "recommended_tests": ["..."]
}}"""
        
        response = self._make_request(prompt)
        
        try:
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            if start_idx != -1 and end_idx > start_idx:
                return json.loads(response[start_idx:end_idx])
        except:
            pass
        
        return {
            "language": "unknown",
            "components": [],
            "complexity": "medium",
            "testability": "medium",
            "recommended_tests": ["Unit Test"]
        }