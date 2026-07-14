"""Gamificação de indicação.

Regra (anti-fraude): um indicado só CONTA para o padrinho quando vira assinante
pago de verdade (referral_active = True) — cadastro simples não gera crédito.

Escada (services/plans.REFERRAL_TIERS): 3 indicados-ativos -> 1 mês,
10 -> 6 meses, 16 -> 12 meses (acumulado, maior tier alcançado).

O crédito é idempotente: concedemos apenas a diferença entre o total devido pela
escada e o que o padrinho já recebeu (referral_months_granted), estendendo o
plano_until dele. Assim, reprocessar um webhook nunca dá crédito em dobro.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import User
from app.services.plans import REFERRED_BONUS_DAYS, months_earned


def count_active_referrals(db: Session, referrer_id) -> int:
    return (
        db.query(User)
        .filter(User.referred_by == referrer_id, User.referral_active.is_(True))
        .count()
    )


def apply_referral_credit(db: Session, referrer: User) -> int:
    """Recalcula o crédito devido ao padrinho e concede só o incremento.
    Retorna quantos meses foram adicionados agora (0 se nada a fazer)."""
    active = count_active_referrals(db, referrer.id)
    total_due = months_earned(active)
    delta = total_due - (referrer.referral_months_granted or 0)
    if delta <= 0:
        return 0

    now = datetime.now(timezone.utc)
    base = referrer.plan_until if (referrer.plan_until and referrer.plan_until > now) else now
    referrer.plan_until = base + timedelta(days=30 * delta)
    referrer.referral_months_granted = total_due
    # Crédito dá acesso ao Pro (o valor central do produto) enquanto durar.
    if not referrer.plan or referrer.plan == "free":
        referrer.plan = "pro"
    db.commit()
    return delta


def on_referred_user_subscribed(db: Session, user: User) -> None:
    """Chamado quando `user` vira assinante pago. Marca-o como indicado-ativo
    (uma única vez) e credita o padrinho, se houver."""
    if user.referral_active or not user.referred_by:
        return
    user.referral_active = True
    # Bônus do indicado: +15 dias na primeira assinatura (o flip de referral_active
    # acima garante que isso roda UMA vez, mesmo com webhooks repetidos)
    if user.plan_until:
        user.plan_until = user.plan_until + timedelta(days=REFERRED_BONUS_DAYS)
    db.commit()
    referrer = db.get(User, user.referred_by)
    if referrer:
        apply_referral_credit(db, referrer)
