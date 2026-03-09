"""
Routing Logic for Phase 3 Multi-Tier LLM Orchestration

Routes tickets to Tier 1 (Opus 4.6), Tier 2 (Sonnet 4.5), or Tier 3 (Haiku 4.5)
based on hybrid scoring (clinic attributes + ticket attributes).

Decision: 20.7e (DECISIONS_IN_PROGRESS.md)
"""

import logging
from typing import Dict, List, Literal
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ClinicContext:
    """Clinic-level attributes from Snowflake CLINIC_MOST_RELEVANT_INFO view"""
    clinic_id: int
    has_bnpl_contract: bool
    has_capim_pos: bool
    current_subscription_status: str  # 'ativo', 'cancelado', 'nunca_assinou', etc.
    
    def score(self) -> float:
        """Calculate clinic-level routing score"""
        points = 0.0
        
        # BNPL contract: strategic product
        if self.has_bnpl_contract:
            points += 1.5
            logger.debug(f"Clinic {self.clinic_id}: +1.5 (BNPL contract)")
        
        # Capim POS: strategic product
        if self.has_capim_pos:
            points += 1.5
            logger.debug(f"Clinic {self.clinic_id}: +1.5 (Capim POS)")
        
        # Current subscriber: active relationship
        if self.current_subscription_status == 'ativo':
            points += 1.0
            logger.debug(f"Clinic {self.clinic_id}: +1.0 (active subscriber)")
        
        # Ex-subscriber: churn prevention opportunity
        elif self.current_subscription_status == 'cancelado':
            points += 0.5
            logger.debug(f"Clinic {self.clinic_id}: +0.5 (ex-subscriber)")
        
        return points


@dataclass
class TicketContext:
    """Ticket-level attributes from ticket metadata"""
    zendesk_ticket_id: int
    tags: List[str]
    escalation_level: str  # 'N1', 'N2', etc.
    assignee_group: str
    conversation_turns: int
    total_tokens: int  # estimated from conversation length
    priority: str  # 'low', 'normal', 'high', 'urgent'
    subject: str
    product_mentions: List[str]  # detected product names in conversation
    
    def is_spam_or_trivial(self) -> bool:
        """Check if ticket is spam or trivial (override to T3)"""
        
        # Spam indicators
        if self.subject and any(spam in self.subject.lower() for spam in ['test', 'teste', 'ignore', 'debug']):
            logger.debug(f"Ticket {self.zendesk_ticket_id}: SPAM (subject keyword)")
            return True
        
        # Trivial: single-turn, low priority
        if self.conversation_turns == 1 and self.priority == 'low':
            logger.debug(f"Ticket {self.zendesk_ticket_id}: TRIVIAL (1 turn + low priority)")
            return True
        
        return False
    
    def score(self) -> float:
        """Calculate ticket-level routing score"""
        points = 0.0
        
        # Churn tags: critical for retention
        churn_tags = {'churn', 'cancelamento', 'saida', 'desistencia', 'cancelar'}
        if any(tag.lower() in churn_tags for tag in self.tags):
            points += 1.5
            logger.debug(f"Ticket {self.zendesk_ticket_id}: +1.5 (churn tag)")
        
        # N2 escalation: complex or high-stakes issue
        if self.escalation_level == 'N2' or (self.assignee_group and 'N2' in self.assignee_group.upper()):
            points += 1.0
            logger.debug(f"Ticket {self.zendesk_ticket_id}: +1.0 (N2 escalation)")
        
        # Multi-product conversation: cross-domain complexity
        if len(self.product_mentions) >= 3:
            points += 0.5
            logger.debug(f"Ticket {self.zendesk_ticket_id}: +0.5 (multi-product: {len(self.product_mentions)} products)")
        
        # High complexity: long conversation or high token count
        if self.conversation_turns >= 8 or self.total_tokens >= 1500:
            points += 0.5
            logger.debug(f"Ticket {self.zendesk_ticket_id}: +0.5 (high complexity: {self.conversation_turns} turns, {self.total_tokens} tokens)")
        
        return points


TierType = Literal['T1', 'T2', 'T3']


class TicketRouter:
    """Routes tickets to appropriate LLM tier based on hybrid scoring"""
    
    # Thresholds
    TIER1_THRESHOLD = 3.0  # Hybrid score >= 3.0 => Opus 4.6
    TIER3_THRESHOLD = 1.0  # Hybrid score < 1.0 OR spam/trivial => Haiku 4.5
    
    def __init__(self, log_routing_decisions: bool = True):
        """
        Args:
            log_routing_decisions: If True, log all routing decisions for audit
        """
        self.log_routing_decisions = log_routing_decisions
        self.routing_stats = {'T1': 0, 'T2': 0, 'T3': 0}
    
    def route(self, clinic: ClinicContext, ticket: TicketContext) -> TierType:
        """
        Route ticket to appropriate tier based on hybrid scoring
        
        Args:
            clinic: Clinic-level context (from Snowflake)
            ticket: Ticket-level context (from ticket metadata)
        
        Returns:
            TierType: 'T1' (Opus), 'T2' (Sonnet), or 'T3' (Haiku)
        """
        
        # OVERRIDE RULE: Spam/trivial => T3 (regardless of score)
        if ticket.is_spam_or_trivial():
            tier = 'T3'
            reason = "SPAM/TRIVIAL override"
            logger.info(f"Ticket {ticket.zendesk_ticket_id} => {tier} ({reason})")
            self.routing_stats[tier] += 1
            
            if self.log_routing_decisions:
                self._log_decision(clinic, ticket, tier, reason, clinic_score=0, ticket_score=0, hybrid_score=0)
            
            return tier
        
        # Calculate hybrid score
        clinic_score = clinic.score()
        ticket_score = ticket.score()
        hybrid_score = clinic_score + ticket_score
        
        # FIX (2026-02-14): When clinic context is unknown (clinic_id=0/NULL),
        # default to T2 (Sonnet) for non-trivial tickets instead of T3 (Haiku).
        # Root cause: 62% of tickets have NULL clinic_id => clinic_score=0 =>
        # hybrid_score always < 1.0 → 99% routed to T3, defeating tier strategy.
        # Fix: floor hybrid_score to TIER3_THRESHOLD so unknown-clinic tickets
        # land in T2 by default. T1 still requires high ticket_score signals.
        if clinic_score == 0 and (clinic.clinic_id == 0 or clinic.clinic_id is None):
            hybrid_score = max(hybrid_score, self.TIER3_THRESHOLD)
        
        logger.debug(f"Ticket {ticket.zendesk_ticket_id}: clinic_score={clinic_score:.1f}, ticket_score={ticket_score:.1f}, hybrid={hybrid_score:.1f}")
        
        # Routing logic
        if hybrid_score >= self.TIER1_THRESHOLD:
            tier = 'T1'
            reason = f"Hybrid score {hybrid_score:.1f} >= {self.TIER1_THRESHOLD}"
        elif hybrid_score < self.TIER3_THRESHOLD:
            tier = 'T3'
            reason = f"Hybrid score {hybrid_score:.1f} < {self.TIER3_THRESHOLD}"
        else:
            tier = 'T2'
            reason = f"Default (hybrid score {hybrid_score:.1f} in [{self.TIER3_THRESHOLD}, {self.TIER1_THRESHOLD}))"
        
        logger.info(f"Ticket {ticket.zendesk_ticket_id} (clinic {clinic.clinic_id}) => {tier} ({reason})")
        self.routing_stats[tier] += 1
        
        if self.log_routing_decisions:
            self._log_decision(clinic, ticket, tier, reason, clinic_score, ticket_score, hybrid_score)
        
        return tier
    
    def _log_decision(self, clinic: ClinicContext, ticket: TicketContext, tier: TierType, 
                      reason: str, clinic_score: float, ticket_score: float, hybrid_score: float):
        """Log routing decision for audit (can be extended to write to DB/file)"""
        
        # For now, just structured logging
        # In production, write to a dedicated audit table or file
        logger.info(
            f"ROUTING_DECISION | "
            f"ticket_id={ticket.zendesk_ticket_id} | "
            f"clinic_id={clinic.clinic_id} | "
            f"tier={tier} | "
            f"clinic_score={clinic_score:.2f} | "
            f"ticket_score={ticket_score:.2f} | "
            f"hybrid_score={hybrid_score:.2f} | "
            f"reason='{reason}' | "
            f"has_bnpl={clinic.has_bnpl_contract} | "
            f"has_pos={clinic.has_capim_pos} | "
            f"subscription={clinic.current_subscription_status} | "
            f"escalation={ticket.escalation_level} | "
            f"turns={ticket.conversation_turns} | "
            f"tokens={ticket.total_tokens}"
        )
    
    def get_stats(self) -> Dict[str, int]:
        """Get routing statistics"""
        return self.routing_stats.copy()
    
    def get_distribution(self) -> Dict[str, float]:
        """Get routing distribution as percentages"""
        total = sum(self.routing_stats.values())
        if total == 0:
            return {'T1': 0.0, 'T2': 0.0, 'T3': 0.0}
        
        return {
            tier: (count / total) * 100
            for tier, count in self.routing_stats.items()
        }


# Example usage and testing
if __name__ == "__main__":
    # Test cases
    router = TicketRouter(log_routing_decisions=True)
    
    print("=" * 80)
    print("TESTING ROUTING LOGIC")
    print("=" * 80)
    
    # Test 1: Strategic clinic + churn ticket => T1
    print("\n--- Test 1: Strategic clinic + churn ticket ---")
    clinic1 = ClinicContext(
        clinic_id=12345,
        has_bnpl_contract=True,
        has_capim_pos=True,
        current_subscription_status='ativo'
    )
    ticket1 = TicketContext(
        zendesk_ticket_id=100001,
        tags=['churn', 'cancelamento'],
        escalation_level='N2',
        assignee_group='Support_N2',
        conversation_turns=10,
        total_tokens=1800,
        priority='high',
        subject='Cliente quer cancelar assinatura',
        product_mentions=['bnpl', 'saas', 'pos']
    )
    tier1 = router.route(clinic1, ticket1)
    print(f"[OK] Expected: T1, Got: {tier1}")
    assert tier1 == 'T1', f"Expected T1, got {tier1}"
    
    # Test 2: Standard clinic + standard ticket => T2
    print("\n--- Test 2: Standard clinic + standard ticket ---")
    clinic2 = ClinicContext(
        clinic_id=67890,
        has_bnpl_contract=False,
        has_capim_pos=False,
        current_subscription_status='ativo'
    )
    ticket2 = TicketContext(
        zendesk_ticket_id=100002,
        tags=['duvida', 'agenda'],
        escalation_level='N1',
        assignee_group='Support_N1',
        conversation_turns=4,
        total_tokens=800,
        priority='normal',
        subject='Dúvida sobre agendamento',
        product_mentions=['saas']
    )
    tier2 = router.route(clinic2, ticket2)
    print(f"[OK] Expected: T2, Got: {tier2}")
    assert tier2 == 'T2', f"Expected T2, got {tier2}"
    
    # Test 3: Spam ticket => T3 (override)
    print("\n--- Test 3: Spam ticket (override) ---")
    clinic3 = ClinicContext(
        clinic_id=99999,
        has_bnpl_contract=True,
        has_capim_pos=True,
        current_subscription_status='ativo'
    )
    ticket3 = TicketContext(
        zendesk_ticket_id=100003,
        tags=[],
        escalation_level='N1',
        assignee_group='Support_N1',
        conversation_turns=1,
        total_tokens=50,
        priority='low',
        subject='Test ticket please ignore',
        product_mentions=[]
    )
    tier3 = router.route(clinic3, ticket3)
    print(f"[OK] Expected: T3 (spam override), Got: {tier3}")
    assert tier3 == 'T3', f"Expected T3, got {tier3}"
    
    # Test 4: Trivial ticket => T3
    print("\n--- Test 4: Trivial ticket ---")
    clinic4 = ClinicContext(
        clinic_id=11111,
        has_bnpl_contract=False,
        has_capim_pos=False,
        current_subscription_status='nunca_assinou'
    )
    ticket4 = TicketContext(
        zendesk_ticket_id=100004,
        tags=['info'],
        escalation_level='N1',
        assignee_group='Support_N1',
        conversation_turns=1,
        total_tokens=100,
        priority='low',
        subject='Como funciona o sistema?',
        product_mentions=[]
    )
    tier4 = router.route(clinic4, ticket4)
    print(f"[OK] Expected: T3 (trivial), Got: {tier4}")
    assert tier4 == 'T3', f"Expected T3, got {tier4}"
    
    # Test 5: Ex-subscriber + N2 escalation => T1
    print("\n--- Test 5: Ex-subscriber + N2 escalation ---")
    clinic5 = ClinicContext(
        clinic_id=22222,
        has_bnpl_contract=False,
        has_capim_pos=True,
        current_subscription_status='cancelado'
    )
    ticket5 = TicketContext(
        zendesk_ticket_id=100005,
        tags=['problema_tecnico'],
        escalation_level='N2',
        assignee_group='Support_N2',
        conversation_turns=6,
        total_tokens=1200,
        priority='high',
        subject='Problema crítico com POS',
        product_mentions=['pos', 'pagamento']
    )
    tier5 = router.route(clinic5, ticket5)
    print(f"[OK] Expected: T1, Got: {tier5}")
    assert tier5 == 'T1', f"Expected T1, got {tier5}"
    
    # Print statistics
    print("\n" + "=" * 80)
    print("ROUTING STATISTICS")
    print("=" * 80)
    stats = router.get_stats()
    dist = router.get_distribution()
    print(f"T1 (Opus 4.6):   {stats['T1']} tickets ({dist['T1']:.1f}%)")
    print(f"T2 (Sonnet 4.5): {stats['T2']} tickets ({dist['T2']:.1f}%)")
    print(f"T3 (Haiku 4.5):  {stats['T3']} tickets ({dist['T3']:.1f}%)")
    print(f"TOTAL:           {sum(stats.values())} tickets")
    
    print("\n[OK] All tests passed!")
