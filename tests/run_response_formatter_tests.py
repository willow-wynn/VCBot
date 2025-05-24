#!/usr/bin/env python3
"""
Standalone runner for response formatter tests.

This script runs the response formatter tests independently for development
and debugging purposes.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path for imports
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

if __name__ == "__main__":
    from tests.test_response_formatter import ResponseFormatterTestSuite
    
    print("🧪 Running Response Formatter Tests Standalone")
    print("=" * 60)
    
    # Run the test suite
    success = ResponseFormatterTestSuite.run_all_tests()
    
    if success:
        print("\n✅ All tests passed! Response formatter is ready for integration.")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed. Please fix before integrating.")
        sys.exit(1)