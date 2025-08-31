#!/usr/bin/env python3
"""
Command-line interface for manual cleanup operations.
Usage: python cleanup_cli.py [options]
"""

import sys
import argparse
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Import cleanup module directly to avoid package init issues
import importlib.util
spec = importlib.util.spec_from_file_location("cleanup", Path(__file__).parent / "src" / "cleanup.py")
cleanup_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleanup_module)

CleanupManager = cleanup_module.CleanupManager
get_cleanup_status = cleanup_module.get_cleanup_status

def format_bytes(bytes_value: int) -> str:
    """Format bytes into human readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_value < 1024.0:
            return ".1f"
        bytes_value /= 1024.0
    return ".1f"

def main():
    parser = argparse.ArgumentParser(
        description="Geopolitical Daily Cleanup System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cleanup_cli.py --status                    # Show what would be cleaned
  python cleanup_cli.py --dry-run                   # Preview cleanup without deleting
  python cleanup_cli.py                             # Run actual cleanup
  python cleanup_cli.py --logs-only                 # Clean only log files
  python cleanup_cli.py --newsletters-only          # Clean only newsletter archives
  python cleanup_cli.py --output-only               # Clean only output files
  python cleanup_cli.py --metrics-only              # Clean only metrics database
        """
    )

    parser.add_argument("--dry-run", action="store_true",
                       help="Run in dry-run mode (no files deleted)")
    parser.add_argument("--status", action="store_true",
                       help="Show cleanup status without running cleanup")
    parser.add_argument("--logs-only", action="store_true",
                       help="Clean only log files")
    parser.add_argument("--newsletters-only", action="store_true",
                       help="Clean only newsletter archives")
    parser.add_argument("--output-only", action="store_true",
                       help="Clean only output files")
    parser.add_argument("--metrics-only", action="store_true",
                       help="Clean only metrics database")

    args = parser.parse_args()

    # Validate mutually exclusive options
    cleanup_types = [args.logs_only, args.newsletters_only, args.output_only, args.metrics_only]
    if sum(cleanup_types) > 1:
        print("❌ Error: Only one cleanup type can be specified at a time")
        sys.exit(1)

    try:
        if args.status:
            # Show cleanup status
            print("=== Geopolitical Daily Cleanup Status ===\n")
            status = get_cleanup_status()

            print("Retention Policies:")
            print(f"  Logs: {status['retention_policies']['logs_days']} days")
            print(f"  Newsletters: {status['retention_policies']['newsletters_days']} days")
            print(f"  Output files: {status['retention_policies']['output_days']} days")
            print(f"  Metrics data: {status['retention_policies']['metrics_days']} days")
            print()

            print("Current Status:")
            print(f"  Log files: {status['log_files']['old']}/{status['log_files']['total']} old ({format_bytes(status['log_files']['size_old'])})")
            print(f"  Newsletter files: {status['newsletter_files']['old']}/{status['newsletter_files']['total']} old ({format_bytes(status['newsletter_files']['size_old'])})")
            print(f"  Output files: {status['output_files']['old']}/{status['output_files']['total']} old ({format_bytes(status['output_files']['size_old'])})")
            print(f"  Metrics records: {status['metrics_records']['old']}/{status['metrics_records']['total']} old")
            print()

            total_files = status['log_files']['old'] + status['newsletter_files']['old'] + status['output_files']['old']
            total_size = status['log_files']['size_old'] + status['newsletter_files']['size_old'] + status['output_files']['size_old']

            print("Summary:")
            print(f"  Total files to clean: {total_files}")
            print(f"  Total size to free: {format_bytes(total_size)}")
            print(f"  Database records to clean: {status['metrics_records']['old']}")

        else:
            # Run cleanup
            manager = CleanupManager(dry_run=args.dry_run)

            if args.dry_run:
                print("🧹 Running cleanup in DRY RUN mode (no files will be deleted)")
            else:
                print("🧹 Running cleanup...")

            if args.logs_only:
                print("\n=== Cleaning Log Files ===")
                result = manager.cleanup_log_files()
            elif args.newsletters_only:
                print("\n=== Cleaning Newsletter Archives ===")
                result = manager.cleanup_newsletter_archives()
            elif args.output_only:
                print("\n=== Cleaning Output Files ===")
                result = manager.cleanup_output_files()
            elif args.metrics_only:
                print("\n=== Cleaning Metrics Database ===")
                result = manager.cleanup_metrics_database()
            else:
                print("\n=== Running Full Cleanup ===")
                result = manager.run_full_cleanup()

            # Show results
            print("\n=== Cleanup Results ===")
            if result.dry_run:
                print("DRY RUN - No files were actually deleted")
            print(f"Files removed: {result.files_removed}")
            print(f"Bytes freed: {format_bytes(result.bytes_freed)}")
            print(f"Database records removed: {result.database_records_removed}")

            if result.errors:
                print(f"\n⚠️  Errors encountered: {len(result.errors)}")
                for i, error in enumerate(result.errors, 1):
                    print(f"  {i}. {error}")
                sys.exit(1)
            else:
                print("\n✅ Cleanup completed successfully!")

    except KeyboardInterrupt:
        print("\n\n⚠️  Cleanup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()