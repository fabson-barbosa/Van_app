import { z } from 'zod';

export const loginSchema = z.object({
  email: z.string().min(1, 'Informe o e-mail').email('E-mail inválido'),
  senha: z.string().min(6, 'A senha precisa de ao menos 6 caracteres'),
});

export type LoginInput = z.infer<typeof loginSchema>;
