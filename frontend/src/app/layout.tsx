import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import { AppProviders } from '@/providers/AppProviders';
import './globals.css';
export const metadata: Metadata = { title: 'AI数字化人才平台', description: '单企业外部人才智慧招聘平台' };
export default function RootLayout({children}: {children: ReactNode}) {
 return <html lang="zh-CN"><body><AppProviders>{children}</AppProviders></body></html>;
}
