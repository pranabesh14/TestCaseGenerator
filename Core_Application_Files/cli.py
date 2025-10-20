#!/usr/bin/env python3
"""
Command-line interface for the Test Case Generator
"""
import argparse
import sys
from pathlib import Path
import json

from llm_handler import LLMHandler
from code_parser import CodeParser
from test_generator import TestGenerator
from git_handler import GitHandler
from csv_handler import CSVHandler
from rag_system import RAGSystem
from logger import get_app_logger

logger = get_app_logger("cli")


def generate_tests_from_files(
    file_paths: list,
    test_types: list,
    output_format: str = "csv"
):
    """Generate tests from local files"""
    logger.info(f"Processing {len(file_paths)} files...")
    
    # Initialize components
    llm = LLMHandler()
    parser = CodeParser()
    rag = RAGSystem()
    
    # Parse files
    parsed_data = {}
    for file_path in file_paths:
        path = Path(file_path)
        if not path.exists():
            logger.error(f"File not found: {file_path}")
            continue
        
        logger.info(f"Parsing {path.name}...")
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            parsed_data[path.name] = parser.parse_code(content, path.name)
    
    if not parsed_data:
        logger.error("No valid files to process")
        return
    
    # Add to RAG
    rag.add_code_documents(parsed_data)
    
    # Generate tests
    logger.info("Generating tests...")
    generator = TestGenerator(llm, rag)
    test_cases = generator.generate_tests(parsed_data, test_types, module_level=True)
    
    # Export
    csv_handler = CSVHandler()
    
    if output_format == "csv":
        output_file = csv_handler.generate_csv(test_cases)
        logger.info(f"Tests exported to: {output_file}")
    elif output_format == "json":
        output_file = csv_handler._export_json(test_cases)
        logger.info(f"Tests exported to: {output_file}")
    elif output_format == "txt":
        output_file = csv_handler._export_text(test_cases)
        logger.info(f"Tests exported to: {output_file}")
    elif output_format == "all":
        outputs = csv_handler.export_to_multiple_formats(test_cases)
        logger.info("Tests exported to:")
        for fmt, path in outputs.items():
            logger.info(f"  - {fmt}: {path}")
    
    # Print summary
    total_tests = sum(len(tests) for tests in test_cases.values())
    logger.info(f"\nGenerated {total_tests} test cases:")
    for test_type, tests in test_cases.items():
        logger.info(f"  - {test_type}: {len(tests)}")


def generate_tests_from_repo(
    repo_url: str,
    branch: str,
    test_types: list,
    output_format: str = "csv"
):
    """Generate tests from Git repository"""
    logger.info(f"Cloning repository: {repo_url}")
    
    # Initialize components
    git_handler = GitHandler()
    llm = LLMHandler()
    parser = CodeParser()
    rag = RAGSystem()
    
    try:
        # Clone repo
        repo_path = git_handler.clone_repository(repo_url, branch)
        logger.info(f"Repository cloned to: {repo_path}")
        
        # Get code files
        code_files = git_handler.get_code_files(repo_path)
        logger.info(f"Found {len(code_files)} code files")
        
        # Parse files
        parsed_data = {}
        for file_path in code_files:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                parsed_data[file_path.name] = parser.parse_code(content, file_path.name)
        
        # Add to RAG
        rag.add_code_documents(parsed_data)
        
        # Generate tests
        logger.info("Generating tests...")
        generator = TestGenerator(llm, rag)
        test_cases = generator.generate_tests(parsed_data, test_types, module_level=True)
        
        # Export
        csv_handler = CSVHandler()
        
        if output_format == "csv":
            output_file = csv_handler.generate_csv(test_cases)
            logger.info(f"Tests exported to: {output_file}")
        elif output_format == "all":
            outputs = csv_handler.export_to_multiple_formats(test_cases)
            logger.info("Tests exported to:")
            for fmt, path in outputs.items():
                logger.info(f"  - {fmt}: {path}")
        
        # Print summary
        total_tests = sum(len(tests) for tests in test_cases.values())
        logger.info(f"\nGenerated {total_tests} test cases:")
        for test_type, tests in test_cases.items():
            logger.info(f"  - {test_type}: {len(tests)}")
        
        # Cleanup
        git_handler.cleanup(repo_path)
        
    except Exception as e:
        logger.error(f"Error processing repository: {e}")
        sys.exit(1)


def analyze_code(file_path: str):
    """Analyze code structure"""
    logger.info(f"Analyzing: {file_path}")
    
    path = Path(file_path)
    if not path.exists():
        logger.error(f"File not found: {file_path}")
        return
    
    parser = CodeParser()
    
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        parsed = parser.parse_code(content, path.name)
    
    # Print analysis
    print("\n" + "="*60)
    print(f"Code Analysis: {path.name}")
    print("="*60)
    print(f"Language: {parsed['language']}")
    print(f"Lines of Code: {parsed['lines_of_code']}")
    print(f"Complexity: {parsed['complexity']}")
    print(f"\nFunctions ({len(parsed['functions'])}):")
    for func in parsed['functions'][:10]:
        print(f"  - {func['name']} (line {func.get('line', 'N/A')})")
    
    print(f"\nClasses ({len(parsed['classes'])}):")
    for cls in parsed['classes'][:10]:
        print(f"  - {cls['name']} (line {cls.get('line', 'N/A')})")
    
    print(f"\nImports ({len(parsed['imports'])}):")
    for imp in parsed['imports'][:10]:
        print(f"  - {imp}")
    
    print("="*60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Test Case Generator CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate tests from local files
  python cli.py generate file1.py file2.py --types unit regression
  
  # Generate tests from Git repository
  python cli.py generate-repo https://github.com/user/repo.git
  
  # Analyze code structure
  python cli.py analyze mycode.py
  
  # Generate all format types
  python cli.py generate file.py --output all
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Generate command
    generate_parser = subparsers.add_parser('generate', help='Generate tests from files')
    generate_parser.add_argument('files', nargs='+', help='Code files to process')
    generate_parser.add_argument(
        '--types',
        nargs='+',
        choices=['unit', 'regression', 'functional'],
        default=['unit', 'regression', 'functional'],
        help='Test types to generate'
    )
    generate_parser.add_argument(
        '--output',
        choices=['csv', 'json', 'txt', 'all'],
        default='csv',
        help='Output format'
    )
    
    # Generate from repo command
    repo_parser = subparsers.add_parser('generate-repo', help='Generate tests from Git repo')
    repo_parser.add_argument('repo_url', help='Git repository URL')
    repo_parser.add_argument('--branch', default='main', help='Branch to clone')
    repo_parser.add_argument(
        '--types',
        nargs='+',
        choices=['unit', 'regression', 'functional'],
        default=['unit', 'regression', 'functional'],
        help='Test types to generate'
    )
    repo_parser.add_argument(
        '--output',
        choices=['csv', 'json', 'txt', 'all'],
        default='csv',
        help='Output format'
    )
    
    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Analyze code structure')
    analyze_parser.add_argument('file', help='Code file to analyze')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Map test type names
    type_mapping = {
        'unit': 'Unit Test',
        'regression': 'Regression Test',
        'functional': 'Functional Test'
    }
    
    # Execute command
    if args.command == 'generate':
        test_types = [type_mapping[t] for t in args.types]
        generate_tests_from_files(args.files, test_types, args.output)
    
    elif args.command == 'generate-repo':
        test_types = [type_mapping[t] for t in args.types]
        generate_tests_from_repo(args.repo_url, args.branch, test_types, args.output)
    
    elif args.command == 'analyze':
        analyze_code(args.file)


if __name__ == "__main__":
    main()