from typing import Dict, List
from llm_handler import LLMHandler
from rag_system import RAGSystem

class TestGenerator:
    """Generate different types of test cases"""
    
    def __init__(self, llm_handler: LLMHandler, rag_system: RAGSystem):
        self.llm = llm_handler
        self.rag = rag_system
    
    def generate_tests(
        self,
        parsed_data: Dict[str, Dict],
        test_types: List[str],
        module_level: bool = False
    ) -> Dict[str, List[Dict]]:
        """
        Generate test cases based on parsed code
        
        Args:
            parsed_data: Dictionary of parsed code files
            test_types: List of test types to generate
            module_level: Whether to generate module-level tests
            
        Returns:
            Dictionary mapping test types to lists of test cases
        """
        all_tests = {
            'Unit Test': [],
            'Regression Test': [],
            'Functional Test': []
        }
        
        # Generate unit tests
        if 'Unit Test' in test_types:
            all_tests['Unit Test'] = self._generate_unit_tests(parsed_data)
        
        # Generate regression tests
        if 'Regression Test' in test_types:
            all_tests['Regression Test'] = self._generate_regression_tests(parsed_data)
        
        # Generate functional tests
        if 'Functional Test' in test_types:
            all_tests['Functional Test'] = self._generate_functional_tests(
                parsed_data,
                module_level
            )
        
        return all_tests
    
    def _generate_unit_tests(self, parsed_data: Dict) -> List[Dict]:
        """Generate unit tests for individual functions/methods"""
        unit_tests = []
        
        for filename, data in parsed_data.items():
            # Get context from RAG
            context = self.rag.get_relevant_context(
                f"unit tests for {filename}"
            )
            
            # Generate tests using LLM
            tests = self.llm.generate_unit_tests(
                data['code'],
                filename,
                {
                    'functions': data.get('functions', []),
                    'classes': data.get('classes', []),
                    'language': data.get('language', 'unknown')
                }
            )
            
            # Add metadata
            for test in tests:
                test['file'] = filename
                test['type'] = 'Unit Test'
            
            unit_tests.extend(tests)
        
        return unit_tests
    
    def _generate_regression_tests(self, parsed_data: Dict) -> List[Dict]:
        """Generate regression tests for code changes"""
        regression_tests = []
        
        for filename, data in parsed_data.items():
            # Check if there's previous version in RAG
            previous_versions = self.rag.get_code_versions(filename)
            
            if previous_versions:
                # Generate regression tests for changes
                old_code = previous_versions[0]['code']
                new_code = data['code']
                
                # Detect changes
                changes = self._detect_changes(old_code, new_code)
                
                if changes['has_changes']:
                    tests = self.llm.generate_regression_tests(
                        old_code,
                        new_code,
                        changes
                    )
                    
                    for test in tests:
                        test['file'] = filename
                        test['type'] = 'Regression Test'
                        test['changes'] = changes
                    
                    regression_tests.extend(tests)
            else:
                # If no previous version, generate basic regression tests
                tests = self._generate_basic_regression_tests(data)
                regression_tests.extend(tests)
        
        return regression_tests
    
    def _generate_functional_tests(self, parsed_data: Dict, module_level: bool) -> List[Dict]:
        """Generate functional tests for features"""
        functional_tests = []
        
        if module_level:
            # Generate module-level tests
            module_info = self._build_module_info(parsed_data)
            
            # Get all code combined
            all_code = '\n\n'.join([
                f"# File: {fname}\n{data['code']}"
                for fname, data in parsed_data.items()
            ])
            
            tests = self.llm.generate_functional_tests(
                all_code[:5000],  # Limit size
                module_info
            )
            
            for test in tests:
                test['type'] = 'Functional Test'
                test['scope'] = 'module'
            
            functional_tests.extend(tests)
        else:
            # Generate file-level functional tests
            for filename, data in parsed_data.items():
                module_info = {
                    'filename': filename,
                    'functions': data.get('functions', []),
                    'classes': data.get('classes', []),
                    'language': data.get('language', 'unknown')
                }
                
                tests = self.llm.generate_functional_tests(
                    data['code'],
                    module_info
                )
                
                for test in tests:
                    test['file'] = filename
                    test['type'] = 'Functional Test'
                    test['scope'] = 'file'
                
                functional_tests.extend(tests)
        
        return functional_tests
    
    def _detect_changes(self, old_code: str, new_code: str) -> Dict:
        """Detect changes between code versions"""
        old_lines = set(old_code.split('\n'))
        new_lines = set(new_code.split('\n'))
        
        added = new_lines - old_lines
        removed = old_lines - new_lines
        
        return {
            'has_changes': len(added) > 0 or len(removed) > 0,
            'added_lines': len(added),
            'removed_lines': len(removed),
            'added_samples': list(added)[:10],
            'removed_samples': list(removed)[:10]
        }
    
    def _generate_basic_regression_tests(self, data: Dict) -> List[Dict]:
        """Generate basic regression tests when no previous version exists"""
        tests = []
        
        # Create basic regression tests for main functions
        for func in data.get('functions', [])[:5]:  # Limit to 5
            test = {
                'name': f"test_regression_{func['name']}",
                'description': f"Regression test for {func['name']} function",
                'code': f"""def test_regression_{func['name']}():
    # Test that {func['name']} maintains expected behavior
    # TODO: Add specific test assertions
    pass""",
                'type': 'Regression Test',
                'file': data['filename'],
                'target': func['name']
            }
            tests.append(test)
        
        return tests
    
    def _build_module_info(self, parsed_data: Dict) -> Dict:
        """Build comprehensive module information"""
        all_functions = []
        all_classes = []
        all_imports = []
        languages = set()
        
        for data in parsed_data.values():
            all_functions.extend(data.get('functions', []))
            all_classes.extend(data.get('classes', []))
            all_imports.extend(data.get('imports', []))
            languages.add(data.get('language', 'unknown'))
        
        return {
            'total_files': len(parsed_data),
            'total_functions': len(all_functions),
            'total_classes': len(all_classes),
            'languages': list(languages),
            'main_functions': [f['name'] for f in all_functions[:20]],
            'main_classes': [c['name'] for c in all_classes[:10]],
            'dependencies': list(set(all_imports))[:20]
        }
    
    def generate_test_summary(self, all_tests: Dict) -> Dict:
        """Generate summary statistics for generated tests"""
        summary = {
            'total_tests': 0,
            'by_type': {},
            'by_file': {},
            'coverage_estimate': 0
        }
        
        for test_type, tests in all_tests.items():
            summary['by_type'][test_type] = len(tests)
            summary['total_tests'] += len(tests)
            
            for test in tests:
                filename = test.get('file', 'unknown')
                summary['by_file'][filename] = summary['by_file'].get(filename, 0) + 1
        
        # Rough coverage estimate
        if summary['total_tests'] > 0:
            summary['coverage_estimate'] = min(
                100,
                summary['total_tests'] * 5  # Rough heuristic
            )
        
        return summary