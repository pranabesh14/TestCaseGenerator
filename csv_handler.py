"""
CSV Handler with enhanced export capabilities and logging
"""
import csv
from pathlib import Path
from typing import Dict, List
from datetime import datetime
from logger import get_app_logger

logger = get_app_logger("csv_handler")

class CSVHandler:
    """Handle CSV export of test cases with support for different formats"""
    
    def __init__(self):
        self.output_dir = Path("test_outputs")
        self.output_dir.mkdir(exist_ok=True)
        logger.info(f" CSVHandler initialized")
        logger.info(f" Output directory: {self.output_dir.absolute()}")
    
    def generate_csv(self, test_cases: Dict[str, List[Dict]]) -> Path:
        """
        Generate CSV file from test cases
        
        Args:
            test_cases: Dictionary of test cases by type
            
        Returns:
            Path to generated CSV file
        """
        logger.info(" Generating CSV file from test cases")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_file = self.output_dir / f"test_cases_{timestamp}.csv"
        
        # Count total tests
        total_tests = sum(len(tests) for tests in test_cases.values())
        logger.info(f" Total test cases to export: {total_tests}")
        
        # Check if we have professional format functional tests
        has_professional_format = any(
            test.get('format') == 'professional' 
            for tests in test_cases.values() 
            for test in tests
        )
        
        if has_professional_format:
            logger.info(" Using professional CSV format")
            result = self._generate_professional_csv(test_cases, csv_file)
        else:
            logger.info(" Using standard CSV format")
            result = self._generate_standard_csv(test_cases, csv_file)
        
        file_size = csv_file.stat().st_size / 1024
        logger.info(f" CSV file generated: {csv_file.name} ({file_size:.2f} KB)")
        
        return result
    
    def _generate_professional_csv(self, test_cases: Dict[str, List[Dict]], csv_file: Path) -> Path:
        """Generate CSV with professional test case format"""
        logger.info(" Generating professional format CSV")
        
        functional_headers = [
            'Test Case ID',
            'Test Type',
            'Description',
            'Steps',
            'Expected Result',
            'Target Function/Class',
            'Source File',
            'Priority',
            'Status',
            'Created Date'
        ]
        
        try:
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=functional_headers)
                writer.writeheader()
                
                test_id_counter = {'Unit Test': 1, 'Regression Test': 1, 'Functional Test': 1}
                rows_written = 0
                
                for test_type, tests in test_cases.items():
                    logger.debug(f"   Writing {len(tests)} {test_type}s")
                    
                    for test in tests:
                        if test.get('format') == 'professional':
                            # Professional format
                            row = {
                                'Test Case ID': test.get('test_case_id', test.get('name', f'TC-{test_id_counter[test_type]:03d}')),
                                'Test Type': test_type,
                                'Description': test.get('description', ''),
                                'Steps': test.get('steps', 'N/A'),
                                'Expected Result': test.get('expected_result', 'N/A'),
                                'Target Function/Class': test.get('target', 'N/A'),
                                'Source File': test.get('file', 'N/A'),
                                'Priority': self._get_priority(test_type, test),
                                'Status': 'Not Executed',
                                'Created Date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            }
                        else:
                            # Convert code-based to professional format
                            row = {
                                'Test Case ID': f'TC-{test_type[:3].upper()}-{test_id_counter[test_type]:02d}',
                                'Test Type': test_type,
                                'Description': test.get('description', ''),
                                'Steps': self._code_to_steps(test.get('code', '')),
                                'Expected Result': 'Test passes without errors. Expected behavior validated.',
                                'Target Function/Class': test.get('target', 'N/A'),
                                'Source File': test.get('file', 'N/A'),
                                'Priority': self._get_priority(test_type, test),
                                'Status': 'Not Executed',
                                'Created Date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            }
                        
                        writer.writerow(row)
                        rows_written += 1
                        test_id_counter[test_type] += 1
            
            logger.info(f" Wrote {rows_written} rows to professional CSV")
            
        except Exception as e:
            logger.error(f" Error generating professional CSV: {e}", exc_info=True)
            raise
        
        return csv_file
    
    def _generate_standard_csv(self, test_cases: Dict[str, List[Dict]], csv_file: Path) -> Path:
        """Generate standard CSV with code-based tests"""
        logger.info(" Generating standard format CSV")
        
        headers = [
            'Test ID',
            'Test Type',
            'Test Name',
            'Description',
            'Target Function/Class',
            'Source File',
            'Test Code',
            'Priority',
            'Status',
            'Created Date'
        ]
        
        try:
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                
                test_id = 1
                rows_written = 0
                
                for test_type, tests in test_cases.items():
                    logger.debug(f"   Writing {len(tests)} {test_type}s")
                    
                    for test in tests:
                        priority = self._get_priority(test_type, test)
                        
                        row = {
                            'Test ID': f"TC{test_id:04d}",
                            'Test Type': test_type,
                            'Test Name': test.get('name', f'Test_{test_id}'),
                            'Description': test.get('description', ''),
                            'Target Function/Class': test.get('target', 'N/A'),
                            'Source File': test.get('file', 'N/A'),
                            'Test Code': self._format_code_for_csv(test.get('code', '')),
                            'Priority': priority,
                            'Status': 'Not Executed',
                            'Created Date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        
                        writer.writerow(row)
                        rows_written += 1
                        test_id += 1
            
            logger.info(f" Wrote {rows_written} rows to standard CSV")
            
        except Exception as e:
            logger.error(f" Error generating standard CSV: {e}", exc_info=True)
            raise
        
        return csv_file
    
    def _code_to_steps(self, code: str) -> str:
        """Convert test code to test steps"""
        if not code or code == '# No code generated':
            return 'Step 1: Execute test\nStep 2: Verify results'
        
        lines = code.split('\n')
        steps = []
        step_num = 1
        
        for line in lines:
            line = line.strip()
            if line.startswith('#') and len(line) > 2:
                steps.append(f"Step {step_num}: {line[1:].strip()}")
                step_num += 1
            elif 'assert' in line.lower():
                steps.append(f"Step {step_num}: Verify {line}")
                step_num += 1
        
        if not steps:
            return 'Step 1: Execute test function\nStep 2: Verify expected behavior\nStep 3: Check for errors'
        
        return '\n'.join(steps[:5])
    
    def _get_priority(self, test_type: str, test: Dict) -> str:
        """Determine test priority"""
        if test_type == "Unit Test":
            return "High"
        elif test_type == "Regression Test":
            if test.get('changes', {}).get('has_changes'):
                return "Critical"
            return "High"
        elif test_type == "Functional Test":
            if test.get('scope') == 'module':
                return "Medium"
            return "High"
        
        return "Medium"
    
    def _format_code_for_csv(self, code: str) -> str:
        """Format code for CSV (escape quotes, limit length)"""
        code = code.replace('"', "'")
        
        max_length = 5000
        if len(code) > max_length:
            code = code[:max_length] + "\n... (truncated)"
        
        return code
    
    def generate_professional_test_report(self, test_cases: Dict[str, List[Dict]]) -> Path:
        """Generate a detailed professional test case document"""
        logger.info(" Generating professional test report")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.output_dir / f"test_cases_report_{timestamp}.txt"
        
        total_tests = sum(len(tests) for tests in test_cases.values())
        logger.info(f" Report will contain {total_tests} test cases")
        
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                # Header
                f.write("=" * 80 + "\n")
                f.write("TEST CASES SPECIFICATION DOCUMENT\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total Test Cases: {total_tests}\n")
                f.write("=" * 80 + "\n\n")
                
                # Table of Contents
                f.write("TABLE OF CONTENTS\n")
                f.write("-" * 80 + "\n")
                for test_type, tests in test_cases.items():
                    if tests:
                        f.write(f"{test_type}s: {len(tests)} test cases\n")
                f.write("\n" + "=" * 80 + "\n\n")
                
                # Test cases by type
                for test_type, tests in test_cases.items():
                    if not tests:
                        continue
                    
                    f.write(f"\n{'=' * 80}\n")
                    f.write(f"{test_type.upper()}S ({len(tests)} test cases)\n")
                    f.write(f"{'=' * 80}\n\n")
                    
                    for i, test in enumerate(tests, 1):
                        if test.get('format') == 'professional':
                            # Professional format
                            f.write(f"Test Case ID: {test.get('test_case_id', test.get('name'))}\n")
                            f.write(f"Description: {test.get('description', 'N/A')}\n")
                            f.write(f"Target: {test.get('target', 'N/A')}\n")
                            f.write(f"File: {test.get('file', 'N/A')}\n")
                            f.write(f"Priority: {self._get_priority(test_type, test)}\n\n")
                            
                            f.write("Steps:\n")
                            steps = test.get('steps', 'N/A')
                            if steps != 'N/A':
                                for step in steps.split('\n'):
                                    if step.strip():
                                        f.write(f"  {step.strip()}\n")
                            else:
                                f.write("  N/A\n")
                            f.write("\n")
                            
                            f.write("Expected Result:\n")
                            f.write(f"  {test.get('expected_result', 'N/A')}\n")
                        else:
                            # Code-based format
                            f.write(f"Test {i}: {test.get('name', 'Unnamed')}\n")
                            f.write(f"Description: {test.get('description', 'N/A')}\n")
                            f.write(f"Target: {test.get('target', 'N/A')}\n")
                            f.write(f"File: {test.get('file', 'N/A')}\n")
                            f.write(f"Priority: {self._get_priority(test_type, test)}\n")
                            f.write(f"\nCode:\n{'-' * 40}\n")
                            f.write(test.get('code', 'No code available'))
                            f.write(f"\n{'-' * 40}\n")
                        
                        f.write("\n" + "-" * 80 + "\n\n")
            
            file_size = report_file.stat().st_size / 1024
            logger.info(f" Test report generated: {report_file.name} ({file_size:.2f} KB)")
            
        except Exception as e:
            logger.error(f" Error generating test report: {e}", exc_info=True)
            raise
        
        return report_file
    
    def export_to_multiple_formats(self, test_cases: Dict[str, List[Dict]]) -> Dict[str, Path]:
        """Export test cases to multiple formats"""
        logger.info("📦 Exporting test cases to multiple formats")
        
        outputs = {}
        
        try:
            # CSV
            logger.info("   Generating CSV...")
            outputs['csv'] = self.generate_csv(test_cases)
            
            # Text Report
            logger.info("   Generating text report...")
            outputs['txt'] = self.generate_professional_test_report(test_cases)
            
            # JSON
            logger.info("  Generating JSON...")
            outputs['json'] = self._export_json(test_cases)
            
            logger.info(f" Exported to {len(outputs)} formats")
            
        except Exception as e:
            logger.error(f" Error exporting to multiple formats: {e}", exc_info=True)
        
        return outputs
    
    def _export_json(self, test_cases: Dict[str, List[Dict]]) -> Path:
        """Export test cases to JSON format"""
        import json
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_file = self.output_dir / f"test_cases_{timestamp}.json"
        
        try:
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(test_cases, f, indent=2, ensure_ascii=False)
            
            logger.info(f" JSON file generated: {json_file.name}")
            
        except Exception as e:
            logger.error(f" Error generating JSON: {e}", exc_info=True)
            raise
        
        return json_file
    
    def cleanup_old_files(self, days: int = 7):
        """Clean up old test output files"""
        logger.info(f" Cleaning up test files older than {days} days")
        
        import time
        
        current_time = time.time()
        cutoff_time = current_time - (days * 24 * 60 * 60)
        
        deleted_count = 0
        
        try:
            for file in self.output_dir.glob("*"):
                if file.is_file() and file.stat().st_mtime < cutoff_time:
                    file.unlink()
                    deleted_count += 1
                    logger.debug(f"  Deleted: {file.name}")
            
            logger.info(f" Cleaned up {deleted_count} old files")
            
        except Exception as e:
            logger.error(f" Error during cleanup: {e}")