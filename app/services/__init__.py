"""Service layer facade.

Routes import this package as services. Public functions are re-exported here
while implementation stays grouped by business capability.
"""

from .common import CHART_FLAGS, mes_atual, normalizar_mes
from .users import (
    alterar_senha_perfil,
    atualizar_configuracoes,
    atualizar_perfil,
    atualizar_usuario_admin,
    configuracoes_usuario,
    criar_usuario,
    deletar_usuario_admin,
    limpar_login_falhas,
    listar_admin,
    obter_usuario_por_email,
    obter_usuario_por_id,
    registrar_auditoria,
    registrar_login_falha,
    senha_confere,
    verificar_rate_limit_login,
)
from .categories import (
    atualizar_categoria,
    criar_categoria,
    deletar_categoria,
    listar_categorias,
    obter_categoria,
)
from .accounts import deletar_conta, listar_contas, obter_conta, salvar_conta
from .transactions import (
    deletar_movimentacao,
    filtros_movimentacoes_from_args,
    listar_movimentacoes,
    listar_movimentacoes_conta,
    obter_movimentacao,
    salvar_movimentacao,
)
from .forecasts import deletar_previsao, listar_previsoes, obter_previsao, salvar_previsao
from .cards import (
    deletar_cartao,
    deletar_compra_cartao,
    listar_cartoes,
    listar_compras_cartao,
    obter_cartao,
    parcelas_cartao_mes,
    registrar_compra_cartao,
    resumo_faturas_geral,
    salvar_cartao,
)
from .debts import (
    antecipar_proxima_parcela_divida,
    deletar_divida,
    listar_dividas,
    obter_divida,
    pagar_parcela_divida,
    parcelas_dividas_mes,
    salvar_divida,
)
from .savings import deletar_caixinha, listar_caixinhas, movimentar_caixinha, obter_caixinha, salvar_caixinha
from .dashboard import obter_resumo_dashboard

__all__ = [name for name in globals() if not name.startswith("_")]
