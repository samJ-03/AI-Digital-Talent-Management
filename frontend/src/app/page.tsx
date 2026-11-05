'use client';
import { useQuery } from '@tanstack/react-query';
import { Button, Tag } from 'antd';
import { apiFetch } from '@/lib/http';
export default function HomePage() {
 const health = useQuery({queryKey:['health','live'],queryFn:()=>apiFetch<{alive:boolean}>('/api/v1/health/live')});
 return <div className="app"><aside className="sidebar"><div className="brand"><span className="brand-logo">AI</span><div>数字化人才平台<small>智慧招聘 · 开发环境</small></div></div><div className="nav-group">平台</div><div className="nav-active">系统概览</div><div className="sidebar-note">管理员配置系统<br/>HR开展招聘<br/>候选人独立考试</div></aside><main><header>平台 / <strong>系统概览</strong><Tag color="blue">开发阶段</Tag></header><section className="content"><div className="page-head"><div><h1>开发环境已建立</h1><p>正在按开发计划逐项实现招聘流程，业务模块尚未开放。</p></div><Button onClick={()=>health.refetch()} loading={health.isFetching}>刷新服务状态</Button></div><div className="cards"><article><h2>接口服务</h2>{health.isPending?<Tag>正在检查</Tag>:health.isError?<Tag color="red">暂不可用</Tag>:<Tag color="green">进程在线</Tag>}<p>在线只表示接口进程可响应，不代表所有业务和依赖已经就绪。</p></article><article><h2>当前阶段</h2><strong>基础设施与应用骨架</strong><p>下一阶段：权限、岗位、简历解析与人才档案。</p></article></div><article className="scope"><h2>招聘主线</h2><p>岗位配置 → HR导入简历 → 硬条件粗筛 → 画像匹配 → 邮件邀考 → 在线笔试 → HR复核与选人</p><p className="muted">本页不展示虚构人才数量、匹配率或考试成绩。</p></article></section></main></div>;
}
