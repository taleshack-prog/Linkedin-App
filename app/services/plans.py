"""Planos, features e regras de acesso — fonte única da verdade sobre o que
cada plano libera. Usado por gating de endpoints e pela página de preços.

Planos (mensal, BRL): free (sem assinatura) | starter 20 | pro 45,70 | agency 100
"""
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class Plan:
    key: str
    name: str
    price_cents: int                # MENSAL, em CENTAVOS (padrão Stripe; sem float em dinheiro)
    price_cents_annual: int         # ANUAL, em centavos (10x o mensal = 2 meses grátis)
    linkedin_accounts: int          # nº máximo de contas LinkedIn conectáveis
    ai_images: bool                 # geração de imagem por IA
    doc_upload: bool                # material de referência (upload de docs)
    brand_profile: bool             # perfil de marca
    text_formatting: bool           # negrito/itálico/mono (Unicode) no editor


PLANS: dict[str, Plan] = {
    "free":    Plan("free",    "Gratuito",     0, price_cents_annual=0,      linkedin_accounts=1,  ai_images=False, doc_upload=False, brand_profile=False, text_formatting=False),
    "starter": Plan("starter", "Starter",   2000, price_cents_annual=20000,  linkedin_accounts=1,  ai_images=False, doc_upload=False, brand_profile=True,  text_formatting=False),
    "pro":     Plan("pro",     "Pro",       4570, price_cents_annual=45700,  linkedin_accounts=2,  ai_images=True,  doc_upload=True,  brand_profile=True,  text_formatting=True),
    "agency":  Plan("agency",  "Agency",   10000, price_cents_annual=100000, linkedin_accounts=10, ai_images=True,  doc_upload=True,  brand_profile=True,  text_formatting=True),
}

# Bônus do INDICADO: dias extras ao assinar via link de indicação
REFERRED_BONUS_DAYS = 15

# Recompensa do PADRINHO: nº de indicados-assinantes -> meses de crédito (acumulados)
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


def has_active_subscription(user) -> bool:
    """Sem assinatura ativa (ou crédito de indicação vigente), não há serviço.

    Não existe plano gratuito: o núcleo do produto (gerar com IA, conectar o
    LinkedIn, publicar) custa dinheiro real por uso. 'free' aqui significa
    'sem assinatura', não 'plano grátis'.
    """
    return plan_of(user).key != "free"


def require_feature(user, feature: str) -> bool:
    return getattr(plan_of(user), feature, False)


def months_earned(active_referrals: int) -> int:
    """Meses de crédito conforme a escada (maior tier alcançado)."""
    earned = 0
    for threshold, months in REFERRAL_TIERS:
        if active_referrals >= threshold:
            earned = months
    return earned


CYCLES = ("monthly", "annual")


def annual_savings_cents(plan: Plan) -> int:
    """Quanto o cliente economiza pagando anual (12 mensais - 1 anual)."""
    return plan.price_cents * 12 - plan.price_cents_annual
