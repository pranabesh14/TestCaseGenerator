import ast
import re
from typing import Dict, List, Optional
from pathlib import Path

class CodeParser:
    """Parse and analyze code files for test generation"""
    
    def __init__(self):
        self.language_patterns = {
            'python': r'\.py$',
            'javascript': r'\.(js|jsx)$',
            'typescript': r'\.(ts|tsx)$',
            'java': r'\.java$',
            'cpp': r'\.(cpp|cc|cxx)$',
            'c': r'\.c$',
            'csharp': r'\.cs$',
            'go': r'\.go$',
            'rust': r'\.rs$',
            'ruby': r'\.rb$',
            'php': r'\.php$',
        }
    
    def detect_language(self, filename: str) -> str:
        """Detect programming language from filename"""
        for lang, pattern in self.language_patterns.items():
            if re.search(pattern, filename, re.IGNORECASE):
                return lang
        return 'unknown'
    
    def parse_code(self, code: str, filename: str) -> Dict:
        """Parse code and extract structure"""
        language = self.detect_language(filename)
        
        parsed_data = {
            'filename': filename,
            'language': language,
            'code': code,
            'functions': [],
            'classes': [],
            'imports': [],
            'complexity': 'medium',
            'lines_of_code': len(code.split('\n'))
        }
        
        # Language-specific parsing
        if language == 'python':
            parsed_data.update(self._parse_python(code))
        elif language in ['javascript', 'typescript']:
            parsed_data.update(self._parse_javascript(code))
        elif language == 'java':
            parsed_data.update(self._parse_java(code))
        else:
            parsed_data.update(self._parse_generic(code))
        
        # Calculate complexity
        parsed_data['complexity'] = self._calculate_complexity(parsed_data)
        
        return parsed_data
    
    def _parse_python(self, code: str) -> Dict:
        """Parse Python code using AST"""
        result = {
            'functions': [],
            'classes': [],
            'imports': []
        }
        
        try:
            tree = ast.parse(code)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    result['functions'].append({
                        'name': node.name,
                        'line': node.lineno,
                        'args': [arg.arg for arg in node.args.args],
                        'docstring': ast.get_docstring(node),
                        'decorators': [d.id for d in node.decorator_list if hasattr(d, 'id')]
                    })
                
                elif isinstance(node, ast.ClassDef):
                    methods = [
                        n.name for n in node.body 
                        if isinstance(n, ast.FunctionDef)
                    ]
                    result['classes'].append({
                        'name': node.name,
                        'line': node.lineno,
                        'methods': methods,
                        'docstring': ast.get_docstring(node),
                        'bases': [self._get_name(base) for base in node.bases]
                    })
                
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        result['imports'].append(alias.name)
                
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ''
                    for alias in node.names:
                        result['imports'].append(f"{module}.{alias.name}")
        
        except SyntaxError as e:
            result['parse_error'] = str(e)
        
        return result
    
    def _parse_javascript(self, code: str) -> Dict:
        """Parse JavaScript/TypeScript code using regex"""
        result = {
            'functions': [],
            'classes': [],
            'imports': []
        }
        
        # Find function declarations
        func_pattern = r'(?:function|const|let|var)\s+(\w+)\s*(?:=\s*)?(?:async\s*)?\([^)]*\)'
        for match in re.finditer(func_pattern, code):
            result['functions'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1
            })
        
        # Find arrow functions
        arrow_pattern = r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>'
        for match in re.finditer(arrow_pattern, code):
            result['functions'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1
            })
        
        # Find class declarations
        class_pattern = r'class\s+(\w+)'
        for match in re.finditer(class_pattern, code):
            result['classes'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1
            })
        
        # Find imports
        import_pattern = r'import\s+.*?\s+from\s+[\'"]([^\'"]+)[\'"]'
        for match in re.finditer(import_pattern, code):
            result['imports'].append(match.group(1))
        
        return result
    
    def _parse_java(self, code: str) -> Dict:
        """Parse Java code using regex"""
        result = {
            'functions': [],
            'classes': [],
            'imports': []
        }
        
        # Find method declarations
        method_pattern = r'(?:public|private|protected)?\s+(?:static\s+)?(?:\w+)\s+(\w+)\s*\([^)]*\)'
        for match in re.finditer(method_pattern, code):
            result['functions'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1
            })
        
        # Find class declarations
        class_pattern = r'(?:public\s+)?class\s+(\w+)'
        for match in re.finditer(class_pattern, code):
            result['classes'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1
            })
        
        # Find imports
        import_pattern = r'import\s+([\w.]+);'
        for match in re.finditer(import_pattern, code):
            result['imports'].append(match.group(1))
        
        return result
    
    def _parse_generic(self, code: str) -> Dict:
        """Generic parsing for unknown languages"""
        result = {
            'functions': [],
            'classes': [],
            'imports': []
        }
        
        # Try to find function-like patterns
        func_patterns = [
            r'(?:def|function|func|fn)\s+(\w+)',
            r'(\w+)\s*\([^)]*\)\s*{',
        ]
        
        for pattern in func_patterns:
            for match in re.finditer(pattern, code):
                result['functions'].append({
                    'name': match.group(1),
                    'line': code[:match.start()].count('\n') + 1
                })
        
        # Try to find class-like patterns
        class_pattern = r'(?:class|struct|interface)\s+(\w+)'
        for match in re.finditer(class_pattern, code):
            result['classes'].append({
                'name': match.group(1),
                'line': code[:match.start()].count('\n') + 1
            })
        
        return result
    
    def _get_name(self, node):
        """Get name from AST node"""
        if hasattr(node, 'id'):
            return node.id
        elif hasattr(node, 'attr'):
            return node.attr
        return 'Unknown'
    
    def _calculate_complexity(self, parsed_data: Dict) -> str:
        """Calculate code complexity level"""
        loc = parsed_data['lines_of_code']
        num_functions = len(parsed_data['functions'])
        num_classes = len(parsed_data['classes'])
        
        complexity_score = loc / 100 + num_functions + num_classes * 2
        
        if complexity_score < 5:
            return 'low'
        elif complexity_score < 15:
            return 'medium'
        else:
            return 'high'
    
    def extract_functions_code(self, code: str, language: str) -> List[Dict]:
        """Extract individual function code blocks"""
        functions = []
        
        if language == 'python':
            try:
                tree = ast.parse(code)
                lines = code.split('\n')
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        # Extract function code
                        start_line = node.lineno - 1
                        end_line = node.end_lineno if hasattr(node, 'end_lineno') else start_line + 10
                        func_code = '\n'.join(lines[start_line:end_line])
                        
                        functions.append({
                            'name': node.name,
                            'code': func_code,
                            'start_line': node.lineno,
                            'end_line': end_line
                        })
            except:
                pass
        
        return functions