-- OhMyCoin - generic demo data
-- Safe for public repositories. No values below represent a real person.
-- Run through flask seed-demo: it binds a freshly generated Werkzeug password hash.

SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;
-- @demo_email, @demo_name and @demo_password_hash are supplied by flask seed-demo.

INSERT INTO usuarios (nome, email, senha, nivel_acesso, ativo)
VALUES (@demo_name, @demo_email, @demo_password_hash, 'USER', 1)
ON DUPLICATE KEY UPDATE
    nome = VALUES(nome),
    senha = VALUES(senha),
    ativo = 1;

SET @usuario_id := (SELECT id FROM usuarios WHERE email = @demo_email LIMIT 1);

DELETE FROM pagamentos_dividas WHERE usuario_id = @usuario_id;
DELETE FROM movimentacoes WHERE usuario_id = @usuario_id;
DELETE FROM compras_cartao WHERE usuario_id = @usuario_id;
DELETE FROM dividas WHERE usuario_id = @usuario_id;
DELETE FROM previsoes_mensais WHERE usuario_id = @usuario_id;
DELETE FROM caixinhas WHERE usuario_id = @usuario_id;
DELETE FROM cartoes_credito WHERE usuario_id = @usuario_id;
DELETE FROM contas WHERE usuario_id = @usuario_id;
DELETE FROM categorias WHERE usuario_id = @usuario_id;

INSERT INTO categorias (usuario_id, nome, tipo, descricao) VALUES
(@usuario_id, 'Income', 'receita', 'Primary income'),
(@usuario_id, 'Freelance', 'receita', 'Additional projects'),
(@usuario_id, 'Housing', 'despesa', 'Housing and utilities'),
(@usuario_id, 'Food', 'despesa', 'Groceries and restaurants'),
(@usuario_id, 'Transport', 'despesa', 'Transport expenses'),
(@usuario_id, 'Leisure', 'despesa', 'Entertainment'),
(@usuario_id, 'Debt', 'despesa', 'Installments');

SET @cat_income := (SELECT id FROM categorias WHERE usuario_id=@usuario_id AND nome='Income');
SET @cat_freelance := (SELECT id FROM categorias WHERE usuario_id=@usuario_id AND nome='Freelance');
SET @cat_housing := (SELECT id FROM categorias WHERE usuario_id=@usuario_id AND nome='Housing');
SET @cat_food := (SELECT id FROM categorias WHERE usuario_id=@usuario_id AND nome='Food');
SET @cat_transport := (SELECT id FROM categorias WHERE usuario_id=@usuario_id AND nome='Transport');
SET @cat_leisure := (SELECT id FROM categorias WHERE usuario_id=@usuario_id AND nome='Leisure');
SET @cat_debt := (SELECT id FROM categorias WHERE usuario_id=@usuario_id AND nome='Debt');

INSERT INTO contas (usuario_id, nome, tipo, saldo_inicial, moeda, ativa) VALUES
(@usuario_id, 'Main Account', 'digital', 1500.00, 'BRL', 1),
(@usuario_id, 'Wallet', 'carteira', 200.00, 'BRL', 1);

SET @main_account := (SELECT id FROM contas WHERE usuario_id=@usuario_id AND nome='Main Account');
SET @wallet := (SELECT id FROM contas WHERE usuario_id=@usuario_id AND nome='Wallet');

INSERT INTO cartoes_credito (
    usuario_id, nome, bandeira, limite_total, dia_fechamento, dia_vencimento, ativo
) VALUES
(@usuario_id, 'Demo Card', 'Visa', 4000.00, 8, 15, 1);

SET @demo_card := (SELECT id FROM cartoes_credito WHERE usuario_id=@usuario_id AND nome='Demo Card');

SET @mes_atual := DATE_FORMAT(CURRENT_DATE(), '%Y-%m');
SET @inicio_mes := STR_TO_DATE(CONCAT(@mes_atual, '-01'), '%Y-%m-%d');

INSERT INTO previsoes_mensais (
    usuario_id, ano_mes, tipo, descricao, valor_previsto, dia_previsto,
    categoria_id, conta_id, recorrente
) VALUES
(@usuario_id, @mes_atual, 'receita', 'Monthly income', 5000.00, 5, @cat_income, @main_account, 1),
(@usuario_id, @mes_atual, 'despesa', 'Housing budget', 1400.00, 10, @cat_housing, @main_account, 1),
(@usuario_id, @mes_atual, 'despesa', 'Food budget', 900.00, 12, @cat_food, @main_account, 1);

INSERT INTO movimentacoes (
    usuario_id, tipo, valor, descricao, data_movimentacao, categoria_id, conta_id,
    forma_pagamento, origem
) VALUES
(@usuario_id, 'receita', 5000.00, 'Monthly income', DATE_ADD(@inicio_mes, INTERVAL 4 DAY), @cat_income, @main_account, 'conta', 'manual'),
(@usuario_id, 'receita', 650.00, 'Freelance project', DATE_ADD(@inicio_mes, INTERVAL 9 DAY), @cat_freelance, @main_account, 'conta', 'manual'),
(@usuario_id, 'despesa', 420.00, 'Groceries', DATE_ADD(@inicio_mes, INTERVAL 6 DAY), @cat_food, @main_account, 'conta', 'manual'),
(@usuario_id, 'despesa', 85.00, 'Transport', DATE_ADD(@inicio_mes, INTERVAL 7 DAY), @cat_transport, @wallet, 'conta', 'manual');

INSERT INTO compras_cartao (
    usuario_id, cartao_id, descricao, valor_total, valor_parcela, parcelas,
    data_compra, categoria_id, observacao
) VALUES
(@usuario_id, @demo_card, 'Demo purchase', 600.00, 200.00, 3,
 DATE_ADD(@inicio_mes, INTERVAL 3 DAY), @cat_leisure, 'Fictional purchase for demo data');

INSERT INTO dividas (
    usuario_id, descricao, credor, valor_total, saldo_devedor, taxa_juros,
    status, valor_parcela, parcelas_total, parcelas_pagas, data_inicio,
    dia_vencimento, categoria_id, conta_id, ativa, observacao
) VALUES
(@usuario_id, 'Equipment financing', 'Example Lender', 2400.00, 2400.00, 0,
 'ativa', 200.00, 12, 0, @inicio_mes, 20, @cat_debt, @main_account, 1,
 'Fictional debt used only for the public demo');

INSERT INTO caixinhas (
    usuario_id, nome, valor_guardado, meta, aporte_mensal, data_inicio, descricao
) VALUES
(@usuario_id, 'Emergency Fund', 1200.00, 5000.00, 400.00, @inicio_mes, 'Generic demo savings goal'),
(@usuario_id, 'Travel Goal', 500.00, 3000.00, 250.00, @inicio_mes, 'Generic demo savings goal');
