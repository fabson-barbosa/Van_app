import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { EmptyState } from '@/components/ui/empty-state';
import { Button } from '@/components/ui/button';
import { Field } from '@/components/ui/field';

describe('componentes base', () => {
  it('EmptyState mostra título, descrição e ação', () => {
    render(
      <EmptyState
        title="Nenhum aluno cadastrado"
        description="Importe uma planilha para começar."
        action={<Button>Importar</Button>}
      />,
    );
    expect(screen.getByText('Nenhum aluno cadastrado')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Importar' })).toBeInTheDocument();
  });

  it('Button em loading fica desabilitado e não dispara clique', async () => {
    const onClick = vi.fn();
    render(
      <Button loading onClick={onClick}>
        Salvar
      </Button>,
    );
    const button = screen.getByRole('button', { name: /Salvar/ });
    expect(button).toBeDisabled();
    button.click();
    expect(onClick).not.toHaveBeenCalled();
  });

  it('Field associa rótulo ao controle e anuncia o erro', () => {
    render(
      <Field label="E-mail" htmlFor="email" error="E-mail inválido" required>
        <input id="email" />
      </Field>,
    );
    expect(screen.getByLabelText(/E-mail/)).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('E-mail inválido');
  });
});
