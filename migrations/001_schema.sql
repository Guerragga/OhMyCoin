-- OhMyCoin - canonical schema
-- This file contains structure only. It intentionally contains no real user data.
-- Run it against an empty MySQL 8+ database.

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    email VARCHAR(120) NOT NULL,
    senha VARCHAR(255) NOT NULL,
    nivel_acesso ENUM('USER','ADMIN') NOT NULL DEFAULT 'USER',
    ativo TINYINT(1) NOT NULL DEFAULT 1,
    avatar_emoji VARCHAR(16) NOT NULL DEFAULT '💰',
    tema ENUM('claro','escuro') NOT NULL DEFAULT 'escuro',
    mostrar_grafico_real_previsto TINYINT(1) NOT NULL DEFAULT 1,
    mostrar_grafico_categorias TINYINT(1) NOT NULL DEFAULT 1,
    mostrar_grafico_evolucao TINYINT(1) NOT NULL DEFAULT 1,
    mostrar_grafico_forma_pagamento TINYINT(1) NOT NULL DEFAULT 1,
    mostrar_grafico_contas TINYINT(1) NOT NULL DEFAULT 1,
    mostrar_grafico_cartoes TINYINT(1) NOT NULL DEFAULT 1,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_usuarios_email (email),
    KEY idx_usuarios_ativo (ativo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE IF NOT EXISTS categorias (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NOT NULL,
    nome VARCHAR(100) NOT NULL,
    tipo ENUM('receita','despesa','geral') NOT NULL DEFAULT 'geral',
    descricao VARCHAR(255) NULL,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_categorias_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    UNIQUE KEY uk_categoria_usuario_nome (usuario_id, nome),
    KEY idx_categorias_usuario_tipo (usuario_id, tipo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS contas (
    CONSTRAINT ck_contas_values CHECK (moeda='BRL' AND saldo_inicial >= 0),
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NOT NULL,
    nome VARCHAR(100) NOT NULL,
    tipo ENUM('corrente','poupanca','carteira','digital','investimento','outros') NOT NULL DEFAULT 'corrente',
    saldo_inicial DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    moeda CHAR(3) NOT NULL DEFAULT 'BRL',
    imagem_url VARCHAR(500) NULL,
    ativa TINYINT(1) NOT NULL DEFAULT 1,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_contas_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    UNIQUE KEY uk_contas_usuario_nome (usuario_id, nome),
    KEY idx_contas_usuario_ativa (usuario_id, ativa)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS cartoes_credito (
    CONSTRAINT ck_cartoes_credito_values CHECK (limite_total >= 0 AND dia_fechamento BETWEEN 1 AND 31 AND dia_vencimento BETWEEN 1 AND 31),
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NOT NULL,
    nome VARCHAR(100) NOT NULL,
    bandeira VARCHAR(40) NULL,
    limite_total DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    dia_fechamento TINYINT NOT NULL DEFAULT 1,
    dia_vencimento TINYINT NOT NULL DEFAULT 10,
    imagem_url VARCHAR(500) NULL,
    ativo TINYINT(1) NOT NULL DEFAULT 1,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_cartoes_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    UNIQUE KEY uk_cartoes_usuario_nome (usuario_id, nome),
    KEY idx_cartoes_usuario_ativo (usuario_id, ativo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS movimentacoes (
    CONSTRAINT ck_movimentacoes_values CHECK (valor > 0 AND parcelas BETWEEN 1 AND 240),
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NOT NULL,
    tipo ENUM('receita','despesa') NOT NULL,
    valor DECIMAL(12,2) NOT NULL,
    descricao VARCHAR(160) NOT NULL,
    data_movimentacao DATE NOT NULL,
    categoria_id INT NULL,
    conta_id INT NULL,
    forma_pagamento ENUM('conta','cartao') NOT NULL DEFAULT 'conta',
    cartao_id INT NULL,
    parcelas INT NOT NULL DEFAULT 1,
    origem ENUM('manual','divida','cartao') NOT NULL DEFAULT 'manual',
    referencia_id INT NULL,
    observacao TEXT NULL,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_mov_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    CONSTRAINT fk_mov_categoria
        FOREIGN KEY (categoria_id) REFERENCES categorias(id) ON DELETE SET NULL,
    CONSTRAINT fk_mov_conta
        FOREIGN KEY (conta_id) REFERENCES contas(id) ON DELETE SET NULL,
    CONSTRAINT fk_mov_cartao
        FOREIGN KEY (cartao_id) REFERENCES cartoes_credito(id) ON DELETE SET NULL,
    KEY idx_mov_usuario_data (usuario_id, data_movimentacao),
    KEY idx_mov_usuario_data_tipo (usuario_id, data_movimentacao, tipo),
    KEY idx_mov_usuario_categoria (usuario_id, categoria_id),
    KEY idx_mov_usuario_conta_data (usuario_id, conta_id, data_movimentacao),
    KEY idx_mov_usuario_cartao_data (usuario_id, cartao_id, data_movimentacao),
    KEY idx_mov_usuario_origem_data (usuario_id, origem, data_movimentacao),
    KEY idx_mov_forma (usuario_id, forma_pagamento),
    KEY idx_mov_origem_ref (usuario_id, origem, referencia_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS previsoes_mensais (
    CONSTRAINT ck_previsoes_mensais_values CHECK (valor_previsto > 0 AND dia_previsto BETWEEN 1 AND 31),
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NOT NULL,
    ano_mes CHAR(7) NOT NULL,
    tipo ENUM('receita','despesa') NOT NULL,
    descricao VARCHAR(160) NOT NULL,
    valor_previsto DECIMAL(12,2) NOT NULL,
    dia_previsto TINYINT NOT NULL DEFAULT 1,
    categoria_id INT NULL,
    conta_id INT NULL,
    recorrente TINYINT(1) NOT NULL DEFAULT 0,
    observacao TEXT NULL,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_prev_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    CONSTRAINT fk_prev_categoria
        FOREIGN KEY (categoria_id) REFERENCES categorias(id) ON DELETE SET NULL,
    CONSTRAINT fk_prev_conta
        FOREIGN KEY (conta_id) REFERENCES contas(id) ON DELETE SET NULL,
    KEY idx_prev_usuario_mes (usuario_id, ano_mes)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS compras_cartao (
    CONSTRAINT ck_compras_cartao_values CHECK (valor_total > 0 AND valor_parcela > 0 AND parcelas BETWEEN 1 AND 240),
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NOT NULL,
    cartao_id INT NOT NULL,
    descricao VARCHAR(160) NOT NULL,
    valor_total DECIMAL(12,2) NOT NULL,
    valor_parcela DECIMAL(12,2) NOT NULL,
    parcelas INT NOT NULL DEFAULT 1,
    data_compra DATE NOT NULL,
    categoria_id INT NULL,
    observacao TEXT NULL,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_compras_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    CONSTRAINT fk_compras_cartao
        FOREIGN KEY (cartao_id) REFERENCES cartoes_credito(id) ON DELETE CASCADE,
    CONSTRAINT fk_compras_categoria
        FOREIGN KEY (categoria_id) REFERENCES categorias(id) ON DELETE SET NULL,
    KEY idx_compras_usuario_data (usuario_id, data_compra),
    KEY idx_compras_usuario_cartao_data (usuario_id, cartao_id, data_compra),
    KEY idx_compras_usuario_categoria (usuario_id, categoria_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS dividas (
    CONSTRAINT ck_dividas_values CHECK (valor_parcela > 0 AND parcelas_total BETWEEN 1 AND 600 AND parcelas_pagas BETWEEN 0 AND parcelas_total AND saldo_devedor >= 0 AND dia_vencimento BETWEEN 1 AND 31),
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NOT NULL,
    descricao VARCHAR(160) NOT NULL,
    credor VARCHAR(120) NULL,
    valor_total DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    saldo_devedor DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    taxa_juros DECIMAL(8,4) NOT NULL DEFAULT 0.0000,
    status ENUM('ativa','quitada','renegociada','cancelada') NOT NULL DEFAULT 'ativa',
    valor_parcela DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    parcelas_total INT NOT NULL DEFAULT 1,
    parcelas_pagas INT NOT NULL DEFAULT 0,
    data_inicio DATE NOT NULL,
    dia_vencimento TINYINT NOT NULL DEFAULT 1,
    categoria_id INT NULL,
    conta_id INT NULL,
    ativa TINYINT(1) NOT NULL DEFAULT 1,
    observacao TEXT NULL,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_div_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    CONSTRAINT fk_div_categoria
        FOREIGN KEY (categoria_id) REFERENCES categorias(id) ON DELETE SET NULL,
    CONSTRAINT fk_div_conta
        FOREIGN KEY (conta_id) REFERENCES contas(id) ON DELETE SET NULL,
    KEY idx_div_usuario_status (usuario_id, status, ativa)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS pagamentos_dividas (
    CONSTRAINT ck_pagamentos_dividas_values CHECK (parcela_numero BETWEEN 1 AND 600),
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NOT NULL,
    divida_id INT NOT NULL,
    parcela_numero INT NOT NULL,
    ano_mes CHAR(7) NOT NULL,
    data_pagamento DATE NOT NULL,
    movimentacao_id INT NULL,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_pagdiv_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    CONSTRAINT fk_pagdiv_divida
        FOREIGN KEY (divida_id) REFERENCES dividas(id) ON DELETE CASCADE,
    CONSTRAINT fk_pagdiv_mov
        FOREIGN KEY (movimentacao_id) REFERENCES movimentacoes(id) ON DELETE SET NULL,
    UNIQUE KEY uk_pagdiv_parcela (usuario_id, divida_id, parcela_numero),
    KEY idx_pagdiv_usuario_mes (usuario_id, ano_mes),
    KEY idx_pagdiv_usuario_data_pagamento (usuario_id, data_pagamento)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS caixinhas (
    CONSTRAINT ck_caixinhas_values CHECK (valor_guardado >= 0 AND aporte_mensal >= 0 AND (meta IS NULL OR meta > 0)),
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NOT NULL,
    nome VARCHAR(120) NOT NULL,
    valor_guardado DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    meta DECIMAL(12,2) NULL,
    aporte_mensal DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    data_inicio DATE NULL,
    descricao TEXT NULL,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_caix_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    KEY idx_caix_usuario (usuario_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS login_attempts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(120) NOT NULL,
    ip VARCHAR(45) NOT NULL,
    tentativas INT NOT NULL DEFAULT 0,
    primeira_tentativa DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ultima_tentativa DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    bloqueado_ate DATETIME NULL,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_login_attempts_email_ip (email, ip),
    KEY idx_login_attempts_bloqueado (bloqueado_ate),
    KEY idx_login_attempts_email (email, ultima_tentativa),
    KEY idx_login_attempts_ip (ip, ultima_tentativa)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NULL,
    acao VARCHAR(80) NOT NULL,
    entidade VARCHAR(80) NULL,
    entidade_id INT NULL,
    detalhes VARCHAR(1000) NULL,
    ip VARCHAR(45) NULL,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_audit_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL,
    KEY idx_audit_usuario_data (usuario_id, criado_em),
    KEY idx_audit_acao_data (acao, criado_em),
    KEY idx_audit_entidade (entidade, entidade_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
