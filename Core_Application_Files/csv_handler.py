import csv
from pathlib import Path
from typing import Dict, List
from datetime import datetime

class CSVHandler:
    """Handle CSV export of test cases"""
    
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
        
        # Prepare CSV headers
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
    
    def generate_summary_csv(self, test_cases: Dict[str, List[Dict]], summary: Dict) -> Path:
        """Generate a summary CSV with statistics"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_file = self.output_dir / f"test_summary_{timestamp}.csv"
        
        headers = ['Metric', 'Value']
        
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            
            # Write summary statistics
            rows = [
                {'Metric': 'Total Tests Generated', 'Value': summary.get('total_tests', 0)},
                {'Metric': 'Unit Tests', 'Value': summary['by_type'].get('Unit Test', 0)},
                {'Metric': 'Regression Tests', 'Value': summary['by_type'].get('Regression Test', 0)},
                {'Metric': 'Functional Tests', 'Value': summary['by_type'].get('Functional Test', 0)},
                {'Metric': 'Estimated Coverage', 'Value': f"{summary.get('coverage_estimate', 0)}%"},
                {'Metric': 'Files Analyzed', 'Value': len(summary.get('by_file', {}))},
                {'Metric': 'Generation Date', 'Value': datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            ]
            
            writer.writerows(rows)
        
        return csv_file
    
    def export_to_multiple_formats(self, test_cases: Dict[str, List[Dict]]) -> Dict[str, Path]:
        """Export test cases to multiple formats"""
        outputs = {}
        
        # CSV format
        outputs['csv'] = self.generate_csv(test_cases)
        
        # JSON format
        outputs['json'] = self._export_json(test_cases)
        
        # Text format (readable)
        outputs['txt'] = self._export_text(test_cases)
        
        return outputs
    
    def _export_json(self, test_cases: Dict[str, List[Dict]]) -> Path:
        """Export to JSON format"""
        import json
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_file = self.output_dir / f"test_cases_{timestamp}.json"
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump({
                'generated_at': datetime.now().isoformat(),
                'test_cases': test_cases
            }, f, indent=2)
        
        return json_file
    
    def _export_text(self, test_cases: Dict[str, List[Dict]]) -> Path:
        """Export to readable text format"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        txt_file = self.output_dir / f"test_cases_{timestamp}.txt"
        
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("TEST CASES REPORT\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")
            
            for test_type, tests in test_cases.items():
                f.write(f"\n{'=' * 80}\n")
                f.write(f"{test_type.upper()}S ({len(tests)} tests)\n")
                f.write(f"{'=' * 80}\n\n")
                
                for i, test in enumerate(tests, 1):
                    f.write(f"Test {i}: {test.get('name', 'Unnamed')}\n")
                    f.write(f"Description: {test.get('description', 'N/A')}\n")
                    f.write(f"Target: {test.get('target', 'N/A')}\n")
                    f.write(f"File: {test.get('file', 'N/A')}\n")
                    f.write(f"\nCode:\n{'-' * 40}\n")
                    f.write(test.get('code', 'No code available'))
                    f.write(f"\n{'-' * 40}\n\n")
        
        return txt_file
    
    def cleanup_old_files(self, days: int = 7):
        """Clean up old test output files"""
        import time
        
        current_time = time.time()
        cutoff_time = current_time - (days * 24 * 60 * 60)
        
        for file in self.output_dir.glob("*"):
            if file.is_file() and file.stat().st_mtime < cutoff_time:
                file.unlink()