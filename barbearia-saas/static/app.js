/* Painel SPA — consome a API multi-tenant. */
let sessao = JSON.parse(localStorage.getItem('sessao') || 'null');

const fmt = v => (v ?? 0).toLocaleString('pt-BR', {style: 'currency', currency: 'BRL'});
const fmtDataHora = iso => iso ? iso.replace('T', ' ').slice(0, 16) : '';
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

async function api(caminho, opcoes = {}) {
  const cab = {'Content-Type': 'application/json'};
  if (sessao) cab['Authorization'] = 'Bearer ' + sessao.token;
  const r = await fetch(caminho, {...opcoes, headers: {...cab, ...(opcoes.headers || {})}});
  if (r.status === 401) { sair(); throw new Error('Sessão expirada'); }
  const corpo = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(corpo.detail || 'Erro na requisição');
  return corpo;
}

function avisar(texto, tipo = 'ok') {
  const el = document.getElementById('alerta-global');
  el.textContent = texto; el.className = 'alerta ' + tipo;
  setTimeout(() => el.className = 'alerta', 4000);
}

/* ---------- login ---------- */
async function fazerLogin() {
  const alerta = document.getElementById('login-alerta');
  try {
    const dados = await api('/api/auth/login', {method: 'POST', body: JSON.stringify({
      email: document.getElementById('login-email').value,
      senha: document.getElementById('login-senha').value})});
    sessao = dados;
    localStorage.setItem('sessao', JSON.stringify(sessao));
    iniciarApp();
  } catch (e) { alerta.textContent = e.message; alerta.className = 'alerta erro'; }
}

function sair() { localStorage.removeItem('sessao'); sessao = null; location.reload(); }

/* ---------- shell ---------- */
const PAGINAS = [
  {id: 'dashboard', titulo: 'Dashboard', papeis: ['gerente', 'recepcao']},
  {id: 'agenda', titulo: 'Agenda', papeis: ['gerente', 'recepcao']},
  {id: 'clientes', titulo: 'Clientes', papeis: ['gerente', 'recepcao']},
  {id: 'recorrencias', titulo: 'Recorrências', papeis: ['gerente', 'recepcao']},
  {id: 'whatsapp', titulo: 'WhatsApp', papeis: ['gerente', 'recepcao']},
  {id: 'caixa', titulo: 'Caixa', papeis: ['gerente', 'recepcao']},
  {id: 'barbeiros', titulo: 'Barbeiros & Cadeiras', papeis: ['gerente']},
  {id: 'servicos', titulo: 'Serviços & Combos', papeis: ['gerente']},
  {id: 'estoque', titulo: 'Estoque', papeis: ['gerente', 'recepcao']},
  {id: 'dre', titulo: 'Relatórios & DRE', papeis: ['gerente']},
  {id: 'whitelabel', titulo: 'Minha Marca', papeis: ['gerente']},
  {id: 'plataforma', titulo: 'Plataforma (Admin)', papeis: ['superadmin']},
];

function iniciarApp() {
  document.getElementById('tela-login').style.display = 'none';
  document.getElementById('tela-app').style.display = 'grid';
  document.getElementById('chip-nome').textContent = sessao.usuario.nome;
  document.getElementById('chip-papel').textContent = sessao.usuario.papel;
  if (sessao.tenant) {
    document.getElementById('marca-nome').textContent = sessao.tenant.nome;
    document.documentElement.style.setProperty('--ouro', sessao.tenant.cor_primaria || '#C9A227');
  } else {
    document.getElementById('marca-nome').textContent = 'Plataforma White Label';
  }
  const menu = document.getElementById('menu');
  menu.innerHTML = '';
  PAGINAS.filter(p => p.papeis.includes(sessao.usuario.papel)).forEach(p => {
    const b = document.createElement('button');
    b.textContent = p.titulo; b.dataset.pagina = p.id;
    b.onclick = () => abrir(p.id);
    menu.appendChild(b);
  });
  abrir(sessao.usuario.papel === 'superadmin' ? 'plataforma' : 'dashboard');
}

async function abrir(pagina) {
  document.querySelectorAll('#menu button').forEach(b =>
    b.classList.toggle('ativo', b.dataset.pagina === pagina));
  document.getElementById('titulo-pagina').textContent =
    PAGINAS.find(p => p.id === pagina)?.titulo || pagina;
  const alvo = document.getElementById('conteudo');
  alvo.innerHTML = '<p style="color:var(--texto-suave)">Carregando…</p>';
  try { await VISTAS[pagina](alvo); }
  catch (e) { alvo.innerHTML = `<div class="alerta erro" style="display:block">${esc(e.message)}</div>`; }
}

/* ---------- vistas ---------- */
const VISTAS = {

async dashboard(el) {
  const hoje = new Date().toISOString().slice(0, 10);
  const [kpi, agenda] = await Promise.all([
    api('/api/relatorios/indicadores'), api('/api/agendamentos?data=' + hoje)]);
  el.innerHTML = `
    <div class="grade-kpi">
      <div class="kpi"><div class="rotulo">Faturamento do mês</div><div class="valor">${fmt(kpi.faturamento)}</div></div>
      <div class="kpi"><div class="rotulo">Ticket médio</div><div class="valor">${fmt(kpi.ticket_medio)}</div></div>
      <div class="kpi"><div class="rotulo">Agendamentos no mês</div><div class="valor">${kpi.agendamentos}</div></div>
      <div class="kpi"><div class="rotulo">Taxa de no-show</div><div class="valor">${kpi.taxa_no_show_pct}%</div></div>
      <div class="kpi"><div class="rotulo">Recorrências ativas</div><div class="valor">${kpi.recorrencias_ativas}</div></div>
      <div class="kpi"><div class="rotulo">Confirmação WhatsApp</div><div class="valor">${kpi.taxa_confirmacao_whatsapp_pct}%</div></div>
    </div>
    <div class="painel"><h3>Agenda de hoje (${agenda.length})</h3>${tabelaAgenda(agenda)}</div>`;
},

async agenda(el) {
  const hoje = new Date().toISOString().slice(0, 10);
  const [barbeiros, clientes, servicos] = await Promise.all([
    api('/api/barbeiros'), api('/api/clientes'), api('/api/servicos')]);
  el.innerHTML = `
    <div class="painel"><h3>Novo agendamento</h3>
      <div class="linha-form">
        <div><label>Cliente</label><select id="ag-cliente">${clientes.map(c => `<option value="${c.id}">${esc(c.nome)}</option>`).join('')}</select></div>
        <div><label>Barbeiro</label><select id="ag-barbeiro">${barbeiros.map(b => `<option value="${b.id}">${esc(b.nome)}</option>`).join('')}</select></div>
        <div><label>Data</label><input id="ag-data" type="date" value="${hoje}"></div>
        <div><label>Hora</label><input id="ag-hora" type="time" value="10:00"></div>
        <div><button class="btn" onclick="criarAgendamento()">Agendar</button></div>
      </div>
      <label>Serviços (segure Ctrl para vários)</label>
      <select id="ag-servicos" multiple size="4">${servicos.map(s =>
        `<option value="${s.id}">${s.eh_combo ? '🎁 ' : ''}${esc(s.nome)} — ${fmt(s.preco)} · ${s.duracao_min}min</option>`).join('')}</select>
    </div>
    <div class="painel"><h3>Agenda do dia</h3>
      <div class="linha-form" style="margin-bottom:12px">
        <div><label>Data</label><input id="filtro-data" type="date" value="${hoje}" onchange="recarregarAgenda()"></div>
        <div><label>Barbeiro</label><select id="filtro-barbeiro" onchange="recarregarAgenda()">
          <option value="">Todos</option>${barbeiros.map(b => `<option value="${b.id}">${esc(b.nome)}</option>`).join('')}</select></div>
      </div>
      <div id="lista-agenda"></div>
    </div>`;
  recarregarAgenda();
},

async clientes(el) {
  const lista = await api('/api/clientes');
  el.innerHTML = `
    <div class="painel"><h3>Novo cliente</h3>
      <div class="linha-form">
        <div><label>Nome*</label><input id="cl-nome"></div>
        <div><label>Telefone (DDD+número)*</label><input id="cl-telefone" placeholder="34999990000"></div>
        <div><label>CPF</label><input id="cl-cpf" placeholder="000.000.000-00"></div>
        <div><label>Aniversário (DD/MM)</label><input id="cl-aniv" placeholder="15/08"></div>
        <div><button class="btn" onclick="criarCliente()">Cadastrar</button></div>
      </div>
    </div>
    <div class="painel"><h3>Clientes (${lista.length})</h3><div class="tabela-wrap"><table>
      <tr><th>Nome</th><th>Telefone</th><th>CPF</th><th>Aniversário</th><th>Visitas</th><th>Última visita</th></tr>
      ${lista.map(c => `<tr><td>${esc(c.nome)}</td><td>${esc(c.telefone)}</td><td>${esc(c.cpf) || '—'}</td>
        <td>${c.aniversario ? c.aniversario.split('-').reverse().join('/') : '—'}</td>
        <td>${c.visitas}</td><td>${fmtDataHora(c.ultima_visita) || '—'}</td></tr>`).join('')}
    </table></div></div>`;
},

async recorrencias(el) {
  const [lista, clientes, barbeiros, servicos] = await Promise.all([
    api('/api/recorrencias'), api('/api/clientes'), api('/api/barbeiros'), api('/api/servicos')]);
  const DIAS = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo'];
  el.innerHTML = `
    <div class="painel"><h3>Nova recorrência (cliente fiel)</h3>
      <div class="linha-form">
        <div><label>Cliente</label><select id="rc-cliente">${clientes.map(c => `<option value="${c.id}">${esc(c.nome)}</option>`).join('')}</select></div>
        <div><label>Barbeiro</label><select id="rc-barbeiro">${barbeiros.map(b => `<option value="${b.id}">${esc(b.nome)}</option>`).join('')}</select></div>
        <div><label>Serviço</label><select id="rc-servico">${servicos.map(s => `<option value="${s.id}">${esc(s.nome)}</option>`).join('')}</select></div>
        <div><label>Frequência</label><select id="rc-freq" onchange="ajustarCampoFreq()">
          <option value="semanal">Semanal</option><option value="quinzenal">Quinzenal</option>
          <option value="mensal">Mensal</option><option value="anual">Anual</option></select></div>
        <div id="rc-campo-dia"><label>Dia da semana</label><select id="rc-dia-semana">
          ${DIAS.map((d, i) => `<option value="${i}">${d}</option>`).join('')}</select></div>
        <div><label>Hora</label><input id="rc-hora" type="time" value="10:00"></div>
        <div><button class="btn" onclick="criarRecorrencia()">Criar</button></div>
      </div>
    </div>
    <div class="painel"><h3>Recorrências ativas (${lista.length})</h3><div class="tabela-wrap"><table>
      <tr><th>Cliente</th><th>Barbeiro</th><th>Serviço</th><th>Frequência</th><th>Quando</th><th></th></tr>
      ${lista.map(r => `<tr><td>${esc(r.cliente)}</td><td>${esc(r.barbeiro)}</td><td>${esc(r.servico)}</td>
        <td>${r.frequencia}</td>
        <td>${r.dia_semana != null ? DIAS[r.dia_semana] : (r.dia_mes ? 'dia ' + r.dia_mes : r.data_base)} às ${r.hora}</td>
        <td><button class="btn-mini" onclick="gerarRecorrencia(${r.id})">Gerar próximos 4</button>
            <button class="btn-mini" onclick="encerrarRecorrencia(${r.id})">Encerrar</button></td></tr>`).join('')}
    </table></div></div>`;
},

async whatsapp(el) {
  const fila = await api('/api/whatsapp/fila');
  const mesAtual = new Date().getMonth() + 1;
  el.innerHTML = `
    <div class="painel"><h3>Automação</h3>
      <div class="linha-form">
        <div><button class="btn" onclick="processarFila()">Disparar mensagens pendentes</button></div>
        <div><label>Campanha de aniversário — mês</label><select id="wa-mes">
          ${Array.from({length: 12}, (_, i) => `<option value="${i + 1}" ${i + 1 === mesAtual ? 'selected' : ''}>${i + 1}</option>`).join('')}</select></div>
        <div><button class="btn-ghost" onclick="campanhaAniversario()">Gerar campanha 🎂</button></div>
      </div>
      <p style="font-size:12px;color:var(--texto-suave);margin-top:10px">
        Confirmação sai 30 min antes do horário; lembrete na véspera às 19h. Sem credenciais da
        WhatsApp Cloud API o envio é simulado — use o link wa.me para disparo manual.</p>
    </div>
    <div class="painel"><h3>Fila de mensagens (${fila.length})</h3><div class="tabela-wrap"><table>
      <tr><th>Quando</th><th>Cliente</th><th>Tipo</th><th>Status</th><th>Resposta</th><th>Ações</th></tr>
      ${fila.map(m => `<tr><td>${fmtDataHora(m.agendada_para)}</td><td>${esc(m.cliente) || esc(m.telefone)}</td>
        <td>${m.tipo}</td><td><span class="selo s-${m.status}">${m.status}</span></td>
        <td>${m.resposta || '—'}</td>
        <td><a class="btn-mini" style="text-decoration:none" href="${m.link_wame}" target="_blank">wa.me ↗</a>
          ${m.tipo === 'confirmacao' && m.status === 'enviada' && !m.resposta ? `
            <button class="btn-mini" onclick="responderMsg(${m.id},'confirmar')">✅</button>
            <button class="btn-mini" onclick="responderMsg(${m.id},'cancelar')">❌</button>
            <button class="btn-mini" onclick="responderMsg(${m.id},'atrasar')">⏰</button>` : ''}</td></tr>`).join('')}
    </table></div></div>`;
},

async caixa(el) {
  const dados = await api('/api/caixa');
  el.innerHTML = `
    <div class="grade-kpi">
      <div class="kpi"><div class="rotulo">Entradas (mês)</div><div class="valor positivo">${fmt(dados.entradas)}</div></div>
      <div class="kpi"><div class="rotulo">Saídas (mês)</div><div class="valor negativo">${fmt(dados.saidas)}</div></div>
      <div class="kpi"><div class="rotulo">Saldo</div><div class="valor">${fmt(dados.saldo)}</div></div>
    </div>
    <div class="painel"><h3>Novo lançamento</h3>
      <div class="linha-form">
        <div><label>Data</label><input id="cx-data" type="date" value="${new Date().toISOString().slice(0, 10)}"></div>
        <div><label>Tipo</label><select id="cx-tipo"><option value="entrada">Entrada</option><option value="saida">Saída</option></select></div>
        <div><label>Categoria</label><select id="cx-cat">
          ${['servico','produto','aluguel_cadeira','comissao','despesa_fixa','despesa_variavel','imposto','outro']
            .map(c => `<option>${c}</option>`).join('')}</select></div>
        <div><label>Descrição</label><input id="cx-desc"></div>
        <div><label>Valor (R$)</label><input id="cx-valor" type="number" step="0.01"></div>
        <div><button class="btn" onclick="lancarCaixa()">Lançar</button></div>
      </div>
    </div>
    <div class="painel"><h3>Lançamentos do mês</h3><div class="tabela-wrap"><table>
      <tr><th>Data</th><th>Tipo</th><th>Categoria</th><th>Descrição</th><th>Valor</th><th></th></tr>
      ${dados.lancamentos.map(l => `<tr><td>${l.data}</td>
        <td class="${l.tipo === 'entrada' ? 'positivo' : 'negativo'}">${l.tipo}</td>
        <td>${l.categoria}</td><td>${esc(l.descricao)}</td>
        <td class="${l.tipo === 'entrada' ? 'positivo' : 'negativo'}">${fmt(l.valor)}</td>
        <td>${l.agendamento_id ? '' : `<button class="btn-mini" onclick="excluirLancamento(${l.id})">🗑</button>`}</td></tr>`).join('')}
    </table></div></div>`;
},

async barbeiros(el) {
  const lista = await api('/api/barbeiros');
  const comp = new Date().toISOString().slice(0, 7);
  el.innerHTML = `
    <div class="painel"><h3>Novo barbeiro</h3>
      <div class="linha-form">
        <div><label>Nome*</label><input id="bb-nome"></div>
        <div><label>Telefone</label><input id="bb-telefone"></div>
        <div><label>Modelo</label><select id="bb-modelo">
          <option value="comissao">Comissão</option><option value="aluguel_cadeira">Aluguel de cadeira</option></select></div>
        <div><label>% comissão</label><input id="bb-comissao" type="number" value="50"></div>
        <div><label>Aluguel mensal (R$)</label><input id="bb-aluguel" type="number" value="0"></div>
        <div><label>Expediente</label><div style="display:flex;gap:6px">
          <input id="bb-inicio" type="time" value="09:00"><input id="bb-fim" type="time" value="19:00"></div></div>
        <div><button class="btn" onclick="criarBarbeiro()">Cadastrar</button></div>
      </div>
    </div>
    <div class="painel"><h3>Equipe (${lista.length})</h3><div class="tabela-wrap"><table>
      <tr><th>Nome</th><th>Modelo</th><th>Condição</th><th>Expediente</th><th>Ações</th></tr>
      ${lista.map(b => `<tr><td>${esc(b.nome)}</td>
        <td>${b.modelo === 'comissao' ? 'Comissão' : '💺 Aluguel de cadeira'}</td>
        <td>${b.modelo === 'comissao' ? b.percentual_comissao + '%' : fmt(b.valor_aluguel) + '/mês'}</td>
        <td>${b.hora_inicio}–${b.hora_fim}</td>
        <td>${b.modelo === 'aluguel_cadeira' ? `<button class="btn-mini" onclick="cobrarAluguel(${b.id},'${comp}')">Lançar aluguel ${comp}</button>` : ''}
            <button class="btn-mini" onclick="desativarBarbeiro(${b.id})">Desativar</button></td></tr>`).join('')}
    </table></div></div>`;
},

async servicos(el) {
  const lista = await api('/api/servicos');
  const simples = lista.filter(s => !s.eh_combo);
  el.innerHTML = `
    <div class="painel"><h3>Novo serviço</h3>
      <div class="linha-form">
        <div><label>Nome*</label><input id="sv-nome"></div>
        <div><label>Preço (R$)*</label><input id="sv-preco" type="number" step="0.01"></div>
        <div><label>Duração (min)</label><input id="sv-duracao" type="number" value="30"></div>
        <div><button class="btn" onclick="criarServico()">Cadastrar</button></div>
      </div>
    </div>
    <div class="painel"><h3>Novo combo</h3>
      <div class="linha-form">
        <div><label>Nome do combo*</label><input id="cb-nome" placeholder="Combo Corte + Barba"></div>
        <div><label>Preço fechado (R$)*</label><input id="cb-preco" type="number" step="0.01"></div>
        <div><button class="btn" onclick="criarCombo()">Criar combo</button></div>
      </div>
      <label>Serviços do combo (Ctrl para vários)</label>
      <select id="cb-itens" multiple size="4">${simples.map(s =>
        `<option value="${s.id}">${esc(s.nome)} — ${fmt(s.preco)}</option>`).join('')}</select>
    </div>
    <div class="painel"><h3>Tabela de preços</h3><div class="tabela-wrap"><table>
      <tr><th>Serviço</th><th>Preço</th><th>Duração</th><th>Composição</th><th></th></tr>
      ${lista.map(s => `<tr><td>${s.eh_combo ? '🎁 ' : ''}${esc(s.nome)}</td><td>${fmt(s.preco)}</td>
        <td>${s.duracao_min}min</td>
        <td>${s.itens ? s.itens.map(i => esc(i.nome)).join(' + ') + ` <span style="color:var(--texto-suave)">(avulso ${fmt(s.itens.reduce((a, i) => a + i.preco, 0))})</span>` : '—'}</td>
        <td><button class="btn-mini" onclick="desativarServico(${s.id})">Desativar</button></td></tr>`).join('')}
    </table></div></div>`;
},

async estoque(el) {
  const lista = await api('/api/estoque');
  el.innerHTML = `
    <div class="painel"><h3>Novo produto</h3>
      <div class="linha-form">
        <div><label>Nome*</label><input id="pd-nome"></div>
        <div><label>Custo (R$)</label><input id="pd-custo" type="number" step="0.01"></div>
        <div><label>Preço de venda (R$)</label><input id="pd-venda" type="number" step="0.01"></div>
        <div><label>Estoque mínimo</label><input id="pd-minimo" type="number" value="3"></div>
        <div><button class="btn" onclick="criarProduto()">Cadastrar</button></div>
      </div>
    </div>
    <div class="painel"><h3>Produtos (${lista.length})</h3><div class="tabela-wrap"><table>
      <tr><th>Produto</th><th>Custo</th><th>Venda</th><th>Em estoque</th><th>Movimentar</th></tr>
      ${lista.map(p => `<tr><td>${esc(p.nome)} ${p.abaixo_minimo ? '<span class="selo s-atrasado">repor!</span>' : ''}</td>
        <td>${fmt(p.custo)}</td><td>${fmt(p.preco_venda)}</td><td>${p.quantidade}</td>
        <td><button class="btn-mini" onclick="moverEstoque(${p.id},'compra')">+ Compra</button>
            <button class="btn-mini" onclick="moverEstoque(${p.id},'consumo')">− Consumo</button></td></tr>`).join('')}
    </table></div></div>`;
},

async dre(el) {
  const comp = new Date().toISOString().slice(0, 7);
  el.innerHTML = `
    <div class="painel"><div class="linha-form">
      <div><label>Competência</label><input id="dre-comp" type="month" value="${comp}"></div>
      <div><button class="btn" onclick="carregarDre()">Gerar</button></div>
    </div></div>
    <div id="dre-resultado"></div>`;
  carregarDre();
},

async whitelabel(el) {
  const t = await api('/api/tenants/meu');
  el.innerHTML = `
    <div class="painel"><h3>Identidade da minha barbearia (white label)</h3>
      <div class="linha-form">
        <div><label>Nome exibido</label><input id="wl-nome" value="${esc(t.nome)}"></div>
        <div><label>Cor primária</label><input id="wl-cor" type="color" value="${t.cor_primaria}" style="height:40px;padding:2px"></div>
        <div><label>WhatsApp oficial</label><input id="wl-whats" value="${esc(t.telefone_whatsapp)}"></div>
        <div><label>Logo (URL)</label><input id="wl-logo" value="${esc(t.logo_url)}"></div>
        <div><button class="btn" onclick="salvarWhiteLabel()">Salvar</button></div>
      </div>
      <p style="font-size:12px;color:var(--texto-suave);margin-top:10px">
        Plano ${t.plano} · mensalidade ${fmt(t.mensalidade)} · sua marca, sua identidade.</p>
    </div>
    <div class="painel"><h3>Novo usuário da equipe</h3>
      <div class="linha-form">
        <div><label>Nome</label><input id="us-nome"></div>
        <div><label>E-mail</label><input id="us-email" type="email"></div>
        <div><label>Senha</label><input id="us-senha" type="password"></div>
        <div><label>Papel</label><select id="us-papel"><option value="recepcao">Recepção</option><option value="gerente">Gerente</option></select></div>
        <div><button class="btn" onclick="criarUsuario()">Criar acesso</button></div>
      </div>
    </div>`;
},

async plataforma(el) {
  const lista = await api('/api/tenants');
  const mrr = lista.filter(t => t.ativo).reduce((a, t) => a + t.mensalidade, 0);
  el.innerHTML = `
    <div class="grade-kpi">
      <div class="kpi"><div class="rotulo">Barbearias ativas</div><div class="valor">${lista.filter(t => t.ativo).length}</div></div>
      <div class="kpi"><div class="rotulo">MRR</div><div class="valor">${fmt(mrr)}</div></div>
    </div>
    <div class="painel"><h3>Nova barbearia (tenant)</h3>
      <div class="linha-form">
        <div><label>Nome*</label><input id="tn-nome"></div>
        <div><label>Slug*</label><input id="tn-slug" placeholder="minha-barbearia"></div>
        <div><label>Mensalidade (R$)</label><input id="tn-mensalidade" type="number" value="199.90" step="0.01"></div>
        <div><label>Gerente — nome*</label><input id="tn-ger-nome"></div>
        <div><label>Gerente — e-mail*</label><input id="tn-ger-email" type="email"></div>
        <div><label>Gerente — senha*</label><input id="tn-ger-senha" type="password"></div>
        <div><button class="btn" onclick="criarTenant()">Criar</button></div>
      </div>
    </div>
    <div class="painel"><h3>Barbearias (${lista.length})</h3><div class="tabela-wrap"><table>
      <tr><th>Nome</th><th>Slug</th><th>Plano</th><th>Mensalidade</th><th>Clientes</th><th>Agendamentos</th><th>Status</th><th></th></tr>
      ${lista.map(t => `<tr><td>${esc(t.nome)}</td><td>${esc(t.slug)}</td><td>${t.plano}</td>
        <td>${fmt(t.mensalidade)}</td><td>${t.total_clientes}</td><td>${t.total_agendamentos}</td>
        <td><span class="selo ${t.ativo ? 's-pago' : 's-cancelado'}">${t.ativo ? 'ativa' : 'suspensa'}</span></td>
        <td><button class="btn-mini" onclick="alternarTenant(${t.id})">${t.ativo ? 'Suspender' : 'Reativar'}</button></td></tr>`).join('')}
    </table></div></div>`;
},
};

/* ---------- ações ---------- */
function tabelaAgenda(lista) {
  if (!lista.length) return '<p style="color:var(--texto-suave)">Nenhum agendamento.</p>';
  return `<div class="tabela-wrap"><table>
    <tr><th>Horário</th><th>Cliente</th><th>Barbeiro</th><th>Serviços</th><th>Valor</th><th>Status</th><th>Ações</th></tr>
    ${lista.map(a => `<tr>
      <td>${a.inicio.slice(11)}–${a.fim.slice(11)}</td><td>${esc(a.cliente)}</td><td>${esc(a.barbeiro)}</td>
      <td>${a.servicos.map(s => esc(s.nome)).join(' + ')}</td><td>${fmt(a.valor_total)}</td>
      <td><span class="selo s-${a.status}">${a.status.replace('_', '-')}</span></td>
      <td>${acoesAgendamento(a)}</td></tr>`).join('')}
  </table></div>`;
}

function acoesAgendamento(a) {
  const b = [];
  if (['agendado'].includes(a.status)) b.push(`<button class="btn-mini" onclick="mudarStatus(${a.id},'confirmado')">Confirmar</button>`);
  if (['agendado', 'confirmado', 'atrasado'].includes(a.status)) {
    b.push(`<button class="btn-mini" onclick="mudarStatus(${a.id},'atendido')">Atendido</button>`);
    b.push(`<button class="btn-mini" onclick="mudarStatus(${a.id},'cancelado')">Cancelar</button>`);
    b.push(`<button class="btn-mini" onclick="mudarStatus(${a.id},'no_show')">No-show</button>`);
  }
  if (a.status === 'atendido') b.push(`<button class="btn-mini" style="border-color:var(--ouro);color:var(--ouro-claro)" onclick="fecharConta(${a.id})">💰 Fechar conta</button>`);
  return b.join(' ');
}

async function recarregarAgenda() {
  const data = document.getElementById('filtro-data').value;
  const bb = document.getElementById('filtro-barbeiro').value;
  const lista = await api(`/api/agendamentos?data=${data}${bb ? '&barbeiro_id=' + bb : ''}`);
  document.getElementById('lista-agenda').innerHTML = tabelaAgenda(lista);
}

async function criarAgendamento() {
  const servicos = [...document.getElementById('ag-servicos').selectedOptions].map(o => +o.value);
  try {
    const r = await api('/api/agendamentos', {method: 'POST', body: JSON.stringify({
      cliente_id: +document.getElementById('ag-cliente').value,
      barbeiro_id: +document.getElementById('ag-barbeiro').value,
      inicio: document.getElementById('ag-data').value + 'T' + document.getElementById('ag-hora').value,
      servico_ids: servicos})});
    avisar(`Agendado! Total ${fmt(r.valor_total)} — confirmação WhatsApp na fila.`);
    recarregarAgenda();
  } catch (e) { avisar(e.message, 'erro'); }
}

async function mudarStatus(id, status) {
  try { await api(`/api/agendamentos/${id}/status?status=${status}`, {method: 'PATCH'});
    avisar('Status atualizado.');
    document.getElementById('filtro-data') ? recarregarAgenda() : abrir('dashboard');
  } catch (e) { avisar(e.message, 'erro'); }
}

async function fecharConta(id) {
  const forma = prompt('Forma de pagamento (dinheiro/pix/debito/credito):', 'pix');
  if (!forma) return;
  try {
    const r = await api(`/api/agendamentos/${id}/fechar`, {method: 'POST',
      body: JSON.stringify({forma_pagamento: forma})});
    avisar(`Fechado: ${fmt(r.total_recebido)} recebido · comissão ${fmt(r.comissao_barbeiro)} lançada no caixa.`);
    document.getElementById('filtro-data') ? recarregarAgenda() : abrir('dashboard');
  } catch (e) { avisar(e.message, 'erro'); }
}

async function criarCliente() {
  try {
    await api('/api/clientes', {method: 'POST', body: JSON.stringify({
      nome: document.getElementById('cl-nome').value,
      telefone: document.getElementById('cl-telefone').value,
      cpf: document.getElementById('cl-cpf').value,
      aniversario: document.getElementById('cl-aniv').value})});
    avisar('Cliente cadastrado.'); abrir('clientes');
  } catch (e) { avisar(e.message, 'erro'); }
}

function ajustarCampoFreq() {
  const f = document.getElementById('rc-freq').value;
  const campo = document.getElementById('rc-campo-dia');
  if (f === 'semanal' || f === 'quinzenal')
    campo.innerHTML = `<label>Dia da semana</label><select id="rc-dia-semana">
      ${['Segunda','Terça','Quarta','Quinta','Sexta','Sábado','Domingo'].map((d, i) => `<option value="${i}">${d}</option>`).join('')}</select>`;
  else if (f === 'mensal')
    campo.innerHTML = `<label>Dia do mês (1–28)</label><input id="rc-dia-mes" type="number" min="1" max="28" value="10">`;
  else
    campo.innerHTML = `<label>Data base</label><input id="rc-data-base" type="date">`;
}

async function criarRecorrencia() {
  const f = document.getElementById('rc-freq').value;
  const corpo = {
    cliente_id: +document.getElementById('rc-cliente').value,
    barbeiro_id: +document.getElementById('rc-barbeiro').value,
    servico_id: +document.getElementById('rc-servico').value,
    frequencia: f, hora: document.getElementById('rc-hora').value};
  if (f === 'semanal' || f === 'quinzenal') corpo.dia_semana = +document.getElementById('rc-dia-semana').value;
  else if (f === 'mensal') corpo.dia_mes = +document.getElementById('rc-dia-mes').value;
  else corpo.data_base = document.getElementById('rc-data-base').value;
  try { await api('/api/recorrencias', {method: 'POST', body: JSON.stringify(corpo)});
    avisar('Recorrência criada.'); abrir('recorrencias');
  } catch (e) { avisar(e.message, 'erro'); }
}

async function gerarRecorrencia(id) {
  try {
    const r = await api(`/api/recorrencias/${id}/gerar?quantidade=4`, {method: 'POST'});
    avisar(`${r.criados.length} agendamentos gerados${r.pulados.length ? `, ${r.pulados.length} pulados (${r.pulados[0].motivo})` : ''}.`);
  } catch (e) { avisar(e.message, 'erro'); }
}

async function encerrarRecorrencia(id) {
  try { await api(`/api/recorrencias/${id}`, {method: 'DELETE'}); abrir('recorrencias'); }
  catch (e) { avisar(e.message, 'erro'); }
}

async function processarFila() {
  try { const r = await api('/api/whatsapp/processar', {method: 'POST'});
    avisar(`${r.enviadas} enviadas, ${r.erros} erros.`); abrir('whatsapp');
  } catch (e) { avisar(e.message, 'erro'); }
}

async function campanhaAniversario() {
  try {
    const r = await api('/api/whatsapp/campanha-aniversario?mes=' + document.getElementById('wa-mes').value, {method: 'POST'});
    avisar(`${r.mensagens_criadas} mensagens criadas para ${r.aniversariantes} aniversariantes.`); abrir('whatsapp');
  } catch (e) { avisar(e.message, 'erro'); }
}

async function responderMsg(id, resposta) {
  try { await api(`/api/whatsapp/${id}/resposta`, {method: 'POST', body: JSON.stringify({resposta})});
    avisar('Resposta registrada e agenda atualizada.'); abrir('whatsapp');
  } catch (e) { avisar(e.message, 'erro'); }
}

async function lancarCaixa() {
  try {
    await api('/api/caixa', {method: 'POST', body: JSON.stringify({
      data: document.getElementById('cx-data').value,
      tipo: document.getElementById('cx-tipo').value,
      categoria: document.getElementById('cx-cat').value,
      descricao: document.getElementById('cx-desc').value,
      valor: +document.getElementById('cx-valor').value})});
    avisar('Lançamento registrado.'); abrir('caixa');
  } catch (e) { avisar(e.message, 'erro'); }
}

async function excluirLancamento(id) {
  try { await api('/api/caixa/' + id, {method: 'DELETE'}); abrir('caixa'); }
  catch (e) { avisar(e.message, 'erro'); }
}

async function criarBarbeiro() {
  try {
    await api('/api/barbeiros', {method: 'POST', body: JSON.stringify({
      nome: document.getElementById('bb-nome').value,
      telefone: document.getElementById('bb-telefone').value,
      modelo: document.getElementById('bb-modelo').value,
      percentual_comissao: +document.getElementById('bb-comissao').value,
      valor_aluguel: +document.getElementById('bb-aluguel').value,
      hora_inicio: document.getElementById('bb-inicio').value,
      hora_fim: document.getElementById('bb-fim').value})});
    avisar('Barbeiro cadastrado.'); abrir('barbeiros');
  } catch (e) { avisar(e.message, 'erro'); }
}

async function desativarBarbeiro(id) {
  if (!confirm('Desativar este barbeiro?')) return;
  try { await api('/api/barbeiros/' + id, {method: 'DELETE'}); abrir('barbeiros'); }
  catch (e) { avisar(e.message, 'erro'); }
}

async function cobrarAluguel(id, comp) {
  try { const r = await api(`/api/barbeiros/${id}/cobrar-aluguel?competencia=${comp}`, {method: 'POST'});
    avisar(`${r.mensagem}: ${fmt(r.valor)} lançado no caixa.`);
  } catch (e) { avisar(e.message, 'erro'); }
}

async function criarServico() {
  try {
    await api('/api/servicos', {method: 'POST', body: JSON.stringify({
      nome: document.getElementById('sv-nome').value,
      preco: +document.getElementById('sv-preco').value,
      duracao_min: +document.getElementById('sv-duracao').value})});
    avisar('Serviço criado.'); abrir('servicos');
  } catch (e) { avisar(e.message, 'erro'); }
}

async function criarCombo() {
  const itens = [...document.getElementById('cb-itens').selectedOptions].map(o => +o.value);
  try {
    await api('/api/servicos/combo', {method: 'POST', body: JSON.stringify({
      nome: document.getElementById('cb-nome').value,
      preco: +document.getElementById('cb-preco').value,
      servico_ids: itens})});
    avisar('Combo criado.'); abrir('servicos');
  } catch (e) { avisar(e.message, 'erro'); }
}

async function desativarServico(id) {
  try { await api('/api/servicos/' + id, {method: 'DELETE'}); abrir('servicos'); }
  catch (e) { avisar(e.message, 'erro'); }
}

async function criarProduto() {
  try {
    await api('/api/estoque', {method: 'POST', body: JSON.stringify({
      nome: document.getElementById('pd-nome').value,
      custo: +document.getElementById('pd-custo').value || 0,
      preco_venda: +document.getElementById('pd-venda').value || 0,
      estoque_minimo: +document.getElementById('pd-minimo').value || 0})});
    avisar('Produto cadastrado.'); abrir('estoque');
  } catch (e) { avisar(e.message, 'erro'); }
}

async function moverEstoque(id, tipo) {
  const qtd = prompt(`Quantidade para ${tipo}:`, '1');
  if (!qtd) return;
  try {
    await api(`/api/estoque/${id}/movimento`, {method: 'POST',
      body: JSON.stringify({tipo, quantidade: +qtd})});
    avisar('Movimento registrado.'); abrir('estoque');
  } catch (e) { avisar(e.message, 'erro'); }
}

async function carregarDre() {
  const comp = document.getElementById('dre-comp').value;
  const [d, barbeiros] = await Promise.all([
    api('/api/relatorios/dre?competencia=' + comp),
    api('/api/relatorios/barbeiros?competencia=' + comp)]);
  const linha = (rotulo, valor, cls = '', sub = false) =>
    `<div class="dre-linha ${cls}"><span class="${sub ? 'sub' : ''}">${rotulo}</span><span>${fmt(valor)}</span></div>`;
  document.getElementById('dre-resultado').innerHTML = `
    <div class="painel"><h3>DRE gerencial — ${d.competencia}</h3>
      ${linha('Receita bruta', d.receita_bruta)}
      ${linha('Serviços', d.detalhe_receita.servicos, '', true)}
      ${linha('Produtos', d.detalhe_receita.produtos, '', true)}
      ${linha('Aluguel de cadeiras', d.detalhe_receita.aluguel_cadeiras, '', true)}
      ${linha('(−) Impostos', -d.impostos)}
      ${linha('Receita líquida', d.receita_liquida)}
      ${linha('(−) Comissões', -d.comissoes)}
      ${linha('(−) Custos variáveis', -d.custos_variaveis)}
      ${linha('Margem de contribuição', d.margem_contribuicao)}
      ${linha('(−) Despesas fixas', -d.despesas_fixas)}
      ${linha('(−) Outras saídas', -d.outras_saidas)}
      ${linha(`Lucro líquido (${d.margem_liquida_pct}%)`, d.lucro_liquido, 'total')}
    </div>
    <div class="painel"><h3>Desempenho por barbeiro</h3><div class="tabela-wrap"><table>
      <tr><th>Barbeiro</th><th>Modelo</th><th>Atendimentos</th><th>Faturamento</th><th>No-shows</th></tr>
      ${barbeiros.map(b => `<tr><td>${esc(b.nome)}</td><td>${b.modelo}</td>
        <td>${b.atendimentos}</td><td>${fmt(b.faturamento)}</td><td>${b.no_shows || 0}</td></tr>`).join('')}
    </table></div></div>`;
}

async function salvarWhiteLabel() {
  try {
    await api('/api/tenants/meu', {method: 'PATCH', body: JSON.stringify({
      nome: document.getElementById('wl-nome').value,
      cor_primaria: document.getElementById('wl-cor').value,
      telefone_whatsapp: document.getElementById('wl-whats').value,
      logo_url: document.getElementById('wl-logo').value})});
    sessao.tenant.nome = document.getElementById('wl-nome').value;
    sessao.tenant.cor_primaria = document.getElementById('wl-cor').value;
    localStorage.setItem('sessao', JSON.stringify(sessao));
    document.getElementById('marca-nome').textContent = sessao.tenant.nome;
    document.documentElement.style.setProperty('--ouro', sessao.tenant.cor_primaria);
    avisar('Identidade atualizada.');
  } catch (e) { avisar(e.message, 'erro'); }
}

async function criarUsuario() {
  try {
    await api('/api/tenants/meu/usuarios', {method: 'POST', body: JSON.stringify({
      nome: document.getElementById('us-nome').value,
      email: document.getElementById('us-email').value,
      senha: document.getElementById('us-senha').value,
      papel: document.getElementById('us-papel').value})});
    avisar('Acesso criado.');
  } catch (e) { avisar(e.message, 'erro'); }
}

async function criarTenant() {
  try {
    await api('/api/tenants', {method: 'POST', body: JSON.stringify({
      nome: document.getElementById('tn-nome').value,
      slug: document.getElementById('tn-slug').value,
      mensalidade: +document.getElementById('tn-mensalidade').value,
      gerente_nome: document.getElementById('tn-ger-nome').value,
      gerente_email: document.getElementById('tn-ger-email').value,
      gerente_senha: document.getElementById('tn-ger-senha').value})});
    avisar('Barbearia criada com login de gerente.'); abrir('plataforma');
  } catch (e) { avisar(e.message, 'erro'); }
}

async function alternarTenant(id) {
  try { await api(`/api/tenants/${id}/ativo`, {method: 'PATCH'}); abrir('plataforma'); }
  catch (e) { avisar(e.message, 'erro'); }
}

/* ---------- boot ---------- */
document.getElementById('login-senha').addEventListener('keydown', e => { if (e.key === 'Enter') fazerLogin(); });
if (sessao) iniciarApp();
