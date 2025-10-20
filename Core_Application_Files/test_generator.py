from typing import Dict, List
from llm_handler import LLMHandler
from rag_system import RAGSystem
from code_chunker import CodeChunker
from logger import get_app_logger

logger = get_app_logger("test_generator")

class TestGenerator:
    """Generate different types of test cases using code chunking"""
    
    def __init__(self, llm_handler: LLMHandler, rag_system: RAGSystem):
        self.llm = llm_handler
        self.rag = rag_system
        self.chunker = CodeChunker(max_chunk_size=1500)
        logger.info("TestGenerator initialized with chunking support")
    
    def generate_tests(
        self,
        parsed_data: Dict[str, Dict],
        test_types: List[str],
        module_level: bool = False
    ) -> Dict[str, List[Dict]]:
        """
        Generate test cases based on parsed code using chunking
        
        Args:
            parsed_data: Dictionary of parsed code files
            test_types: List of test types to generate
            module_level: Whether to generate module-level tests
            
        Returns:
            Dictionary mapping test types to lists of test cases
        """
        logger.info(f"Starting CHUNKED test generation for types: {test_types}")
        logger.info(f"Module level: {module_level}")
        logger.info(f"Number of files: {len(parsed_data)}")
        
        all_tests = {
            'Unit Test': [],
            'Regression Test': [],
            'Functional Test': []
        }
        
        # Generate unit tests
        if 'Unit Test' in test_types:
            logger.info("Generating unit tests with chunking...")
            try:
                all_tests['Unit Test'] = self._generate_unit_tests_chunked(parsed_data)
                logger.info(f" Generated {len(all_tests['Unit Test'])} unit tests")
            except Exception as e:
                logger.error(f"Error generating unit tests: {e}", exc_info=True)
        
        # Generate regression tests
        if 'Regression Test' in test_types:
            logger.info("Generating regression tests with chunking...")
            try:
                all_tests['Regression Test'] = self._generate_regression_tests_chunked(parsed_data)
                logger.info(f" Generated {len(all_tests['Regression Test'])} regression tests")
            except Exception as e:
                logger.error(f"Error generating regression tests: {e}", exc_info=True)
        
        # Generate functional tests
        if 'Functional Test' in test_types:
            logger.info("Generating functional tests with chunking...")
            try:
                all_tests['Functional Test'] = self._generate_functional_tests_chunked(
                    parsed_data,
                    module_level
                )
                logger.info(f" Generated {len(all_tests['Functional Test'])} functional tests")
            except Exception as e:
                logger.error(f"Error generating functional tests: {e}", exc_info=True)
        
        # Log summary
        total = sum(len(tests) for tests in all_tests.values())
        logger.info("="*60)
        logger.info(f"TEST GENERATION COMPLETE: {total} total tests")
        for test_type, tests in all_tests.items():
            logger.info(f"  {test_type}: {len(tests)} tests")
        logger.info("="*60)
        
        return all_tests
    
    def _generate_unit_tests_chunked(self, parsed_data: Dict) -> List[Dict]:
        """Generate unit tests using code chunking"""
        logger.info("="*60)
        logger.info("UNIT TEST GENERATION (CHUNKED)")
        logger.info("="*60)
        
        all_unit_tests = []
        
        for filename, data in parsed_data.items():
            logger.info(f"\n Processing file: {filename}")
            
            # Chunk the code
            chunks = self.chunker.chunk_code(data['code'], data)
            chunk_summary = self.chunker.get_chunk_summary(chunks)
            
            logger.info(f"Created {chunk_summary['total_chunks']} chunks:")
            for chunk_type, count in chunk_summary['by_type'].items():
                logger.info(f"  - {chunk_type}: {count}")
            
            # Generate tests for each chunk
            for i, chunk in enumerate(chunks, 1):
                logger.info(f"\n  Processing chunk {i}/{len(chunks)}: {chunk['name']} ({chunk['type']})")
                
                try:
                    chunk_tests = self.llm.generate_tests_for_chunk(
                        chunk,
                        "Unit Test",
                        filename
                    )
                    
                    logger.info(f"    Generated {len(chunk_tests)} tests for this chunk")
                    all_unit_tests.extend(chunk_tests)
                    
                except Exception as e:
                    logger.error(f"    Error processing chunk {chunk['name']}: {e}")
                    continue
        
        logger.info(f"\n Total unit tests generated: {len(all_unit_tests)}")
        return all_unit_tests
    
    def _generate_regression_tests_chunked(self, parsed_data: Dict) -> List[Dict]:
        """Generate regression tests using code chunking"""
        logger.info("="*60)
        logger.info("REGRESSION TEST GENERATION (CHUNKED)")
        logger.info("="*60)
        
        all_regression_tests = []
        
        for filename, data in parsed_data.items():
            logger.info(f"\n Processing file: {filename}")
            
            # Check if there's previous version in RAG
            previous_versions = self.rag.get_code_versions(filename)
            
            if previous_versions:
                logger.info(f"Found previous version for {filename}")
                
                # Chunk both old and new code
                old_data = {
                    'code': previous_versions[0]['code'],
                    'language': data.get('language', 'unknown'),
                    'functions': previous_versions[0].get('functions', []),
                    'classes': previous_versions[0].get('classes', [])
                }
                
                old_chunks = self.chunker.chunk_code(old_data['code'], old_data)
                new_chunks = self.chunker.chunk_code(data['code'], data)
                
                logger.info(f"Old code: {len(old_chunks)} chunks, New code: {len(new_chunks)} chunks")
                
                # Compare chunks and generate tests for changed ones
                changed_chunks = self._identify_changed_chunks(old_chunks, new_chunks)
                logger.info(f"Identified {len(changed_chunks)} changed chunks")
                
                for chunk in changed_chunks:
                    try:
                        chunk_tests = self.llm.generate_tests_for_chunk(
                            chunk,
                            "Regression Test",
                            filename
                        )
                        all_regression_tests.extend(chunk_tests)
                    except Exception as e:
                        logger.error(f"Error processing changed chunk: {e}")
                        continue
            else:
                logger.info(f"No previous version for {filename}, generating basic regression tests")
                
                # Generate basic regression tests for new files
                chunks = self.chunker.chunk_code(data['code'], data)
                
                # Generate regression tests for first few chunks
                for chunk in chunks[:3]:  # Limit to first 3 chunks
                    try:
                        chunk_tests = self.llm.generate_tests_for_chunk(
                            chunk,
                            "Regression Test",
                            filename
                        )
                        all_regression_tests.extend(chunk_tests)
                    except Exception as e:
                        logger.error(f"Error processing chunk: {e}")
                        continue
        
        logger.info(f"\n Total regression tests generated: {len(all_regression_tests)}")
        return all_regression_tests
    
    def _generate_functional_tests_chunked(self, parsed_data: Dict, module_level: bool) -> List[Dict]:
        """Generate functional tests using code chunking"""
        logger.info("="*60)
        logger.info("FUNCTIONAL TEST GENERATION (CHUNKED)")
        logger.info("="*60)
        logger.info(f"Module level: {module_level}")
        
        all_functional_tests = []
        
        if module_level:
            logger.info("Generating MODULE-LEVEL functional tests")
            
            # Combine all files and chunk
            all_code = ""
            combined_data = {
                'language': 'unknown',
                'functions': [],
                'classes': [],
                'code': ''
            }
            
            for filename, data in parsed_data.items():
                all_code += f"\n\n# File: {filename}\n{data['code']}"
                combined_data['functions'].extend(data.get('functions', []))
                combined_data['classes'].extend(data.get('classes', []))
                if not combined_data['language'] or combined_data['language'] == 'unknown':
                    combined_data['language'] = data.get('language', 'unknown')
            
            combined_data['code'] = all_code
            
            # Chunk the combined code
            chunks = self.chunker.chunk_code(all_code, combined_data)
            logger.info(f"Created {len(chunks)} chunks from combined module code")
            
            # Generate functional tests for each chunk
            for i, chunk in enumerate(chunks, 1):
                logger.info(f"\n  Processing module chunk {i}/{len(chunks)}: {chunk['name']}")
                
                try:
                    chunk_tests = self.llm.generate_tests_for_chunk(
                        chunk,
                        "Functional Test",
                        "module"
                    )
                    
                    # Mark as module-level tests
                    for test in chunk_tests:
                        test['scope'] = 'module'
                    
                    logger.info(f"    Generated {len(chunk_tests)} functional tests for this chunk")
                    all_functional_tests.extend(chunk_tests)
                    
                except Exception as e:
                    logger.error(f"    Error processing module chunk: {e}")
                    continue
        
        else:
            logger.info("Generating FILE-LEVEL functional tests")
            
            # Process each file separately
            for filename, data in parsed_data.items():
                logger.info(f"\n Processing file: {filename}")
                
                # Chunk the code
                chunks = self.chunker.chunk_code(data['code'], data)
                logger.info(f"Created {len(chunks)} chunks")
                
                # Generate functional tests for each chunk
                for i, chunk in enumerate(chunks, 1):
                    logger.info(f"  Processing chunk {i}/{len(chunks)}: {chunk['name']}")
                    
                    try:
                        chunk_tests = self.llm.generate_tests_for_chunk(
                            chunk,
                            "Functional Test",
                            filename
                        )
                        
                        # Mark as file-level tests
                        for test in chunk_tests:
                            test['scope'] = 'file'
                        
                        logger.info(f"    Generated {len(chunk_tests)} functional tests")
                        all_functional_tests.extend(chunk_tests)
                        
                    except Exception as e:
                        logger.error(f"    Error processing chunk: {e}")
                        continue
        
        logger.info("="*60)
        logger.info(f"FUNCTIONAL TEST GENERATION COMPLETE: {len(all_functional_tests)} tests")
        logger.info("="*60)
        
        return all_functional_tests
    
    def _identify_changed_chunks(self, old_chunks: List[Dict], new_chunks: List[Dict]) -> List[Dict]:
        """Identify which chunks have changed between versions"""
        changed = []
        
        # Create mapping of chunk names
        old_chunk_map = {chunk['name']: chunk for chunk in old_chunks}
        new_chunk_map = {chunk['name']: chunk for chunk in new_chunks}
        
        # Find changed or new chunks
        for name, new_chunk in new_chunk_map.items():
            if name not in old_chunk_map:
                # New chunk
                changed.append(new_chunk)
                logger.debug(f"New chunk identified: {name}")
            elif old_chunk_map[name]['code'] != new_chunk['code']:
                # Modified chunk
                changed.append(new_chunk)
                logger.debug(f"Modified chunk identified: {name}")
        
        return changed
    
    def generate_test_summary(self, all_tests: Dict) -> Dict:
        """Generate summary statistics for generated tests"""
        summary = {
            'total_tests': 0,
            'by_type': {},
            'by_file': {},
            'by_chunk': {},
            'coverage_estimate': 0
        }
        
        for test_type, tests in all_tests.items():
            summary['by_type'][test_type] = len(tests)
            summary['total_tests'] += len(tests)
            
            for test in tests:
                filename = test.get('file', 'unknown')
                summary['by_file'][filename] = summary['by_file'].get(filename, 0) + 1
                
                chunk_name = test.get('chunk_name', 'unknown')
                summary['by_chunk'][chunk_name] = summary['by_chunk'].get(chunk_name, 0) + 1
        
        # Calculate coverage estimate
        if summary['total_tests'] > 0:
            # More sophisticated estimate based on chunks covered
            chunks_covered = len(summary['by_chunk'])
            summary['coverage_estimate'] = min(100, chunks_covered * 10 + summary['total_tests'] * 2)
        
        return summary