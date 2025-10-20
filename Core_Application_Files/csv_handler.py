import csv
from pathlib import Path
from typing import Dict, List
from datetime import datetime

class CSVHandler:
    """Handle CSV export of test cases with support for different formats"""
    
    def __init__(self):
        self.output_dir = Path("test_outputs")
        self.output_dir.mkdir(exist_ok=True)
    
    def generate_csv(self, test_cases: Dict[str, List[Dict]]) -> Path:
        """
        Generate CSV file from test cases
        
        Args:
            test_cases: Dictionary of test cases by type
            
        Returns:
            Path to generated CSV file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_file = self.output_dir / f"test_cases_{timestamp}.csv"
        
        # Check if we have professional format functional tests
        has_professional_format = any(
            test.get('format') == 'professional' 
            for tests in test_cases.values() 
            for test in tests
        )
        
        if has_professional_format:
            return self._generate_professional_csv(test_cases, csv_file)
        else:
            return self._generate_standard_csv(test_cases, csv_file)
    
    def _generate_professional_csv(self, test_cases: Dict[str, List[Dict]], csv_file: Path) -> Path:
        """Generate CSV with professional test case format"""
        
        # Separate headers for different test types
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
        
        code_based_headers = [
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
        
        # Determine which format to use based on majority
        functional_count = sum(
            1 for tests in test_cases.values() 
            for test in tests 
            if test.get('format') == 'professional'
        )
        code_count = sum(
            1 for tests in test_cases.values() 
            for test in tests 
            if test.get('format') != 'professional'
        )
        
        if functional_count > 0:
            # Use professional format
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=functional_headers)
                writer.writeheader()
                
                test_id_counter = {'Unit Test': 1, 'Regression Test': 1, 'Functional Test': 1}
                
                # Write test cases
                for test_type, tests in test_cases.items():
                    for test in tests:
                        if test.get('format') == 'professional':
                            # Professional format (for functional tests)
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
                                'Expected Result': f'Test passes without errors. Expected behavior validated.',
                                'Target Function/Class': test.get('target', 'N/A'),
                                'Source File': test.get('file', 'N/A'),
                                'Priority': self._get_priority(test_type, test),
                                'Status': 'Not Executed',
                                'Created Date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            }
                        
                        writer.writerow(row)
                        test_id_counter[test_type] += 1
        
        return csv_file
    
    def _generate_standard_csv(self, test_cases: Dict[str, List[Dict]], csv_file: Path) -> Path:
        """Generate standard CSV with code-based tests"""
        
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
        
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            
            test_id = 1
            
            # Write test cases
            for test_type, tests in test_cases.items():
                for test in tests:
                    # Determine priority based on test type
                    priority = self._get_priority(test_type, test)
                    
                    # Safely get values with defaults
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
                    test_id += 1
        
        return csv_file
    
    def _code_to_steps(self, code: str) -> str:
        """Convert test code to test steps"""
        if not code or code == '# No code generated':
            return 'Step 1: Execute test\nStep 2: Verify results'
        
        # Try to extract meaningful steps from code
        lines = code.split('\n')
        steps = []
        step_num = 1
        
        for line in lines:
            line = line.strip()
            # Look for comments or assertions
            if line.startswith('#') and len(line) > 2:
                steps.append(f"Step {step_num}: {line[1:].strip()}")
                step_num += 1
            elif 'assert' in line.lower():
                steps.append(f"Step {step_num}: Verify {line}")
                step_num += 1
        
        if not steps:
            return 'Step 1: Execute test function\nStep 2: Verify expected behavior\nStep 3: Check for errors'
        
        return '\n'.join(steps[:5])  # Limit to 5 steps
    
    def _get_priority(self, test_type: str, test: Dict) -> str:
        """Determine test priority"""
        # Priority rules
        if test_type == "Unit Test":
            return "High"
        elif test_type == "Regression Test":
            # Check if related to changes
            if test.get('changes', {}).get('has_changes'):
                return "Critical"
            return "High"
        elif test_type == "Functional Test":
            # Module-level tests are medium priority
            if test.get('scope') == 'module':
                return "Medium"
            return "High"
        
        return "Medium"
    
    def _format_code_for_csv(self, code: str) -> str:
        """Format code for CSV (escape quotes, limit length)"""
        # Replace double quotes with single quotes
        code = code.replace('"', "'")
        
        # Limit length for CSV
        max_length = 5000
        if len(code) > max_length:
            code = code[:max_length] + "\n... (truncated)"
        
        return code
    
    def generate_professional_test_report(self, test_cases: Dict[str, List[Dict]]) -> Path:
        """Generate a detailed professional test case document"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.output_dir / f"test_cases_report_{timestamp}.txt"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("TEST CASES SPECIFICATION DOCUMENT\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")
            
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
                        f.write(f"File: {test.get('file', 'N/A')}\n\n")
                        
                        f.write("Steps:\n")
                        steps = test.get('steps', 'N/A')
                        if steps != 'N/A':
                            for step in steps.split('\n'):
                                f.write(f"  {step}\n")
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
                        f.write(f"\nCode:\n{'-' * 40}\n")
                        f.write(test.get('code', 'No code available'))
                        f.write(f"\n{'-' * 40}\n")
                    
                    f.write("\n" + "-" * 80 + "\n\n")
        
        return report_file
    
    def cleanup_old_files(self, days: int = 7):
        """Clean up old test output files"""
        import time
        
        current_time = time.time()
        cutoff_time = current_time - (days * 24 * 60 * 60)
        
        for file in self.output_dir.glob("*"):
            if file.is_file() and file.stat().st_mtime < cutoff_time:
                file.unlink()