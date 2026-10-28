import { Globe2, Laptop, Sparkles } from 'lucide-react';
import { TrendDesk } from './Intelligence';

export default function PublicApp() {
  return <div className="public-app">
    <header className="topbar"><a className="brand" href="/"><Sparkles size={24}/>goodform<span className="brand-dot">.</span></a><span className="private-label"><Globe2 size={15}/>Public Trend desk</span></header>
    <main className="main-content" style={{maxWidth:1200,margin:'0 auto'}}>
      <div className="page-title"><div><div className="eyebrow">PUBLIC INTELLIGENCE</div><h1>A shared view of what’s happening.</h1><p>Public conversations, useful signals, and sources you can inspect. No creator account required.</p></div></div>
      <TrendDesk/>
      <section className="panel" style={{padding:24,marginTop:24}}><div className="panel-heading"><div><h3><Laptop size={18}/> Your creator workspace stays on your device</h3><p>Analytics, content ideas, learning experiments and draft approvals belong to the local Goodform app.</p></div></div><p className="fine-print">This website serves the shared Trend desk. Run Goodform locally to use your private workspace. Desktop installers are not available yet.</p></section>
    </main>
  </div>;
}
