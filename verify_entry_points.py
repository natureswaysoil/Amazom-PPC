#!/usr/bin/env python3
"""
Verify Cloud Function Entry Points

This script verifies that all required entry points for Google Cloud Functions
are properly defined and decorated in main.py. This should be run before
deployment to catch any issues early.
"""

import ast
import sys
from pathlib import Path
from typing import List, Tuple


def parse_main_py() -> ast.Module:
    """Parse main.py and return the AST."""
    main_path = Path(__file__).parent / "main.py"
    if not main_path.exists():
        print(f"❌ ERROR: main.py not found at {main_path}")
        sys.exit(1)
    
    try:
        with open(main_path, 'r', encoding='utf-8') as f:
            return ast.parse(f.read(), filename='main.py')
    except SyntaxError as e:
        print(f"❌ ERROR: Syntax error in main.py: {e}")
        sys.exit(1)


def find_http_decorated_functions(tree: ast.Module) -> List[str]:
    """Find all functions decorated with @functions_framework.http."""
    http_functions = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for decorator in node.decorator_list:
                # Check for @functions_framework.http decorator
                if isinstance(decorator, ast.Attribute):
                    if (hasattr(decorator.value, 'id') and 
                        decorator.value.id == 'functions_framework' and 
                        decorator.attr == 'http'):
                        http_functions.append(node.name)
    
    return http_functions


def verify_entry_points() -> Tuple[bool, List[str]]:
    """
    Verify that all required entry points are properly defined.
    
    Returns:
        Tuple of (success, errors)
    """
    print("🔍 Verifying Cloud Function entry points...")
    print()
    
    # Required entry points
    required_entry_points = {
        'run_optimizer': 'Main entry point',
        'optimizePPC': 'Legacy compatibility alias',
        'run_pipeline': 'Cloud Run Job compatibility alias'
    }
    
    # Parse main.py
    tree = parse_main_py()
    print("✓ main.py parsed successfully")
    
    # Find HTTP-decorated functions
    http_functions = find_http_decorated_functions(tree)
    print(f"✓ Found {len(http_functions)} HTTP-decorated functions")
    print()
    
    # Check each required entry point
    errors = []
    all_ok = True
    
    for func_name, description in required_entry_points.items():
        if func_name in http_functions:
            print(f"✓ {func_name:<20} - {description}")
        else:
            print(f"❌ {func_name:<20} - MISSING or not properly decorated")
            errors.append(f"{func_name} is missing or not decorated with @functions_framework.http")
            all_ok = False
    
    print()
    
    # Additional checks
    if all_ok:
        print("✅ All required entry points are properly defined!")
        print()
        print("Available entry points for deployment:")
        for func_name in required_entry_points:
            print(f"  --entry-point={func_name}")
        print()
        print("Recommended: --entry-point=run_optimizer")
    else:
        print("❌ Some entry points are missing!")
        print()
        print("Errors:")
        for error in errors:
            print(f"  - {error}")
    
    return all_ok, errors


def main():
    """Main entry point."""
    success, errors = verify_entry_points()
    
    if not success:
        print()
        print("❌ Verification FAILED")
        sys.exit(1)
    
    print("✅ Verification PASSED")
    sys.exit(0)


if __name__ == '__main__':
    main()
