import { RISK_BANDS, type TelemetryEvent } from '../api';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';

interface RiskTimelineProps {
  history: TelemetryEvent[];
}

// Defined outside the component so Recharts doesn't remount it every render.
const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    const dataPoint = payload[0].payload;
    return (
      <div className="bg-slate-900 border border-slate-800 p-3 rounded-lg shadow-md text-xs font-mono uppercase tracking-widest text-slate-400">
        <p className="font-bold text-slate-50 mb-2 border-b border-slate-800 pb-1">{label}</p>
        <p className="text-amber-500 mb-1">EWMA Risk: {dataPoint.ewmaRisk}</p>
        <p className="text-blue-500">Instant Risk: {dataPoint.instantRisk}</p>
        {dataPoint.blocked && <p className="text-red-500 mt-2 font-bold bg-red-950/30 px-1 py-0.5 border border-red-900/50 inline-block rounded-sm">BLOCKED</p>}
      </div>
    );
  }
  return null;
};

export function RiskTimeline({ history }: RiskTimelineProps) {
  if (!history || history.length === 0) {
    return (
      <div className="h-48 w-full flex items-center justify-center text-slate-500 text-xs font-mono uppercase tracking-widest border border-slate-800 bg-slate-950 rounded-lg">
        No telemetry history available
      </div>
    );
  }

  // Format data for Recharts
  const data = history.map((event, index) => ({
    query: `Q${index + 1}`,
    ewmaRisk: Number(event.smoothed_risk.toFixed(4)),
    instantRisk: Number(event.instantaneous_risk.toFixed(4)),
    blocked: event.blocked_by_policy,
  }));


  return (
    <div className="h-56 w-full mt-4">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
          <XAxis 
            dataKey="query" 
            stroke="#64748b" 
            fontSize={10} 
            fontFamily='"IBM Plex Mono", monospace'
            tickMargin={8} 
            axisLine={false} 
            tickLine={false}
          />
          <YAxis 
            domain={[0, 1]} 
            stroke="#64748b" 
            fontSize={10} 
            fontFamily='"IBM Plex Mono", monospace'
            tickFormatter={(val) => val.toFixed(1)} 
            axisLine={false} 
            tickLine={false}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ stroke: '#1e293b', strokeWidth: 1, strokeDasharray: '4 4' }} />
          
          {/* Policy bands: MASK from 0.35, BLOCK from 0.65 */}
          <ReferenceLine y={RISK_BANDS.medium} stroke="#f59e0b" strokeOpacity={0.5} strokeDasharray="3 3" />
          <ReferenceLine y={RISK_BANDS.high} stroke="#ef4444" strokeOpacity={0.5} strokeDasharray="3 3" />
          
          <Line 
            type="monotone" 
            dataKey="ewmaRisk" 
            stroke="#f59e0b" 
            strokeWidth={2} 
            dot={{ r: 3, strokeWidth: 1, fill: '#020617', stroke: '#f59e0b' }} 
            activeDot={{ r: 5, fill: '#f59e0b', stroke: '#020617', strokeWidth: 2 }} 
          />
          <Line 
            type="monotone" 
            dataKey="instantRisk" 
            stroke="#3b82f6" 
            strokeWidth={1} 
            strokeDasharray="4 4"
            dot={false}
            activeDot={{ r: 3, fill: '#3b82f6', stroke: '#020617', strokeWidth: 1 }} 
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
