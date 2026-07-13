"""Planos, features e regras de acesso — fonte única da verdade sobre o que
cada plano libera. Usado por gating de endpoints e pela página de preços.

Planos (mensal, BRL): free (sem assinatura) | starter 37 | pro 87 | agency 257
"""
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class Plan:
    key: str
    name: str
    price_brl: int
    linkedin_accounts: int          # nº máximo de contas LinkedIn conectáveis
    ai_images: bool                 # geração de imagem por IA
    doc_upload: bool                # material de referência (upload de docs)
    brand_profile: bool            # perfil de marca avançado


PLANS: dict[str, Plan] = {
    "free":    Plan("free",    "Gratuito", 0,   linkedin_accounts=1,  ai_images=False, doc_upload=False, brand_profile=False),
    "starter": Plan("starter", "Starter",  37,  linkedin_accounts=1,  ai_images=False, doc_upload=False, brand_profile=True),
    "pro":     Plan("pro",     "Pro",      87,  linkedin_accounts=2,  ai_images=True,  doc_upload=True,  brand_profile=True),
    "agency":  Plan("agency",  "Agency",   257, linkedin_accounts=10, ai_images=True,  doc_upload=True,  brand_profile=True),
}

# Recompensa de indicação: nº de indicados-assinantes -> meses de crédito (acumulados)
# Escada do Tales: 3 -> 1 mês, 10 -> 6 meses, 16 -> 12 meses.
REFERRAL_TIERS = [(3, 1), (10, 6), (16, 12)]


def plan_of(user) -> Plan:
    """Plano efetivo do usuário: assinatura ativa/trial, ou crédito de indicação, senão free."""
    now = datetime.now(timezone.utc)
    if user.plan and user.plan in PLANS and user.plan != "free":
        # Assinatura paga vale enquanto ativa; crédito de indicação enquanto não expira.
        if user.plan_until is None or user.plan_until > now:
            return PLANS[user.plan]
    return PLANS["free"]


def require_feature(user, feature: str) -> bool:
    return getattr(plan_of(user), feature, False)


def months_earned(active_referrals: int) -> int:
    """Meses de crédito conforme a escada (maior tier alcançado)."""
    earned = 0
    for threshold, months in REFERRAL_TIERS:
        if active_referrals >= threshold:
            earned = months
    return earned
