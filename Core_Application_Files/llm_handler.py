import os
from typing import List, Dict, Optional
import requests
import json
from logger import get_app_logger

# Initialize logger
logger = get_app_logger("llm_handler")

class LLMHandler:
    """Handler for LLM interactions with support for formatted test cases"""
    
    def __init__(self, model_name: str = "llama3", api_endpoint: str = None):
        """
        Initialize LLM handler
        
        Args:
            model_name: Name of the Llama model to use
            api_endpoint: API endpoint for the LLM (e.g., Ollama)
        """
        self.model_name = model_name
        self.api_endpoint = api_endpoint or os.getenv("LLM_API_ENDPOINT", "http://localhost:11434/api/generate")
        
        logger.info(f"Initializing LLM Handler with model: {self.model_name}, endpoint: {self.api_endpoint}")
        
        # Test connection on init
        self._test_connection()
        
        # System prompt with strict boundaries
        self.system_prompt = """You are a specialized AI assistant for test case generation ONLY. 

Generate comprehensive test cases in valid JSON format.
Always return: [{"name": "test_name", "description": "desc", "code": "test code", "target": "function_name"}]"""

    def _test_connection(self):
        """Test LLM connection on initialization"""
        try:
            response = requests.get(
                self.api_endpoint.replace('/api/generate', '/api/tags'),
                timeout=5
            )
            if response.status_code == 200:
                logger.info("LLM connection successful")
            else:
                logger.warning(f"LLM endpoint returned {response.status_code}")
        except Exception as e:
            logger.error(f"Cannot connect to LLM: {e}")

    def _make_request(self, prompt: str, context: str = "") -> str:
        """Make request to LLM API"""
        
        full_prompt = f"{self.system_prompt}\n\n"
        
        if context:
            full_prompt += f"CONTEXT:\n{context}\n\n"
        
        full_prompt += f"USER REQUEST:\n{prompt}\n\nRESPONSE:"
        
        logger.info(f"Making LLM request to {self.api_endpoint}")
        
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                payload = {
                    "model": self.model_name,
                    "prompt": full_prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "top_p": 0.9,
                        "num_predict": 2000,  # Increased for detailed functional tests
                        "num_ctx": 2048
                    }
                }
                
                response = requests.post(
                    self.api_endpoint,
                    json=payload,
                    timeout=180
                )
                
                if response.status_code == 200:
                    result = response.json()
                    response_text = result.get('response', '')
                    logger.info(f"LLM response received: {len(response_text)} chars")
                    return response_text
                else:
                    error_msg = f"API returned status code {response.status_code}"
                    logger.error(error_msg)
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    return f"Error: {error_msg}"
                    
            except requests.exceptions.Timeout:
                logger.error(f"Request timed out (attempt {attempt + 1})")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                return "Error: Request timed out"
            except requests.exceptions.ConnectionError as e:
                logger.error(f"Connection error: {str(e)}")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                return "Error: Cannot connect to LLM endpoint"
            except Exception as e:
                logger.error(f"LLM request error: {str(e)}", exc_info=True)
                if attempt < max_retries - 1:
                    import time
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                return f"Error: {str(e)}"
        
        return "Error: Max retries exceeded"
    
    def generate_tests_for_chunk(self, chunk: Dict, test_type: str, file_name: str = "") -> List[Dict]:
        """
        Generate tests for a specific code chunk
        
        Args:
            chunk: Code chunk from CodeChunker
            test_type: Type of test (Unit Test, Functional Test, etc.)
            file_name: Source file name
            
        Returns:
            List of test cases
        """
        logger.info(f"Generating {test_type} for chunk: {chunk['name']} ({chunk['type']})")
        
        chunk_code = chunk['code']
        chunk_name = chunk['name']
        chunk_type = chunk['type']
        
        # Build appropriate prompt based on test type
        if test_type == "Unit Test":
            prompt = self._build_unit_test_prompt(chunk_code, chunk_name, chunk_type)
        elif test_type == "Functional Test":
            prompt = self._build_functional_test_prompt(chunk_code, chunk_name, chunk_type)
        elif test_type == "Regression Test":
            prompt = self._build_regression_test_prompt(chunk_code, chunk_name, chunk_type)
        else:
            prompt = self._build_generic_test_prompt(chunk_code, chunk_name, test_type)
        
        response = self._make_request(prompt)
        
        if response.startswith("Error:"):
            logger.error(f"LLM error for {chunk_name}: {response}")
            return self._generate_fallback_tests(chunk, test_type, file_name)
        
        tests = self._parse_test_response(response, test_type)
        
        # Add chunk metadata to tests
        for test in tests:
            test['file'] = file_name
            test['chunk_name'] = chunk_name
            test['chunk_type'] = chunk_type
            test['line_start'] = chunk.get('line_start', 0)
            test['line_end'] = chunk.get('line_end', 0)
        
        logger.info(f"Generated {len(tests)} tests for chunk {chunk_name}")
        return tests
    
    def _build_unit_test_prompt(self, code: str, chunk_name: str, chunk_type: str) -> str:
        """Build prompt for unit test generation"""
        
        if chunk_type == 'function':
            prompt = f"""Generate unit tests for this function.

FUNCTION: {chunk_name}
```
{code}
```

Generate 2-3 unit tests covering:
1. Normal/happy path
2. Edge cases
3. Error conditions if applicable

Return ONLY JSON array:
[{{"name": "test_name", "description": "what it tests", "code": "complete test function", "target": "{chunk_name}"}}]"""
        
        elif chunk_type == 'class':
            prompt = f"""Generate unit tests for this class.

CLASS: {chunk_name}
```
{code}
```

Generate 3-5 unit tests covering different methods and scenarios.

Return ONLY JSON array:
[{{"name": "test_name", "description": "what it tests", "code": "complete test function", "target": "method_name"}}]"""
        
        else:
            prompt = f"""Generate unit tests for this code.

CODE:
```
{code}
```

Generate 2-4 unit tests.

Return ONLY JSON array:
[{{"name": "test_name", "description": "what it tests", "code": "complete test function", "target": "general"}}]"""
        
        return prompt
    
    def _build_functional_test_prompt(self, code: str, chunk_name: str, chunk_type: str) -> str:
        """Build prompt for functional test generation in professional format"""
        
        prompt = f"""Generate functional test cases for this code in PROFESSIONAL TEST CASE FORMAT.

{chunk_type.upper()}: {chunk_name}
```
{code}
```

Generate 3-5 functional test cases that cover:
1. Valid/happy path scenarios
2. Invalid input scenarios
3. Edge cases
4. Error handling
5. Integration scenarios

CRITICAL: Return test cases in this EXACT JSON format:
[
  {{
    "test_case_id": "TC-XXX-01",
    "description": "Brief description of what is being tested",
    "steps": "Step 1: Do something\\nStep 2: Do something else\\nStep 3: Verify result",
    "expected_result": "Detailed expected outcome of the test"
  }}
]

Use appropriate prefixes for test_case_id based on what's being tested:
- TC-TXT-XX for text/input processing
- TC-IMG-XX for image processing
- TC-API-XX for API endpoints
- TC-FN-XX for functions
- TC-INT-XX for integration tests

Make steps clear and actionable. Make expected results specific and measurable.

Return ONLY the JSON array, no other text."""
        
        return prompt
    
    def _build_regression_test_prompt(self, code: str, chunk_name: str, chunk_type: str) -> str:
        """Build prompt for regression test generation"""
        
        prompt = f"""Generate regression tests for this code.

{chunk_type.upper()}: {chunk_name}
```
{code}
```

Generate 2-3 regression tests that ensure:
1. Existing functionality is preserved
2. No breaking changes
3. Backward compatibility

Return ONLY JSON array:
[{{"name": "test_name", "description": "what it tests", "code": "complete test function", "target": "{chunk_name}"}}]"""
        
        return prompt
    
    def _build_generic_test_prompt(self, code: str, chunk_name: str, test_type: str) -> str:
        """Build generic test prompt"""
        
        prompt = f"""Generate {test_type}s for this code.

CODE: {chunk_name}
```
{code}
```

Generate 2-3 {test_type.lower()}s.

Return ONLY JSON array:
[{{"name": "test_name", "description": "what it tests", "code": "complete test function", "target": "{chunk_name}"}}]"""
        
        return prompt
    
    def _parse_test_response(self, response: str, test_type: str) -> List[Dict]:
        """Parse LLM response into structured test cases"""
        
        if not response or response.startswith("Error:"):
            logger.warning(f"Empty or error response for {test_type}")
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
                        # Check if this is a functional test case format
                        if 'test_case_id' in test and test_type == 'Functional Test':
                            # Professional functional test case format
                            valid_test = {
                                'name': test.get('test_case_id', f'TC-FN-{i+1:02d}'),
                                'test_case_id': test.get('test_case_id', f'TC-FN-{i+1:02d}'),
                                'description': test.get('description', 'Test case'),
                                'steps': test.get('steps', 'No steps provided'),
                                'expected_result': test.get('expected_result', 'No expected result provided'),
                                'type': test_type,
                                'target': test.get('target', 'general'),
                                'format': 'professional'
                            }
                        else:
                            # Code-based test format
                            valid_test = {
                                'name': test.get('name', f'{test_type.lower().replace(" ", "_")}_{i+1}'),
                                'description': test.get('description', 'Test case'),
                                'code': test.get('code', '# No code generated'),
                                'type': test_type,
                                'target': test.get('target', 'general'),
                                'format': 'code'
                            }
                        valid_tests.append(valid_test)
                
                if valid_tests:
                    logger.info(f"Successfully parsed {len(valid_tests)} tests from JSON")
                    return valid_tests
            
            # Try plain text parsing
            logger.info("Attempting plain text parsing")
            return self._parse_plain_text_tests(response, test_type)
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            return self._parse_plain_text_tests(response, test_type)
        except Exception as e:
            logger.error(f"Error parsing test response: {e}", exc_info=True)
            return []
    
    def _parse_plain_text_tests(self, response: str, test_type: str) -> List[Dict]:
        """Parse plain text response into test cases"""
        
        import re
        code_blocks = re.findall(r'```(?:python)?\n(.*?)```', response, re.DOTALL)
        
        if code_blocks:
            logger.info(f"Found {len(code_blocks)} code blocks")
            tests = []
            for i, code in enumerate(code_blocks, 1):
                tests.append({
                    'name': f'{test_type.lower().replace(" ", "_")}_{i}',
                    'description': f'Generated {test_type}',
                    'code': code.strip(),
                    'type': test_type,
                    'target': 'general',
                    'format': 'code'
                })
            return tests
        
        return []
    
    def _generate_fallback_tests(self, chunk: Dict, test_type: str, file_name: str) -> List[Dict]:
        """Generate fallback tests when LLM fails"""
        logger.warning(f"Generating fallback tests for {chunk['name']}")
        
        chunk_name = chunk['name']
        chunk_type = chunk['type']
        
        if test_type == "Functional Test":
            # Generate professional format fallback
            return [{
                'name': f'TC-FN-01',
                'test_case_id': f'TC-FN-01',
                'description': f'Functional test for {chunk_name} ({chunk_type})',
                'steps': f'Step 1: Initialize {chunk_name}\nStep 2: Execute main functionality\nStep 3: Verify expected behavior',
                'expected_result': f'{chunk_name} should execute successfully and return expected output without errors',
                'type': test_type,
                'target': chunk_name,
                'file': file_name,
                'fallback': True,
                'format': 'professional'
            }]
        else:
            # Generate code format fallback
            test_name = f"test_{chunk_name}_{test_type.lower().replace(' ', '_')}"
            return [{
                'name': test_name,
                'description': f'{test_type} for {chunk_name} (fallback)',
                'code': f"""def {test_name}():
    \"\"\"
    {test_type} for {chunk_name} ({chunk_type})
    File: {file_name}
    Lines: {chunk.get('line_start', '?')}-{chunk.get('line_end', '?')}
    
    TODO: LLM generation failed. Implement test manually.
    \"\"\"
    # Test implementation here
    pass""",
                'type': test_type,
                'target': chunk_name,
                'file': file_name,
                'fallback': True,
                'format': 'code'
            }]
    
    def generate_chat_response(self, user_message: str, context: str, chat_history: List[Dict]) -> str:
        """Generate response for chat interface"""
        
        logger.info(f"Generating chat response for message: {user_message[:50]}...")
        
        history_text = "\n".join([
            f"{msg['role'].upper()}: {msg['content']}"
            for msg in chat_history[-5:]
        ])
        
        prompt = f"""Previous conversation:
{history_text}

Current question: {user_message}

Provide a helpful response focused on test case generation."""
        
        response = self._make_request(prompt, context)
        logger.info(f"Chat response generated: {len(response)} chars")
        
        return response