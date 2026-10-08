from typing import Dict, List
from llm_handler import LLMHandler
from rag_system import RAGSystem
from code_chunker import CodeChunker
from source_index import SourceIndex
from config import config
from logger import get_app_logger

logger = get_app_logger("test_generator")

class TestGenerator:
    """Generate unit and functional test cases using code chunking"""
    
    def __init__(self, llm_handler: LLMHandler, rag_system: RAGSystem):
        self.llm = llm_handler
        self.rag = rag_system
        self.chunker = CodeChunker(max_chunk_size=1500)
        self.diagnostics = []
        logger.info("TestGenerator initialized (Unit & Functional tests only)")
    
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
            test_types: List of test types to generate (Unit Test, Functional Test)
            module_level: Whether to generate module-level tests
            
        Returns:
            Dictionary mapping test types to lists of test cases
        """
        logger.info(f"Starting test generation for types: {test_types}")
        logger.info(f"Module level: {module_level}")
        logger.info(f"Number of files: {len(parsed_data)}")
        
        all_tests = {
            'Unit Test': [],
            'Functional Test': []
        }
        self.diagnostics = []
        
        # Generate unit tests
        if 'Unit Test' in test_types:
            logger.info("Generating unit tests with chunking...")
            try:
                all_tests['Unit Test'] = self._generate_unit_tests_chunked(parsed_data)
                logger.info(f"✅ Generated {len(all_tests['Unit Test'])} unit tests")
            except Exception as e:
                logger.error(f"Error generating unit tests: {e}", exc_info=True)
        
        # Generate functional tests
        if 'Functional Test' in test_types:
            logger.info("Generating functional tests with chunking...")
            try:
                all_tests['Functional Test'] = self._generate_functional_tests_chunked(
                    parsed_data,
                    module_level
                )
                logger.info(f"✅ Generated {len(all_tests['Functional Test'])} functional tests")
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
        logger.info("UNIT TEST GENERATION")
        logger.info("="*60)
        
        all_unit_tests = []
        
        for filename, data in parsed_data.items():
            logger.info(f"\n📝 Processing file: {filename}")
            
            # Chunk the code
            chunks = self.chunker.chunk_code(data['code'], data)
            chunk_summary = self.chunker.get_chunk_summary(chunks)
            
            logger.info(f"Created {chunk_summary['total_chunks']} chunks:")
            for chunk_type, count in chunk_summary['by_type'].items():
                logger.info(f"  - {chunk_type}: {count}")
            
            # Generate tests for each chunk
            for i, chunk in enumerate(chunks, 1):
                logger.info(f"  Chunk {i}/{len(chunks)}: {chunk['name']} ({chunk['type']})")
                
                try:
                    chunk_tests = self.llm.generate_tests_for_chunk(
                        chunk,
                        "Unit Test",
                        filename
                    )
                    
                    logger.info(f"    ✅ Generated {len(chunk_tests)} tests")
                    all_unit_tests.extend(chunk_tests)
                    
                except Exception as e:
                    logger.error(f"    ❌ Error: {e}")
                    continue
        
        logger.info(f"\n📊 Total unit tests: {len(all_unit_tests)}")
        return all_unit_tests
    
    def _generate_functional_tests_chunked(self, parsed_data: Dict, module_level: bool) -> List[Dict]:
        """Generate from complete definitions plus their transitive dependencies."""
        index = SourceIndex(parsed_data)
        self.diagnostics.extend(index.diagnostics)
        tests = []
        for symbol in index.symbols.values():
            chunk, warnings = index.workflow(
                symbol, config.FUNCTIONAL_CONTEXT_MAX_CHARS,
                config.FUNCTIONAL_CALL_MAX_DEPTH,
            )
            self.diagnostics.extend(warnings)
            if chunk is None:
                continue
            try:
                generated = self.llm.generate_tests_for_chunk(
                    chunk, "Functional Test", symbol['file']
                )
                for test in generated:
                    test['scope'] = 'module' if module_level else 'file'
                tests.extend(generated)
                if not generated:
                    self.diagnostics.append(f"No valid functional tests returned for {symbol['symbol_id']}")
            except Exception as exc:
                self.diagnostics.append(f"Generation failed for {symbol['symbol_id']}: {exc}")
                logger.error("Functional generation failed", exc_info=True)
        for message in dict.fromkeys(self.diagnostics):
            logger.warning(message)
        return tests

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
            chunks_covered = len(summary['by_chunk'])
            summary['coverage_estimate'] = min(100, chunks_covered * 10 + summary['total_tests'] * 2)
        
        return summary
