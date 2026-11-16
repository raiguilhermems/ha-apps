"""Garante que a divisão em routers não perdeu nenhuma rota nem mudou caminhos."""

from app.main import app

ROTAS_ESPERADAS = {
    ("GET", "/"),
    ("POST", "/lancamentos"),
    ("GET", "/lancamentos/{tx_id}/editar"),
    ("POST", "/lancamentos/{tx_id}/editar"),
    ("POST", "/transacoes/{tx_id}/pagar"),
    ("POST", "/transacoes/{tx_id}/excluir"),
    ("GET", "/parcelados"),
    ("POST", "/parcelados"),
    ("POST", "/parcelados/tx/{tx_id}/pagar"),
    ("POST", "/parcelados/{plan_id}/excluir"),
    ("GET", "/parcelados/{plan_id}/editar"),
    ("POST", "/parcelados/{plan_id}/editar"),
    ("GET", "/parcelados/importar"),
    ("POST", "/parcelados/importar/previa"),
    ("POST", "/parcelados/importar/confirmar"),
    ("GET", "/categorias"),
    ("GET", "/tags"),
    ("POST", "/categorias"),
    ("POST", "/categorias/{tag_id}/atualizar"),
    ("POST", "/categorias/{tag_id}/excluir"),
    ("GET", "/categorias/{tag_id}"),
    ("GET", "/categorias/{tag_id}/editar"),
    ("GET", "/recorrentes"),
    ("POST", "/recorrentes"),
    ("GET", "/recorrentes/{rule_id}/editar"),
    ("POST", "/recorrentes/{rule_id}/editar"),
    ("POST", "/recorrentes/{rule_id}/ativar"),
    ("POST", "/recorrentes/{rule_id}/excluir"),
    ("GET", "/configuracoes"),
    ("GET", "/configuracoes/backup"),
    ("POST", "/configuracoes/importar"),
    ("POST", "/configuracoes/apagar"),
    ("POST", "/configuracoes/projecao"),
    ("POST", "/configuracoes/dia_padrao"),
}


def test_todas_as_rotas_continuam_registradas():
    schema = app.openapi()
    registradas = {
        (metodo.upper(), caminho)
        for caminho, operacoes in schema["paths"].items()
        for metodo in operacoes
    }
    assert registradas == ROTAS_ESPERADAS
