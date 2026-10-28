import { riskLevelOf, type TelemetryEvent } from '../api';
import { Shield, ShieldAlert, ShieldBan, ShieldCheck, Activity, SlidersHorizontal, Lock } from 'lucide-react';
import clsx from 'clsx';
import { RiskTimeline } from './RiskTimeline';

interface SecurityPanelProps {
  telemetry: TelemetryEvent | null;
  history: TelemetryEvent[];
}

export function SecurityPanel({ telemetry, history }: SecurityPanelProps) {
  if (!telemetry) {
    return (
      <div className="h-full bg-slate-950 text-slate-400 flex flex-col items-center justify-center p-8">
        <div className="w-20 h-20 bg-slate-900 rounded-lg flex items-center justify-center mb-6 border border-slate-800">
          <Shield className="w-10 h-10 text-slate-500" />
        </div>
        <h3 className="text-sm font-bold uppercase tracking-widest text-slate-50 mb-2">Telemetry Standby</h3>
        <p className="text-center text-xs font-mono max-w-xs leading-relaxed">
          Ask a question and your risk score, the behaviour signals behind it and the policy applied will show up here.
        </p>
      </div>
    );
  }

  const { instantaneous_risk, smoothed_risk, signals, policy, blocked_by_policy, intent, retrieval_strategy, result_count } = telemetry;
  
  const riskLevel = policy?.risk_level || riskLevelOf(smoothed_risk);
  
  const getRiskColor = (level: string) => {
    switch(level) {
      case 'LOW': return 'text-green-500';
      case 'MEDIUM': return 'text-amber-500';
      case 'HIGH': 
      case 'CRITICAL': return 'text-red-500';
      default: return 'text-slate-400';
    }
  };

  const getRiskBg = (level: string) => {
    switch(level) {
      case 'LOW': return 'bg-green-950/20 border-green-900/30';
      case 'MEDIUM': return 'bg-amber-950/20 border-amber-900/30';
      case 'HIGH':
      case 'CRITICAL': return 'bg-red-950/20 border-red-900/30';
      default: return 'bg-slate-900 border-slate-800';
    }
  };

  const getRiskIcon = (level: string) => {
    switch(level) {
      case 'LOW': return <ShieldCheck className="w-6 h-6 text-green-500" />;
      case 'MEDIUM': return <ShieldAlert className="w-6 h-6 text-amber-500" />;
      case 'HIGH':
      case 'CRITICAL': return <ShieldBan className="w-6 h-6 text-red-500" />;
      default: return <Shield className="w-6 h-6 text-slate-500" />;
    }
  };

  return (
    <div className="h-full bg-slate-950 text-slate-50 overflow-y-auto custom-scrollbar">
      
      {/* Header Status */}
      <div className="p-6 border-b border-slate-800 bg-slate-950/90 sticky top-0 z-10 backdrop-blur-md">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-2">
            <Activity className="w-4 h-4 text-blue-500" />
            <h2 className="text-sm font-bold tracking-widest uppercase text-slate-50">Live Telemetry</h2>
          </div>
          <span className="text-xs text-slate-500 font-mono uppercase tracking-widest bg-slate-900 rounded-sm px-2 py-1 border border-slate-800">
            ID: {telemetry.session_id.split('-')[0]}
          </span>
        </div>

        {/* 1. Current Risk State - High Visibility Hero Card */}
        <div className={clsx("flex items-center justify-between p-4 border rounded-lg transition-colors", getRiskBg(riskLevel))}>
          <div className="flex items-center space-x-4">
            <div className="bg-slate-950 p-2 rounded-md border border-slate-800">
              {getRiskIcon(riskLevel)}
            </div>
            <div>
              <div className="text-xs text-slate-500 uppercase font-mono tracking-widest mb-1">System Risk Level</div>
              <div className={clsx("text-2xl font-bold tracking-widest uppercase leading-none", getRiskColor(riskLevel))}>
                {riskLevel}
              </div>
            </div>
          </div>
          <div className="text-right">
            <div className="text-xs text-slate-500 uppercase font-mono tracking-widest mb-1">EWMA Score</div>
            <div className="text-xl font-mono text-slate-50 leading-none">{smoothed_risk.toFixed(3)}</div>
          </div>
        </div>
      </div>

      <div className="p-6 space-y-8">
        
        {/* 2. Adaptive Policy (Actionable constraint block) */}
        <section>
          <div className="flex items-center space-x-2 mb-4">
            <Lock className="w-3 h-3 text-slate-500" />
            <h3 className="text-xs font-mono font-bold uppercase tracking-widest text-slate-400">Policy Enforcement</h3>
          </div>
          
          <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
            {blocked_by_policy ? (
              <div className="bg-red-950/30 border-b border-red-900/50 text-red-500 p-3 text-xs font-mono uppercase tracking-widest flex items-center justify-center">
                <ShieldBan className="w-4 h-4 mr-2" />
                RETRIEVAL BLOCKED BY POLICY
              </div>
            ) : (
              <div className="bg-green-950/30 border-b border-green-900/50 text-green-500 p-3 text-xs font-mono uppercase tracking-widest flex items-center justify-center">
                <ShieldCheck className="w-4 h-4 mr-2" />
                RETRIEVAL PERMITTED
              </div>
            )}
            
            <div className="grid grid-cols-3 divide-x divide-slate-800">
              <div className="p-4 text-center">
                <div className="text-xl font-mono text-slate-50 mb-1">
                  {policy?.attenuation_factor?.toFixed(2) || '1.00'}
                </div>
                <div className="text-xs text-slate-500 font-mono uppercase tracking-widest">Attenuation</div>
              </div>
              <div className="p-4 text-center">
                <div className="text-xl font-mono text-slate-50 mb-1">
                  {policy?.effective_context_limit ?? 20}
                </div>
                <div className="text-xs text-slate-500 font-mono uppercase tracking-widest">Max Records</div>
              </div>
              <div className="p-4 text-center">
                <div className="text-xl font-mono text-slate-50 mb-1">
                  {policy?.effective_graph_depth ?? 5}
                </div>
                <div className="text-xs text-slate-500 font-mono uppercase tracking-widest">Max Depth</div>
              </div>
            </div>
            <div className="bg-slate-950 p-3 border-t border-slate-800 flex justify-between text-xs font-mono uppercase tracking-wider text-slate-500">
              <span>Intent: {intent}</span>
              <span>Strategy: {retrieval_strategy}</span>
              <span>Records Found: {result_count}</span>
            </div>
          </div>
        </section>

        {/* 3. Risk Progression Timeline */}
        <section>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-2">
              <Activity className="w-3 h-3 text-slate-500" />
              <h3 className="text-xs font-mono font-bold uppercase tracking-widest text-slate-400">Risk Timeline</h3>
            </div>
            <span className="text-xs text-slate-500 font-mono uppercase tracking-widest">queries: {history.length}</span>
          </div>
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 pt-6">
            <RiskTimeline history={history} />
          </div>
        </section>

        {/* 4. Behavioral Signals */}
        <section>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-2">
              <SlidersHorizontal className="w-3 h-3 text-slate-500" />
              <h3 className="text-xs font-mono font-bold uppercase tracking-widest text-slate-400">Behavioral Signals</h3>
            </div>
            <span className="text-xs text-slate-500 font-mono uppercase tracking-widest">Inst. Risk: {instantaneous_risk.toFixed(3)}</span>
          </div>
          
          <div className="space-y-5 bg-slate-900 border border-slate-800 rounded-lg p-5">
            {[
              { label: "Semantic Focus", symbol: "S_sem", value: signals.semantic_focus, color: "bg-blue-500" },
              { label: "Temporal Frequency", symbol: "S_temp", value: signals.temporal_frequency, color: "bg-blue-500" },
              { label: "Entity Focus", symbol: "S_ent", value: signals.entity_focus, color: "bg-blue-500" },
              { label: "Graph Footprint", symbol: "S_graph", value: signals.graph_footprint, color: "bg-blue-500" },
              { label: "Sensitivity Exposure", symbol: "S_sens", value: signals.sensitivity_exposure ?? 0, color: "bg-blue-500" },
            ].map((sig) => (
              <div key={sig.symbol}>
                <div className="flex justify-between items-end mb-2">
                  <div>
                    <span className="text-xs font-medium text-slate-50">{sig.label}</span>
                    <span className="ml-2 text-xs text-slate-500 font-mono uppercase">({sig.symbol})</span>
                  </div>
                  <span className="text-xs font-mono text-slate-400">{sig.value.toFixed(3)}</span>
                </div>
                <div className="h-1 w-full bg-slate-800 rounded-full overflow-hidden">
                  <div 
                    className={clsx("h-full transition-all duration-500", sig.color)} 
                    style={{ width: `${Math.min(sig.value * 100, 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </section>

      </div>
    </div>
  );
}
