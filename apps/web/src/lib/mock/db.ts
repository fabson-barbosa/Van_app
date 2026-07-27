import type { Aluno, SessionUser } from '@/types';

/** Usuários de demonstração. Senha de todos: `vaivem123`. */
export const MOCK_USERS: Array<SessionUser & { senha: string }> = [
  {
    id: 'u1',
    name: 'Fábson Dekapoly',
    email: 'owner@aurora.com.br',
    role: 'owner',
    tenantId: 't1',
    tenantName: 'Transporte Aurora',
    senha: 'vaivem123',
  },
  {
    id: 'u2',
    name: 'Renata Souza',
    email: 'gestor@aurora.com.br',
    role: 'gestor',
    tenantId: 't1',
    tenantName: 'Transporte Aurora',
    senha: 'vaivem123',
  },
  {
    id: 'u3',
    name: 'Carla Nunes',
    email: 'financeiro@aurora.com.br',
    role: 'financeiro',
    tenantId: 't1',
    tenantName: 'Transporte Aurora',
    senha: 'vaivem123',
  },
  {
    id: 'u4',
    name: 'Jorge Camargo',
    email: 'auditor@aurora.com.br',
    role: 'auditor',
    tenantId: 't1',
    tenantName: 'Transporte Aurora',
    senha: 'vaivem123',
  },
];

const NOMES = [
  'Laura Martins','Pedro Cavalcanti','Sofia Barreto','Théo Nogueira','Isabela Freitas',
  'Gabriel Andrade','Miguel Rocha','Helena Duarte','Bento Aguiar','Alice Peixoto',
  'Davi Queiroz','Manuela Pires','Arthur Bastos','Cecília Ramos','Heitor Vasques',
  'Lívia Moreira','Enzo Tavares','Maitê Cordeiro','Noah Bittencourt','Antonella Braga',
];
const RESP = [
  'Renata Martins','Marcelo Cavalcanti','Camila Barreto','Aline Nogueira','Paulo Freitas',
  'Sandra Andrade','Fernanda Rocha','Tiago Duarte','Larissa Aguiar','Rodrigo Peixoto',
];
const ESCOLAS = ['Colégio Maranata', 'Escola Semear'];
const ROTAS = [
  { id: 'r1', nome: 'Rota 01' },
  { id: 'r2', nome: 'Rota 02' },
  { id: 'r3', nome: 'Rota 03' },
  { id: 'r4', nome: 'Rota 04' },
];
const STATUS: Aluno['statusPagamento'][] = ['em_dia', 'em_dia', 'em_dia', 'vence_hoje', 'vencida'];

/** Determinístico de propósito: mesma lista em todo reload, testes estáveis. */
export const MOCK_ALUNOS: Aluno[] = Array.from({ length: 134 }, (_, i) => {
  const semRota = i % 23 === 0;
  const rota = ROTAS[i % ROTAS.length];
  return {
    id: `a${i + 1}`,
    nome: `${NOMES[i % NOMES.length]}${i >= NOMES.length ? ` ${Math.floor(i / NOMES.length) + 1}` : ''}`,
    idade: 6 + (i % 8),
    serie: `${1 + (i % 9)}º ano`,
    escola: ESCOLAS[i % ESCOLAS.length],
    rotaId: semRota ? null : rota.id,
    rotaNome: semRota ? null : rota.nome,
    turno: i % 2 === 0 ? 'manha' : 'tarde',
    responsavelNome: RESP[i % RESP.length],
    responsavelTelefone: `(31) 9 ${8000 + (i % 1999)}-${1000 + (i % 8999)}`,
    statusPagamento: STATUS[i % STATUS.length],
    ativo: i % 31 !== 0,
  };
});
