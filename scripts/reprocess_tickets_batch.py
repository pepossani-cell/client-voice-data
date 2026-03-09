"""
Reprocess tickets using Anthropic Batch API for 10x speed improvement.

Batch API benefits:
- 50% cost reduction vs real-time API
- ~10-15 min total time for 1K tickets (vs ~2.5 hours sequential)
- Automatic rate limiting and retry handling

Workflow:
1. Fetch tickets from PostgreSQL
2. Generate prompts + routing for all tickets
3. Create batch JSONL file
4. Submit batch to Anthropic API
5. Poll for completion (~10-15 min)
6. Download results
7. Save to PostgreSQL

Usage:
    python scripts/reprocess_tickets_batch.py --phase phase_3.2_golden --limit 1000 --save-to-db
"""

import os
import sys
import json
import time
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import anthropic
from scripts.prompt_compiler import PromptCompiler, apply_tier1_natureza, derive_metadata_flags
from scripts.routing_logic import TicketRouter, ClinicContext, TicketContext
from scripts.reprocess_tickets_full_taxonomy import (
    fetch_tickets_to_process, 
    get_postgres_connection, 
    save_processed_ticket,
    classify_produto,
    classify_atendimento,
    validate_semantic_consistency,
    EXPECTED_PRODUCT_FOR_ROOT_CAUSE
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Anthropic client
client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

# Tier models config
TIER_MODELS = {
    'T1': {'model': 'claude-opus-4-6', 'input_cost': 5.0, 'output_cost': 25.0},
    'T2': {'model': 'claude-sonnet-4-5', 'input_cost': 3.0, 'output_cost': 15.0},
    'T3': {'model': 'claude-haiku-4-5', 'input_cost': 1.0, 'output_cost': 5.0},
}


def _ensure_parent_dir(file_path: str) -> None:
    """Create parent directory for output artifacts when needed."""
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)


def _as_router_subscription_status(is_subscriber: bool, was_subscriber: bool) -> str:
    """Normalize Snowflake booleans to the values expected by TicketRouter."""
    if is_subscriber:
        return 'ativo'
    if was_subscriber:
        return 'cancelado'
    return 'nunca_assinou'


def create_batch_requests(tickets: list, compiler: PromptCompiler, router: TicketRouter, 
                          clinic_context: dict) -> List[Dict[str, Any]]:
    """Generate batch requests for all tickets with routing."""
    
    batch_requests = []
    
    for ticket in tickets:
        ticket_id = ticket['zendesk_ticket_id']
        clinic_id = ticket.get('clinic_id')
        tags = ticket.get('tags', '')
        conversation = ticket.get('full_conversation', '')
        
        # Parse tags
        if isinstance(tags, str):
            tags_list = [t.strip() for t in tags.split(',') if t.strip()]
        else:
            tags_list = tags or []
        
        # Route to determine model
        clinic_ctx = clinic_context.get(clinic_id) if clinic_id else None
        if clinic_ctx is None:
            clinic_ctx = ClinicContext(
                clinic_id=clinic_id or 0,
                has_bnpl_contract=False,
                has_capim_pos=False,
                current_subscription_status='unknown',
            )
        
        ticket_ctx = TicketContext(
            zendesk_ticket_id=ticket_id,
            tags=tags_list,
            escalation_level='N1',
            assignee_group='',
            conversation_turns=conversation.count('\n') // 2 + 1,
            total_tokens=len(conversation.split()),
            priority=ticket.get('status', 'normal'),
            subject=ticket.get('subject', ''),
            product_mentions=[]
        )
        
        tier = router.route(clinic_ctx, ticket_ctx)
        model_config = TIER_MODELS[tier]
        
        # Compile prompt
        ticket_data = {
            'zendesk_ticket_id': ticket_id,
            'clinic_id': clinic_id,
            'tags': tags,
            'subject': ticket.get('subject', ''),
            'conversation': conversation,
        }
        
        system_prompt, user_prompt = compiler.compile(ticket_data)
        
        # Create batch request
        batch_request = {
            "custom_id": f"ticket_{ticket_id}",
            "params": {
                "model": model_config['model'],
                "max_tokens": 2048,
                "temperature": 0.0,
                "system": system_prompt,
                "messages": [
                    {"role": "user", "content": user_prompt}
                ]
            }
        }
        
        batch_requests.append({
            'request': batch_request,
            'ticket': ticket,
            'tier': tier,
            'tags_list': tags_list,
        })
    
    return batch_requests


def submit_batch(batch_requests: List[Dict], batch_file_path: str) -> str:
    """Submit batch to Anthropic API and return batch_id."""
    
    # Write batch file for backup/audit
    logger.info(f"Writing {len(batch_requests)} requests to {batch_file_path}")
    _ensure_parent_dir(batch_file_path)
    with open(batch_file_path, 'w', encoding='utf-8') as f:
        for item in batch_requests:
            f.write(json.dumps(item['request']) + '\n')
    
    # Submit batch (API accepts list of dicts directly)
    logger.info("Submitting batch to Anthropic API...")
    requests_list = [item['request'] for item in batch_requests]
    batch = client.messages.batches.create(
        requests=requests_list
    )
    
    batch_id = batch.id
    logger.info(f"Batch submitted: {batch_id}")
    logger.info(f"  Status: {batch.processing_status}")
    logger.info(f"  Created: {batch.created_at}")
    
    return batch_id


def poll_batch_completion(batch_id: str, poll_interval: int = 30) -> Dict:
    """Poll batch until completion and return results."""
    
    logger.info(f"\nPolling batch {batch_id} every {poll_interval}s...")
    
    while True:
        batch = client.messages.batches.retrieve(batch_id)
        
        status = batch.processing_status
        progress = batch.request_counts
        
        logger.info(f"  Status: {status} | Processed: {progress.succeeded}/{progress.processing + progress.succeeded + progress.errored}")
        
        if status == 'ended':
            logger.info(f"\n  Batch complete!")
            logger.info(f"    Succeeded: {progress.succeeded}")
            logger.info(f"    Errored: {progress.errored}")
            logger.info(f"    Expired: {progress.expired}")
            logger.info(f"    Canceled: {progress.canceled}")
            
            return batch
        
        elif status in ['canceling', 'canceled', 'expired']:
            logger.error(f"\n  Batch {status}!")
            raise Exception(f"Batch {status}: {batch}")
        
        time.sleep(poll_interval)


def download_batch_results(batch_id: str, output_path: str) -> List[Dict]:
    """Download batch results and parse into list of dicts."""
    
    logger.info(f"\nDownloading batch results to {output_path}...")
    
    # Get results stream
    results = []
    for result in client.messages.batches.results(batch_id):
        results.append(result.model_dump())
    
    # Save raw results
    _ensure_parent_dir(output_path)
    with open(output_path, 'w', encoding='utf-8') as f:
        for result in results:
            f.write(json.dumps(result) + '\n')
    
    logger.info(f"  Downloaded {len(results)} results")
    
    return results


def process_batch_results(batch_requests: List[Dict], batch_results: List[Dict],
                         processing_phase: str) -> List[Dict[str, Any]]:
    """Process batch results and combine with ticket metadata."""
    
    # Map results by custom_id
    results_map = {r['custom_id']: r for r in batch_results}
    
    processed_tickets = []
    stats = {
        'succeeded': 0,
        'errored': 0,
        'tier1_overrides': 0,
        'proactive': 0,
        'no_interaction': 0,
    }
    
    for item in batch_requests:
        ticket = item['ticket']
        ticket_id = ticket['zendesk_ticket_id']
        custom_id = f"ticket_{ticket_id}"
        tags_list = item['tags_list']
        tier = item['tier']
        
        # Get LLM result
        result_item = results_map.get(custom_id)
        if not result_item or result_item['result']['type'] == 'errored':
            logger.warning(f"[Ticket {ticket_id}] LLM call errored or missing")
            stats['errored'] += 1
            continue
        
        # Parse LLM response
        llm_response = result_item['result']['message']
        llm_text = llm_response['content'][0]['text']
        
        # Extract JSON from markdown code block if present
        if '```json' in llm_text:
            json_start = llm_text.find('```json') + 7
            json_end = llm_text.find('```', json_start)
            llm_text = llm_text[json_start:json_end].strip()
        
        try:
            llm_result = json.loads(llm_text)
        except json.JSONDecodeError:
            logger.warning(f"[Ticket {ticket_id}] Failed to parse LLM JSON")
            stats['errored'] += 1
            continue
        
        # Tier 1 deterministic Natureza
        tier1_result = apply_tier1_natureza(tags_list)
        tier1_override = tier1_result.get('tier1_override', False) if tier1_result else False
        
        # Derive metadata flags
        metadata_flags = derive_metadata_flags(tags_list)
        
        # Resolve root_cause
        if tier1_override:
            root_cause = tier1_result['root_cause']
            llm_confidence = max(tier1_result['confidence'], llm_result.get('llm_confidence', 0))
            stats['tier1_overrides'] += 1
        else:
            root_cause = llm_result.get('root_cause', 'Unclear')
            llm_confidence = llm_result.get('llm_confidence', 0.5)
        
        # Classify Produto
        key_themes = llm_result.get('key_themes', [])
        product_l1, product_l2 = classify_produto(tags_list, key_themes, root_cause, 
                                                   ticket.get('full_conversation', ''))
        
        # Post-hoc validation
        is_consistent, conflict_warning = validate_semantic_consistency(product_l1, root_cause)
        if not is_consistent:
            logger.warning(f"[Ticket {ticket_id}] {conflict_warning}")
        
        # Classify Atendimento
        service_type = classify_atendimento(
            tags=tags_list,
            conversation=ticket.get('full_conversation', ''),
            is_claudinha_assigned=ticket.get('is_claudinha_assigned', False),
            via_channel=ticket.get('via_channel')
        )
        
        # Update stats
        if metadata_flags['is_proactive']:
            stats['proactive'] += 1
        if not metadata_flags['has_interaction']:
            stats['no_interaction'] += 1
        stats['succeeded'] += 1
        
        # Combine results
        processed_ticket = {
            # NATUREZA
            'root_cause': root_cause,
            'sentiment': llm_result.get('sentiment'),
            'key_themes': llm_result.get('key_themes'),
            'conversation_summary': llm_result.get('conversation_summary'),
            'customer_effort_score': llm_result.get('customer_effort_score'),
            'frustration_detected': llm_result.get('frustration_detected'),
            'churn_risk_flag': llm_result.get('churn_risk_flag'),
            'llm_confidence': llm_confidence,
            
            # PRODUTO
            'product_area_l1': product_l1,
            'product_area_l2': product_l2,
            
            # ATENDIMENTO
            'service_type': service_type,
            
            # METADATA
            'is_proactive': metadata_flags['is_proactive'],
            'has_interaction': metadata_flags['has_interaction'],
            
            # Pipeline metadata
            '_tier': tier,
            '_model': TIER_MODELS[tier]['model'],
            '_tier1_override': tier1_override,
            '_tier1_tag': tier1_result.get('matched_tag') if tier1_result else None,
            '_proactive_type': metadata_flags.get('proactive_type'),
            '_processing_phase': processing_phase,
            '_input_tokens': llm_response['usage']['input_tokens'],
            '_output_tokens': llm_response['usage']['output_tokens'],
            'zendesk_ticket_id': ticket_id,
            'clinic_id': ticket.get('clinic_id'),
        }
        
        processed_tickets.append(processed_ticket)
    
    # Print stats
    logger.info("\n" + "="*80)
    logger.info("BATCH PROCESSING STATS")
    logger.info("="*80)
    logger.info(f"  Succeeded: {stats['succeeded']}")
    logger.info(f"  Errored: {stats['errored']}")
    logger.info(f"  Tier 1 Overrides: {stats['tier1_overrides']}")
    logger.info(f"  Proactive: {stats['proactive']}")
    logger.info(f"  No Interaction: {stats['no_interaction']}")
    
    return processed_tickets


def main():
    parser = argparse.ArgumentParser(description='Reprocess tickets using Batch API')
    parser.add_argument('--limit', type=int, required=True, help='Number of tickets to process')
    parser.add_argument('--offset', type=int, default=0, help='Offset for pagination')
    parser.add_argument('--save-to-db', action='store_true', help='Save results to PostgreSQL')
    parser.add_argument('--phase', type=str, default='phase_3.2_full',
                        choices=['phase_3.1_golden', 'phase_3.1_subset', 'phase_3.1_full',
                                 'phase_3.2_golden', 'phase_3.2_subset', 'phase_3.2_full'],
                        help='Reprocessing phase identifier (v3.1 = 18 valores, v3.2 = 19 valores Contratacao split)')
    parser.add_argument('--chunk-size', type=int, default=5000,
                        help='Max requests per Anthropic batch (API limit ~10K, default 5000 for safety)')
    parser.add_argument('--batch-file', type=str, default='data/batch_requests.jsonl',
                        help='Path to save batch requests')
    parser.add_argument('--results-file', type=str, default='data/batch_results.jsonl',
                        help='Path to save batch results')
    parser.add_argument('--output', type=str, help='Output JSONL file for processed tickets')
    parser.add_argument('--created-after', type=str, help='Filter tickets created after this date (YYYY-MM-DD)')
    parser.add_argument('--unprocessed-only', action='store_true', help='Only fetch tickets where processing_phase IS NULL')
    args = parser.parse_args()
    
    logger.info("="*80)
    logger.info("PHASE 3: BATCH API REPROCESSING")
    logger.info("="*80)
    logger.info(f"  Processing Phase: {args.phase}")
    logger.info(f"  Limit: {args.limit}")
    logger.info(f"  Save to DB: {args.save_to_db}")
    logger.info(f"  Unprocessed only: {args.unprocessed_only}")
    
    # Initialize components
    compiler = PromptCompiler()
    router = TicketRouter()
    
    # Connect to PostgreSQL
    conn = get_postgres_connection()
    
    # Fetch tickets
    logger.info(f"\nFetching tickets from PostgreSQL...")
    if args.created_after:
        logger.info(f"  Filtering: created >= {args.created_after}")
    if args.unprocessed_only:
        logger.info(f"  Filtering: processing_phase IS NULL only")
    tickets = fetch_tickets_to_process(conn, limit=args.limit, offset=args.offset, 
                                       created_after=args.created_after,
                                       unprocessed_only=args.unprocessed_only,
                                       prioritize_clinic_ids=False)
    logger.info(f"  Fetched {len(tickets)} tickets")
    
    # Fetch clinic context
    clinic_context = {}
    try:
        from src.utils.snowflake_connection import run_query
        clinic_ids = list(set(t.get('clinic_id') for t in tickets if t.get('clinic_id') and t.get('clinic_id') > 0))
        
        if clinic_ids:
            ids_str = ','.join(str(c) for c in clinic_ids)
            logger.info(f"Fetching {len(clinic_ids)} clinic profiles from Snowflake...")
            
            df = run_query(f'''
                SELECT CLINIC_ID, IS_SUBSCRIBER, WAS_SUBSCRIBER, HAS_SIGNED_CONTRACT, HAS_CAPIM_POS
                FROM CAPIM_DATA_DEV.POSSANI_SANDBOX.CLINIC_MOST_RELEVANT_INFO
                WHERE CLINIC_ID IN ({ids_str})
            ''')
            
            if df is not None:
                for _, row in df.iterrows():
                    cid = int(row['CLINIC_ID'])
                    clinic_context[cid] = ClinicContext(
                        clinic_id=cid,
                        has_bnpl_contract=bool(row['HAS_SIGNED_CONTRACT']),
                        has_capim_pos=bool(row['HAS_CAPIM_POS']),
                        current_subscription_status=_as_router_subscription_status(
                            bool(row['IS_SUBSCRIBER']),
                            bool(row['WAS_SUBSCRIBER']),
                        ),
                    )
                logger.info(f"  Loaded {len(clinic_context)} clinic profiles")
    except Exception as e:
        logger.warning(f"Failed to load clinic context: {e}")
    
    # Create batch requests
    logger.info("\nGenerating batch requests...")
    batch_requests = create_batch_requests(tickets, compiler, router, clinic_context)
    logger.info(f"  Generated {len(batch_requests)} requests")
    
    # Split into chunks if needed
    chunk_size = args.chunk_size
    if len(batch_requests) > chunk_size:
        chunks = [batch_requests[i:i+chunk_size] for i in range(0, len(batch_requests), chunk_size)]
        logger.info(f"  Splitting into {len(chunks)} chunks of up to {chunk_size} requests each")
    else:
        chunks = [batch_requests]
    
    # Submit, poll, and download each chunk
    all_batch_results = []
    for chunk_idx, chunk in enumerate(chunks):
        chunk_label = f"[Chunk {chunk_idx+1}/{len(chunks)}]" if len(chunks) > 1 else ""
        
        # Derive chunk-specific file paths
        if len(chunks) > 1:
            base, ext = os.path.splitext(args.batch_file)
            chunk_batch_file = f"{base}_chunk{chunk_idx+1}{ext}"
            base_r, ext_r = os.path.splitext(args.results_file)
            chunk_results_file = f"{base_r}_chunk{chunk_idx+1}{ext_r}"
        else:
            chunk_batch_file = args.batch_file
            chunk_results_file = args.results_file
        
        logger.info(f"\n{chunk_label} Submitting {len(chunk)} requests...")
        try:
            batch_id = submit_batch(chunk, chunk_batch_file)
        except Exception as e:
            logger.error(f"{chunk_label} Failed to submit batch: {type(e).__name__}: {e}")
            raise
        
        # Poll for completion
        batch = poll_batch_completion(batch_id, poll_interval=30)
        
        # Download results
        chunk_results = download_batch_results(batch_id, chunk_results_file)
        all_batch_results.extend(chunk_results)
        logger.info(f"{chunk_label} Done. Total results so far: {len(all_batch_results)}")
    
    # Process results
    logger.info("\nProcessing batch results...")
    processed_tickets = process_batch_results(batch_requests, all_batch_results, args.phase)
    logger.info(f"  Processed {len(processed_tickets)} tickets")
    
    # Save to database (batch commits for performance, with reconnect on failure)
    if args.save_to_db:
        COMMIT_BATCH = 500
        MAX_RECONNECT_RETRIES = 3
        logger.info(f"\nSaving to PostgreSQL (batch commit every {COMMIT_BATCH})...")
        saved = 0
        errors = 0
        
        def _get_fresh_connection():
            """Get a fresh PostgreSQL connection."""
            fresh_conn = get_postgres_connection()
            fresh_conn.autocommit = False
            return fresh_conn
        
        def _reconnect_if_needed(current_conn):
            """Check if connection is alive; reconnect if closed."""
            try:
                cur = current_conn.cursor()
                cur.execute("SELECT 1")
                cur.close()
                return current_conn
            except Exception:
                logger.warning("Connection lost, reconnecting...")
                try:
                    current_conn.close()
                except Exception:
                    pass
                return _get_fresh_connection()
        
        # Ensure connection is fresh before save phase
        conn = _reconnect_if_needed(conn)
        cursor = conn.cursor()
        
        for i, ticket in enumerate(processed_tickets):
            try:
                key_themes = ticket.get('key_themes')
                if isinstance(key_themes, str):
                    key_themes = [k.strip() for k in key_themes.split(',')]
                cursor.execute('''
                    UPDATE ticket_insights SET
                        root_cause = %s, sentiment = %s, key_themes = %s,
                        conversation_summary = %s, customer_effort_score = %s,
                        frustration_detected = %s, churn_risk_flag = %s,
                        llm_confidence = %s, product_area = %s, product_area_l2 = %s,
                        service_type = %s, is_proactive = %s, has_interaction = %s,
                        processing_phase = %s, llm_model = %s, llm_processed_at = NOW()
                    WHERE zendesk_ticket_id = %s
                ''', (
                    ticket.get('root_cause'), ticket.get('sentiment'), key_themes,
                    ticket.get('conversation_summary'), ticket.get('customer_effort_score'),
                    ticket.get('frustration_detected'), ticket.get('churn_risk_flag'),
                    ticket.get('llm_confidence'), ticket.get('product_area_l1'),
                    ticket.get('product_area_l2'), ticket.get('service_type'),
                    ticket.get('is_proactive'), ticket.get('has_interaction'),
                    ticket.get('_processing_phase'), ticket.get('_model'),
                    ticket['zendesk_ticket_id']
                ))
                saved += 1
            except Exception as e:
                logger.error(f"Error saving ticket {ticket.get('zendesk_ticket_id')}: {e}")
                # Try to reconnect and retry once
                for retry in range(MAX_RECONNECT_RETRIES):
                    try:
                        conn = _get_fresh_connection()
                        cursor = conn.cursor()
                        logger.info(f"  Reconnected (attempt {retry+1}), retrying ticket {ticket.get('zendesk_ticket_id')}...")
                        cursor.execute('''
                            UPDATE ticket_insights SET
                                root_cause = %s, sentiment = %s, key_themes = %s,
                                conversation_summary = %s, customer_effort_score = %s,
                                frustration_detected = %s, churn_risk_flag = %s,
                                llm_confidence = %s, product_area = %s, product_area_l2 = %s,
                                service_type = %s, is_proactive = %s, has_interaction = %s,
                                processing_phase = %s, llm_model = %s, llm_processed_at = NOW()
                            WHERE zendesk_ticket_id = %s
                        ''', (
                            ticket.get('root_cause'), ticket.get('sentiment'), key_themes,
                            ticket.get('conversation_summary'), ticket.get('customer_effort_score'),
                            ticket.get('frustration_detected'), ticket.get('churn_risk_flag'),
                            ticket.get('llm_confidence'), ticket.get('product_area_l1'),
                            ticket.get('product_area_l2'), ticket.get('service_type'),
                            ticket.get('is_proactive'), ticket.get('has_interaction'),
                            ticket.get('_processing_phase'), ticket.get('_model'),
                            ticket['zendesk_ticket_id']
                        ))
                        saved += 1
                        break
                    except Exception as retry_err:
                        if retry == MAX_RECONNECT_RETRIES - 1:
                            logger.error(f"  Failed after {MAX_RECONNECT_RETRIES} retries: {retry_err}")
                            errors += 1
            if (i + 1) % COMMIT_BATCH == 0:
                try:
                    conn.commit()
                except Exception:
                    conn = _reconnect_if_needed(conn)
                    cursor = conn.cursor()
                logger.info(f"  Committed {i+1}/{len(processed_tickets)} (saved={saved}, errors={errors})")
        try:
            conn.commit()
        except Exception:
            conn = _reconnect_if_needed(conn)
            conn.commit()
        logger.info(f"  Final: saved={saved}, errors={errors} out of {len(processed_tickets)}")
    
    # Save to output file
    if args.output:
        logger.info(f"\nSaving to {args.output}...")
        _ensure_parent_dir(args.output)
        with open(args.output, 'w', encoding='utf-8') as f:
            for ticket in processed_tickets:
                f.write(json.dumps(ticket) + '\n')
        logger.info(f"  Saved {len(processed_tickets)} tickets")
    
    conn.close()
    
    logger.info("\n" + "="*80)
    logger.info("BATCH PROCESSING COMPLETE")
    logger.info("="*80)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        import traceback
        logger.error(f"FATAL ERROR: {type(e).__name__}: {e}")
        traceback.print_exc()
        # Also write to crash log file
        crash_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'crash_log.txt')
        _ensure_parent_dir(crash_path)
        with open(crash_path, 'w', encoding='utf-8') as f:
            f.write(f"FATAL: {type(e).__name__}: {e}\n\n")
            traceback.print_exc(file=f)
        sys.exit(1)
