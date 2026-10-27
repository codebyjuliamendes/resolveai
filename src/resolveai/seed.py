"""Dados fictícios de demonstração, criados quando a base está vazia."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from resolveai.models import Article, Ticket

DEMO_ARTICLES: tuple[tuple[str, str, str], ...] = (
    (
        "Pedido marcado como entregue, mas não chegou",
        "Entrega",
        "Peça ao cliente para verificar a portaria e confirmar o endereço informado. Se ainda "
        "não encontrar o pedido, fale com a loja e com o entregador pelo painel. Não confirme "
        "uma nova entrega antes de validar a localização.",
    ),
    (
        "Como consultar o prazo de estorno",
        "Pagamento",
        "Quando um cancelamento é aprovado, o estorno volta para o meio de pagamento original. "
        "O prazo depende do banco e da operadora do cartão; consulte a transação no painel "
        "antes de informar uma data. Não prometa um prazo específico sem confirmar a "
        "modalidade.",
    ),
    (
        "Quero alterar o endereço do pedido",
        "Entrega",
        "Depois que o pedido é confirmado, alterações de endereço dependem da etapa e da loja. "
        "Consulte o status atual, confirme a possibilidade com o estabelecimento e informe "
        "eventual diferença de taxa antes de atualizar os dados.",
    ),
    (
        "Item faltando ou diferente no pedido",
        "Pedido",
        "Peça uma descrição do item e, se possível, foto da embalagem. Consulte os itens "
        "confirmados e o comprovante da loja. Se a divergência for confirmada, explique as "
        "opções de solução previstas na política de atendimento.",
    ),
    (
        "Informações sobre alergênicos",
        "Segurança alimentar",
        "Não confirme que um prato é seguro para uma alergia sem informação oficial da loja. "
        "Consulte a ficha do produto ou peça confirmação direta ao estabelecimento. Oriente o "
        "cliente a não consumir o item enquanto não houver confirmação.",
    ),
)

DEMO_TICKETS: tuple[tuple[str, str, str, str, str, str, str], ...] = (
    (
        "Camila Rocha",
        "camila@email.test",
        "Meu pedido aparece como entregue",
        "O aplicativo mostra que chegou, mas não recebi nada e já procurei na portaria.",
        "Entrega",
        "Alta",
        "novo",
    ),
    (
        "Pedro Alves",
        "pedro@email.test",
        "Ainda não recebi o estorno",
        "O cancelamento foi aprovado ontem. Como acompanho a devolução no cartão?",
        "Pagamento",
        "Normal",
        "em_atendimento",
    ),
    (
        "Lia Costa",
        "lia@email.test",
        "Veio um item diferente",
        "Pedi um suco de laranja e recebi limonada.",
        "Pedido",
        "Normal",
        "novo",
    ),
)


def seed_demo_data(session: Session) -> bool:
    """Insere os dados de demonstração se não houver artigos. Retorna True se inseriu."""
    if session.scalar(select(func.count()).select_from(Article)):
        return False
    session.add_all(Article(title=t, category=c, body=b) for t, c, b in DEMO_ARTICLES)
    session.add_all(
        Ticket(
            customer=customer,
            email=email,
            subject=subject,
            message=message,
            category=category,
            priority=priority,
            status=status,
        )
        for customer, email, subject, message, category, priority, status in DEMO_TICKETS
    )
    session.commit()
    return True
