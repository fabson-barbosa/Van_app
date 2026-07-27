import { expect, test } from '@playwright/test';

test('redireciona visitante para o login', async ({ page }) => {
  await page.goto('/alunos');
  await expect(page).toHaveURL(/\/login/);
});

test('login, navegação e logout', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('E-mail').fill('owner@aurora.com.br');
  await page.getByLabel('Senha').fill('vaivem123');
  await page.getByRole('button', { name: 'Entrar' }).click();

  await expect(page).toHaveURL('/');
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Bom dia');

  await page.getByRole('link', { name: 'Alunos' }).click();
  await expect(page).toHaveURL(/\/alunos/);
  await expect(page.getByRole('table')).toBeVisible();

  await page.getByRole('button', { name: 'Sair' }).click();
  await expect(page).toHaveURL(/\/login/);
});

test('recusa credencial inválida', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('E-mail').fill('owner@aurora.com.br');
  await page.getByLabel('Senha').fill('senhaerrada');
  await page.getByRole('button', { name: 'Entrar' }).click();
  // Escopado ao form: o route announcer do Next também expõe role="alert".
  await expect(page.locator('form').getByRole('alert')).toContainText('incorretos');
});

test('papel financeiro não vê o menu de alunos', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('E-mail').fill('financeiro@aurora.com.br');
  await page.getByLabel('Senha').fill('vaivem123');
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page).toHaveURL('/');

  await expect(page.getByRole('link', { name: 'Alunos' })).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'Financeiro' })).toBeVisible();

  // Acesso direto pela URL também é barrado.
  await page.goto('/alunos');
  await expect(page.getByRole('heading', { name: 'Acesso não permitido' })).toBeVisible();
});
