"""
Full deployment wrapper: processes ALL unprocessed tickets in pages.

Runs reprocess_tickets_batch.py with --limit PAGE_SIZE --offset N 
sequentially until all tickets are processed.

Usage:
    python scripts/run_full_deployment.py
    python scripts/run_full_deployment.py --page-size 10000 --start-page 0
"""
import subprocess
import sys
import os
import time
import argparse
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def get_remaining_count(created_after: str | None = None):
    """Count tickets that still need processing."""
    from scripts.reprocess_tickets_full_taxonomy import get_postgres_connection
    conn = get_postgres_connection()
    cur = conn.cursor()
    query = """
        SELECT COUNT(*) FROM ticket_insights
        WHERE processing_phase IS NULL
          AND full_conversation IS NOT NULL
          AND LENGTH(full_conversation) > 100
    """
    params = []
    if created_after:
        query += " AND ticket_created_at >= %s"
        params.append(created_after)

    cur.execute(query, params)
    count = cur.fetchone()[0]
    conn.close()
    return count


def run_page(page_num: int, page_size: int, phase: str, chunk_size: int, created_after: str | None = None):
    """Run one page of batch processing.
    
    NOTE: Always uses offset=0 because --unprocessed-only filters out
    already-processed tickets. Using page_num * page_size would skip tickets
    as the unprocessed pool shrinks with each completed page.
    """
    data_dir = Path(__file__).parent.parent / 'data'
    data_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, 'scripts/reprocess_tickets_batch.py',
        '--phase', phase,
        '--limit', str(page_size),
        '--offset', '0',  # Always 0 — unprocessed-only handles filtering
        '--chunk-size', str(chunk_size),
        '--save-to-db',
        '--unprocessed-only',
        '--batch-file', f'data/full_batch_requests_p{page_num}.jsonl',
        '--results-file', f'data/full_batch_results_p{page_num}.jsonl',
    ]

    if created_after:
        cmd.extend(['--created-after', created_after])
    
    logger.info(f"Running: {' '.join(cmd)}")
    
    result = subprocess.run(
        cmd,
        capture_output=False,
        text=True,
        cwd=str(Path(__file__).parent.parent),
    )
    
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description='Full deployment wrapper')
    parser.add_argument('--page-size', type=int, default=10000, help='Tickets per page')
    parser.add_argument('--chunk-size', type=int, default=5000, help='Requests per API batch')
    parser.add_argument('--start-page', type=int, default=0, help='Page to start from (for resume)')
    parser.add_argument('--phase', type=str, default='phase_3.2_full', help='Processing phase')
    parser.add_argument('--max-pages', type=int, default=20, help='Max pages to process')
    parser.add_argument('--created-after', type=str, default=None, help='Only process tickets created after this date (YYYY-MM-DD)')
    args = parser.parse_args()
    
    remaining = get_remaining_count(args.created_after)
    total_pages = (remaining + args.page_size - 1) // args.page_size
    total_pages = min(total_pages, args.max_pages)
    
    logger.info("="*80)
    logger.info("FULL DEPLOYMENT - TAXONOMY v3.2")
    logger.info("="*80)
    logger.info(f"  Remaining tickets: {remaining}")
    logger.info(f"  Page size: {args.page_size}")
    logger.info(f"  Chunk size: {args.chunk_size}")
    logger.info(f"  Total pages: {total_pages}")
    logger.info(f"  Start page: {args.start_page}")
    logger.info(f"  Phase: {args.phase}")
    logger.info(f"  Created after: {args.created_after}")
    logger.info(f"  Est. time: ~{total_pages * 15} min ({total_pages * 15 / 60:.1f} hours)")
    logger.info("="*80)
    
    start_time = time.time()
    completed_pages = 0
    
    for page in range(args.start_page, args.start_page + total_pages):
        page_start = time.time()
        logger.info(f"\n{'='*60}")
        logger.info(f"PAGE {page + 1}/{args.start_page + total_pages} (offset={page * args.page_size})")
        logger.info(f"{'='*60}")
        
        rc = run_page(page, args.page_size, args.phase, args.chunk_size, created_after=args.created_after)
        
        page_elapsed = time.time() - page_start
        total_elapsed = time.time() - start_time
        completed_pages += 1
        
        if rc != 0:
            logger.warning(f"  Page {page + 1} FAILED (exit code {rc}), retrying once...")
            time.sleep(5)
            rc2 = run_page(page, args.page_size, args.phase, args.chunk_size, created_after=args.created_after)
            if rc2 != 0:
                logger.error(f"  Page {page + 1} FAILED again (exit code {rc2})")
                logger.error(f"  Resume with: --start-page {page}")
                # Check how many remain — some may have been saved before crash
                try:
                    still_remaining = get_remaining_count(args.created_after)
                    logger.info(f"  Tickets still unprocessed: {still_remaining}")
                except Exception:
                    pass
                sys.exit(1)
        
        avg_per_page = total_elapsed / completed_pages
        remaining_pages = (args.start_page + total_pages) - (page + 1)
        eta_min = remaining_pages * avg_per_page / 60
        
        logger.info(f"  Page {page + 1} done in {page_elapsed/60:.1f} min")
        logger.info(f"  Total elapsed: {total_elapsed/60:.1f} min")
        logger.info(f"  ETA remaining: ~{eta_min:.0f} min ({eta_min/60:.1f} hours)")
    
    total_elapsed = time.time() - start_time
    logger.info("\n" + "="*80)
    logger.info("FULL DEPLOYMENT COMPLETE")
    logger.info(f"  Pages processed: {completed_pages}")
    logger.info(f"  Total time: {total_elapsed/60:.1f} min ({total_elapsed/3600:.1f} hours)")
    logger.info("="*80)
    
    # Final count
    remaining_after = get_remaining_count(args.created_after)
    logger.info(f"  Remaining unprocessed: {remaining_after}")


if __name__ == '__main__':
    main()
