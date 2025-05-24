#!/usr/bin/env python3
"""
Run all VCBot tests with production-mimicking scenarios.

This script runs tests in the following order:
1. Unit tests for individual components
2. Integration tests
3. Production-mimicking tests
"""

import sys
import os
import subprocess
import time
from pathlib import Path

# Add parent directory to path so we can import VCBot modules
sys.path.insert(0, str(Path(__file__).parent.parent))


def run_pytest_suite(test_path, suite_name):
    """Run a pytest test suite and return results."""
    print(f"\n{'='*60}")
    print(f"Running {suite_name}")
    print(f"{'='*60}")
    
    start_time = time.time()
    
    # Run pytest with verbose output
    result = subprocess.run(
        [sys.executable, "-m", "pytest", test_path, "-v", "--tb=short"],
        capture_output=True,
        text=True
    )
    
    elapsed_time = time.time() - start_time
    
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    
    print(f"\n{suite_name} completed in {elapsed_time:.2f} seconds")
    print(f"Exit code: {result.returncode}")
    
    return result.returncode == 0


def run_unit_test_suite(suite_path, suite_name):
    """Run a unit test suite that follows the existing pattern."""
    print(f"\n{'='*60}")
    print(f"Running {suite_name}")
    print(f"{'='*60}")
    
    # Import and run the test suite
    try:
        if suite_path == "test_message_router":
            from test_message_router import MessageRouterTestSuite
            return MessageRouterTestSuite.run_all_tests()
        elif suite_path == "test_response_formatter":
            from test_response_formatter import ResponseFormatterTestSuite
            return ResponseFormatterTestSuite.run_all_tests()
        else:
            print(f"Unknown suite: {suite_path}")
            return False
    except Exception as e:
        print(f"Error running {suite_name}: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all test suites."""
    print("VCBot Comprehensive Test Suite")
    print("="*60)
    
    os.chdir(Path(__file__).parent)
    
    results = {}
    
    # 1. Run unit tests using existing pattern
    print("\n📝 UNIT TESTS")
    results['message_router'] = run_unit_test_suite(
        "test_message_router",
        "Message Router Unit Tests"
    )
    
    results['response_formatter'] = run_unit_test_suite(
        "test_response_formatter",
        "Response Formatter Unit Tests"
    )
    
    # 2. Run pytest-based unit tests
    print("\n🧪 PYTEST UNIT TESTS")
    results['services'] = run_pytest_suite(
        "test_services",
        "Service Tests"
    )
    
    results['repositories'] = run_pytest_suite(
        "test_repositories",
        "Repository Tests"
    )
    
    # 3. Run production-mimicking tests
    print("\n🏭 PRODUCTION TESTS")
    results['message_router_prod'] = run_pytest_suite(
        "test_message_router_async.py",
        "Message Router Production Tests"
    )
    
    results['response_formatter_prod'] = run_pytest_suite(
        "test_response_formatter_production.py",
        "Response Formatter Production Tests"
    )
    
    results['message_scenarios'] = run_pytest_suite(
        "test_message_scenarios.py",
        "Message Scenario Tests"
    )
    
    # 4. Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    total_suites = len(results)
    passed_suites = sum(1 for passed in results.values() if passed)
    
    for suite_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{suite_name:.<40} {status}")
    
    print(f"\nTotal: {passed_suites}/{total_suites} suites passed")
    
    if passed_suites == total_suites:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n❌ {total_suites - passed_suites} suite(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())