#!/bin/bash
set -e

# Script para criar o usuário e banco de dados
# Pode ser executado manualmente ou automaticamente pelo serviço db-init

# Usa variáveis de ambiente do .env
PGHOST=${PGHOST:-db}
PGPORT=${PGPORT:-5432}

echo "Criando usuário e banco de dados..."
echo "Usando variáveis do .env:"
echo "  POSTGRES_DB: ${POSTGRES_DB:-fintelis}"
echo "  POSTGRES_USER: ${POSTGRES_USER:-fintelis}"
echo "  POSTGRES_PASSWORD: [definida no .env]"

# Usa socket Unix local (que funciona com trust) em vez de TCP
# Isso evita problemas de autenticação com scram-sha-256
PGUSER=postgres
export PGPASSWORD=""

# Garante que as variáveis estão definidas
POSTGRES_USER=${POSTGRES_USER:-fintelis}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-fintelis}
POSTGRES_DB=${POSTGRES_DB:-fintelis}

echo "Conectando ao PostgreSQL via socket Unix local como ${PGUSER}..."
echo "Criando usuário: ${POSTGRES_USER}"
echo "Criando banco: ${POSTGRES_DB}"

# Usa socket Unix local (trust funciona aqui)
# Usa EOF em vez de EOSQL para evitar problemas com expansão de variáveis
psql -v ON_ERROR_STOP=1 -U "$PGUSER" <<EOF
    -- Cria o usuário se não existir
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '${POSTGRES_USER}') THEN
            CREATE ROLE ${POSTGRES_USER} WITH LOGIN PASSWORD '${POSTGRES_PASSWORD}';
            ALTER ROLE ${POSTGRES_USER} CREATEDB;
            RAISE NOTICE 'Usuário ${POSTGRES_USER} criado com sucesso';
        ELSE
            -- Atualiza a senha caso o usuário já exista
            ALTER ROLE ${POSTGRES_USER} WITH PASSWORD '${POSTGRES_PASSWORD}';
            RAISE NOTICE 'Usuário ${POSTGRES_USER} já existe, senha atualizada';
        END IF;
    END
    \$\$;
    
    -- Cria o banco de dados se não existir
    SELECT 'CREATE DATABASE ${POSTGRES_DB} OWNER ${POSTGRES_USER}'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${POSTGRES_DB}')\gexec
    
    -- Concede todas as permissões no banco de dados
    GRANT ALL PRIVILEGES ON DATABASE ${POSTGRES_DB} TO ${POSTGRES_USER};
EOF

echo "Configuração concluída!"

