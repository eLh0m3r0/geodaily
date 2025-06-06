#!/usr/bin/env python3
"""
Test script to verify the complete pipeline works end-to-end.
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Set dry run mode for testing
os.environ['DRY_RUN'] = 'true'

from main_pipeline import run_complete_pipeline
from logger import setup_logger

def test_complete_pipeline():
    """Test the complete pipeline end-to-end."""
    logger = setup_logger("test_complete_pipeline")
    
    logger.info("=== Testing Complete Newsletter Pipeline ===")
    logger.info("Running in DRY_RUN mode (no real AI API calls)")
    
    try:
        success = run_complete_pipeline()
        
        if success:
            logger.info("✅ Complete pipeline test PASSED!")
            
            # Check if output files were created
            output_dir = Path("output")
            if output_dir.exists():
                html_files = list(output_dir.glob("newsletter_*.html"))
                if html_files:
                    latest_file = max(html_files, key=lambda f: f.stat().st_mtime)
                    logger.info(f"📧 Latest newsletter: {latest_file}")
                    logger.info(f"📊 File size: {latest_file.stat().st_size} bytes")
                else:
                    logger.warning("No newsletter HTML files found in output directory")
            
            return True
        else:
            logger.error("❌ Complete pipeline test FAILED!")
            return False
            
    except Exception as e:
        logger.error(f"❌ Pipeline test failed with exception: {e}")
        logger.exception("Full error traceback:")
        return False

if __name__ == "__main__":
    success = test_complete_pipeline()
    if success:
        print("\n🎉 Complete pipeline test passed!")
        print("The newsletter generation system is ready for production!")
    else:
        print("\n💥 Complete pipeline test failed!")
        print("Check the logs for error details.")
        sys.exit(1)
