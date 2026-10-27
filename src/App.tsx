import React, { useState, useEffect, useMemo } from 'react';
import {
  Activity,
  Search,
  Sliders,
  Eye,
  ShieldAlert,
  Zap,
  ArrowUpDown,
  RefreshCw,
  ExternalLink,
  ChevronRight,
  Sparkles
} from 'lucide-react';

interface Stock {
  c: string; // code
  s: string; // sector
  p: string | null; // phase
  sc: number; // score
  d: number; // days in phase
  cl: number; // close
  ch: number; // chg %
  v: number; // volume
  val: number; // value in mn
  vr: number | null; // volume ratio
  vr5: number | null;
  sq: number | null; // squeeze / atr ratio
  vb: number | null; // volume balance
  m20: number | null;
  m50: number | null;
  m100: number | null;
  w: number | null; // width %
  lo: number | null;
  hi: number | null;
  tr: number; // trend
  ca: number | null; // choch age
  z: string; // zone
  uc: number; // upper circuit
  pu: number | null; // paidup
  pe: number | null;
  cat: string;
  lc: boolean | null;
  pe40: boolean | null;
  pl: string | null;
  st: string | null;
  ok: boolean;
  en: number | null;
  sl: number | null;
  tg: number | null;
  rr: number | null;
  al: number;
  fl: string[];
  wl: boolean;
  lq: boolean;
  sp: number[];
  e_dryup: boolean;
  e_divergence: boolean;
  e_uc_lowvol: boolean;
}

export default function App() {
  const [data, setData] = useState<{ stocks: Stock[]; last_date?: string; config?: Record<string, any> } | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'scanner' | 'filters' | 'config' | 'classic'>('scanner');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedSector, setSelectedSector] = useState('');
  const [selectedPhase, setSelectedPhase] = useState('ALL');
  const [filterMode, setFilterMode] = useState<'ALL' | 'dryup' | 'div' | 'uclow' | 'liquid' | 'setup'>('ALL');
  const [sortCol, setSortCol] = useState<keyof Stock>('sc');
  const [sortAsc, setSortAsc] = useState(false);
  const [selectedStock, setSelectedStock] = useState<Stock | null>(null);

  const loadData = async () => {
    setLoading(true);
    try {
      let res = await fetch('/docs/data/phases.json?t=' + Date.now());
      if (!res.ok) {
        res = await fetch('/data/phases.json?t=' + Date.now());
      }
      if (res.ok) {
        const json = await res.json();
        setData(json);
      }
    } catch (e) {
      console.error('Failed to load phases.json', e);
    }
    setLoading(false);
  };

  useEffect(() => {
    loadData();
  }, []);

  const sectors = useMemo(() => {
    if (!data?.stocks) return [];
    const set = new Set<string>();
    data.stocks.forEach(s => {
      if (s.s) set.add(s.s);
    });
    return Array.from(set).sort();
  }, [data]);

  const filteredStocks = useMemo(() => {
    if (!data?.stocks) return [];
    return data.stocks.filter(s => {
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        const matchesCode = s.c.toLowerCase().includes(q);
        const matchesSec = s.s && s.s.toLowerCase().includes(q);
        if (!matchesCode && !matchesSec) return false;
      }
      if (selectedSector && s.s !== selectedSector) return false;
      if (selectedPhase !== 'ALL') {
        if (selectedPhase === 'NONE' && s.p !== null) return false;
        if (selectedPhase !== 'NONE' && s.p !== selectedPhase) return false;
      }
      if (filterMode === 'dryup' && !s.e_dryup) return false;
      if (filterMode === 'div' && !s.e_divergence) return false;
      if (filterMode === 'uclow' && !s.e_uc_lowvol) return false;
      if (filterMode === 'liquid' && !s.lq) return false;
      if (filterMode === 'setup' && !s.ok) return false;
      return true;
    }).sort((a, b) => {
      let va = a[sortCol];
      let vb = b[sortCol];
      if (typeof va === 'boolean') va = va ? 1 : 0;
      if (typeof vb === 'boolean') vb = vb ? 1 : 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      if (va < vb) return sortAsc ? -1 : 1;
      if (va > vb) return sortAsc ? 1 : -1;
      return 0;
    });
  }, [data, searchQuery, selectedSector, selectedPhase, filterMode, sortCol, sortAsc]);

  const handleSort = (col: keyof Stock) => {
    if (sortCol === col) {
      setSortAsc(!sortAsc);
    } else {
      setSortCol(col);
      setSortAsc(false);
    }
  };

  const renderSparkline = (prices: number[] | undefined, isUp: boolean) => {
    if (!prices || prices.length < 2) return null;
    const min = Math.min(...prices);
    const max = Math.max(...prices);
    const range = max - min || 1;
    const w = 84;
    const h = 22;
    const points = prices.map((p, i) => {
      const x = (i / (prices.length - 1)) * w;
      const y = h - ((p - min) / range) * (h - 4) - 2;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');

    return (
      <svg width={w} height={h} className="overflow-visible">
        <polyline
          fill="none"
          stroke={isUp ? '#16a34a' : '#dc2626'}
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          points={points}
        />
      </svg>
    );
  };

  const dryupCount = useMemo(() => data?.stocks.filter(s => s.e_dryup).length || 0, [data]);
  const divCount = useMemo(() => data?.stocks.filter(s => s.e_divergence).length || 0, [data]);
  const uclowCount = useMemo(() => data?.stocks.filter(s => s.e_uc_lowvol).length || 0, [data]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-900/90 backdrop-blur sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 py-3 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-400 flex items-center justify-center shadow-lg shadow-emerald-500/20 font-black text-slate-950 text-xl">
              DSE
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h1 className="text-lg font-bold text-slate-100 tracking-tight">ডিএসই সিম্পল স্ক্যানার &amp; অপারেটর ফেজ ইঞ্জিন</h1>
                <span className="px-2 py-0.5 text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 rounded-full">
                  v2.5 ৩টি নতুন ফিল্টার সহ
                </span>
              </div>
              <p className="text-xs text-slate-400">
                ঢাকা স্টক এক্সচেঞ্জ (DSE) স্মার্ট মানি ও প্রাতিষ্ঠানিক ট্র্যাকার · তারিখ: <span className="text-slate-200 font-mono">{data?.last_date || '2026-10-27'}</span>
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={loadData}
              disabled={loading}
              className="flex items-center space-x-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition border border-slate-700 disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-emerald-400' : ''}`} />
              <span>রিফ্রেশ</span>
            </button>
            <a
              href="https://github.com/asikstock/simple-scaner-"
              target="_blank"
              rel="noreferrer"
              className="flex items-center space-x-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-emerald-600/20 text-emerald-300 hover:bg-emerald-600/30 border border-emerald-500/30 transition"
            >
              <span>GitHub</span>
              <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="max-w-7xl mx-auto px-4 flex space-x-1 border-t border-slate-800/60 overflow-x-auto text-xs">
          <button
            onClick={() => setActiveTab('scanner')}
            className={`px-4 py-2.5 font-medium border-b-2 flex items-center space-x-2 whitespace-nowrap transition ${
              activeTab === 'scanner'
                ? 'border-emerald-500 text-emerald-400 bg-emerald-500/5'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Activity className="w-4 h-4" />
            <span>স্ক্যানার টেবিল ({filteredStocks.length})</span>
          </button>
          <button
            onClick={() => setActiveTab('filters')}
            className={`px-4 py-2.5 font-medium border-b-2 flex items-center space-x-2 whitespace-nowrap transition ${
              activeTab === 'filters'
                ? 'border-emerald-500 text-emerald-400 bg-emerald-500/5'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <ShieldAlert className="w-4 h-4 text-amber-400" />
            <span>নতুন ৩টি অপারেটর ফিল্টার বিশ্লেষণ</span>
            <span className="px-1.5 py-0.2 bg-amber-500/20 text-amber-300 rounded font-mono text-[10px]">
              {dryupCount + divCount + uclowCount}
            </span>
          </button>
          <button
            onClick={() => setActiveTab('config')}
            className={`px-4 py-2.5 font-medium border-b-2 flex items-center space-x-2 whitespace-nowrap transition ${
              activeTab === 'config'
                ? 'border-emerald-500 text-emerald-400 bg-emerald-500/5'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Sliders className="w-4 h-4 text-purple-400" />
            <span>প্যারামিটার কনফিগ (Cfg)</span>
          </button>
          <button
            onClick={() => setActiveTab('classic')}
            className={`px-4 py-2.5 font-medium border-b-2 flex items-center space-x-2 whitespace-nowrap transition ${
              activeTab === 'classic'
                ? 'border-emerald-500 text-emerald-400 bg-emerald-500/5'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Eye className="w-4 h-4 text-indigo-400" />
            <span>ক্লাসিক HTML ড্যাশবোর্ড (docs/index.html)</span>
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="max-w-7xl mx-auto px-4 py-6 w-full flex-1">
        {/* Quick Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div
            onClick={() => { setActiveTab('scanner'); setFilterMode(filterMode === 'dryup' ? 'ALL' : 'dryup'); }}
            className={`cursor-pointer p-4 rounded-xl border transition flex items-start justify-between ${
              filterMode === 'dryup' ? 'bg-emerald-950/40 border-emerald-500 ring-1 ring-emerald-500' : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
            }`}
          >
            <div>
              <div className="flex items-center space-x-2">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
                <span className="text-xs font-semibold uppercase tracking-wider text-emerald-400">ফিল্টার ১: e_dryup</span>
              </div>
              <h3 className="text-sm font-bold text-slate-100 mt-1">ভলিউম ড্রাই-আপ + ছোট বডি</h3>
              <p className="text-xs text-slate-400 mt-0.5">অ্যাকুমুলেশন ফেজ (Phase A/B) — স্মার্ট মানি লোড নিচ্ছে</p>
              <div className="mt-2 text-xs font-medium text-emerald-300 flex items-center space-x-1">
                <span>ওয়াচলিস্টে রাখুন · {dryupCount} টি শেয়ার</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </div>
            </div>
            <div className="px-2.5 py-1 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-lg text-lg font-black font-mono">
              {dryupCount}
            </div>
          </div>

          <div
            onClick={() => { setActiveTab('scanner'); setFilterMode(filterMode === 'div' ? 'ALL' : 'div'); }}
            className={`cursor-pointer p-4 rounded-xl border transition flex items-start justify-between ${
              filterMode === 'div' ? 'bg-amber-950/40 border-amber-500 ring-1 ring-amber-500' : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
            }`}
          >
            <div>
              <div className="flex items-center space-x-2">
                <span className="w-2.5 h-2.5 rounded-full bg-amber-500"></span>
                <span className="text-xs font-semibold uppercase tracking-wider text-amber-400">ফিল্টার ২: e_divergence</span>
              </div>
              <h3 className="text-sm font-bold text-slate-100 mt-1">সেক্টর/ইনডেক্স ডাইভার্জেন্স</h3>
              <p className="text-xs text-slate-400 mt-0.5">বাজার স্থির কিন্তু শেয়ার একা ৫%+ লাফিয়েছে (VR ≥ ৩.০)</p>
              <div className="mt-2 text-xs font-medium text-amber-300 flex items-center space-x-1">
                <span>ফেক র্যালি সতর্কতা · {divCount} টি শেয়ার</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </div>
            </div>
            <div className="px-2.5 py-1 bg-amber-500/10 border border-amber-500/20 text-amber-400 rounded-lg text-lg font-black font-mono">
              {divCount}
            </div>
          </div>

          <div
            onClick={() => { setActiveTab('scanner'); setFilterMode(filterMode === 'uclow' ? 'ALL' : 'uclow'); }}
            className={`cursor-pointer p-4 rounded-xl border transition flex items-start justify-between ${
              filterMode === 'uclow' ? 'bg-rose-950/40 border-rose-500 ring-1 ring-rose-500' : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
            }`}
          >
            <div>
              <div className="flex items-center space-x-2">
                <span className="w-2.5 h-2.5 rounded-full bg-rose-500"></span>
                <span className="text-xs font-semibold uppercase tracking-wider text-rose-400">ফিল্টার ৩: e_uc_lowvol</span>
              </div>
              <h3 className="text-sm font-bold text-slate-100 mt-1">সার্কিট ব্রেকার + কম ভলিউম</h3>
              <p className="text-xs text-slate-400 mt-0.5">আপার সার্কিট হিট কিন্তু ভলিউম ড্রপ (VR &lt; ১.০ বা vdry &lt; ০.৮)</p>
              <div className="mt-2 text-xs font-medium text-rose-300 flex items-center space-x-1">
                <span>ডাম্প ফাঁদ / প্রফিট বুক করুন · {uclowCount} টি শেয়ার</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </div>
            </div>
            <div className="px-2.5 py-1 bg-rose-500/10 border border-rose-500/20 text-rose-400 rounded-lg text-lg font-black font-mono">
              {uclowCount}
            </div>
          </div>
        </div>

        {/* TAB 1: SCANNER TABLE */}
        {activeTab === 'scanner' && (
          <div className="space-y-4">
            <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl flex flex-wrap items-center justify-between gap-3 text-xs">
              <div className="flex flex-wrap items-center gap-2">
                <div className="relative min-w-[200px]">
                  <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
                  <input
                    type="text"
                    placeholder="কোড বা সেক্টর দিয়ে খুঁজুন..."
                    value={searchQuery}
                    onChange={e => setSearchQuery(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-3 py-2 text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-emerald-500"
                  />
                </div>

                <select
                  value={selectedSector}
                  onChange={e => setSelectedSector(e.target.value)}
                  className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-300 focus:outline-none focus:border-emerald-500"
                >
                  <option value="">সব সেক্টর</option>
                  {sectors.map(sec => (
                    <option key={sec} value={sec}>{sec}</option>
                  ))}
                </select>

                <select
                  value={selectedPhase}
                  onChange={e => setSelectedPhase(e.target.value)}
                  className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-300 focus:outline-none focus:border-emerald-500"
                >
                  <option value="ALL">সব ওয়াইকফ ফেজ</option>
                  <option value="Phase A">Phase A (সেলিং ক্লাইম্যাক্স)</option>
                  <option value="Phase B">Phase B (রেঞ্জ তৈরি)</option>
                  <option value="Phase C">Phase C (স্প্রিং টেস্ট)</option>
                  <option value="Phase D">Phase D (ব্রেকআউট / LPS)</option>
                  <option value="Phase E">Phase E (মার্কআপ)</option>
                  <option value="Re-accumulation">Re-accumulation</option>
                  <option value="Distribution">Distribution</option>
                  <option value="Markdown">Markdown</option>
                  <option value="NONE">অনির্দিষ্ট</option>
                </select>
              </div>

              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-slate-400 mr-1">ফিল্টার:</span>
                <button
                  onClick={() => setFilterMode('ALL')}
                  className={`px-2.5 py-1.5 rounded-lg border transition ${
                    filterMode === 'ALL'
                      ? 'bg-emerald-600 text-white border-emerald-500'
                      : 'bg-slate-950 text-slate-400 border-slate-800 hover:text-slate-200'
                  }`}
                >
                  সব ({data?.stocks?.length || 0})
                </button>
                <button
                  onClick={() => setFilterMode('dryup')}
                  className={`px-2.5 py-1.5 rounded-lg border transition flex items-center space-x-1 ${
                    filterMode === 'dryup'
                      ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500'
                      : 'bg-slate-950 text-slate-400 border-slate-800 hover:text-slate-200'
                  }`}
                >
                  <span>ড্রাই-আপ</span>
                  <span className="font-mono text-[10px] opacity-80">({dryupCount})</span>
                </button>
                <button
                  onClick={() => setFilterMode('div')}
                  className={`px-2.5 py-1.5 rounded-lg border transition flex items-center space-x-1 ${
                    filterMode === 'div'
                      ? 'bg-amber-500/20 text-amber-300 border-amber-500'
                      : 'bg-slate-950 text-slate-400 border-slate-800 hover:text-slate-200'
                  }`}
                >
                  <span>ডাইভার্জেন্স</span>
                  <span className="font-mono text-[10px] opacity-80">({divCount})</span>
                </button>
                <button
                  onClick={() => setFilterMode('uclow')}
                  className={`px-2.5 py-1.5 rounded-lg border transition flex items-center space-x-1 ${
                    filterMode === 'uclow'
                      ? 'bg-rose-500/20 text-rose-300 border-rose-500'
                      : 'bg-slate-950 text-slate-400 border-slate-800 hover:text-slate-200'
                  }`}
                >
                  <span>UC লো-ভল</span>
                  <span className="font-mono text-[10px] opacity-80">({uclowCount})</span>
                </button>
              </div>
            </div>

            <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-x-auto shadow-xl">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-slate-950/80 text-slate-400 border-b border-slate-800 font-medium">
                    <th onClick={() => handleSort('c')} className="p-3 cursor-pointer hover:text-slate-200 whitespace-nowrap">
                      <div className="flex items-center space-x-1">
                        <span>কোড / সেক্টর</span>
                        <ArrowUpDown className="w-3 h-3" />
                      </div>
                    </th>
                    <th onClick={() => handleSort('cl')} className="p-3 cursor-pointer hover:text-slate-200 whitespace-nowrap">
                      <div className="flex items-center space-x-1">
                        <span>দর (LTP)</span>
                        <ArrowUpDown className="w-3 h-3" />
                      </div>
                    </th>
                    <th onClick={() => handleSort('ch')} className="p-3 cursor-pointer hover:text-slate-200 whitespace-nowrap">
                      <div className="flex items-center space-x-1">
                        <span>পরিবর্তন %</span>
                        <ArrowUpDown className="w-3 h-3" />
                      </div>
                    </th>
                    <th onClick={() => handleSort('p')} className="p-3 cursor-pointer hover:text-slate-200 whitespace-nowrap">
                      <div className="flex items-center space-x-1">
                        <span>ওয়াইকফ ফেজ</span>
                        <ArrowUpDown className="w-3 h-3" />
                      </div>
                    </th>
                    <th onClick={() => handleSort('e_dryup')} className="p-3 cursor-pointer hover:text-emerald-300 text-emerald-400 whitespace-nowrap bg-emerald-950/20">
                      <div className="flex items-center space-x-1" title="ভলিউম ড্রাই-আপ + ছোট বডি (অ্যাকুমুলেশন)">
                        <span>ড্রাই-আপ</span>
                        <ArrowUpDown className="w-3 h-3" />
                      </div>
                    </th>
                    <th onClick={() => handleSort('e_divergence')} className="p-3 cursor-pointer hover:text-amber-300 text-amber-400 whitespace-nowrap bg-amber-950/20">
                      <div className="flex items-center space-x-1" title="সেক্টর/ইনডেক্স ডাইভার্জেন্স (পাম্প সতর্কতা)">
                        <span>ডাইভার্জেন্স</span>
                        <ArrowUpDown className="w-3 h-3" />
                      </div>
                    </th>
                    <th onClick={() => handleSort('e_uc_lowvol')} className="p-3 cursor-pointer hover:text-rose-300 text-rose-400 whitespace-nowrap bg-rose-950/20">
                      <div className="flex items-center space-x-1" title="সার্কিট ব্রেকার + কম ভলিউম (ফেক ডিমান্ড ফাঁদ)">
                        <span>UC লো-ভল</span>
                        <ArrowUpDown className="w-3 h-3" />
                      </div>
                    </th>
                    <th onClick={() => handleSort('vr')} className="p-3 cursor-pointer hover:text-slate-200 whitespace-nowrap">
                      <div className="flex items-center space-x-1">
                        <span>ভলিউম &amp; VR</span>
                        <ArrowUpDown className="w-3 h-3" />
                      </div>
                    </th>
                    <th className="p-3 whitespace-nowrap">ট্রেড প্ল্যান &amp; অ্যাকশন</th>
                    <th className="p-3 whitespace-nowrap">৫০ দিন ট্রেন্ড</th>
                    <th onClick={() => handleSort('pu')} className="p-3 cursor-pointer hover:text-slate-200 whitespace-nowrap">
                      <div className="flex items-center space-x-1">
                        <span>মূলধন / PE</span>
                        <ArrowUpDown className="w-3 h-3" />
                      </div>
                    </th>
                    <th className="p-3 text-center whitespace-nowrap">অডিট</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono">
                  {filteredStocks.length === 0 ? (
                    <tr>
                      <td colSpan={12} className="p-8 text-center text-slate-500 font-sans">
                        কোনো স্টক মেলেনি। অনুগ্রহ করে ফিল্টার পরিবর্তন করুন।
                      </td>
                    </tr>
                  ) : (
                    filteredStocks.map(stock => {
                      const isUp = (stock.ch || 0) > 0;
                      const isDown = (stock.ch || 0) < 0;
                      return (
                        <tr key={stock.c} className="hover:bg-slate-800/40 transition">
                          <td className="p-3 font-sans">
                            <div className="flex items-center space-x-2">
                              <span className="font-bold font-mono text-slate-100 text-sm">{stock.c}</span>
                              {stock.cat === 'Z' && (
                                <span className="px-1 text-[10px] bg-rose-900/50 text-rose-400 border border-rose-800 rounded">Z</span>
                              )}
                            </div>
                            <div className="text-[11px] text-slate-400 truncate max-w-[140px]">{stock.s || 'Other'}</div>
                          </td>

                          <td className="p-3 font-bold text-slate-100">
                            ৳{stock.cl != null ? stock.cl.toFixed(1) : '–'}
                          </td>

                          <td className="p-3">
                            <span className={`px-2 py-0.5 rounded font-bold text-xs ${
                              isUp ? 'text-emerald-400 bg-emerald-500/10' : isDown ? 'text-rose-400 bg-rose-500/10' : 'text-slate-400'
                            }`}>
                              {isUp ? '+' : ''}{stock.ch != null ? stock.ch.toFixed(1) + '%' : '0.0%'}
                            </span>
                          </td>

                          <td className="p-3 font-sans">
                            {stock.p ? (
                              <span className={`px-2 py-0.5 rounded text-xs font-semibold inline-block ${
                                stock.p === 'Phase C' ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40' :
                                stock.p === 'Phase D' ? 'bg-blue-500/20 text-blue-300 border border-blue-500/40' :
                                stock.p === 'Phase E' ? 'bg-purple-500/20 text-purple-300 border border-purple-500/40' :
                                stock.p === 'Phase A' ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40' :
                                stock.p === 'Distribution' ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40' :
                                'bg-slate-800 text-slate-300'
                              }`}>
                                {stock.p}
                              </span>
                            ) : (
                              <span className="text-slate-500">–</span>
                            )}
                          </td>

                          <td className="p-3 text-center bg-emerald-950/10">
                            {stock.e_dryup ? (
                              <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-emerald-500/20 text-emerald-400 font-bold text-sm" title="e_dryup: True">
                                ✔
                              </span>
                            ) : (
                              <span className="text-slate-600 text-sm" title="e_dryup: False">✘</span>
                            )}
                          </td>

                          <td className="p-3 text-center bg-amber-950/10">
                            {stock.e_divergence ? (
                              <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-amber-500/20 text-amber-400 font-bold text-sm animate-pulse" title="e_divergence: True">
                                ✔
                              </span>
                            ) : (
                              <span className="text-slate-600 text-sm" title="e_divergence: False">✘</span>
                            )}
                          </td>

                          <td className="p-3 text-center bg-rose-950/10">
                            {stock.e_uc_lowvol ? (
                              <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-rose-500/20 text-rose-400 font-bold text-sm" title="e_uc_lowvol: True">
                                ✔
                              </span>
                            ) : (
                              <span className="text-slate-600 text-sm" title="e_uc_lowvol: False">✘</span>
                            )}
                          </td>

                          <td className="p-3">
                            <div className="font-semibold text-slate-200">
                              {stock.v > 1000000 ? (stock.v / 1000000).toFixed(1) + 'M' : stock.v > 1000 ? (stock.v / 1000).toFixed(0) + 'K' : stock.v}
                            </div>
                            <div className={`text-[11px] ${
                              (stock.vr || 0) >= 2.5 ? 'text-emerald-400 font-bold' : (stock.vr || 0) >= 1.5 ? 'text-amber-400' : 'text-slate-400'
                            }`}>
                              VR {stock.vr != null ? stock.vr.toFixed(1) : '–'}
                            </div>
                          </td>

                          <td className="p-3 font-sans">
                            {stock.e_uc_lowvol ? (
                              <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/40">
                                🚨 ডাম্প ফাঁদ / সেল
                              </span>
                            ) : stock.e_divergence ? (
                              <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40">
                                ⚠️ সতর্ক / নতুন বাই নয়
                              </span>
                            ) : stock.e_dryup ? (
                              <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                                🎯 ড্রাই-আপ ওয়াচলিস্ট
                              </span>
                            ) : stock.ok ? (
                              <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                                {stock.st} (RRR {stock.rr != null ? stock.rr.toFixed(1) : '৩+'})
                              </span>
                            ) : stock.pl ? (
                              <span className="text-slate-300 text-xs">{stock.pl}</span>
                            ) : (
                              <span className="text-slate-500 text-xs">পর্যবেক্ষণ</span>
                            )}
                          </td>

                          <td className="p-3">
                            {renderSparkline(stock.sp, isUp)}
                          </td>

                          <td className="p-3 font-sans">
                            <div className="text-slate-200">{stock.pu ? `${stock.pu.toFixed(0)} কোটি` : '–'}</div>
                            <div className="text-slate-400 text-[11px]">{stock.pe ? `P/E ${stock.pe.toFixed(1)}` : 'P/E –'}</div>
                          </td>

                          <td className="p-3 text-center">
                            <button
                              onClick={() => setSelectedStock(stock)}
                              className="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded border border-slate-700 text-xs font-sans transition"
                            >
                              বিস্তারিত
                            </button>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* TAB 2: FILTERS DETAIL */}
        {activeTab === 'filters' && (
          <div className="space-y-6">
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
              <h2 className="text-lg font-bold text-slate-100 flex items-center space-x-2">
                <Sparkles className="w-5 h-5 text-emerald-400" />
                <span>নতুন ৩টি অপারেটর ফিল্টারের বিবরণ</span>
              </h2>

              <div className="mt-6 overflow-x-auto">
                <table className="w-full text-left text-xs border border-slate-800 rounded-lg overflow-hidden">
                  <thead className="bg-slate-950 text-slate-300 border-b border-slate-800 font-semibold">
                    <tr>
                      <th className="p-3">ফিল্টার নাম</th>
                      <th className="p-3">কী শনাক্ত করে</th>
                      <th className="p-3">অপারেটরের ধাপ</th>
                      <th className="p-3">ট্রেডারের করণীয়</th>
                      <th className="p-3 text-center">বর্তমান স্টক সংখ্যা</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 font-sans">
                    <tr className="bg-emerald-950/20">
                      <td className="p-3 font-mono font-bold text-emerald-400">e_dryup</td>
                      <td className="p-3 text-slate-200">ভলিউম শুকিয়ে আসা + দাম স্থির (ছোট বডি ও সংকুচিত ATR)</td>
                      <td className="p-3 text-emerald-300">অ্যাকুমুলেশন (Phase A/B)</td>
                      <td className="p-3 text-emerald-300 font-medium">ওয়াচলিস্টে রাখুন, এখনো কিনবেন না (স্প্রিং টেস্টের অপেক্ষা)</td>
                      <td className="p-3 text-center font-mono font-bold text-emerald-400">{dryupCount} টি</td>
                    </tr>
                    <tr className="bg-amber-950/20">
                      <td className="p-3 font-mono font-bold text-amber-400">e_divergence</td>
                      <td className="p-3 text-slate-200">শেয়ার একা লাফাচ্ছে (≥ ৫%), কিন্তু বাজার ও সেক্টর স্থির (≤ ১%)</td>
                      <td className="p-3 text-amber-300">ফেক র্যালি / কৃত্রিম পাম্পের শুরু</td>
                      <td className="p-3 text-amber-300 font-medium">নতুন এন্ট্রি নয়, অত্যন্ত সতর্ক হোন (FOMO এড়িয়ে চলুন)</td>
                      <td className="p-3 text-center font-mono font-bold text-amber-400">{divCount} টি</td>
                    </tr>
                    <tr className="bg-rose-950/20">
                      <td className="p-3 font-mono font-bold text-rose-400">e_uc_lowvol</td>
                      <td className="p-3 text-slate-200">সার্কিট হিট করেছে (≥ ৯.৫%) অথচ ভলিউম গড়ের নিচে (VR &lt; ১.০)</td>
                      <td className="p-3 text-rose-300">ডিস্ট্রিবিউশন / ডাম্পের ফাঁদ</td>
                      <td className="p-3 text-rose-300 font-bold">পুরো পজিশন বিক্রি করুন / প্রফিট বুক করে প্রস্থান করুন</td>
                      <td className="p-3 text-center font-mono font-bold text-rose-400">{uclowCount} টি</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: CONFIG */}
        {activeTab === 'config' && (
          <div className="space-y-6">
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
              <h2 className="text-lg font-bold text-slate-100 flex items-center space-x-2">
                <Sliders className="w-5 h-5 text-purple-400" />
                <span>Cfg ডেটাক্লাস ও প্যারামিটার কনফিগারেশন</span>
              </h2>
              <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-slate-950 border border-slate-800 rounded-xl p-4">
                  <h3 className="text-sm font-bold text-emerald-400 mb-3">নতুন ৫টি প্যারামিটার (e_dryup)</h3>
                  <div className="space-y-2 font-mono text-xs">
                    <div className="flex justify-between p-2 bg-slate-900/50 rounded">
                      <span className="text-slate-400">dryup_win:</span>
                      <span className="text-slate-100 font-bold">5 (দিন)</span>
                    </div>
                    <div className="flex justify-between p-2 bg-slate-900/50 rounded">
                      <span className="text-slate-400">dryup_min_days:</span>
                      <span className="text-slate-100 font-bold">3 (দিন)</span>
                    </div>
                    <div className="flex justify-between p-2 bg-slate-900/50 rounded">
                      <span className="text-slate-400">dryup_vdry_max:</span>
                      <span className="text-slate-100 font-bold">0.75</span>
                    </div>
                    <div className="flex justify-between p-2 bg-slate-900/50 rounded">
                      <span className="text-slate-400">dryup_body_atr_max:</span>
                      <span className="text-slate-100 font-bold">0.5</span>
                    </div>
                    <div className="flex justify-between p-2 bg-slate-900/50 rounded">
                      <span className="text-slate-400">dryup_atr_ratio_max:</span>
                      <span className="text-slate-100 font-bold">0.85</span>
                    </div>
                  </div>
                </div>

                <div className="bg-slate-950 border border-slate-800 rounded-xl p-4">
                  <h3 className="text-sm font-bold text-amber-400 mb-3">নতুন ৩টি প্যারামিটার (e_divergence)</h3>
                  <div className="space-y-2 font-mono text-xs">
                    <div className="flex justify-between p-2 bg-slate-900/50 rounded">
                      <span className="text-slate-400">div_chg_min:</span>
                      <span className="text-slate-100 font-bold">5.0%</span>
                    </div>
                    <div className="flex justify-between p-2 bg-slate-900/50 rounded">
                      <span className="text-slate-400">div_index_chg_max:</span>
                      <span className="text-slate-100 font-bold">1.0%</span>
                    </div>
                    <div className="flex justify-between p-2 bg-slate-900/50 rounded">
                      <span className="text-slate-400">div_vr_min:</span>
                      <span className="text-slate-100 font-bold">3.0</span>
                    </div>
                  </div>

                  <h3 className="text-sm font-bold text-rose-400 mt-4 mb-3">নতুন ২টি প্যারামিটার (e_uc_lowvol)</h3>
                  <div className="space-y-2 font-mono text-xs">
                    <div className="flex justify-between p-2 bg-slate-900/50 rounded">
                      <span className="text-slate-400">uc_lowvol_vr_max:</span>
                      <span className="text-slate-100 font-bold">1.0</span>
                    </div>
                    <div className="flex justify-between p-2 bg-slate-900/50 rounded">
                      <span className="text-slate-400">uc_lowvol_vdry_max:</span>
                      <span className="text-slate-100 font-bold">0.8</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 4: CLASSIC HTML */}
        {activeTab === 'classic' && (
          <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-2xl">
            <div className="p-3 bg-slate-950 border-b border-slate-800 flex items-center justify-between text-xs">
              <span className="text-slate-400">প্রিভিউ: <code className="text-slate-200">docs/index.html</code> (৩টি নতুন কলামসহ আসল এইচটিএমএল ড্যাশবোর্ড)</span>
              <a
                href="/docs/index.html"
                target="_blank"
                rel="noreferrer"
                className="flex items-center space-x-1 text-emerald-400 hover:text-emerald-300 font-medium"
              >
                <span>নতুন ট্যাবে খুলুন</span>
                <ExternalLink className="w-3.5 h-3.5" />
              </a>
            </div>
            <iframe
              src="/docs/index.html"
              title="Classic DSE Scanner Dashboard"
              className="w-full h-[800px] border-none bg-white"
            />
          </div>
        )}
      </main>

      {/* Stock Details Modal */}
      {selectedStock && (
        <div
          onClick={() => setSelectedStock(null)}
          className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4"
        >
          <div
            onClick={e => e.stopPropagation()}
            className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4"
          >
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <div className="flex items-center space-x-2">
                  <h2 className="text-xl font-bold font-mono text-slate-100">{selectedStock.c}</h2>
                  <span className="px-2 py-0.5 rounded text-xs font-semibold bg-slate-800 text-slate-300">
                    {selectedStock.s || 'Other'}
                  </span>
                </div>
                <div className="text-xs text-slate-400 mt-0.5">LTP: ৳{selectedStock.cl} ({selectedStock.ch > 0 ? '+' : ''}{selectedStock.ch}%)</div>
              </div>
              <button
                onClick={() => setSelectedStock(null)}
                className="w-8 h-8 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 flex items-center justify-center"
              >
                ✕
              </button>
            </div>

            <div className="space-y-2">
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">৩টি নতুন ফিল্টারের স্ট্যাটাস:</h4>
              <div className="grid grid-cols-3 gap-2 font-mono text-xs">
                <div className={`p-2.5 rounded-lg border flex flex-col items-center justify-center ${
                  selectedStock.e_dryup ? 'bg-emerald-950/40 border-emerald-500 text-emerald-300' : 'bg-slate-950 border-slate-800 text-slate-500'
                }`}>
                  <span className="font-bold">e_dryup</span>
                  <span className="text-base mt-1 font-bold">{selectedStock.e_dryup ? '✔ True' : '✘ False'}</span>
                </div>
                <div className={`p-2.5 rounded-lg border flex flex-col items-center justify-center ${
                  selectedStock.e_divergence ? 'bg-amber-950/40 border-amber-500 text-amber-300' : 'bg-slate-950 border-slate-800 text-slate-500'
                }`}>
                  <span className="font-bold">e_divergence</span>
                  <span className="text-base mt-1 font-bold">{selectedStock.e_divergence ? '✔ True' : '✘ False'}</span>
                </div>
                <div className={`p-2.5 rounded-lg border flex flex-col items-center justify-center ${
                  selectedStock.e_uc_lowvol ? 'bg-rose-950/40 border-rose-500 text-rose-300' : 'bg-slate-950 border-slate-800 text-slate-500'
                }`}>
                  <span className="font-bold">e_uc_lowvol</span>
                  <span className="text-base mt-1 font-bold">{selectedStock.e_uc_lowvol ? '✔ True' : '✘ False'}</span>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs font-mono">
              <div className="p-2.5 bg-slate-950 rounded-lg border border-slate-800">
                <span className="text-slate-400">ওয়াইকফ ফেজ:</span> <b className="text-slate-200">{selectedStock.p || 'অনির্দিষ্ট'}</b>
              </div>
              <div className="p-2.5 bg-slate-950 rounded-lg border border-slate-800">
                <span className="text-slate-400">ভলিউম রেশিও (VR):</span> <b className="text-slate-200">{selectedStock.vr != null ? selectedStock.vr.toFixed(2) : '–'}</b>
              </div>
              <div className="p-2.5 bg-slate-950 rounded-lg border border-slate-800">
                <span className="text-slate-400">স্টপ-লস (SL):</span> <b className="text-rose-400">{selectedStock.sl != null ? `৳${selectedStock.sl}` : '–'}</b>
              </div>
              <div className="p-2.5 bg-slate-950 rounded-lg border border-slate-800">
                <span className="text-slate-400">টার্গেট (TP):</span> <b className="text-emerald-400">{selectedStock.tg != null ? `৳${selectedStock.tg}` : '–'}</b>
              </div>
            </div>

            <div className="pt-2 border-t border-slate-800 flex justify-end">
              <button
                onClick={() => setSelectedStock(null)}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold transition"
              >
                বন্ধ করুন
              </button>
            </div>
          </div>
        </div>
      )}

      <footer className="border-t border-slate-900 bg-slate-950 py-4 text-center text-xs text-slate-500">
        ডিএসই সিম্পল স্ক্যানার — ঢাকা স্টক এক্সচেঞ্জ ওয়াইকফ ফেজ &amp; স্মার্ট মানি ইঞ্জিন
      </footer>
    </div>
  );
}
