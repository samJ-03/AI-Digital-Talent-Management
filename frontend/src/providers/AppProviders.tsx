'use client';
import { useState, type ReactNode } from 'react';
import { ConfigProvider, App } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
/** 页面级公共依赖；QueryClient在组件生命周期内保持同一实例。 */
export function AppProviders({children}: {children: ReactNode}) {
 const [client] = useState(() => new QueryClient({defaultOptions:{queries:{retry:1,refetchOnWindowFocus:false}}}));
 return <QueryClientProvider client={client}><ConfigProvider locale={zhCN} theme={{token:{colorPrimary:'#2563eb',borderRadius:10}}}><App>{children}</App></ConfigProvider></QueryClientProvider>;
}
