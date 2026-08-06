# Pesquisa de Mercado — Software de Gestão para Barbearias e Salões (Brasil)

> Data da pesquisa: **2026-08-06**. Toda afirmação factual abaixo vem de fonte consultada nesta data (busca na web; várias páginas oficiais bloquearam acesso direto — nesses casos os dados vieram de resultados de busca sobre as páginas oficiais ou de fontes secundárias identificadas). O que não pôde ser confirmado está marcado literalmente como **não confirmado**.

---

## 1. Panorama do mercado brasileiro

- O Brasil tinha, segundo levantamento do Sebrae, cerca de **1.058.594 salões de beleza registrados no CNAE 9602-5/02 como atividade primária** e **199.305 como atividade secundária**, totalizando **~1,26 milhão de estabelecimentos ativos** — o segundo maior setor em quantidade de empresas ativas do país. Fonte: Sebrae PR ("Sebrae em Dados — Salões de Beleza", sebraepr.com.br) e BuyCo (buyco.com.br/mercado-de-saloes-de-beleza/), consultadas via busca em 2026-08-06.
- Cerca de **1,3 milhão dos ~15 milhões de MEIs** do país são profissionais de beleza (cabeleireiros, barbeiros, esteticistas, manicures — **9,1% do total de MEIs**). Em 2023 foram **mais de 180 mil novos MEIs no setor (média de 524 novos negócios/dia)**. Fonte: Agência Sebrae de Notícias (agenciasebrae.com.br), consultada via busca em 2026-08-06.
- **99,75% dos salões são micro e pequenas empresas**; o setor gera mais de 7 milhões de empregos diretos e indiretos. Fonte: Sebrae/BuyCo (mesmas páginas acima), 2026-08-06.
- Implicação: o mercado endereçável é enorme, extremamente pulverizado e dominado por negócios pequenos com baixa maturidade de gestão — o software vence por simplicidade e preço, não por profundidade corporativa.

## 2. Dores estruturais do setor

### 2.1 No-show (faltas)
- Em salões **sem confirmação automatizada, o no-show consome 15–20% da agenda**; salões sem regras claras de agendamento perdem **até R$ 3.200/mês** em faltas e horários desperdiçados. Fontes: Blog Belio (blog.belio.com.br/artigos/como-reduzir-no-shows-salao-beleza/ e /regras-agendamento-salao-beleza/), consultadas via busca em 2026-08-06.
- Para barbearias, estimativa do Barbeiro.app: **cada no-show custa em média R$ 55–70**; exemplo publicado: barbearia com 3 profissionais, 10 atendimentos/dia cada e 15% de faltas perde ~R$ 270/dia (~R$ 5.940/mês). Fonte: barbeiro.app/blog/mensagem-confirmacao-barbearia, via busca em 2026-08-06. (Estimativas de fornecedor — tratar como referência, não como dado independente.)
- Confirmação ativa por WhatsApp + política de cancelamento + lista de espera **cortam faltas em 30% a 60%**, segundo o mesmo conjunto de fontes (Belio/Barbeiro.app). Percentual exato independente: **não confirmado**.

### 2.2 Recorrência e assinatura
- O modelo "clube de assinatura" (corte + barba recorrentes) é tendência explorada comercialmente: a própria Trinks vende "Clube de Assinaturas" para barbearias (negocios.trinks.com/negocios/barbearias/, via busca em 2026-08-06) e players de nicho como BestBarbers se posicionam em "app próprio + clube de assinaturas" (bestbarbers.app, via busca em 2026-08-06).
- Penetração real de assinatura nas barbearias brasileiras: **não confirmado** (não encontrei estatística pública).

### 2.3 Gestão de cadeiras / Salão Parceiro
- O regime "Salão Parceiro" (Lei 13.352/2016) formaliza a parceria salão–profissional com divisão de receita via contrato; comissões de mercado citadas entre **30% e 50%** do serviço. Fontes: GG Contabilidade (ggcontabilidade.com/salao-parceiro/) e Blog Belio (blog.belio.com.br/artigos/como-calcular-comissao-cabeleireiro/), via busca em 2026-08-06.
- Nos softwares pesquisados, "comissão por profissional" é comum, mas **gestão explícita de aluguel de cadeira quase não aparece como funcionalidade nomeada**: o mais próximo encontrado foi o BestBarbers ("agendamento por cadeira", comissões compartilhadas, barbeiros em múltiplas unidades — bestbarbers.app, via busca 2026-08-06). Nos demais (Trinks, Avec, AppBarber, Booksy, Fresha): **não confirmado** que exista módulo de aluguel de cadeira.

### 2.4 Caixa, comissão e visão financeira (DRE)
- Comissão automática, comanda, caixa e estoque são o "feijão com arroz" dos líderes (Trinks, AppBarber, Avec — fontes nas fichas abaixo). Porém **DRE (demonstrativo de resultado) como funcionalidade nomeada não foi confirmada em nenhum concorrente pesquisado** — os sites falam em "relatórios financeiros", "fluxo de caixa", "controle financeiro". Para todos: DRE = **não confirmado**.

### 2.5 WhatsApp: oficial vs. não oficial
- WhatsApp é o canal dominante de agendamento/confirmação no Brasil. Vários players anunciam automação por WhatsApp, mas **poucos declaram usar a API oficial da Meta**: o Barbeiro.app declara explicitamente usar a API oficial do WhatsApp Business (com modo de coexistência para manter o número da barbearia) e contrapõe-se a "APIs não oficiais que arriscam bloqueio do número". Fonte: barbeiro.app e barbeiro.app/blog/agendamento-online-barbearia, via busca em 2026-08-06. Opero também anuncia "WhatsApp oficial" (gestaoparabarbearia.com.br, via busca 2026-08-06).
- Para Trinks (que tem "Rotina de Mensagens" via WhatsApp com confirmação automática, lembrete 24h e 1h antes e pedido de avaliação — ajuda.trinks.com, via busca 2026-08-06) e Avec (agendamento por WhatsApp 24h e lembretes automáticos — avec.app, via busca 2026-08-06): **não confirmado** se usam a API oficial da Meta.

---

## 3. Fichas dos concorrentes

Formato: dados confirmados com fonte + data; lacunas marcadas "não confirmado". O acesso direto às páginas de planos de Trinks, Avec e AppBarber foi bloqueado (HTTP 403) — preços vieram dos resultados de busca sobre essas páginas e de fontes secundárias nomeadas.

### 3.1 Trinks (Brasil)
- **País/dono**: Brasil; "empresa do Grupo Stone" (Reclame Aqui, página "Sobre Trinks", 2026-08-06).
- **Público-alvo**: salões, barbearias, clínicas de estética; afirma **+40 mil empreendedores** (Reclame Aqui "Sobre", 2026-08-06). Fontes secundárias sugerem que serve melhor salões com 10+ profissionais (agende-me.com/comparacao-sistemas-agendamento/, 2026-08-06).
- **Preço**: teste grátis de 5 dias, sem taxa de setup (negocios.trinks.com/planos/, via busca 2026-08-06). Valores citados por terceiros em 2026: **inicial ~R$ 89/mês**, com "funcionalidades essenciais como agendamento online direto e multi-profissional apenas nos planos R$ 149–249" (agendiva.com.br/blog/trinks-vs-belezzia-vs-agendiva, 2026-08-06); **R$ 110/mês para 1–2 profissionais** (agende-me.com, 2026-08-06); **plano anual "a partir de R$ 65/mês"** (revistaforum.com.br/cupom/trinks/, 2026-08-06). Tabela oficial completa: **não confirmado** (página bloqueada).
- **Funcionalidades confirmadas**: agenda online 24/7 com confirmação instantânea; integração Reserve with Google; Rotina de Mensagens WhatsApp (confirmação automática, lembrete 24h e 1h antes, pesquisa de avaliação, mensagens personalizáveis) (ajuda.trinks.com, 2026-08-06); comissões automáticas e divisão de valores; estoque; fechamento automático de conta; pagamentos integrados; vouchers/descontos; Clube de Assinaturas para barbearias (recorrência) (negocios.trinks.com, via busca 2026-08-06); cobrança de entrada no agendamento para reduzir no-show (agende-me.com, 2026-08-06); BI/CRM e API como integrações adicionais (negocios.trinks.com/solucoes/, via busca 2026-08-06).
- **WhatsApp oficial (API Meta)**: não confirmado. **Lista de espera**: não confirmado. **Aluguel de cadeira**: não confirmado. **DRE**: não confirmado. **White label**: não confirmado.
- **Reputação**: Reclame Aqui nota **8,7/10**, 99 reclamações, 100% respondidas, 97,7% resolvidas, nota do consumidor 7,52 (reclameaqui.com.br/empresa/trinks/, 2026-08-06). Reclamações recorrentes: problemas no agendamento online/cadastro, dificuldade de cancelar assinatura, notas fiscais duplicadas; há relato individual "sistema não é confiável" e reclamação de quem migrou da Avec (títulos de reclamações públicas, mesma página, 2026-08-06).

### 3.2 Avec / SalãoVIP (Brasil — grupo Hyperlocal)
- **País/dono**: Brasil; nasceu em 2013 como "Salão Vip", virou fintech Avec; hoje aparece no Reclame Aqui como "Avec by Hyperlocal" (Correio Braziliense 2019 + Reclame Aqui, via busca 2026-08-06). SalãoVIP segue existindo como produto/site próprio (salaovip.com.br, 2026-08-06).
- **Público-alvo**: salões, barbearias, clínicas e SPAs; afirma **40 mil estabelecimentos** (avec.app, via busca 2026-08-06).
- **Preço**: valores citados em resultados de busca sobre a página oficial de planos: **plano a partir de R$ 279,90/mês** e outro de **R$ 369,90/mês**, aplicados a empresas com 20 funcionários, variando conforme número de funcionários (negocios.avec.app/planos e /avec-planos, via busca 2026-08-06). Estrutura completa de planos e preço para negócios pequenos: **não confirmado** (página bloqueada).
- **Funcionalidades confirmadas**: agendamento por WhatsApp 24h; lembretes automáticos para reduzir no-show; pagamentos integrados (maquininha, conta digital, conciliação); controle financeiro/fluxo de caixa em tempo real; controle de estoque; automação com IA (avec.app e negocios.avec.app, via busca 2026-08-06; estoque também em Correio Braziliense 2019).
- **WhatsApp oficial**: não confirmado. **Recorrência/assinatura**: não confirmado. **Lista de espera**: não confirmado. **Fidelidade**: não confirmado. **Aluguel de cadeira**: não confirmado. **DRE**: não confirmado. **White label**: não confirmado.
- **Reputação**: reclamações públicas no Reclame Aqui (registradas sob "Hyperlocal", "Avec by Hyperlocal" e "Belezasoft"): suporte ineficiente/demorado (casos sem resposta por meses), bugs e dificuldade de configuração, cobranças indevidas, bloqueio de acesso por pagamento, faturamento retido, limitação de grade horária por tipo de serviço (reclameaqui.com.br, várias reclamações, 2026-08-06). Nota agregada da empresa: **não confirmado** (não obtive o número).

### 3.3 AppBarber / AppBeleza (Brasil)
- **Público-alvo**: barbearias (AppBarber) e salões (AppBeleza).
- **Preço (fonte oficial — central de ajuda Zendesk, via busca 2026-08-06)**: **Mensal R$ 79,90 no cartão; Semestral R$ 406,80 (~R$ 67,80/mês, −15%); Anual R$ 670,80 (~R$ 55,90/mês, −30%)**; desconto extra de 5% à vista (boleto/PIX/cartão). A diferença entre planos é **apenas a quantidade de profissionais** — todas as funções em todos os planos.
- **Funcionalidades confirmadas**: agendamento online (webadmin + app), caixa, financeiro, gestão de pacotes, estoque (com valor de inventário), programa de fidelidade, pesquisa de satisfação, **lista de espera**, mensagens automáticas de retorno, comanda gerada por agendamento (serviços + produtos), comissões por profissional, histórico de clientes, relatórios financeiros (appbarber.com.br + central de ajuda, via busca 2026-08-06).
- **App**: app cliente com **4,9/5 e ~99 mil avaliações na App Store** (apps.apple.com AppBarber Cliente, via busca 2026-08-06); app do profissional (AppBarber PRO). Existem apps individuais de barbearias na App Store aparentemente ligados à plataforma, mas white label como produto oficial: **não confirmado**.
- **WhatsApp oficial**: não confirmado. **Confirmação automática via WhatsApp**: não confirmado (há "lembretes automáticos" via app/push; canal exato não confirmado). **Recorrência**: não confirmado. **Aluguel de cadeira**: não confirmado. **DRE**: não confirmado.
- **Reputação**: Reclame Aqui nota **6,6/10**, 41 reclamações, **57,9% resolvidas**, tempo médio de resposta 1 dia e 11 h (jan–jun/2026) (reclameaqui.com.br/empresa/app-barber/, 2026-08-06). Reclamações recorrentes: cobrança indevida e renovação automática difícil de desativar, dificuldade de cancelamento, falhas em agendamento/estoque/pacotes, suporte ineficiente.

### 3.4 Booksy (internacional; opera no Brasil)
- **País**: origem polonesa/americana; no Brasil desde antes de 2021 — recebeu aporte de US$ 70 mi e planejava dobrar a operação brasileira (Exame, via busca 2026-08-06).
- **Público-alvo**: barbearias e salões; forte modelo **marketplace** (cliente descobre profissionais no app; integração nativa com Instagram — botão "Agendar") (agende-me.com, 2026-08-06).
- **Preço Brasil**: **R$ 99,90/mês para 1 profissional + R$ 20/mês por profissional adicional** (agende-me.com, 2026-08-06; Exame citou "assinatura de 99 reais por mês"). Preço EUA: US$ 29,99/mês + US$ 20/membro adicional (biz.booksy.com/pricing, via busca 2026-08-06). Todas as funcionalidades inclusas na assinatura (marketing, message blasts, **lista de espera**, gift cards). Plano grátis limitado permanente citado em fonte secundária: **não confirmado** para o Brasil.
- **Boost (aquisição de clientes)**: comissão única de **30% do valor do primeiro atendimento** de cliente novo vindo do marketplace; para serviços com preço "variável", cobrança fixa de **R$ 25** (booksy.com/blog/br/, via busca 2026-08-06).
- **Anti-no-show**: permite cobrar entrada/pré-pagamento no agendamento (agende-me.com, 2026-08-06).
- **WhatsApp oficial**: não confirmado (comunicação por SMS/push aparece nas reclamações). **Comissão de equipe / estoque / caixa / DRE / aluguel de cadeira / white label / recorrência**: não confirmado.
- **Reputação Brasil**: Reclame Aqui — 10 reclamações avaliadas, nota do consumidor **5,2**, 60% resolvidas, 40% voltariam a fazer negócio (reclameaqui.com.br/empresa/booksy/, 2026-08-06). Recorrentes: cobrança diferente do valor anunciado, bloqueio de conta mesmo com pagamento em dia, impossibilidade de cancelar, SPAM de SMS.

### 3.5 Fresha (internacional)
- **País**: Reino Unido (ex-Shedul, fundada 2015); presente em 120+ países, 100 mil negócios ativos, 18 mi de agendamentos/mês (PR Newswire, via busca 2026-08-06). Lançou a plataforma **em português do Brasil em 2023**; listada como disponível em SP, RJ, Salvador, Brasília, Fortaleza, BH, Manaus, Curitiba, Recife e Porto Alegre (Inforchannel/PR Newswire, via busca 2026-08-06).
- **Preço (global, USD)**: **removeu o plano grátis-para-sempre no início de 2025**; assinatura a partir de **US$ 19,95/mês (solo)** ou **US$ 14,95/membro agendável/mês (equipe)**; **comissão de 20% (mín. US$ 6) sobre clientes novos vindos do marketplace**; processamento de pagamentos ~2,19% + US$ 0,20 por transação (Pabau, TheSalonBusiness, SchedulingKit, RZRV — via busca 2026-08-06). **Preços em R$ e processamento de pagamentos no Brasil: não confirmado.**
- **Reclamações recorrentes (fontes internacionais)**: custo real muito acima da assinatura quando somadas comissões de 20% e taxas de processamento; insatisfação com o fim do plano grátis (mesmas fontes, 2026-08-06).
- **WhatsApp / comissão de equipe / estoque / caixa / DRE / aluguel de cadeira / white label / recorrência no Brasil**: não confirmado.

### 3.6 Singu (Brasil) — concorrente indireto
- **Modelo**: marketplace de serviços de beleza **a domicílio** (manicure, cabelo, depilação, massagem), criado por Tallis Gomes (fundador do Easy Taxi); profissionais autônomas se cadastram (relato de ~5% de aprovação), preços dinâmicos definidos por algoritmo; cobertura relatada: Rio de Janeiro e Grande São Paulo (Mobile Time 2016, Correio Braziliense 2018, TechTudo — via busca 2026-08-06; dados antigos).
- **Não é um sistema de gestão para barbearias** — não compete no SaaS de agenda/caixa; compete apenas pela demanda do consumidor final. Percentual de comissão da plataforma: **não confirmado**. Situação operacional em 2026: **não confirmado**.

### 3.7 Squire (EUA)
- Barbershop-first, mercado americano. **Preços**: Independent US$ 30/mês; Pro US$ 50; Executive US$ 150 (desbloqueia comissão, estoque e fidelidade); Titan US$ 250 (multi-unidade, relatórios avançados); teste de 14 dias; cobra do cliente final US$ 1–3 por agendamento em certos planos (getsquire.com/pricing + Capterra/SoftwareAdvice, via busca 2026-08-06). Operação no Brasil: **não confirmado** (nenhum indício encontrado).

### 3.8 Schedulicity (EUA)
- **Preços**: Unlimited US$ 34,99/mês (solo) + US$ 10/profissional até 5; US$ 94,99/mês para 7+; add-ons de US$ 5/mês (SMS, pacotes, cobrança automática); plano grátis limitado a 10 agendamentos/mês (schedulicity.com/essentials/pricing/ + MarketBox/ITQlick, via busca 2026-08-06). Operação no Brasil: **não confirmado**.

### 3.9 Outros players brasileiros relevantes encontrados (nicho barbearia)
Todos via busca em 2026-08-06; dados limitados ao que as buscas retornaram:
- **EiBarber** — Essencial R$ 49/mês (até 2 barbeiros), Profissional R$ 89 (até 4), Avançado R$ 139 (ilimitado); anuncia IA + WhatsApp (eibarber.com.br).
- **AgendZap** — Starter R$ 57/mês (1 profissional), Growth R$ 127 (até 3), Elite R$ 197 (até 6) (agendzap.com.br).
- **Agendaê** — planos a partir de R$ 44,98/mês (agendaeapp.com).
- **Simples Agenda** — a partir de R$ 39,90/mês, sem implantação e sem fidelidade (simplesagenda.com.br).
- **Barbeiro.app** — anuncia **API oficial do WhatsApp (Meta)** com botão de confirmação e modo coexistência (barbeiro.app). Preços: não confirmado.
- **BestBarbers** — app próprio (white label), clube de assinaturas, agendamento por cadeira, comissões compartilhadas, multiunidade (bestbarbers.app). Preços: não confirmado.
- **Gendo** — afirma 250 mil negócios e 53 milhões de agendamentos; automação WhatsApp (gendo.com.br). Preços: não confirmado.
- **Agende-me** — a partir de R$ 59,90/mês com automações de WhatsApp sem cobrança por mensagem (agende-me.com).
- **GendaJá** — **não confirmado**: nenhuma empresa com esse nome foi localizada nas buscas (existem Gendo, Genda, Gendaa, Agende Já e Premium Genda, que podem ser a referência pretendida).

### 3.10 Faixas de preço do mercado BR (referência agregada)
- Comparativo agende-me.com (2026-08-06): sistemas de agendamento no Brasil vão de **R$ 19,90/mês (Tua Agenda) a R$ 110/mês (Trinks, 1–2 profissionais)**; sistemas com WhatsApp automático sem cobrança por mensagem concentram-se entre **R$ 59,90 e R$ 119,90/mês**.

---

## 4. Síntese das lacunas observadas

1. **Ninguém dos líderes nomeia "DRE" nem "aluguel de cadeira/gestão de cadeiras"** como funcionalidade (não confirmado em todos) — a linguagem é "relatórios" e "comissão". O regime Salão Parceiro é dor real e juridicamente formalizada sem software líder claro.
2. **WhatsApp oficial (API Meta) é raro e vira diferencial anunciável**: só players de nicho (Barbeiro.app, Opero) o declaram explicitamente; líderes não declaram qual API usam.
3. **Recorrência/assinatura existe (Trinks, BestBarbers), mas não é o centro de nenhum líder generalista.**
4. **Reputação de suporte é o calcanhar de aquiles geral**: cancelamento difícil e cobrança indevida aparecem nas reclamações de AppBarber, Booksy e Avec; a Trinks é a melhor avaliada (8,7/10) mas também tem queixas de cancelamento.
5. **Modelos de comissão sobre cliente novo (Booksy 30%, Fresha 20%) geram ressentimento documentado** — espaço para posicionamento "sem comissão, preço fixo".
