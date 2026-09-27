"""Guarda de segredos fora de desenvolvimento (deploy Cloud Run).

Por que isto merece teste próprio: `jwt_secret` assina os tokens que carregam
`tenant_id` e `role`. O valor padrão está no `.env.example`, versionado e
público. Com ele em produção, qualquer pessoa forja um token de admin de qualquer
tenant — e o RLS não protege nada, porque `get_tenant_db` passa a setar o
`app.tenant_id` que o atacante escolheu (CLAUDE.md §7.3 confia na identidade do
token).

O modo de falha que a guarda existe para impedir é **silencioso**: um deploy que
esquecesse de montar o segredo do Secret Manager subiria saudável, responderia
200 no `/health` e passaria todo teste de fumaça.
"""
import pytest
from pydantic import ValidationError

from app.core.config import JWT_SECRET_PADRAO, Settings


def _settings(**kwargs) -> Settings:
    """Instancia ignorando o `.env` do repositório — senão o teste passaria ou
    falharia conforme a máquina de quem roda."""
    return Settings(_env_file=None, **kwargs)


class TestDesenvolvimento:
    def test_aceita_o_segredo_de_exemplo(self):
        assert _settings(env="development", jwt_secret=JWT_SECRET_PADRAO).jwt_secret == JWT_SECRET_PADRAO

    def test_aceita_segredo_curto(self):
        # Atrito em desenvolvimento não compra segurança nenhuma — e compraria
        # a chance de alguém desativar a guarda inteira para trabalhar.
        assert _settings(env="development", jwt_secret="curto").jwt_secret == "curto"


class TestForaDeDesenvolvimento:
    @pytest.mark.parametrize("env", ["production", "staging", "PRODUCTION", "homologacao"])
    def test_recusa_o_segredo_de_exemplo_em_qualquer_ambiente_nao_dev(self, env):
        # Qualquer coisa que não seja exatamente "development" é tratada como
        # ambiente real: `is_development` é allowlist, não denylist, então um
        # `ENV=prod` digitado errado erra para o lado seguro.
        with pytest.raises(ValidationError, match="JWT_SECRET"):
            _settings(env=env, jwt_secret=JWT_SECRET_PADRAO)

    def test_recusa_segredo_curto(self):
        with pytest.raises(ValidationError, match="JWT_SECRET"):
            _settings(env="production", jwt_secret="a" * 31)

    def test_aceita_segredo_real(self):
        segredo = "a" * 32
        assert _settings(env="production", jwt_secret=segredo).jwt_secret == segredo

    def test_a_mensagem_diz_o_que_fazer(self):
        # Quem vê este erro está com o deploy quebrado e sem contexto: a mensagem
        # precisa apontar o caminho, não só constatar o problema.
        with pytest.raises(ValidationError) as erro:
            _settings(env="production", jwt_secret=JWT_SECRET_PADRAO)
        texto = str(erro.value)
        assert "Secret Manager" in texto
        assert "deploy/README.md" in texto


class TestPoolDeConexoes:
    def test_padrao_cabe_no_menor_tier_do_cloud_sql(self):
        """`(pool_size + max_overflow) × max-instances` tem que caber em 25.

        O `--max-instances=4` do `deploy/provisionar.sh` e estes dois números são
        um único cálculo repartido em dois arquivos. Este teste é o que amarra os
        dois: quem aumentar o pool sem olhar o deploy esgota as conexões do
        Cloud SQL em produção, sob pico — exatamente quando o motorista está
        registrando embarque.
        """
        s = _settings(env="development")
        MAX_INSTANCIAS_CLOUD_RUN = 4
        LIMITE_DB_F1_MICRO = 25
        por_instancia = s.db_pool_size + s.db_max_overflow
        assert por_instancia * MAX_INSTANCIAS_CLOUD_RUN < LIMITE_DB_F1_MICRO
